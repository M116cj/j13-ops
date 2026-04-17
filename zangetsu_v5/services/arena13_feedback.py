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
from zangetsu_v5.services.pidlock import acquire_lock
acquire_lock("arena13_feedback")

from zangetsu_v5.config.settings import Settings
from zangetsu_v5.engine.components.logger import StructuredLogger

REFRESH_INTERVAL_S = 300  # Update guidance every 5 minutes
GUIDANCE_PATH = "/home/j13/j13-ops/zangetsu_v5/config/a13_guidance.json"
GATING_PATH = "/home/j13/j13-ops/zangetsu_v5/config/a13_gating.json"

def load_gating_policy():
    try:
        with open(GATING_PATH) as f:
            return json.load(f)
    except Exception:
        return {"min_survivors_for_soft": 20, "min_failures_for_soft": 50,
                "min_survivors_for_active": 50, "min_failures_for_active": 100}

def determine_mode(n_survivors, n_failures, gating):
    if n_survivors >= gating.get("min_survivors_for_active", 50) and n_failures >= gating.get("min_failures_for_active", 100):
        return "active"
    if n_survivors >= gating.get("min_survivors_for_soft", 20) and n_failures >= gating.get("min_failures_for_soft", 50):
        return "soft"
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

    gating = load_gating_policy()
    mode = determine_mode(len(survivors), len(failures), gating)

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

    cycle = 0
    while running:
        cycle += 1
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
                f"A13 guidance #{cycle} MODE={guidance.get('mode','?')} | survivors={meta['survivors_analyzed']} "
                f"failures={meta['failures_analyzed']} cool_off={meta['cool_off_count']} | "
                f"top: {', '.join(f'{k}={v}' for k,v in top3)} | "
                f"bot: {', '.join(f'{k}={v}' for k,v in bot3)}"
            )

        except Exception as e:
            log.error(f"A13 guidance computation failed: {e}")

        # Sleep in small chunks so we can respond to signals
        for _ in range(REFRESH_INTERVAL_S):
            if not running:
                break
            await asyncio.sleep(1)

    await db.close()
    log.info("Arena 13 Feedback Controller stopped")


if __name__ == "__main__":
    asyncio.run(main())
