"""Arena 4+5 Orchestrator — Validation gate + ELO tournament for champions.

Arena 4: Validates ARENA3_COMPLETE champions on HOLDOUT data (last 30%).
         Produces CANDIDATE (not DEPLOYABLE directly).
Arena 5: Continuous ELO tournament for CANDIDATE + DEPLOYABLE strategies (Swiss-system pairing).
         Only DEPLOYABLE can become ACTIVE card.

v9: Arena 4 uses holdout data only — never sees train data from Arena 1/2/3.
v9: Dual-tier CANDIDATE → DEPLOYABLE promotion gate (AD2).
v9: A4 now faithfully replays A3's TP strategy + ATR params + max_hold = _strategy_max_hold(champ.get('strategy_id', 'j01')) on holdout.
v6c: A4 min_seg_trades=8, A5 same-symbol evidence accumulation for Wilson LB promotion, pool_size=2, A3 PnL pre-filter.
v9: Deduplicated shared_utils (compute_indicators, compute_atr, wilson_lower,
    compute_config_hash, apply_trailing_stop, apply_fixed_target, apply_tp_strategy,
    extract_a3_params). Fixed A5 max_hold bug, ATR stop in ELO matches,
    config hash compatibility, trailing stop semantic mismatch.
"""
import sys, os, asyncio, signal, time, json, random, datetime, math
sys.path.insert(0, '/home/j13/j13-ops')
sys.path.insert(0, '/home/j13/j13-ops/zangetsu/indicator_engine/target/release')
os.chdir('/home/j13/j13-ops')

import numpy as np
import polars as pl
import asyncpg
from zangetsu.services.pidlock import acquire_lock

from zangetsu.services.db_audit import log_transition
from zangetsu.engine.components.signal_utils import generate_threshold_signals
from zangetsu.services.signal_reconstructor import reconstruct_signal_from_passport
from zangetsu.engine.components.data_preprocessor import enrich_data_cache
# v0.5.9: Central passport schema dispatch (prevents V9→V10 silent regressions).
from zangetsu.services.passport_schema import is_v10, get_dedup_key, get_alpha

# ── V10 factor-expression helpers (added by v10_complete_upgrade) ──
_V10_ALPHA_ENGINE = None

def _get_v10_engine():
    global _V10_ALPHA_ENGINE
    if _V10_ALPHA_ENGINE is None:
        from zangetsu.engine.components.alpha_engine import AlphaEngine
        _V10_ALPHA_ENGINE = AlphaEngine()
    return _V10_ALPHA_ENGINE


def _v10_get_alpha_expression(passport):
    """Extract alpha_expression from passport, handling both schema variants."""
    return (
        passport.get("alpha_expression")
        or (passport.get("arena1", {}) or {}).get("alpha_expression")
        or {}
    )


def _v10_alpha_to_signal(ast_json, close, high, low, open_arr, volume,
                          entry_thresh=0.5, exit_thresh=0.2):
    """Compile AST and produce (signal, alpha_norm, err).

    signal: int8 array {-1, 0, +1} (short / flat / long)
    alpha_norm: float array clipped to [-1, 1]
    err: None on success, str describing failure otherwise
    """
    import numpy as _np
    import logging as _logging
    _log = _logging.getLogger("arena45")
    engine = _get_v10_engine()
    # end-to-end-upgrade fix 2026-04-19: populate indicator_cache for this
    # symbol's holdout window so the 126 indicator terminals evaluate against
    # real data instead of silent zeros (consistent with A1/A2/A3 paths).
    try:
        from zangetsu.engine.components.indicator_bridge import build_indicator_cache
        _v10_cache = build_indicator_cache(
            _np.ascontiguousarray(close, dtype=_np.float64),
            _np.ascontiguousarray(high, dtype=_np.float64),
            _np.ascontiguousarray(low, dtype=_np.float64),
            _np.ascontiguousarray(volume, dtype=_np.float64),
        )
        engine.indicator_cache.clear()
        engine.indicator_cache.update(_v10_cache)
    except Exception as _ce:  # noqa: BLE001
        _log.warning(f"A4/A5 indicator_cache build failed: {_ce}")
    try:
        fn = engine.compile_ast(ast_json)
        raw = fn(close, high, low, open_arr, volume)
    except Exception as e:
        return None, None, f"compile_fail:{type(e).__name__}:{e}"
    if raw is None:
        return None, None, "alpha_returned_none"
    raw = _np.asarray(raw, dtype=_np.float64).ravel()
    if raw.shape[0] != close.shape[0]:
        if raw.shape[0] < close.shape[0]:
            padded = _np.full(close.shape[0], _np.nan)
            padded[-raw.shape[0]:] = raw
            raw = padded
        else:
            raw = raw[-close.shape[0]:]
    valid = _np.isfinite(raw)
    if valid.sum() < 100:
        return None, None, "alpha_mostly_nan"
    med = _np.nanmedian(raw)
    mad = _np.nanmedian(_np.abs(raw[valid] - med)) * 1.4826
    if mad < 1e-10:
        return None, None, "alpha_zero_variance"
    alpha_norm = _np.clip((raw - med) / (2 * mad + 1e-9), -1.0, 1.0)
    alpha_norm = _np.nan_to_num(alpha_norm, nan=0.0, posinf=1.0, neginf=-1.0)
    signal = _np.zeros(alpha_norm.shape[0], dtype=_np.int8)
    signal[alpha_norm > entry_thresh] = 1
    signal[alpha_norm < -entry_thresh] = -1
    exit_mask = _np.abs(alpha_norm) < exit_thresh
    signal[exit_mask] = 0
    return signal, alpha_norm, None


def _v10_extract_symbol(champion, data_cache):
    import json as _json
    pp = champion.get("passport")
    if isinstance(pp, str):
        pp = _json.loads(pp)
    a1 = pp.get("arena1", {}) or {}
    sym = a1.get("symbol") or a1.get("arena1_symbol")
    if sym and sym in data_cache:
        return sym
    discovery = pp.get("discovery", {}) or {}
    sym = discovery.get("symbol")
    if sym and sym in data_cache:
        return sym
    ih = champion.get("indicator_hash", "") or ""
    for s in data_cache:
        if ih.endswith(s):
            return s
    return None

from zangetsu.services.data_collector import merge_funding_to_1m, merge_oi_to_1m
from pathlib import Path
from zangetsu.services.shared_utils import (
    wilson_lower,
    compute_atr,
    compute_config_hash,
    apply_trailing_stop,
    apply_fixed_target,
    apply_tp_strategy,
    compute_indicators,
    extract_a3_params,
    extract_a2_params,
    extract_symbol,
    backtest_with_a3_params,
    ensure_db_connection,
    reap_expired_leases,
)

# ── V9: PGQueuer event-driven pickup (opt-in via A45_USE_PGQUEUER=1) ──
try:
    from zangetsu.services.event_queue import EventQueue
    _EVENT_QUEUE_AVAILABLE = True
except Exception:
    EventQueue = None  # type: ignore[assignment]
    _EVENT_QUEUE_AVAILABLE = False

WORKER_ID = 'arena45'
TRAIN_SPLIT_RATIO = 0.7

# ── Arena 4 thresholds ───────────────────────────────────────────
A4_MIN_WR = 0.40
A4_MIN_SEG_TRADES = 8  # v6b: minimum trades per holdout segment (was implicit 3)
A4_MAX_VARIABILITY = 1.5

# ── Arena 5 constants ───────────────────────────────────────────
A5_INITIAL_ELO = 1500.0
A5_K_FACTOR = 32.0
A5_MATCH_WINDOW = 5000  # bars per match
A5_TIE_THRESHOLD = 0.05
A5_ROUNDS_FOR_PROMOTION = 100
A5_MAX_ELO = 2500.0
A5_MIN_ELO = -500.0
A5_MIN_POOL_SIZE = 2  # was 3, lowered to unblock PARABOLIC  # minimum strategies per regime for ELO matches

# ── Directional indicators (same as arena_pipeline) ─────────────
DIRECTIONAL = [
    "rsi", "stochastic_k", "cci", "roc", "ppo", "cmo", "zscore",
    "adx", "aroon_osc", "trix", "fisher", "awesome_osc",
    "normalized_atr", "realized_vol", "bollinger_bw",
    "relative_volume", "vwap_deviation",
    "funding_rate", "funding_zscore", "oi_change", "oi_divergence",
]




def normalize_with_passport(arrs, passport):
    """Normalize using stored medians/MADs from passport."""
    norm_data = passport.get("normalization", {})
    medians = np.array(norm_data.get("medians", []))
    mads = np.array(norm_data.get("mads", []))

    matrix = np.column_stack(arrs)

    if len(medians) == matrix.shape[1] and len(mads) == matrix.shape[1]:
        mads_safe = mads.copy()
        mads_safe[mads_safe == 0] = 1e-12
        norm = np.clip((matrix - medians) / mads_safe, -5, 5)
    else:
        # Fallback: compute fresh normalization
        med = np.median(matrix, axis=0)
        mad = np.median(np.abs(matrix - med), axis=0) * 1.4826
        mad[mad == 0] = 1e-12
        norm = np.clip((matrix - med) / mad, -5, 5)

    return norm


def backtest_slice(backtester, signals, close, high, low, symbol, cost_bps, max_hold,
                   atr=None, atr_stop_mult=None, sizes=None):
    """Run backtest on a data slice with optional ATR stop."""
    if len(signals) < 50:
        return None
    kwargs = {"high": high, "low": low}
    if atr is not None and atr_stop_mult is not None:
        kwargs["atr"] = atr[:len(signals)]
        kwargs["atr_stop_mult"] = atr_stop_mult
    if sizes is not None:
        kwargs["sizes"] = sizes[:len(signals)]
    return backtester.run(signals, close, symbol, cost_bps, max_hold, **kwargs)



# v0.7.2 horizon alignment: per-strategy MAX_HOLD via lazy loader.
# Orchestrators process rows from multiple strategies; each row's
# strategy_id determines which thresholds.MAX_HOLD_BARS is used for
# its A2/A3/A4 backtests.
_STRATEGY_THRESHOLDS_CACHE = {}
def _strategy_max_hold(strategy_id):
    if strategy_id not in _STRATEGY_THRESHOLDS_CACHE:
        if strategy_id == "j01":
            from j01.config import thresholds as t
        elif strategy_id == "j02":
            from j02.config import thresholds as t
        else:
            raise RuntimeError(
                f"Unknown strategy_id={strategy_id!r} in orchestrator. "
                "Expected j01 or j02; refuse to proceed."
            )
        _STRATEGY_THRESHOLDS_CACHE[strategy_id] = int(t.MAX_HOLD_BARS)
    return _STRATEGY_THRESHOLDS_CACHE[strategy_id]

async def pick_arena3_complete(db):
    """Atomically pick one ARENA3_COMPLETE champion for processing."""
    # v9: Pre-filter - skip A3 champions with non-positive PnL
    # MEDIUM-M2: unify V10 detection with python check below (line ~321 startswith("zv5_v10"))
    # Using NOT LIKE 'zv5_v10%' instead of != 'zv5_v10_alpha' to cover future v10 variants
    # (e.g. zv5_v10_beta) consistently across SQL and Python call sites.
    n_prefiltered = await db.fetchval("""
        WITH to_filter AS (
            SELECT id FROM champion_pipeline_fresh
            WHERE status = 'ARENA3_COMPLETE' AND COALESCE(arena3_pnl, 0) <= 0 AND (engine_hash IS NULL OR engine_hash NOT LIKE 'zv5_v10%')
        )
        UPDATE champion_pipeline_fresh cp
        SET status = 'ARENA4_ELIMINATED',
            arena4_completed_at = NOW(),
            passport = passport || '{"arena4_elimination_reason": "a3_pnl_nonpositive"}'::jsonb,
            updated_at = NOW()
        FROM to_filter tf
        WHERE cp.id = tf.id
        RETURNING cp.id
    """)
    row = await db.fetchrow("""
        UPDATE champion_pipeline_fresh
        SET status = 'ARENA4_PROCESSING', worker_id_str = $1, lease_until = NOW() + INTERVAL '15 minutes', updated_at = NOW()
        WHERE id = (
            SELECT id FROM champion_pipeline_fresh
            WHERE status = 'ARENA3_COMPLETE'
            ORDER BY arena3_pnl DESC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
    """, WORKER_ID)
    if row:
        await log_transition(db, row["id"], "ARENA3_COMPLETE", "ARENA4_PROCESSING", worker_id=WORKER_ID)
    return row


async def arena4_pass(db, champ_id, quant_class, hell_wr, variability, extra_passport):
    """Mark champion as CANDIDATE (dual-tier: must pass promotion gate for DEPLOYABLE)."""
    await db.execute("""
        UPDATE champion_pipeline_fresh
        SET status = 'CANDIDATE',
            quant_class = $1,
            arena4_hell_wr = $2,
            arena4_variability = $3,
            arena4_completed_at = NOW(),
            elo_rating = $6,
            card_status = 'INACTIVE',
            passport = passport || $4::jsonb,
            updated_at = NOW()
        WHERE id = $5
    """, quant_class, hell_wr, variability, json.dumps(extra_passport), champ_id, A5_INITIAL_ELO)
    await log_transition(db, champ_id, "ARENA4_PROCESSING", "CANDIDATE", worker_id=WORKER_ID, metadata={"quant_class": quant_class})


async def arena4_fail(db, champ_id, reason, hell_wr, variability):
    """Mark champion as ARENA4_ELIMINATED."""
    await db.execute("""
        UPDATE champion_pipeline_fresh
        SET status = 'ARENA4_ELIMINATED',
            arena4_hell_wr = $1,
            arena4_variability = $2,
            arena4_completed_at = NOW(),
            passport = passport || $3::jsonb,
            updated_at = NOW()
        WHERE id = $4
    """, hell_wr, variability, json.dumps({"arena4_elimination_reason": reason}), champ_id)
    await log_transition(db, champ_id, "ARENA4_PROCESSING", "ARENA4_ELIMINATED", worker_id=WORKER_ID, metadata={"reason": reason})


# ── CANDIDATE → DEPLOYABLE promotion thresholds ──────────────────
# Patch H3 2026-04-20: moved to config/settings.py
from zangetsu.config.settings import PROMOTE_WILSON_LB, PROMOTE_MIN_TRADES  # re-exported


async def promote_candidate(champ, db, log, verbose=False):
    """Check if CANDIDATE meets DEPLOYABLE criteria (Wilson LB > PROMOTE_WILSON_LB, min PROMOTE_MIN_TRADES trades, PnL > 0).
    Returns (promoted: bool, reason: str)."""
    champ_id = champ["id"]
    passport = json.loads(champ["passport"]) if champ["passport"] else {}
    a4 = passport.get("arena4", {})
    holdout = a4.get("holdout_full", {})

    holdout_wr = float(holdout.get("wr", 0))
    holdout_pnl = float(holdout.get("pnl", 0))
    holdout_trades = int(holdout.get("trades", 0))

    # Gate 1: minimum trade count
    if holdout_trades < PROMOTE_MIN_TRADES:
        if verbose:
            log.info(f"CANDIDATE #{champ_id}: STAY (trades={holdout_trades} < {PROMOTE_MIN_TRADES})")
        return False

    # Gate 2: Wilson lower bound on win rate (combined A4 + A5 evidence, v6)
    a4_wins = int(round(holdout_wr * holdout_trades))
    a5_ev = passport.get("arena5_evidence", {"wins": 0, "total": 0})
    a5_wins = int(a5_ev.get("wins", 0))
    a5_total = int(a5_ev.get("total", 0))
    combined_wins = a4_wins + a5_wins
    combined_total = holdout_trades + a5_total
    wlb = wilson_lower(combined_wins, combined_total)

    if wlb <= PROMOTE_WILSON_LB:
        combined_wr = combined_wins / combined_total if combined_total > 0 else 0
        log.info(f"CANDIDATE #{champ_id}: Wilson LB={wlb:.4f} (threshold={PROMOTE_WILSON_LB}) combined={combined_total}(a4={holdout_trades}+a5={a5_total}) wr={combined_wr:.3f} — STAY")
        return False


    # Gate 3: positive holdout PnL
    if holdout_pnl <= 0:
        if verbose:
            log.info(f"CANDIDATE #{champ_id}: STAY (holdout PnL={holdout_pnl:.4f} <= 0)")
        return False

    # Gate 4: positive arena3 PnL (prevent negative-PnL strategies from reaching DEPLOYABLE)
    arena3_pnl = float(champ.get("arena3_pnl", 0) or 0)
    _is_v10 = (champ.get("engine_hash") or "").startswith("zv5_v10")
    if not _is_v10 and arena3_pnl <= 0:
        if verbose:
            log.info(f"CANDIDATE #{champ_id}: STAY (arena3_pnl={arena3_pnl:.4f} <= 0)")
        return False

    # Gate 5 (v0.5.9): dedup via passport_schema — handles V9 config_hash AND V10 alpha_hash.
    # Pre-fix: V10 champions had config_hash=None → dedup silently skipped → duplicates reached DEPLOYABLE.
    dedup_key = None
    dedup_kind = None
    try:
        passport_data = json.loads(champ["passport"]) if champ["passport"] else {}
        spec = get_alpha(passport_data)
        if spec:
            dedup_kind = spec["kind"]
            dedup_key = spec.get("alpha_hash") if dedup_kind == "v10" else spec.get("config_hash")
    except (json.JSONDecodeError, TypeError) as e:
        log.debug(f"passport parse failed for champ {champ.get('id')}: {e}")
    if dedup_key:
        json_field = "alpha_hash" if dedup_kind == "v10" else "config_hash"
        existing = await db.fetchval(f"""
            SELECT id FROM champion_pipeline_fresh
            WHERE status = 'DEPLOYABLE' AND id != $1 AND regime = $3
            AND passport::jsonb -> 'arena1' ->> '{json_field}' = $2
            LIMIT 1
        """, champ_id, dedup_key, champ["regime"])
        if existing:
            if verbose:
                log.info(f"CANDIDATE #{champ_id}: STAY (duplicate {dedup_kind}:{json_field}={dedup_key} in {champ['regime']}, existing DEPLOYABLE #{existing})")
            return False
    elif passport_data:
        # Gemini 2026-04-19: pre-fix would log WARN then fall through to PROMOTE, allowing
        # dedup-keyless (malformed) passports to flood DEPLOYABLE. Fail hard instead.
        log.error(f"CANDIDATE #{champ_id}: passport missing dedup key (engine_hash={champ.get('engine_hash')!r}) — REFUSING to promote (malformed passport)")
        return False

    # All gates passed — PROMOTE to DEPLOYABLE
    await db.execute("""
        UPDATE champion_pipeline_fresh SET status = 'DEPLOYABLE', deployable_tier = 'fresh', updated_at = NOW()
        WHERE id = $1
    """, champ_id)
    await log_transition(db, champ_id, "CANDIDATE", "DEPLOYABLE", worker_id=WORKER_ID,
                         metadata={"wilson_lb": round(wlb, 4), "trades": holdout_trades, "pnl": round(holdout_pnl, 6)})
    log.info(f"PROMOTED #{champ_id}: CANDIDATE → DEPLOYABLE | Wilson={wlb:.3f} combined={combined_total}(a4={holdout_trades}+a5={a5_total}) PnL={holdout_pnl:.4f}")
    return True


async def process_arena4(champ, data_cache, backtester, cost_model, rust_engine, db, log):
    """Arena 4: Validate a champion on HOLDOUT data (last 30%) that Arena 1/2/3 never saw."""
    champ_id = champ["id"]
    regime = champ["regime"]
    indicator_hash = champ["indicator_hash"]
    passport = json.loads(champ["passport"]) if champ["passport"] else {}

    # Extract symbol from indicator_hash (format: v5_r{N}_c{N}_{SYMBOL})
    parts = indicator_hash.split("_")
    symbol = parts[-1] if len(parts) >= 3 else None

    # Fallback: pick a random symbol from data_cache instead of always first
    if symbol not in data_cache:
        if data_cache:
            symbol = random.choice(list(data_cache.keys()))
        else:
            symbol = None

    if symbol is None or symbol not in data_cache:
        log.warning(f"A4 #{champ_id}: no data for symbol derived from {indicator_hash}")
        await arena4_fail(db, champ_id, "no_data", 0.0, 0.0)
        return

    d = data_cache[symbol]
    close, high, low, vol = d["close"], d["high"], d["low"], d["volume"]
    cost_bps = cost_model.get(symbol).total_round_trip_bps

    # Extract passport branches (V10 dispatcher bridge: p0g v0.5.2)
    arena1 = passport.get("arena1", {})
    has_v10_alpha = bool(arena1.get("alpha_expression"))
    configs = arena1.get("configs", []) or []
    # Only V9 rows that ALSO lack an alpha formula truly have no playable signal.
    # Pre-p0g bug: this guard fired on every V10 champion (no configs by design),
    # making V10 pass-rate 0% silently.
    if not configs and not has_v10_alpha:
        log.warning(f"A4 #{champ_id}: no indicator configs and no V10 alpha_expression")
        await arena4_fail(db, champ_id, "no_configs", 0.0, 0.0)
        return

    # Extract thresholds from passport (Arena 2 may have optimized them)
    arena2 = passport.get("arena2", {})
    entry_thr = arena2.get("entry_threshold", arena2.get("entry_thr", 0.80))
    exit_thr = arena2.get("exit_threshold", arena2.get("exit_thr", 0.40))
    cooldown = arena2.get("cooldown", 10)

    # Arena 3 params: ATR stop + TP strategy + max_hold — use shared_utils extractor
    a3_params = extract_a3_params(passport)
    atr_stop_mult = a3_params["atr_stop_mult"]
    max_hold = a3_params["max_hold"]  # Always 480 from extract_a3_params
    tp_strategy = a3_params["tp_type"]  # FIXED: was get(best_tp_strategy) which always returned none
    tp_param = float(a3_params.get("tp_param", 0.0) or 0.0)

    # Compute ATR on holdout data for ATR stop
    atr = compute_atr(high, low, close, period=14)

    # V10 path: alpha_expression -> reconstruct directly (no indicator compute).
    # V9 path: configs -> legacy compute+filter+vote pipeline.
    if has_v10_alpha:
        signals, _sizes_a4, _agr_a4 = reconstruct_signal_from_passport(
            passport, close, high, low, d.get("open", np.zeros_like(close)), vol,
            entry_threshold=entry_thr, exit_threshold=exit_thr,
            min_hold=60, cooldown=cooldown, regime=regime,
        )
        # reconstruct_signal_from_passport returns a zero-signal fallback on
        # internal failure (alpha modules missing / compile failure / NaN flood).
        # Treat all-zero as explicit A4 fail — do NOT let a dead strategy flow
        # into backtest and "pass" by accident. (Q1 dim-2: no silent failure.)
        if not np.any(signals):
            log.warning(f"A4 #{champ_id}: V10 alpha reconstruct produced zero signal")
            await arena4_fail(db, champ_id, "v10_alpha_reconstruct_failed", 0.0, 0.0)
            return
    else:
        # V9 legacy path (unchanged logic, just indented under else).
        arrs = compute_indicators(configs, close, high, low, vol, rust_engine)
        if len(arrs) < 2:
            log.warning(f"A4 #{champ_id}: insufficient indicators computed ({len(arrs)})")
            await arena4_fail(db, champ_id, "insufficient_indicators", 0.0, 0.0)
            return

        # Filter zero-variance indicators
        valid = [(i, a) for i, a in enumerate(arrs) if np.median(np.abs(a - np.median(a))) > 0]
        if len(valid) < 2:
            log.warning(f"A4 #{champ_id}: insufficient valid indicators after filtering ({len(valid)})")
            await arena4_fail(db, champ_id, "insufficient_valid_indicators", 0.0, 0.0)
            return
        valid_idx = [v[0] for v in valid]
        arrs = [v[1] for v in valid]
        configs = [configs[i] for i in valid_idx]
        names = [c["name"] for c in configs]

        # Generate signals using indicator-specific thresholds (same as Arena 1)
        # V10 BUG-3: use A2-optimized thresholds from passport (was hardcoded 0.55/0.30)
        signals, _sizes_a4, _agr_a4 = generate_threshold_signals(
            names, arrs,
            entry_threshold=entry_thr, exit_threshold=exit_thr, min_hold=60, cooldown=cooldown, regime=regime,
        )

    # Apply A3's TP strategy using shared_utils (handles long+short, tracks unrealized PnL)
    signals = apply_tp_strategy(signals, close, tp_strategy, tp_param)

    n = len(close)

    # Arena 4 now validates on the ENTIRE holdout set
    # Split holdout into 3 segments for walk-forward variability check
    seg_len = n // 3
    segment_wrs = []
    segment_results = {}

    for seg_i in range(3):
        seg_name = ["early", "mid", "late"][seg_i]
        s_start = seg_i * seg_len
        s_end = s_start + seg_len if seg_i < 2 else n
        seg_s = signals[s_start:s_end]
        seg_c = close[s_start:s_end]
        seg_h = high[s_start:s_end]
        seg_l = low[s_start:s_end]
        seg_atr = atr[s_start:s_end]
        seg_sizes = _sizes_a4[s_start:s_end]
        bt = backtest_slice(backtester, seg_s, seg_c, seg_h, seg_l, symbol, cost_bps, max_hold,
                            atr=seg_atr, atr_stop_mult=atr_stop_mult, sizes=seg_sizes)
        if bt and bt.total_trades >= A4_MIN_SEG_TRADES:
            wr = float(bt.win_rate)
            segment_wrs.append(wr)
            segment_results[seg_name] = {
                "wr": wr,
                "pnl": float(bt.net_pnl),
                "trades": int(bt.total_trades),
                "sharpe": float(bt.sharpe_ratio),
                "dd": float(bt.max_drawdown),
                "expectancy": float(bt.pnl_per_trade),
            }
        else:
            segment_wrs.append(0.0)
            segment_results[seg_name] = {"wr": 0.0, "pnl": 0.0, "trades": 0, "sharpe": 0.0}

    # Full holdout backtest (with ATR stop, matching A3 params)
    bt_full = backtest_slice(backtester, signals, close, high, low, symbol, cost_bps, max_hold,
                             atr=atr, atr_stop_mult=atr_stop_mult, sizes=_sizes_a4)
    if bt_full and bt_full.total_trades >= 3:
        full_wr = float(bt_full.win_rate)
        full_result = {
            "wr": full_wr,
            "pnl": float(bt_full.net_pnl),
            "trades": int(bt_full.total_trades),
            "sharpe": float(bt_full.sharpe_ratio),
            "dd": float(bt_full.max_drawdown),
            "expectancy": float(bt_full.pnl_per_trade),
        }
    else:
        full_wr = 0.0
        full_result = {"wr": 0.0, "pnl": 0.0, "trades": 0, "sharpe": 0.0}

    mean_wr = np.mean(segment_wrs) if segment_wrs else 0.0
    std_wr = np.std(segment_wrs) if len(segment_wrs) > 1 else 0.0
    variability = float(std_wr / mean_wr) if mean_wr > 0 else 999.0

    hell_wr = float(min(segment_wrs)) if segment_wrs else 0.0

    # Gate check
    all_segments_pass = all(wr >= A4_MIN_WR for wr in segment_wrs)
    full_pass = full_wr >= A4_MIN_WR
    positive_metrics = {
        "sharpe": float(full_result.get("sharpe", 0.0) or 0.0),
        "expectancy": float(full_result.get("expectancy", 0.0) or 0.0),
        "pnl": float(full_result.get("pnl", 0.0) or 0.0),
    }
    has_positive_metric = any(v > 0 for v in positive_metrics.values())

    gate_pass = all_segments_pass and full_pass and variability < A4_MAX_VARIABILITY and has_positive_metric

    if gate_pass:
        metrics = {k: v for k, v in positive_metrics.items() if v > 0}
        quant_class = max(metrics, key=metrics.get)

        extra = {
            "arena4": {
                "holdout_full": full_result,
                "holdout_segments": segment_results,
                "segment_wrs": segment_wrs,
                "variability": variability,
                "quant_class": quant_class,
                "symbol": symbol,
                "holdout_bars": n,
                "data_source": "holdout_only",
                "tp_strategy": tp_strategy,
                "tp_param": tp_param,
                "atr_stop_mult": atr_stop_mult,
                "max_hold": max_hold,
            }
        }
        await arena4_pass(db, champ_id, quant_class, hell_wr, variability, extra)
        log.info(
            f"A4 PASS #{champ_id} | {symbol}/{regime} | class={quant_class} "
            f"| hell_wr={hell_wr:.3f} var={variability:.3f} "
            f"| holdout_wr={full_wr:.3f} holdout_pnl={full_result['pnl']:.4f} "
            f"| segments: {[f'{w:.3f}' for w in segment_wrs]} "
            f"| tp={tp_strategy}({tp_param}) atr={atr_stop_mult} hold={max_hold} "
            f"| holdout_bars={n}"
        )
    else:
        reason_parts = []
        if not all_segments_pass:
            failed = [f"{['early','mid','late'][i]}={segment_wrs[i]:.3f}" for i in range(3) if segment_wrs[i] < A4_MIN_WR]
            reason_parts.append(f"seg_wr_fail:{','.join(failed)}")
        if not full_pass:
            reason_parts.append(f"full_wr={full_wr:.3f}")
        if variability >= A4_MAX_VARIABILITY:
            reason_parts.append(f"var={variability:.3f}")
        if not has_positive_metric:
            reason_parts.append("no_positive_holdout_metric")
        reason = "|".join(reason_parts) or "unknown"

        await arena4_fail(db, champ_id, reason, hell_wr, variability)
        log.info(
            f"A4 FAIL #{champ_id} | {symbol}/{regime} | reason={reason} "
            f"| hell_wr={hell_wr:.3f} var={variability:.3f} | holdout_bars={n}"
        )


async def get_deployable_by_regime(db):
    """Get CANDIDATE + DEPLOYABLE champions grouped by regime for ELO matching."""
    rows = await db.fetch("""
        SELECT id, regime, elo_rating, quant_class, indicator_hash, passport, status
        FROM champion_pipeline_fresh
        WHERE status IN ('CANDIDATE', 'DEPLOYABLE')
          AND (card_status IS NULL OR card_status NOT IN ('SEED','DISCOVERED'))
        ORDER BY regime, elo_rating DESC
    """)
    by_regime = {}
    for r in rows:
        regime = r["regime"]
        if regime not in by_regime:
            by_regime[regime] = []
        by_regime[regime].append(r)
    return by_regime


async def sync_active_cards(db):
    """Keep exactly one ACTIVE card per regime — only DEPLOYABLE can be ACTIVE."""
    regimes = await db.fetch(
        "SELECT DISTINCT regime FROM champion_pipeline_fresh WHERE status = 'DEPLOYABLE'"
    )
    for row in regimes:
        regime = row["regime"]
        # Only DEPLOYABLE can be ACTIVE card (CANDIDATE participates in ELO but can't be ACTIVE)
        leaders = await db.fetch(
            """
            SELECT id
            FROM champion_pipeline_fresh
            WHERE status = 'DEPLOYABLE' AND regime = $1
              AND (card_status IS NULL OR card_status NOT IN ('SEED','DISCOVERED'))
            ORDER BY elo_rating DESC NULLS LAST,
                     arena4_hell_wr DESC NULLS LAST,
                     arena3_sharpe DESC NULLS LAST,
                     id ASC
            """,
            regime,
        )
        if not leaders:
            continue
        active_id = leaders[0]["id"]
        # Reset all DEPLOYABLE + CANDIDATE cards in this regime to INACTIVE
        await db.execute(
            """
            UPDATE champion_pipeline_fresh
            SET card_status = 'INACTIVE', updated_at = NOW()
            WHERE status IN ('DEPLOYABLE', 'CANDIDATE') AND regime = $1 AND COALESCE(card_status, 'INACTIVE') != 'INACTIVE'
            """,
            regime,
        )
        await db.execute(
            """
            UPDATE champion_pipeline_fresh
            SET card_status = 'ACTIVE', updated_at = NOW()
            WHERE id = $1
            """,
            active_id,
        )


def swiss_pair(pool):
    """Swiss-system pairing: pair strategies with similar ELO.
    Skips pairs with identical dedup keys to avoid TIE spam.

    v0.5.9: dedup key via passport_schema (V10 alpha_hash OR V9 config_hash).
    Pre-fix: V10 champions all hashed to "" → every V10/V10 pair skipped → V10 pool
    was structurally starved of ELO matches.
    """
    sorted_pool = sorted(pool, key=lambda r: r["elo_rating"] or A5_INITIAL_ELO, reverse=True)
    def _dedup_hash(s):
        try:
            passport = json.loads(s["passport"]) if s.get("passport") else {}
            return get_dedup_key(passport)
        except (json.JSONDecodeError, TypeError, ValueError):
            # Missing/unresolvable dedup key → return unique sentinel so this
            # row does not collide with any other row (opposite of pre-fix "" bug).
            # Gemini 2026-04-19: `s.get('id', id(s))` returns None if id key is literally None;
            # use `or` so explicit-None also falls through to Python id().
            return f"__no_key__:{s.get('id') or id(s)}"
    hashes = [_dedup_hash(s) for s in sorted_pool]
    pairs = []
    used = set()
    for i in range(len(sorted_pool)):
        if i in used:
            continue
        for j in range(i + 1, len(sorted_pool)):
            if j in used:
                continue
            # Skip pairs with identical indicator configs (would always TIE)
            if hashes[i] == hashes[j]:
                continue
            pairs.append((sorted_pool[i], sorted_pool[j]))
            used.add(i)
            used.add(j)
            break
    return pairs


async def run_elo_round(by_regime, data_cache, backtester, cost_model, rust_engine, db, log):
    """Arena 5: Run one round of ELO matches on holdout data."""
    matches_played = 0

    for regime, pool in by_regime.items():
        if len(pool) < A5_MIN_POOL_SIZE:
            continue

        pairs = swiss_pair(pool)
        if not pairs:
            continue

        pair = random.choice(pairs)
        champ_a, champ_b = pair

        symbols = list(data_cache.keys())
        if not symbols:
            continue
        symbol = random.choice(symbols)
        d = data_cache[symbol]
        total_bars = len(d["close"])
        if total_bars < A5_MATCH_WINDOW + 100:
            continue

        max_start = total_bars - A5_MATCH_WINDOW
        start = random.randint(0, max_start)
        end = start + A5_MATCH_WINDOW

        close = d["close"][start:end]
        high = d["high"][start:end]
        low = d["low"][start:end]
        vol = d["volume"][start:end]
        cost_bps = cost_model.get(symbol).total_round_trip_bps

        scores = {}
        for label, champ in [("A", champ_a), ("B", champ_b)]:
            passport = json.loads(champ["passport"]) if champ["passport"] else {}
            arena1 = passport.get("arena1", {})
            configs = arena1.get("configs", [])
            arena2 = passport.get("arena2", {})
            entry_thr = arena2.get("entry_threshold", arena2.get("entry_thr", 0.80))
            exit_thr = arena2.get("exit_threshold", arena2.get("exit_thr", 0.40))
            cooldown = arena2.get("cooldown", 10)

            # Fix #1: Use extract_a3_params — always returns max_hold = _strategy_max_hold(champ.get('strategy_id', 'j01'))
            a3_params = extract_a3_params(passport)
            max_hold = a3_params["max_hold"]
            atr_stop_mult = a3_params["atr_stop_mult"]
            tp_strategy = a3_params["tp_type"]
            tp_param = float(a3_params["tp_param"])

            # v0.5.9: V10 dispatcher MUST precede the `configs` guard. Pre-fix
            # the guard below fired before the V10 branch at the old L748 could
            # run, so every V10 champion was scored -999 and silently lost every
            # ELO match. Same family as the 2026-04-18 P0-G incident.
            if passport.get("arena1", {}).get("alpha_expression"):
                try:
                    signals, _sz_elo, _agr_elo = reconstruct_signal_from_passport(
                        passport, close, high, low, d.get("open", np.zeros_like(close)), vol,
                        entry_threshold=entry_thr, exit_threshold=exit_thr,
                        min_hold=60, cooldown=cooldown, regime=regime,
                    )
                except Exception as _re:
                    log.debug(f"ELO V10 reconstruct failed for champ {champ.get('id')}: {_re}")
                    scores[label] = {"metric": -999.0}
                    continue
            else:
                if not configs:
                    scores[label] = {"metric": -999.0}
                    continue

                arrs = compute_indicators(configs, close, high, low, vol, rust_engine)
                if len(arrs) < 2:
                    scores[label] = {"metric": -999.0}
                    continue

                elo_names = [c["name"] for c in configs]
                signals, _sz_elo, _agr_elo = generate_threshold_signals(
                    elo_names, arrs,
                    entry_threshold=entry_thr, exit_threshold=exit_thr, min_hold=60, cooldown=cooldown, regime=regime,
                )

            # Fix #3: Apply TP strategy to signals before backtest (matching A3/A4)
            signals = apply_tp_strategy(signals, close, tp_strategy, tp_param)

            # Fix #3: Compute ATR on the match slice and pass to backtest
            match_atr = compute_atr(high, low, close, period=14)
            bt = backtest_slice(backtester, signals, close, high, low, symbol, cost_bps, max_hold,
                                atr=match_atr, atr_stop_mult=atr_stop_mult, sizes=_sz_elo)

            if bt is None or bt.total_trades < 2:
                scores[label] = {"metric": -999.0}
                continue

            qc = champ["quant_class"] or "pnl"
            if qc == "sharpe":
                metric = float(bt.sharpe_ratio)
            elif qc == "expectancy":
                metric = float(bt.pnl_per_trade)
            else:
                metric = float(bt.net_pnl)

            scores[label] = {"metric": metric, "wr": float(bt.win_rate), "trades": int(bt.total_trades)}

        score_a = scores["A"]["metric"]
        score_b = scores["B"]["metric"]

        elo_a = float(champ_a["elo_rating"] or A5_INITIAL_ELO)
        elo_b = float(champ_b["elo_rating"] or A5_INITIAL_ELO)

        e_a = 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))
        e_b = 1.0 - e_a

        diff = abs(score_a - score_b)
        if diff < A5_TIE_THRESHOLD:
            s_a, s_b = 0.5, 0.5
            outcome = "TIE"
        elif score_a > score_b:
            s_a, s_b = 1.0, 0.0
            outcome = "A_WIN"
        else:
            s_a, s_b = 0.0, 1.0
            outcome = "B_WIN"

        new_elo_a = elo_a + A5_K_FACTOR * (s_a - e_a)
        new_elo_a = max(A5_MIN_ELO, min(A5_MAX_ELO, new_elo_a))
        new_elo_b = elo_b + A5_K_FACTOR * (s_b - e_b)
        new_elo_b = max(A5_MIN_ELO, min(A5_MAX_ELO, new_elo_b))

        await db.execute(
            "UPDATE champion_pipeline_fresh SET elo_rating=$1, arena5_last_tested=NOW(), updated_at=NOW() WHERE id=$2",
            new_elo_a, champ_a["id"],
        )
        await db.execute(
            "UPDATE champion_pipeline_fresh SET elo_rating=$1, arena5_last_tested=NOW(), updated_at=NOW() WHERE id=$2",
            new_elo_b, champ_b["id"],
        )

        # -- A5 Evidence Accumulation (v6b: same-symbol only) --
        # Only accumulate Wilson evidence when match symbol matches candidate's A4 symbol
        # Cross-symbol performance is tracked via ELO only, not Wilson LB
        for _lbl, _champ_ref in [("A", champ_a), ("B", champ_b)]:
            _sc = scores.get(_lbl, {})
            _mt = _sc.get("trades", 0)
            _mw = _sc.get("wr", 0.0)
            _passport = json.loads(_champ_ref["passport"]) if _champ_ref.get("passport") else {}
            _a4_symbol = _passport.get("arena4", {}).get("symbol", "")
            if _mt >= 2 and symbol == _a4_symbol:
                _mwins = int(round(_mw * _mt))
                try:
                    await db.execute(
                        "UPDATE champion_pipeline_fresh SET passport = jsonb_set("
                        "jsonb_set(passport, '{arena5_evidence,wins}', "
                        "to_jsonb(COALESCE((passport->'arena5_evidence'->>'wins')::int, 0) + $1)), "
                        "'{arena5_evidence,total}', "
                        "to_jsonb(COALESCE((passport->'arena5_evidence'->>'total')::int, 0) + $2)), "
                        "updated_at = NOW() WHERE id = $3",
                        _mwins, _mt, _champ_ref["id"],
                    )
                except Exception:
                    try:
                        await db.execute(
                            "UPDATE champion_pipeline_fresh SET passport = passport || $1::jsonb, "
                            "updated_at = NOW() WHERE id = $2",
                            json.dumps({"arena5_evidence": {"wins": _mwins, "total": _mt}}),
                            _champ_ref["id"],
                        )
                    except Exception as e:
                        log.debug(f"A5 evidence accumulation update failed id={_champ_ref.get('id')}: {e}")
        # -- End A5 Evidence Accumulation --

        matches_played += 1
        log.info(
            f"A5 ELO | {regime} | #{champ_a['id']} vs #{champ_b['id']} | {outcome} "
            f"| {elo_a:.0f}->{new_elo_a:.0f} vs {elo_b:.0f}->{new_elo_b:.0f} "
            f"| metric: {score_a:.4f} vs {score_b:.4f} | {symbol} (holdout)"
        )

    return matches_played


# ── Daily Reset ─────────────────────────────────────────────────
_last_reset_date = None
A5_KEEP_PER_REGIME = 10


async def check_daily_reset(db, log):
    """Daily reset at 00:00 UTC: keep top N per regime, retire the rest."""
    global _last_reset_date
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    if _last_reset_date == today:
        return

    if now.hour == 0 or _last_reset_date is None:
        log.info("Daily reset starting")

        regimes = await db.fetch(
            "SELECT DISTINCT regime FROM champion_pipeline_fresh WHERE status IN ('CANDIDATE', 'DEPLOYABLE')"
        )

        total_retired = 0
        total_kept = 0
        for row in regimes:
            regime = row["regime"]
            # Rank by status (DEPLOYABLE first) then ELO
            strategies = await db.fetch("""
                SELECT id, elo_rating, status FROM champion_pipeline_fresh
                WHERE status IN ('CANDIDATE', 'DEPLOYABLE') AND regime = $1
                  AND (card_status IS NULL OR card_status NOT IN ('SEED','DISCOVERED'))
                ORDER BY (CASE WHEN status = 'DEPLOYABLE' THEN 0 ELSE 1 END),
                         elo_rating DESC
            """, regime)

            for i, s in enumerate(strategies):
                if i >= A5_KEEP_PER_REGIME:
                    await db.execute("""
                        UPDATE champion_pipeline_fresh
                        SET status = 'ELO_RETIRED', elo_rating = 0, card_status = 'INACTIVE', updated_at = NOW()
                        WHERE id = $1
                    """, s["id"])
                    total_retired += 1
                else:
                    await db.execute("""
                        UPDATE champion_pipeline_fresh
                        SET arena5_last_tested = NULL, card_status = 'INACTIVE', updated_at = NOW()
                        WHERE id = $1
                    """, s["id"])
                    total_kept += 1

        await sync_active_cards(db)
        _last_reset_date = today
        log.info(
            f"Daily reset complete: kept={total_kept} retired={total_retired} "
            f"across {len(regimes)} regimes"
        )


async def main():
    from zangetsu.config.settings import Settings
    from zangetsu.config.cost_model import CostModel
    from zangetsu.engine.components.backtester import Backtester
    from zangetsu.engine.components.logger import StructuredLogger

    settings = Settings()
    cost_model = CostModel()
    log = StructuredLogger("arena45", settings.log_level, settings.log_file, settings.log_rotation_mb)

    log.info("Arena 4+5 Orchestrator starting (v9: shared_utils dedup + ATR/TP fixes)")

    # Load Rust engine
    rust_engine = None
    try:
        import zangetsu_indicators as zi
        rust_engine = zi
        log.info("Rust indicator engine loaded")
    except ImportError:
        log.warning("No Rust engine — indicators will be zeros")

    # Backtester
    class BtConfig:
        backtest_chunk_size = 10000
        backtest_gpu_enabled = False
        backtest_gpu_batch_size = 64
    backtester = Backtester(BtConfig())

    # DB connection
    db = await asyncpg.connect(
        host=settings.db_host, port=settings.db_port,
        database='zangetsu', user=settings.db_user,
        password=settings.db_password,
    )
    log.info("DB connected")

    # Load HOLDOUT data only (last 30%)
    _data_dir = Path(settings.parquet_dir).parent
    data_cache = {}
    for sym in settings.symbols:
        try:
            df = pl.read_parquet(f"{settings.parquet_dir}/{sym}.parquet")
            w = min(200000, len(df))
            split = int(w * TRAIN_SPLIT_RATIO)
            holdout_bars = w - split
            # Load only the holdout portion (last 30%)
            data_cache[sym] = {
                "holdout": {
                    "open": df["open"].to_numpy()[-w+split:].astype(np.float32),
                    "close": df["close"].to_numpy()[-w+split:].astype(np.float32),
                    "high": df["high"].to_numpy()[-w+split:].astype(np.float32),
                    "low": df["low"].to_numpy()[-w+split:].astype(np.float32),
                    "volume": df["volume"].to_numpy()[-w+split:].astype(np.float32),
                },
            }

            # Load funding + OI for holdout slice
            funding_arr = merge_funding_to_1m(
                Path(settings.parquet_dir) / f"{sym}.parquet",
                _data_dir / "funding" / f"{sym}.parquet",
            )
            if funding_arr is not None:
                data_cache[sym]["holdout"]["funding_rate"] = funding_arr[-w:][split:].astype(np.float32)

            oi_arr = merge_oi_to_1m(
                Path(settings.parquet_dir) / f"{sym}.parquet",
                _data_dir / "oi" / f"{sym}.parquet",
            )
            if oi_arr is not None:
                data_cache[sym]["holdout"]["oi"] = oi_arr[-w:][split:].astype(np.float32)

            log.info(f"Loaded {sym}: {holdout_bars} bars (holdout only, last {1-TRAIN_SPLIT_RATIO:.0%} of {w})")
        except Exception as e:
            log.warning(f"Skip {sym}: {e}")

    # Enrich with nondimensional factors
    enrich_data_cache(data_cache)

    # Backward compat: arena45 accesses data_cache[sym]["close"] directly
    for sym in list(data_cache.keys()):
        if "holdout" in data_cache[sym]:
            for k, v in data_cache[sym]["holdout"].items():
                data_cache[sym][k] = v

    log.info(f"Data loaded: {len(data_cache)} symbols (holdout split only, factor-enriched)")

    running = True
    a4_processed = 0
    a4_passed = 0
    a5_matches = 0
    _candidate_sweep_done = False
    _last_promotion_check = 0
    _loop_iteration = 0

    def handle_sig(s, f):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    log.info("Arena 4+5 Orchestrator running (v9: shared_utils dedup + ATR/TP fixes)")

    # ── V9: Optional PGQueuer LISTEN/NOTIFY pickup (opt-in) ──────
    # Default OFF. A3 is not yet emitting notify events, so this is prep
    # work only — the polling loop below remains the primary driver.
    _use_pgqueuer = os.environ.get("A45_USE_PGQUEUER", "0") == "1"
    _event_queue = None
    if _use_pgqueuer and _EVENT_QUEUE_AVAILABLE:
        try:
            _event_queue = EventQueue()

            async def _on_a45_event(stage: str, champion_id: str) -> None:
                log.info(f"A45 pgqueuer wake stage={stage} champion={champion_id}")

            asyncio.create_task(_event_queue.listen(_on_a45_event))
            log.info("A45 PGQueuer listener started (prep mode, polling still primary)")
        except Exception as e:
            log.warning(f"A45 PGQueuer init failed, fallback to polling: {e}")
            _event_queue = None
    elif _use_pgqueuer and not _EVENT_QUEUE_AVAILABLE:
        log.warning("A45_USE_PGQUEUER=1 but event_queue module unavailable; polling only")

    while running:
        try:
            _loop_iteration += 1

            # Periodic lease reaper (every 100 iterations)
            if _loop_iteration % 100 == 0:
                try:
                    await reap_expired_leases(db, log)
                except Exception as e:
                    log.warning(f"Lease reaper error: {e}")

            # Periodic DB health check (every 100 iterations)
            if _loop_iteration % 100 == 0:
                try:
                    db, _ = await ensure_db_connection(db, settings, log)
                except Exception as e:
                    log.warning(f"DB health check error: {e}")

            await check_daily_reset(db, log)

            # Priority 0: Batch-promote all eligible CANDIDATE → DEPLOYABLE
            # Run verbose on first sweep, then only on newly-arrived CANDIDATEs
            candidates = await db.fetch("""
                SELECT * FROM champion_pipeline_fresh WHERE status = 'CANDIDATE'
            """)
            # Periodic promotion re-check every 500 A5 matches (not just first sweep)
            if candidates and (not _candidate_sweep_done or a5_matches - _last_promotion_check >= 50):
                promoted = 0
                for cand in candidates:
                    if await promote_candidate(cand, db, log, verbose=True):
                        promoted += 1
                await sync_active_cards(db)
                if promoted > 0 or not _candidate_sweep_done:
                    log.info(f"Promotion sweep: {promoted}/{len(candidates)} CANDIDATE → DEPLOYABLE (matches={a5_matches})")
                _candidate_sweep_done = True
                _last_promotion_check = a5_matches

            # Priority 1: Validate new ARENA3_COMPLETE on holdout data
            champ = await pick_arena3_complete(db)
            if champ:
                t0 = time.time()
                await process_arena4(champ, data_cache, backtester, cost_model, rust_engine, db, log)
                a4_processed += 1
                elapsed = time.time() - t0
                row = await db.fetchrow("SELECT * FROM champion_pipeline_fresh WHERE id=$1", champ["id"])
                if row and row["status"] == "CANDIDATE":
                    a4_passed += 1
                    # Immediately try to promote the new CANDIDATE
                    await promote_candidate(row, db, log, verbose=True)
                elif row and row["status"] == "DEPLOYABLE":
                    a4_passed += 1
                await sync_active_cards(db)
                if a4_processed <= 10 or a4_processed % 25 == 0:
                    log.info(f"A4 stats: processed={a4_processed} passed={a4_passed} rate={a4_passed/a4_processed:.1%} | {elapsed:.1f}s")
                continue

            # Priority 2: Run ELO matches for CANDIDATE + DEPLOYABLE on holdout data
            by_regime = await get_deployable_by_regime(db)
            total_deployable = sum(len(v) for v in by_regime.values())
            matchable_regimes = sum(1 for v in by_regime.values() if len(v) >= 2)

            if matchable_regimes > 0:
                played = await run_elo_round(by_regime, data_cache, backtester, cost_model, rust_engine, db, log)
                await sync_active_cards(db)
                a5_matches += played
                if played > 0 and (a5_matches <= 10 or a5_matches % 50 == 0):
                    log.info(f"A5 stats: matches={a5_matches} candidates={total_deployable} regimes={matchable_regimes}")
                continue

            # Idle — no A4 work and no ELO matches possible. Sleep longer to reduce log/CPU waste.
            await asyncio.sleep(10)

        except asyncpg.exceptions.ConnectionDoesNotExistError:
            log.error("DB connection lost, reconnecting...")
            try:
                db = await asyncpg.connect(
                    host=settings.db_host, port=settings.db_port,
                    database='zangetsu', user=settings.db_user,
                    password=settings.db_password,
                )
                log.info("DB reconnected")
            except Exception as e:
                log.error(f"DB reconnect failed: {e}")
                await asyncio.sleep(5)
        except Exception as e:
            log.error(f"Loop error: {e}")
            await asyncio.sleep(2)

    # V9: close PGQueuer listener if active
    if _event_queue is not None:
        try:
            await _event_queue.close()
        except Exception as e:
            log.warning(f"A45 PGQueuer close error: {e}")

    await db.close()
    log.info(f"Stopped. a4_processed={a4_processed} a4_passed={a4_passed} a5_matches={a5_matches}")


if __name__ == "__main__":
    acquire_lock("arena45_orchestrator")
    asyncio.run(main())
