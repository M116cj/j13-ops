"""Arena 13 — Downstream Truth Feedback Controller.

Converts A3/A4/A5 outcome data into soft guidance for Arena 1 discovery.
Does NOT evolve, mutate, or re-inject candidates. Produces a guidance file
that A1 reads periodically to adjust indicator weights and period preferences.

Guidance is soft (weights, not blocks), bounded (0.3x-3.0x), and diversity-preserving
(random exploration never drops below DIVERSITY_FLOOR).

Runs as a background service, updating guidance every REFRESH_INTERVAL_S seconds.
"""
import sys, os, asyncio, signal, time, json, math
sys.path.insert(0, '/home/j13/j13-ops')
os.chdir('/home/j13/j13-ops')

import numpy as np
from zangetsu.services.pidlock import acquire_lock

from zangetsu.config.settings import Settings
from zangetsu.engine.components.logger import StructuredLogger

REFRESH_INTERVAL_S = 300  # Update guidance every 5 minutes
GUIDANCE_PATH = "/home/j13/j13-ops/zangetsu/config/a13_guidance.json"
GATING_PATH = "/home/j13/j13-ops/zangetsu/config/a13_gating.json"

def load_gating_policy():
    try:
        with open(GATING_PATH) as f:
            return json.load(f)
    except Exception:
        return {"min_survivors_for_soft": 3, "min_failures_for_soft": 5,
                "min_survivors_for_active": 20, "min_failures_for_active": 50,
                "soft_exit_below_survivors": 1, "active_exit_below_survivors": 12}

def determine_mode(n_survivors, n_failures, gating, previous_mode="observe"):
    """V9 (2026-04-17): hysteresis-aware mode transition.

    Standard entry thresholds apply when going UP (observe → soft → active).
    Exit thresholds (lower) apply when going DOWN to prevent thrash near boundary.
    """
    soft_in = gating.get("min_survivors_for_soft", 3)
    soft_in_fail = gating.get("min_failures_for_soft", 5)
    active_in = gating.get("min_survivors_for_active", 20)
    active_in_fail = gating.get("min_failures_for_active", 50)
    soft_exit = gating.get("soft_exit_below_survivors", 1)
    active_exit = gating.get("active_exit_below_survivors", 12)

    # Currently active → only drop if survivors fall below active_exit
    if previous_mode == "active":
        if n_survivors < active_exit:
            # Drop one level: active → soft (if still meets soft entry, else observe)
            if n_survivors >= soft_in and n_failures >= soft_in_fail:
                return "soft"
            return "observe"
        return "active"

    # Currently soft → only drop to observe if survivors fall below soft_exit
    if previous_mode == "soft":
        if n_survivors >= active_in and n_failures >= active_in_fail:
            return "active"
        if n_survivors < soft_exit:
            return "observe"
        return "soft"

    # Currently observe → standard upgrade thresholds
    if n_survivors >= active_in and n_failures >= active_in_fail:
        return "active"
    if n_survivors >= soft_in and n_failures >= soft_in_fail:
        return "soft"
    return "observe"


def load_previous_mode():
    """Read mode from existing guidance.json for hysteresis logic."""
    try:
        with open(GUIDANCE_PATH) as f:
            return json.load(f).get("mode", "observe")
    except Exception:
        return "observe"

# Bounds: guidance weights are clamped to prevent overfit or collapse
WEIGHT_FLOOR = 0.5
WEIGHT_CEIL = 2.0
DIVERSITY_FLOOR = 0.30  # A1 random exploration never drops below this
COOL_OFF_HOURS = 6      # How long a repeatedly-failed combo stays on cool-off

# Base indicator weights (same as A1 defaults — guidance adjusts these)
BASE_WEIGHTS = {
    "tsi": 2.0, "macd": 2.0, "zscore": 1.8, "ppo": 1.8,
    "cci": 1.5, "trix": 1.5, "cmo": 1.2, "roc": 1.2,
    "rsi": 1.0, "stochastic_k": 1.0, "obv": 1.0, "mfi": 1.2, "vwap": 1.0,
}

ALL_INDICATORS = list(BASE_WEIGHTS.keys())
ALL_PERIODS = [7, 14, 20, 30, 48, 50, 100, 200]


async def compute_guidance(db, log):
    """Extract downstream truth and compute guidance weights."""
    # V9: load gating early so failure-noise guard can use bootstrap thresholds
    gating = load_gating_policy()

    # ── 1. Survivor analysis: what indicators/periods appear in successful champions? ──
    survivors = await db.fetch("""
        SELECT id, status, passport->'arena1'->'configs' as configs
        FROM champion_pipeline
        WHERE status IN ('CANDIDATE', 'DEPLOYABLE')
          AND passport->'arena1'->'configs' IS NOT NULL
    """)

    survivor_ind_count = {}   # indicator_name -> count in survivors
    survivor_period_count = {} # (indicator_name, period) -> count in survivors
    for row in survivors:
        try:
            configs = json.loads(row["configs"]) if isinstance(row["configs"], str) else row["configs"]
            for cfg in configs:
                name = cfg.get("name", "")
                period = cfg.get("period", 14)
                survivor_ind_count[name] = survivor_ind_count.get(name, 0) + 1
                key = f"{name}_{period}"
                survivor_period_count[key] = survivor_period_count.get(key, 0) + 1
        except (json.JSONDecodeError, TypeError):
            continue

    # ── 2. Failure analysis: what indicators appear in A4-eliminated champions? ──
    failures = await db.fetch("""
        SELECT id, passport->'arena1'->'configs' as configs
        FROM champion_pipeline
        WHERE status = 'ARENA4_ELIMINATED'
          AND engine_hash = 'zv9'
          AND passport->'arena1'->'configs' IS NOT NULL
    """)

    failure_ind_count = {}
    for row in failures:
        try:
            configs = json.loads(row["configs"]) if isinstance(row["configs"], str) else row["configs"]
            for cfg in configs:
                name = cfg.get("name", "")
                failure_ind_count[name] = failure_ind_count.get(name, 0) + 1
        except (json.JSONDecodeError, TypeError):
            continue

    # ── 3. Compute indicator quality scores ──
    # Score = (survivor_count + 1) / (failure_count + 1) — Laplace smoothing
    indicator_scores = {}
    for ind in ALL_INDICATORS:
        s = survivor_ind_count.get(ind, 0)
        f = failure_ind_count.get(ind, 0)
        score = (s + 1) / (f + 1)
        indicator_scores[ind] = score

    # V9 FIX: Skip weight calc when survivors < gating threshold (avoid failure-only noise)
    survivor_total = sum(survivor_ind_count.values())
    MIN_SURVIVORS_FOR_WEIGHTS = gating.get('min_survivors_for_soft', 3)  # V9: matches gating bootstrap threshold
    if survivor_total < MIN_SURVIVORS_FOR_WEIGHTS:
        log.info(f"A13: only {survivor_total} survivor indicator-uses, using BASE_WEIGHTS (need {MIN_SURVIVORS_FOR_WEIGHTS})") if log else None
        guided_weights = dict(BASE_WEIGHTS)
    else:
        # Normalize scores to weights: map score range to [WEIGHT_FLOOR, WEIGHT_CEIL]
        scores = list(indicator_scores.values())
        if max(scores) > min(scores):
            s_min, s_max = min(scores), max(scores)
            guided_weights = {}
            for ind, score in indicator_scores.items():
                normalized = (score - s_min) / (s_max - s_min)  # 0-1
                weight = WEIGHT_FLOOR + normalized * (WEIGHT_CEIL - WEIGHT_FLOOR)
                # Blend with base weight: 60% guidance, 40% base (prevents drift)
                blended = 0.3 * weight + 0.7 * BASE_WEIGHTS.get(ind, 1.0)
                guided_weights[ind] = round(max(WEIGHT_FLOOR, min(WEIGHT_CEIL, blended)), 3)
        else:
            guided_weights = dict(BASE_WEIGHTS)

    # ── 4. Period preferences from survivors ──
    period_preferences = {}
    for ind in ALL_INDICATORS:
        ind_periods = {}
        for period in ALL_PERIODS:
            key = f"{ind}_{period}"
            ind_periods[period] = survivor_period_count.get(key, 0)
        # Only include if there's signal (at least 1 survivor used this indicator)
        if sum(ind_periods.values()) > 0:
            # Sort by count, take top 3
            sorted_periods = sorted(ind_periods.items(), key=lambda x: -x[1])
            period_preferences[ind] = [p for p, c in sorted_periods[:3] if c > 0]

    # ── 5. Cool-off list: config_hashes that failed A4 recently ──
    cool_off_rows = await db.fetch(f"""
        SELECT DISTINCT passport->'arena1'->>'config_hash' as ch, regime
        FROM champion_pipeline
        WHERE status = 'ARENA4_ELIMINATED'
          AND engine_hash = 'zv9'
          AND updated_at > NOW() - INTERVAL '{COOL_OFF_HOURS} hours'
          AND passport->'arena1'->>'config_hash' IS NOT NULL
    """)
    cool_off = [f"{r['regime']}|{r['ch']}" for r in cool_off_rows if r["ch"]]

    # ── 6. Regime-specific indicator boosts ──
    regime_rows = await db.fetch("""
        SELECT regime,
          jsonb_array_elements(passport->'arena1'->'configs')->>'name' as ind_name,
          count(*) as cnt
        FROM champion_pipeline
        WHERE status IN ('CANDIDATE', 'DEPLOYABLE')
          AND passport->'arena1'->'configs' IS NOT NULL
        GROUP BY 1, 2
    """)
    regime_boosts = {}
    for row in regime_rows:
        regime = row["regime"]
        ind = row["ind_name"]
        cnt = row["cnt"]
        if regime not in regime_boosts:
            regime_boosts[regime] = {}
        # Boost = 1.0 + 0.3 per survivor occurrence (capped at 2.0)
        regime_boosts[regime][ind] = round(min(1.0 + 0.3 * cnt, 2.0), 2)

    # ── 7. A3 training insight: what TP/ATR combos survive A4? ──
    tp_rows = await db.fetch("""
        SELECT
          passport->'arena3'->>'best_tp_strategy' as tp,
          passport->'arena3'->>'tp_param' as tp_p,
          status,
          count(*) as cnt
        FROM champion_pipeline
        WHERE engine_hash = 'zv9' AND arena3_sharpe IS NOT NULL
        GROUP BY 1, 2, 3
    """)
    tp_survival = {}
    for row in tp_rows:
        key = f"{row['tp']}_{row['tp_p']}"
        if key not in tp_survival:
            tp_survival[key] = {"survived": 0, "failed": 0}
        if row["status"] in ("CANDIDATE", "DEPLOYABLE"):
            tp_survival[key]["survived"] += row["cnt"]
        else:
            tp_survival[key]["failed"] += row["cnt"]

    previous_mode = load_previous_mode()
    mode = determine_mode(len(survivors), len(failures), gating, previous_mode)

    # ── 8. Assemble guidance ──
    guidance = {
        "version": 3,
        "mode": mode,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "indicator_weights": guided_weights,
        "period_preferences": period_preferences,
        "cool_off_hashes": cool_off,
        "regime_boosts": regime_boosts,
        "diversity_floor": DIVERSITY_FLOOR,
        "tp_survival": tp_survival,
        "meta": {
            "mode": mode,
            "gating": gating,
            "survivors_analyzed": len(survivors),
            "failures_analyzed": len(failures),
            "cool_off_count": len(cool_off),
            "indicator_scores": {k: round(v, 3) for k, v in indicator_scores.items()},
        },
    }

    return guidance


async def main():
    settings = Settings()
    log = StructuredLogger("arena13_feedback", settings.log_level, settings.log_file, settings.log_rotation_mb)
    log.info("Arena 13 Feedback Controller starting")

    import asyncpg
    db = await asyncpg.connect(
        host=settings.db_host, port=settings.db_port,
        database='zangetsu', user=settings.db_user,
        password=settings.db_password,
    )
    log.info("DB connected")

    running = True
    def handle_sig(s, f):
        nonlocal running
        running = False
        log.info(f"Shutdown signal received ({s})")
    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    # V9 SINGLE-SHOT: compute once, write, exit (triggered by systemd timer every 1h)
    try:
        guidance = await compute_guidance(db, log)

        # Write atomically (write to tmp, rename)
        tmp_path = GUIDANCE_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(guidance, f, indent=2)
        os.replace(tmp_path, GUIDANCE_PATH)

        meta = guidance["meta"]
        weights = guidance["indicator_weights"]
        top3 = sorted(weights.items(), key=lambda x: -x[1])[:3]
        bot3 = sorted(weights.items(), key=lambda x: x[1])[:3]

        log.info(
            f"A13 guidance MODE={guidance.get('mode','?')} | survivors={meta['survivors_analyzed']} "
            f"failures={meta['failures_analyzed']} cool_off={meta['cool_off_count']} | "
            f"top: {', '.join(f'{k}={v}' for k,v in top3)} | "
            f"bot: {', '.join(f'{k}={v}' for k,v in bot3)}"
        )

    except Exception as e:
        log.error(f"A13 guidance computation failed: {e}")
        await db.close()
        sys.exit(1)

    await db.close()
    log.info("Arena 13 Feedback complete (single-shot)")


if __name__ == "__main__":
    acquire_lock("arena13_feedback")
    asyncio.run(main())
