"""Arena 4+5 Orchestrator — Validation gate + ELO tournament for champions.

Arena 4: Validates ARENA3_COMPLETE champions on HOLDOUT data (last 30%).
         Produces CANDIDATE (not DEPLOYABLE directly).
Arena 5: Continuous ELO tournament for CANDIDATE + DEPLOYABLE strategies (Swiss-system pairing).
         Only DEPLOYABLE can become ACTIVE card.

v9: Arena 4 uses holdout data only — never sees train data from Arena 1/2/3.
v9: Dual-tier CANDIDATE → DEPLOYABLE promotion gate (AD2).
v9: A4 now faithfully replays A3's TP strategy + ATR params + max_hold=480 on holdout.
v6c: A4 min_seg_trades=8, A5 same-symbol evidence accumulation for Wilson LB promotion, pool_size=2, A3 PnL pre-filter.
v9: Deduplicated shared_utils (compute_indicators, compute_atr, wilson_lower,
    compute_config_hash, apply_trailing_stop, apply_fixed_target, apply_tp_strategy,
    extract_a3_params). Fixed A5 max_hold bug, ATR stop in ELO matches,
    config hash compatibility, trailing stop semantic mismatch.
"""
import sys, os, asyncio, signal, time, json, random, datetime, math
sys.path.insert(0, '/home/j13/j13-ops')
sys.path.insert(0, '/home/j13/j13-ops/zangetsu_v5/indicator_engine/target/release')
os.chdir('/home/j13/j13-ops')

import numpy as np
import polars as pl
import asyncpg
from zangetsu_v5.services.pidlock import acquire_lock
acquire_lock("arena45_orchestrator")

from zangetsu_v5.services.db_audit import log_transition
from zangetsu_v5.engine.components.signal_utils import generate_threshold_signals
from zangetsu_v5.engine.components.data_preprocessor import enrich_data_cache
from zangetsu_v5.services.data_collector import merge_funding_to_1m, merge_oi_to_1m
from pathlib import Path
from zangetsu_v5.services.shared_utils import (
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

WORKER_ID = 'arena45'
TRAIN_SPLIT_RATIO = 0.7

# ── Arena 4 thresholds ───────────────────────────────────────────
A4_MIN_WR = 0.40
A4_MIN_SEG_TRADES = 8  # v6b: minimum trades per holdout segment (was implicit 3)
A4_MAX_VARIABILITY = 1.5

# ── Arena 5 constants ───────────────────────────────────────────
A4_MIN_DSR = 0.05  # V9 oneshot A2: deflated Sharpe floor
A4_MIN_TRIALS_FOR_DSR = 20  # V9 oneshot A2: multi-trial floor
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


A4_MAX_HOLD_BARS = 480  # Must match A3's MAX_HOLD_BARS_A3


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


def backtest_slice(backtester, signals, close, high, low, symbol, cost_bps, max_hold=480,
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


async def pick_arena3_complete(db):
    """Atomically pick one ARENA3_COMPLETE champion for processing."""
    # v9: Pre-filter - skip A3 champions with non-positive PnL
    n_prefiltered = await db.fetchval("""
        WITH to_filter AS (
            SELECT id FROM champion_pipeline
            WHERE status = 'ARENA3_COMPLETE' AND COALESCE(arena3_pnl, 0) <= 0
        )
        UPDATE champion_pipeline cp
        SET status = 'ARENA4_ELIMINATED',
            arena4_completed_at = NOW(),
            passport = passport || '{"arena4_elimination_reason": "a3_pnl_nonpositive"}'::jsonb,
            updated_at = NOW()
        FROM to_filter tf
        WHERE cp.id = tf.id
        RETURNING cp.id
    """)
    row = await db.fetchrow("""
        UPDATE champion_pipeline
        SET status = 'ARENA4_PROCESSING', worker_id = $1, lease_until = NOW() + INTERVAL '15 minutes', updated_at = NOW()
        WHERE id = (
            SELECT id FROM champion_pipeline
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
        UPDATE champion_pipeline
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
        UPDATE champion_pipeline
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
PROMOTE_WILSON_LB = 0.50
PROMOTE_MIN_TRADES = 25


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
    if arena3_pnl <= 0:
        if verbose:
            log.info(f"CANDIDATE #{champ_id}: STAY (arena3_pnl={arena3_pnl:.4f} <= 0)")
        return False

    # Gate 5: dedup — skip if a DEPLOYABLE with same config_hash already exists
    config_hash = None
    try:
        passport_data = json.loads(champ["passport"]) if champ["passport"] else {}
        config_hash = passport_data.get("arena1", {}).get("config_hash")
    except (json.JSONDecodeError, TypeError):
        pass
    if config_hash:
        existing = await db.fetchval("""
            SELECT id FROM champion_pipeline
            WHERE status = 'DEPLOYABLE' AND id != $1 AND regime = $3
            AND passport::jsonb -> 'arena1' ->> 'config_hash' = $2
            LIMIT 1
        """, champ_id, config_hash, champ["regime"])
        if existing:
            if verbose:
                log.info(f"CANDIDATE #{champ_id}: STAY (duplicate config_hash={config_hash} in {champ["regime"]}, existing DEPLOYABLE #{existing})")
            return False

    # All gates passed — PROMOTE to DEPLOYABLE
    await db.execute("""
        UPDATE champion_pipeline SET status = 'DEPLOYABLE', updated_at = NOW()
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

    # Extract indicator configs from passport
    arena1 = passport.get("arena1", {})
    configs = arena1.get("configs", [])
    if not configs:
        log.warning(f"A4 #{champ_id}: no indicator configs in passport")
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

    # Compute indicators on holdout data
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
    # FIXED BUG-3: use A2-optimized thresholds from passport (was hardcoded 0.55/0.30)
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

    # V9 oneshot A2: Deflated Sharpe Ratio gate (Lopez de Prado)
    a1_trials = int(passport.get('arena1', {}).get('total_searched', 0) or 0)
    num_trials = max(a1_trials, A4_MIN_TRIALS_FOR_DSR)
    seg_sharpes = [segment_results[k].get('sharpe', 0.0) for k in ('early', 'mid', 'late')]
    sr_std_est = float(np.std(seg_sharpes)) if len(seg_sharpes) > 1 else 0.0
    dsr = deflated_sharpe_ratio(
        observed_sr=float(full_result.get('sharpe', 0.0) or 0.0),
        sr_std=max(sr_std_est, 0.1),
        num_trials=num_trials,
        T=int(full_result.get('trades', 0) or 0),
    )
    dsr_pass = dsr >= A4_MIN_DSR
    gate_pass = all_segments_pass and full_pass and variability < A4_MAX_VARIABILITY and has_positive_metric and dsr_pass

    if gate_pass:
        metrics = {k: v for k, v in positive_metrics.items() if v > 0}
        quant_class = max(metrics, key=metrics.get)

        extra = {
            "arena4": {
                "holdout_full": full_result,
                "holdout_segments": segment_results,
                "segment_wrs": segment_wrs,
                "variability": variability,
                "dsr": float(dsr),
                "dsr_num_trials": num_trials,
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
        if not dsr_pass:
            reason_parts.append(f"dsr={dsr:.3f}")
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
        FROM champion_pipeline
        WHERE status IN ('CANDIDATE', 'DEPLOYABLE')
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
        "SELECT DISTINCT regime FROM champion_pipeline WHERE status = 'DEPLOYABLE'"
    )
    for row in regimes:
        regime = row["regime"]
        # Only DEPLOYABLE can be ACTIVE card (CANDIDATE participates in ELO but can't be ACTIVE)
        leaders = await db.fetch(
            """
            SELECT id
            FROM champion_pipeline
            WHERE status = 'DEPLOYABLE' AND regime = $1
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
            UPDATE champion_pipeline
            SET card_status = 'INACTIVE', updated_at = NOW()
            WHERE status IN ('DEPLOYABLE', 'CANDIDATE') AND regime = $1 AND COALESCE(card_status, 'INACTIVE') != 'INACTIVE'
            """,
            regime,
        )
        await db.execute(
            """
            UPDATE champion_pipeline
            SET card_status = 'ACTIVE', updated_at = NOW()
            WHERE id = $1
            """,
            active_id,
        )


def swiss_pair(pool):
    """Swiss-system pairing: pair strategies with similar ELO.
    Skips pairs with identical indicator config hashes to avoid TIE spam."""
    sorted_pool = sorted(pool, key=lambda r: r["elo_rating"] or A5_INITIAL_ELO, reverse=True)
    # Pre-compute config hashes using shared_utils (sorted pipe-joined[:16], matching A1/A23)
    def _get_config_hash(s):
        passport = json.loads(s["passport"]) if s.get("passport") else {}
        configs = passport.get("arena1", {}).get("configs", [])
        return compute_config_hash(configs) if configs else ""
    hashes = [_get_config_hash(s) for s in sorted_pool]
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

            # Fix #1: Use extract_a3_params — always returns max_hold=480
            a3_params = extract_a3_params(passport)
            max_hold = a3_params["max_hold"]
            atr_stop_mult = a3_params["atr_stop_mult"]
            tp_strategy = a3_params["tp_type"]
            tp_param = float(a3_params["tp_param"])

            if not configs:
                scores[label] = {"metric": -999.0}
                continue

            arrs = compute_indicators(configs, close, high, low, vol, rust_engine)
            if len(arrs) < 2:
                scores[label] = {"metric": -999.0}
                continue

            elo_names = [c["name"] for c in configs]
            # FIXED BUG-3: use A2-optimized thresholds from passport
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
            "UPDATE champion_pipeline SET elo_rating=$1, arena5_last_tested=NOW(), updated_at=NOW() WHERE id=$2",
            new_elo_a, champ_a["id"],
        )
        await db.execute(
            "UPDATE champion_pipeline SET elo_rating=$1, arena5_last_tested=NOW(), updated_at=NOW() WHERE id=$2",
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
                        "UPDATE champion_pipeline SET passport = jsonb_set("
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
                            "UPDATE champion_pipeline SET passport = passport || $1::jsonb, "
                            "updated_at = NOW() WHERE id = $2",
                            json.dumps({"arena5_evidence": {"wins": _mwins, "total": _mt}}),
                            _champ_ref["id"],
                        )
                    except Exception:
                        pass
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
            "SELECT DISTINCT regime FROM champion_pipeline WHERE status IN ('CANDIDATE', 'DEPLOYABLE')"
        )

        total_retired = 0
        total_kept = 0
        for row in regimes:
            regime = row["regime"]
            # Rank by status (DEPLOYABLE first) then ELO
            strategies = await db.fetch("""
                SELECT id, elo_rating, status FROM champion_pipeline
                WHERE status IN ('CANDIDATE', 'DEPLOYABLE') AND regime = $1
                ORDER BY (CASE WHEN status = 'DEPLOYABLE' THEN 0 ELSE 1 END),
                         elo_rating DESC
            """, regime)

            for i, s in enumerate(strategies):
                if i >= A5_KEEP_PER_REGIME:
                    await db.execute("""
                        UPDATE champion_pipeline
                        SET status = 'ELO_RETIRED', elo_rating = 0, card_status = 'INACTIVE', updated_at = NOW()
                        WHERE id = $1
                    """, s["id"])
                    total_retired += 1
                else:
                    await db.execute("""
                        UPDATE champion_pipeline
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
    from zangetsu_v5.config.settings import Settings
    from zangetsu_v5.config.cost_model import CostModel
    from zangetsu_v5.engine.components.backtester import Backtester
    from zangetsu_v5.engine.components.logger import StructuredLogger

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
                SELECT * FROM champion_pipeline WHERE status = 'CANDIDATE'
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
                row = await db.fetchrow("SELECT * FROM champion_pipeline WHERE id=$1", champ["id"])
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

    await db.close()
    log.info(f"Stopped. a4_processed={a4_processed} a4_passed={a4_passed} a5_matches={a5_matches}")


if __name__ == "__main__":
    asyncio.run(main())
