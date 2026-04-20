"""Arena 13 — Downstream Truth Feedback Controller.

Converts A3/A4/A5 outcome data into soft guidance for Arena 1 discovery.
Does NOT evolve, mutate, or re-inject candidates. Produces a guidance file
that A1 reads periodically to adjust indicator weights and period preferences.

Guidance is soft (weights, not blocks), bounded (0.3x-3.0x), and diversity-preserving
(random exploration never drops below DIVERSITY_FLOOR).

Runs as a background service, updating guidance every REFRESH_INTERVAL_S seconds.

V10 (2026-04-19): schema dispatch aware.
- Reads BOTH V9 (passport.arena1.configs) and V10 (passport.arena1.alpha_expression) rows.
- Dedup keyed on alpha_hash (V10) OR config_hash (V9).
- New "failures_only" mode: survivors==0 but many failures → decay-only (no upweight).
- Weight sanity gate: any indicator delta > 50% is rejected and the write is aborted.
- atexit + SIGTERM safe lock release.
"""
import sys, os, asyncio, signal, time, json, math, atexit
sys.path.insert(0, '/home/j13/j13-ops')
os.chdir('/home/j13/j13-ops')

import numpy as np
from zangetsu.services.pidlock import acquire_lock, _release_lock as release_lock

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
                "soft_exit_below_survivors": 1, "active_exit_below_survivors": 12,
                "failures_only_threshold": 20}

def determine_mode(n_survivors, n_failures, gating, previous_mode="observe"):
    """V9/V10 hysteresis-aware mode transition with failures_only_mode.

    Modes:
      observe        — default / insufficient signal on either side
      failures_only  — V10: survivors==0 AND failures>=failures_only_threshold.
                        Caller must apply decay-only weights (never upweight).
      soft           — some survivors + some failures (entry N>=3/5 by default).
      active         — substantial survivors + failures (entry N>=20/50 by default).

    Standard entry thresholds apply going UP; exit thresholds (lower) apply going
    DOWN to prevent thrash near boundary.
    """
    soft_in = gating.get("min_survivors_for_soft", 3)
    soft_in_fail = gating.get("min_failures_for_soft", 5)
    active_in = gating.get("min_survivors_for_active", 20)
    active_in_fail = gating.get("min_failures_for_active", 50)
    soft_exit = gating.get("soft_exit_below_survivors", 1)
    active_exit = gating.get("active_exit_below_survivors", 12)
    failures_only_threshold = gating.get("failures_only_threshold", 20)

    # V10: failures-only path fires only when there are literally zero survivors
    # but enough failures to act on (decay-only). Takes priority over observe so
    # the caller can apply decay instead of freezing.
    if n_survivors == 0 and n_failures >= failures_only_threshold:
        return "failures_only"

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

    # Currently observe (or failures_only, which always re-evaluates fresh) →
    # standard upgrade thresholds
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

# V10 weight sanity gate — reject writes where any indicator weight changes by
# more than MAX_WEIGHT_DELTA_PCT vs the current (prior) weights. Abort entirely
# on violation (never partial-apply).
MAX_WEIGHT_DELTA_PCT = 0.50


def _extract_configs_from_row(row, log=None):
    """V9/V10-agnostic: return list of {name, period} dicts extracted from a row.

    V9 rows carry passport.arena1.configs (list of indicator configs).
    V10 rows carry passport.arena1.alpha_expression (a single string, e.g.
    "tsi_14 + 0.5 * macd_26"). We parse <name>_<period> tokens out of the
    expression. Unknown tokens are silently dropped — this is lossy but safe
    for downstream scoring which is count-based.
    """
    import re as _re
    out = []
    configs = row.get("configs") if isinstance(row, dict) else row["configs"]
    if configs:
        try:
            cfg_list = json.loads(configs) if isinstance(configs, str) else configs
            if isinstance(cfg_list, list):
                for cfg in cfg_list:
                    if isinstance(cfg, dict):
                        out.append({
                            "name": cfg.get("name", ""),
                            "period": cfg.get("period", 14),
                        })
                return out
        except (json.JSONDecodeError, TypeError):
            if log:
                log.warning(f"a13: failed to parse configs for row id={row.get('id')}")
    # V10 fallback: parse alpha_expression
    expr = row.get("alpha_expression") if isinstance(row, dict) else None
    if expr is None:
        try:
            expr = row["alpha_expression"]
        except (KeyError, IndexError):
            expr = None
    if expr and isinstance(expr, str):
        # Token pattern: <indicator_name>_<period> where indicator_name is alpha,
        # period is digits. Case-insensitive on name, then lowered.
        for match in _re.finditer(r"([A-Za-z][A-Za-z0-9_]*?)_(\d+)", expr):
            name = match.group(1).lower()
            try:
                period = int(match.group(2))
            except ValueError:
                continue
            if name in BASE_WEIGHTS:
                out.append({"name": name, "period": period})
    return out


def _weight_sanity_check(new_weights, current_weights, log):
    """Reject the write if any indicator weight changes > MAX_WEIGHT_DELTA_PCT.

    Returns True if safe to write, False if rejected. Never partial-applies.
    """
    for k, new_v in new_weights.items():
        old_v = current_weights.get(k, BASE_WEIGHTS.get(k, 1.0))
        denom = max(abs(old_v), 1e-6)
        delta_pct = abs(new_v - old_v) / denom
        if delta_pct > MAX_WEIGHT_DELTA_PCT:
            if log:
                log.error(
                    f"a13 weight sanity REJECTED: {k} {old_v} -> {new_v} "
                    f"(delta={delta_pct:.1%}, cap={MAX_WEIGHT_DELTA_PCT:.0%})"
                )
            return False
    return True


def _load_current_weights():
    """Load previous indicator_weights from guidance.json (for sanity diff).

    Returns BASE_WEIGHTS if guidance.json missing / malformed.
    """
    try:
        with open(GUIDANCE_PATH) as f:
            data = json.load(f)
        w = data.get("indicator_weights")
        if isinstance(w, dict) and w:
            return {k: float(v) for k, v in w.items()}
    except FileNotFoundError:
        pass  # OK: guidance.json absent on cold start
    except (json.JSONDecodeError, ValueError, TypeError) as e:  # Patch C3 2026-04-20
        import logging as _l
        _l.getLogger(__name__).warning(f"A13 guidance malformed, using BASE_WEIGHTS: {e}")
    return dict(BASE_WEIGHTS)


def _apply_failures_only_decay(current_weights, failure_ind_count, log=None):
    """In failures_only mode: decay weights of indicators appearing in failures.

    Never upweights. Floor at WEIGHT_FLOOR. Indicators not in failures retain
    their current weight unchanged. Returns a new dict.
    """
    if not failure_ind_count:
        return dict(current_weights)
    # Decay factor proportional to failure share, capped at 30% per cycle so the
    # sanity-gate (50% delta cap) is never breached by this alone.
    total_failures = max(sum(failure_ind_count.values()), 1)
    out = {}
    for ind in ALL_INDICATORS:
        cur = float(current_weights.get(ind, BASE_WEIGHTS.get(ind, 1.0)))
        f = failure_ind_count.get(ind, 0)
        if f > 0:
            share = f / total_failures
            decay = min(0.30, share)  # cap per-cycle decay at 30%
            new_v = cur * (1.0 - decay)
            out[ind] = round(max(WEIGHT_FLOOR, min(WEIGHT_CEIL, new_v)), 3)
        else:
            out[ind] = round(max(WEIGHT_FLOOR, min(WEIGHT_CEIL, cur)), 3)
    if log:
        log.info(f"a13 failures_only decay applied to {sum(1 for k in out if out[k] < current_weights.get(k, 1.0))} indicators")
    return out


async def compute_guidance(db, log):
    """Extract downstream truth and compute guidance weights."""
    # V9: load gating early so failure-noise guard can use bootstrap thresholds
    gating = load_gating_policy()

    # ── 1. Survivor analysis: V9 configs OR V10 alpha_expression ──
    survivors = await db.fetch("""
        SELECT id, status, engine_hash,
               passport->'arena1'->'configs' as configs,
               passport->'arena1'->>'alpha_expression' as alpha_expression
        FROM champion_pipeline
        WHERE status IN ('CANDIDATE', 'DEPLOYABLE')
          AND (passport->'arena1'->'configs' IS NOT NULL
               OR passport->'arena1'->'alpha_expression' IS NOT NULL)
          AND (evolution_operator IS NULL OR (evolution_operator NOT LIKE 'cold_seed%' AND evolution_operator != 'gp_evolution'))
          AND (engine_hash IS NULL OR engine_hash NOT LIKE '%_coldstart')
    """)

    survivor_ind_count = {}   # indicator_name -> count in survivors
    survivor_period_count = {} # (indicator_name, period) -> count in survivors
    for row in survivors:
        for cfg in _extract_configs_from_row(row, log):
            name = cfg.get("name", "")
            period = cfg.get("period", 14)
            if not name:
                continue
            survivor_ind_count[name] = survivor_ind_count.get(name, 0) + 1
            key = f"{name}_{period}"
            survivor_period_count[key] = survivor_period_count.get(key, 0) + 1

    # ── 2. Failure analysis: V9 + V10 eliminated in A4. engine_hash LIKE 'zv%' ──
    failures = await db.fetch("""
        SELECT id, engine_hash,
               passport->'arena1'->'configs' as configs,
               passport->'arena1'->>'alpha_expression' as alpha_expression
        FROM champion_pipeline
        WHERE status = 'ARENA4_ELIMINATED'
          AND engine_hash LIKE 'zv%'
          AND (passport->'arena1'->'configs' IS NOT NULL
               OR passport->'arena1'->'alpha_expression' IS NOT NULL)
          AND (evolution_operator IS NULL OR (evolution_operator NOT LIKE 'cold_seed%' AND evolution_operator != 'gp_evolution'))
    """)

    failure_ind_count = {}
    for row in failures:
        for cfg in _extract_configs_from_row(row, log):
            name = cfg.get("name", "")
            if not name:
                continue
            failure_ind_count[name] = failure_ind_count.get(name, 0) + 1

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

    # ── 5. Cool-off list: alpha_hash (V10) OR config_hash (V9) that failed A4 recently ──
    cool_off_rows = await db.fetch(f"""
        SELECT DISTINCT
               COALESCE(
                 passport->'arena1'->>'alpha_hash',
                 passport->'arena1'->>'config_hash'
               ) as dedup_key,
               regime,
               engine_hash
        FROM champion_pipeline
        WHERE status = 'ARENA4_ELIMINATED'
          AND engine_hash LIKE 'zv%'
          AND updated_at > NOW() - INTERVAL '{COOL_OFF_HOURS} hours'
          AND (passport->'arena1'->>'alpha_hash' IS NOT NULL
               OR passport->'arena1'->>'config_hash' IS NOT NULL)
          AND (evolution_operator IS NULL OR (evolution_operator NOT LIKE 'cold_seed%' AND evolution_operator != 'gp_evolution'))
    """)
    cool_off = [f"{r['regime']}|{r['dedup_key']}" for r in cool_off_rows if r["dedup_key"]]

    # ── 6. Regime-specific indicator boosts: V9 + V10 ──
    # V9: jsonb_array_elements(passport->'arena1'->'configs')->>'name'
    # V10: parse indicator names out of passport->'arena1'->>'alpha_expression' in Python
    #      (regex on the expression string). SQL just widens the filter.
    regime_rows = await db.fetch("""
        SELECT id, regime, engine_hash,
               passport->'arena1'->'configs' as configs,
               passport->'arena1'->>'alpha_expression' as alpha_expression
        FROM champion_pipeline
        WHERE status IN ('CANDIDATE', 'DEPLOYABLE')
          AND (passport->'arena1'->'configs' IS NOT NULL
               OR passport->'arena1'->'alpha_expression' IS NOT NULL)
          AND (evolution_operator IS NULL OR (evolution_operator NOT LIKE 'cold_seed%' AND evolution_operator != 'gp_evolution'))
          AND (engine_hash IS NULL OR engine_hash NOT LIKE '%_coldstart')
    """)
    # Aggregate: regime -> indicator -> count (V9 + V10 unified)
    regime_ind_cnt = {}  # {regime: {ind_name: cnt}}
    for row in regime_rows:
        regime = row["regime"]
        if not regime:
            continue
        if regime not in regime_ind_cnt:
            regime_ind_cnt[regime] = {}
        for cfg in _extract_configs_from_row(row, log):
            name = cfg.get("name", "")
            if not name:
                continue
            regime_ind_cnt[regime][name] = regime_ind_cnt[regime].get(name, 0) + 1
    regime_boosts = {}
    for regime, ind_counts in regime_ind_cnt.items():
        regime_boosts[regime] = {}
        for ind, cnt in ind_counts.items():
            # Boost = 1.0 + 0.3 per survivor occurrence (capped at 2.0)
            regime_boosts[regime][ind] = round(min(1.0 + 0.3 * cnt, 2.0), 2)

    # ── 7. A3 training insight: what TP/ATR combos survive A4? (V9+V10) ──
    tp_rows = await db.fetch("""
        SELECT
          passport->'arena3'->>'best_tp_strategy' as tp,
          passport->'arena3'->>'tp_param' as tp_p,
          status,
          count(*) as cnt
        FROM champion_pipeline
        WHERE engine_hash LIKE 'zv%' AND arena3_sharpe IS NOT NULL
          AND (evolution_operator IS NULL OR (evolution_operator NOT LIKE 'cold_seed%' AND evolution_operator != 'gp_evolution'))
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

    # V10: in failures_only mode, reassemble guided_weights from current state +
    # decay-only (never upweight). Overrides the survivor-driven blend above.
    current_weights = _load_current_weights()
    weight_sanity_rejected = False
    if mode == "failures_only":
        guided_weights = _apply_failures_only_decay(current_weights, failure_ind_count, log)

    # V10 sanity gate: reject writes where any indicator weight jumps > 50%.
    if not _weight_sanity_check(guided_weights, current_weights, log):
        weight_sanity_rejected = True
        # Abort the write: keep previous weights exactly.
        guided_weights = dict(current_weights)
        if log:
            log.error("a13 weight sanity gate FIRED — reusing previous weights, no update applied")

    # ── 8. Assemble guidance ──
    guidance = {
        "version": 4,  # V10: schema-aware (V9/V10 dispatch, failures_only, sanity gate)
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
            "weight_sanity_rejected": weight_sanity_rejected,
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

    # V10 single-shot: on SIGTERM/SIGINT release lock + exit immediately.
    # (Earlier V9 handler merely flipped a flag that the main path never polled.)
    def handle_sig(s, f):
        try:
            log.info(f"Shutdown signal received ({s}), releasing lock and exiting")
        except Exception:
            pass
        _release_lock_safe()
        sys.exit(0)
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


def _release_lock_safe():
    """Best-effort lock release — swallow all errors. Used by atexit + SIGTERM.
    `_release_lock` (no args) is the current pidlock.py API; aliased as `release_lock` on import."""
    try:
        release_lock()
    except Exception:
        pass


if __name__ == "__main__":
    acquire_lock("arena13_feedback")
    atexit.register(_release_lock_safe)
    # On SIGTERM (systemd stop), release lock then exit cleanly. SIGINT is also
    # handled symmetrically so the timer-triggered shutdown path always clears
    # the lock.
    signal.signal(signal.SIGTERM, lambda *_: (_release_lock_safe(), sys.exit(0)))
    signal.signal(signal.SIGINT, lambda *_: (_release_lock_safe(), sys.exit(0)))
    asyncio.run(main())
