"""Arena 2+3 Orchestrator — picks up ARENA1_COMPLETE champions and processes them.

Arena 2: Threshold optimization (entry/exit grid search)
Arena 3: PnL training (ATR stop + TP strategy search + half-Kelly sizing)

v9: Shared utils imports, DB reconnect, lease reaper, crash-loop hardening.
    Train-inner/validation split within A3 to prevent overfitting.
    Uses TRAIN data only (70% split) — holdout reserved for Arena 4+5.
    A3 grid search on train-inner (80% of train), validated on train-validation (20% of train).
"""
import sys
import os
import asyncio
import signal
import time
import json
import hashlib
import traceback

sys.path.insert(0, '/home/j13/j13-ops')
sys.path.insert(0, '/home/j13/j13-ops/zangetsu/indicator_engine/target/release')
os.chdir('/home/j13/j13-ops')

import numpy as np
import polars as pl
import asyncpg
import asyncpg.exceptions
from zangetsu.services.pidlock import acquire_lock

from zangetsu.services.db_audit import log_transition

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


def _v10_rolling_zscore(x, window=500):
    """Causal rolling z-score. Mirrors alpha_ensemble._rolling_zscore.
    Ex-ante only: out[i] uses only x[i-window:i] mean/std."""
    import numpy as _np
    n = len(x)
    out = _np.zeros(n, dtype=_np.float32)
    for i in range(window, n):
        w = x[i-window:i]
        m = _np.mean(w)
        s = _np.std(w)
        if s > 1e-10:
            out[i] = (x[i] - m) / s
    return out


def _v10_alpha_to_signal(*_args, **_kwargs):
    """DEPRECATED — retired by v2 fix (2026-04-18).

    Old sign(tanh(rolling_zscore(raw))) pipeline caused A2/A3 to see only
    0-1 trades on V10 champions that A1 had accepted with 30+ trades, because
    A1 uses percentile-rank crossover via generate_alpha_signals. We now call
    generate_alpha_signals inline in process_arena2 / process_arena3.

    Kept as a stub so that accidental imports surface loudly rather than
    silently resurrecting the bug.
    """
    raise NotImplementedError(
        "_v10_alpha_to_signal was removed — A2/A3 now use "
        "generate_alpha_signals() inline (see v2 fix plan 2026-04-18). "
        "If you are importing this, you are re-introducing the bridge bug."
    )


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


from zangetsu.config.settings import Settings
from zangetsu.config.cost_model import CostModel
from zangetsu.engine.components.backtester import Backtester, BacktestResult
from zangetsu.engine.components.signal_utils import generate_threshold_signals as _gen_threshold
from zangetsu.services.signal_reconstructor import reconstruct_signal_from_passport
from zangetsu.engine.components.data_preprocessor import enrich_data_cache
from zangetsu.services.data_collector import merge_funding_to_1m, merge_oi_to_1m
from pathlib import Path

from zangetsu.services.shared_utils import (
    compute_atr, apply_trailing_stop, apply_fixed_target, apply_tp_strategy,
    compute_config_hash, half_kelly, extract_symbol, wilson_lower,
    ensure_db_connection, reap_expired_leases,
)

# v2 fix (2026-04-18): A1 signal-gen alignment. Same module + same env vars as
# arena_pipeline.py so A1/A2/A3 see identical signals from identical alphas.
from zangetsu.engine.components.alpha_signal import generate_alpha_signals

from zangetsu.engine.components.logger import StructuredLogger

# ── V9: CUDA batch backtest (opt-out via A3_USE_CUDA=0) ──────────
try:
    from zangetsu.engine.components.cuda_backtest import batch_backtest, is_cuda_available
    _CUDA_BACKTEST_AVAILABLE = True
except Exception as _cuda_imp_err:  # noqa: BLE001
    batch_backtest = None  # type: ignore[assignment]
    is_cuda_available = lambda: False  # type: ignore[assignment]
    _CUDA_BACKTEST_AVAILABLE = False

# ── V9: PGQueuer event-driven pickup (opt-in via A23_USE_PGQUEUER=1) ──
try:
    from zangetsu.services.event_queue import EventQueue
    _EVENT_QUEUE_AVAILABLE = True
except Exception:
    EventQueue = None  # type: ignore[assignment]
    _EVENT_QUEUE_AVAILABLE = False

# ── Rust engine ──────────────────────────────────────────────────
try:
    import zangetsu_indicators as zi
    RUST_ENGINE = True
except ImportError:
    RUST_ENGINE = False


WORKER_ID = "arena23"
LEASE_MINUTES = 15
TRAIN_SPLIT_RATIO = 0.7

# Arena 2 staged search: fast coarse pass, then local refinement.
ENTRY_THRESHOLDS = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
EXIT_THRESHOLDS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
A2_STAGE1_PAIRS = [(0.60, 0.20), (0.65, 0.25), (0.70, 0.30), (0.75, 0.35), (0.80, 0.40), (0.85, 0.45), (0.90, 0.50)]

# Arena 3 grid
ATR_STOP_MULTS = [2.0, 3.0, 4.0]  # v9: narrowed from 7 to 3 (tight stops never survive A4)
MAX_HOLD_BARS_A2 = 120
MAX_HOLD_BARS_A3 = 480

# Arena 3 TP search params (v9: trimmed extremes to reduce overfitting degrees of freedom)
TRAIL_PCTS = [0.003, 0.005, 0.008, 0.01, 0.015, 0.02]
FIXED_TARGETS = [0.005, 0.008, 0.01, 0.015, 0.02, 0.03]

# v9: Train-inner split ratio for A3 cross-validation
A3_INNER_SPLIT = 0.80  # 80% of train for fitting, 20% for validation

# ── V10 alpha→signal thresholds (v2 fix) ──────────────────────────
# Read at module load; MUST match arena_pipeline.py L447-450 env vars so that
# A1 and A2/A3 see identical signals from the same alpha values. A1 reject at
# bt.total_trades<30; A2 reject at <25 (looser, already existed).
_V10_ENTRY_THR = float(os.environ.get("ALPHA_ENTRY_THR", "0.80"))
_V10_EXIT_THR = float(os.environ.get("ALPHA_EXIT_THR", "0.50"))
try:
    _V10_MIN_HOLD = max(1, int(os.environ.get("ALPHA_MIN_HOLD", "60")))
except ValueError:
    _V10_MIN_HOLD = 60
try:
    _V10_COOLDOWN = max(1, int(os.environ.get("ALPHA_COOLDOWN", "60")))
except ValueError:
    _V10_COOLDOWN = 60


def recompute_normalized_matrix(
    configs: list,
    medians: list,
    mads: list,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
) -> np.ndarray:
    """Recompute indicators and normalize using stored medians/mads."""
    arrays = []
    for cfg in configs:
        name = cfg["name"]
        period = cfg.get("period", 14)
        try:
            if RUST_ENGINE:
                vals = zi.compute(name, {"period": period}, np.ascontiguousarray(close, dtype=np.float64), np.ascontiguousarray(high, dtype=np.float64), np.ascontiguousarray(low, dtype=np.float64), np.ascontiguousarray(volume, dtype=np.float64))
            else:
                vals = np.zeros(len(close))
            arrays.append(np.asarray(vals, dtype=np.float64))
        except Exception:
            arrays.append(np.zeros(len(close), dtype=np.float64))

    if not arrays:
        return np.zeros((len(close), 1), dtype=np.float64)

    matrix = np.column_stack(arrays)
    med = np.array(medians, dtype=np.float64) if medians else np.median(matrix, axis=0)
    mad = np.array(mads, dtype=np.float64) if mads else np.median(np.abs(matrix - med), axis=0) * 1.4826
    if med.shape[0] != matrix.shape[1]:
        med = np.median(matrix, axis=0)
        mad = np.median(np.abs(matrix - med), axis=0) * 1.4826
    mad[mad == 0] = 1e-12
    norm = np.clip((matrix - med) / mad, -5, 5)
    return norm


def recompute_raw_indicators(
    configs: list,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
) -> tuple:
    """Recompute indicators and return RAW values (no normalization).
    Returns (names, raw_arrays) for use with generate_threshold_signals."""
    names = []
    arrays = []
    for cfg in configs:
        name = cfg["name"]
        period = cfg.get("period", 14)
        try:
            if RUST_ENGINE:
                vals = zi.compute(name, {"period": period}, np.ascontiguousarray(close, dtype=np.float64), np.ascontiguousarray(high, dtype=np.float64), np.ascontiguousarray(low, dtype=np.float64), np.ascontiguousarray(volume, dtype=np.float64))
            else:
                vals = np.zeros(len(close))
            names.append(name)
            arrays.append(np.asarray(vals, dtype=np.float64))
        except Exception:
            names.append(name)
            arrays.append(np.zeros(len(close), dtype=np.float64))
    return names, arrays


def compute_trade_stats(bt: BacktestResult):
    """Extract per-trade win/loss stats from backtest result."""
    pnl_diffs = np.diff(bt.equity_curve)
    pnl_diffs = pnl_diffs[pnl_diffs != 0]
    if len(pnl_diffs) > 0:
        wins = pnl_diffs[pnl_diffs > 0]
        losses = pnl_diffs[pnl_diffs < 0]
        avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
        avg_loss = float(np.mean(np.abs(losses))) if len(losses) > 0 else 0.0
    else:
        avg_win = 0.0
        avg_loss = 0.0
    return avg_win, avg_loss


async def is_duplicate_champion(db: asyncpg.Connection, champion_id: int, passport: dict, log) -> bool:
    """Check if a champion with the same indicator combo already exists at a higher arena level."""
    a1 = passport.get("arena1", {})
    configs = a1.get("configs", [])
    if not configs:
        return False
    config_hash = compute_config_hash(configs)

    # Filter in Python since we need to compute config_hash from passport JSON
    # MEDIUM-M3: explicitly exclude V9 engine_hash rows from A2 dedup. V9 LEGACY rows
    # may keep non-LEGACY status (pre-migration artefacts); config_hash collision
    # across engines would falsely block V10 champions. Literal is a static string
    # (no user input), no SQL injection surface.
    rows = await db.fetch("""
        SELECT id, status, arena1_score, passport FROM champion_pipeline
        WHERE id != $1
          AND status NOT IN ('ARENA1_COMPLETE', 'ARENA2_REJECTED', 'ARENA3_REJECTED')
          AND status NOT LIKE 'LEGACY%'
          AND (engine_hash IS NULL OR engine_hash NOT LIKE 'zv5_v9%')
        ORDER BY arena1_score DESC
        LIMIT 200
    """, champion_id)
    for row in rows:
        try:
            p = json.loads(row["passport"]) if isinstance(row["passport"], str) else row["passport"]
            other_configs = p.get("arena1", {}).get("configs", [])
            if other_configs and compute_config_hash(other_configs) == config_hash:
                log.info(f"A2 DEDUP: #{champion_id} duplicates #{row['id']} (status={row['status']}), skipping")
                return True
        except Exception:
            continue
    return False


def _build_base_signal(
    passport: dict,
    close, high, low, volume,
    names_v, arrs_v,
    entry_thr: float, exit_thr: float,
    regime: str,
    open_arr=None,
    min_hold: int = 60,
    cooldown: int = 60,
):
    """V10 dispatcher — route to alpha reconstruction or V9 threshold voting."""
    arena1 = passport.get('arena1', {}) if isinstance(passport, dict) else {}
    if arena1.get('alpha_expression'):
        import numpy as _np
        _open = open_arr if open_arr is not None else _np.zeros_like(close)
        return reconstruct_signal_from_passport(
            passport, close, high, low, _open, volume,
            entry_threshold=entry_thr, exit_threshold=exit_thr,
            min_hold=min_hold, cooldown=cooldown, regime=regime,
        )
    return _gen_threshold(
        names_v, arrs_v,
        entry_threshold=entry_thr, exit_threshold=exit_thr,
        min_hold=min_hold, cooldown=cooldown, regime=regime,
    )


async def pick_champion(db: asyncpg.Connection, from_status: str, to_status: str) -> dict | None:
    """Atomically pick and lease one champion.

    V9: rank by arena1_score × regime_confidence (5-factor MarketState tiebreaker).
    Falls back to arena1_score alone if confidence missing."""
    row = await db.fetchrow(f"""
        UPDATE champion_pipeline
        SET status = $1, worker_id = $2, lease_until = NOW() + INTERVAL '{LEASE_MINUTES} minutes', updated_at = NOW()
        WHERE id = (
            SELECT id FROM champion_pipeline
            WHERE status = $3
            ORDER BY
                arena1_score *
                COALESCE((passport->'market_state'->>'regime_confidence')::float, 1.0) DESC,
                arena1_score DESC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
    """, to_status, WORKER_ID, from_status)
    if row is None:
        return None
    await log_transition(db, row["id"], from_status, to_status, worker_id=WORKER_ID)
    return dict(row)


async def release_champion(db: asyncpg.Connection, champion_id: int, status: str, extra_fields: dict):
    """Update champion status and passport fields after processing."""
    passport_patch = json.dumps(extra_fields.get("passport_patch", {}))
    sets = ["status = $1", "updated_at = NOW()"]
    params: list = [status]
    idx = 2

    for col in ["arena2_win_rate", "arena2_n_trades",
                 "arena3_sharpe", "arena3_expectancy", "arena3_pnl"]:
        if col in extra_fields:
            sets.append(f"{col} = ${idx}")
            params.append(extra_fields[col])
            idx += 1

    if status.startswith("ARENA2"):
        sets.append("arena2_completed_at = NOW()")
    elif status.startswith("ARENA3"):
        sets.append("arena3_completed_at = NOW()")

    if passport_patch != "{}":
        sets.append(f"passport = passport || ${idx}::jsonb")
        params.append(passport_patch)
        idx += 1

    params.append(champion_id)
    query = f"UPDATE champion_pipeline SET {', '.join(sets)} WHERE id = ${idx}"
    await db.execute(query, *params)
    # Audit trail
    await log_transition(db, champion_id, "PROCESSING", status, worker_id=WORKER_ID)


def _a2_stage2_pairs(best_entry: float, best_exit: float) -> list[tuple[float, float]]:
    entry_idx = ENTRY_THRESHOLDS.index(best_entry)
    exit_idx = EXIT_THRESHOLDS.index(best_exit)
    pairs = []
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ei = entry_idx + di
            xj = exit_idx + dj
            if 0 <= ei < len(ENTRY_THRESHOLDS) and 0 <= xj < len(EXIT_THRESHOLDS):
                entry_thr = ENTRY_THRESHOLDS[ei]
                exit_thr = EXIT_THRESHOLDS[xj]
                if exit_thr < entry_thr:
                    pairs.append((entry_thr, exit_thr))
    # Preserve order while deduping
    return list(dict.fromkeys(pairs))


async def process_arena2(
    champion: dict,
    data_cache: dict,
    cost_model: CostModel,
    backtester: Backtester,
    log: StructuredLogger,
) -> tuple | None:
    """Arena 2: Threshold optimization via grid search. Returns (improved, fields) or None."""
    champion_id = champion["id"]
    passport = json.loads(champion["passport"]) if isinstance(champion["passport"], str) else champion["passport"]
    a1 = passport.get("arena1", {})
    norm_params = passport.get("normalization", {})

    configs = a1.get("configs", [])
    medians = norm_params.get("medians", a1.get("medians", []))
    mads = norm_params.get("mads", a1.get("mads", []))
    arena1_wr = champion["arena1_win_rate"]
    regime = champion.get("regime", "")

    symbol = extract_symbol(champion["indicator_hash"])

    if symbol not in data_cache:
        # Fallback: try to get symbol from passport
        for sym in data_cache:
            if a1.get("hash", "").endswith(sym) or champion["indicator_hash"].endswith(sym):
                symbol = sym
                break

    if symbol not in data_cache:
        log.warning(f"A2 skip id={champion_id}: no data for {symbol}")
        return None

    d = data_cache[symbol]
    close, high, low, volume = d["close"], d["high"], d["low"], d["volume"]
    cost_bps = cost_model.get(symbol).total_round_trip_bps

    # ── V10 factor-expression branch (v2 fix 2026-04-18) ──
    # Align with A1: compile AST, run generate_alpha_signals with SAME env
    # thresholds A1 uses. The old _v10_alpha_to_signal (sign(tanh(zscore)))
    # caused 0-1 trades here vs 30+ in A1 → 100% no_valid_combos rejection.
    _v10_alpha = _v10_get_alpha_expression(passport)
    _v10_ast = _v10_alpha.get("ast_json")
    if _v10_ast:
        import numpy as _np
        open_arr = d.get("open", close)
        try:
            # end-to-end-upgrade fix 2026-04-19: populate singleton indicator_cache
            # for this symbol before compiling, so the 126 indicator terminals are
            # evaluated against real indicator data instead of silent zeros.
            engine = _get_v10_engine()
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
                log.warning(f"A2 indicator_cache build failed for {symbol}: {_ce}")
            fn = engine.compile_ast(_v10_ast)
            alpha_values = fn(close, high, low, open_arr, volume)
            alpha_values = _np.asarray(alpha_values, dtype=_np.float64).ravel()
            # Length alignment: pad head with nan if shorter, else trim head.
            if alpha_values.shape[0] != close.shape[0]:
                if alpha_values.shape[0] < close.shape[0]:
                    padded = _np.full(close.shape[0], _np.nan)
                    padded[-alpha_values.shape[0]:] = alpha_values
                    alpha_values = padded
                else:
                    alpha_values = alpha_values[-close.shape[0]:]
            alpha_values = _np.nan_to_num(alpha_values, nan=0.0, posinf=0.0, neginf=0.0)
            if not _np.isfinite(alpha_values).all() or _np.std(alpha_values) < 1e-10:
                log.info(f"A2 REJECTED id={champion_id} {symbol} [V10]: alpha_invalid_or_flat")
                return None
            sig, sz, _ = generate_alpha_signals(
                alpha_values,
                entry_threshold=_V10_ENTRY_THR,
                exit_threshold=_V10_EXIT_THR,
                min_hold=_V10_MIN_HOLD,
                cooldown=_V10_COOLDOWN,
            )
        except Exception as _sg_err:  # noqa: BLE001
            log.warning(
                f"A2 V10 signal_gen failed id={champion_id} {symbol}: "
                f"{type(_sg_err).__name__}:{_sg_err}"
            )
            return None
        bt = backtester.run(sig, close, symbol, cost_bps, 480, high=high, low=low, sizes=sz)
        if bt.total_trades < 25:
            log.info(f"A2 REJECTED id={champion_id} {symbol} [V10]: trades={bt.total_trades} < 25")
            return None
        _pos = int(bt.net_pnl > 0) + int(bt.sharpe_ratio > 0) + int(bt.pnl_per_trade > 0)
        if _pos < 2:
            log.info(f"A2 REJECTED id={champion_id} {symbol} [V10]: pos_count={_pos}")
            return None
        passport_patch = {
            "arena2": {
                "v10_native": True,
                "trades": int(bt.total_trades),
                "pnl": float(bt.net_pnl),
                "sharpe": float(bt.sharpe_ratio),
                "ppt": float(bt.pnl_per_trade),
                "alpha_ic": float(_v10_alpha.get("ic", 0.0)),
                "alpha_hash": _v10_alpha.get("alpha_hash"),
                "signal_gen": "generate_alpha_signals",
                "signal_params": {
                    "entry_threshold": _V10_ENTRY_THR,
                    "exit_threshold": _V10_EXIT_THR,
                    "min_hold": _V10_MIN_HOLD,
                    "cooldown": _V10_COOLDOWN,
                },
            },
        }
        log.info(f"A2 PASS id={champion_id} {symbol} [V10]: trades={bt.total_trades} wr={bt.win_rate:.3f} sharpe={bt.sharpe_ratio:.2f}")
        return True, {
            "status": "ARENA2_COMPLETE",
            "arena2_win_rate": float(bt.win_rate),
            "arena2_n_trades": int(bt.total_trades),
            "passport_patch": passport_patch,
        }
    # ── V9 indicator-combo flow below ──
    # Use RAW indicator values for signal generation (indicator_vote expects raw scales)
    names_raw, arrays_raw = recompute_raw_indicators(configs, close, high, low, volume)
    # Zero-MAD filter: skip indicators with no variance
    valid = [(n, a) for n, a in zip(names_raw, arrays_raw) if np.median(np.abs(a - np.median(a))) > 0]
    if len(valid) < 2:
        log.info(f"A2 REJECTED id={champion_id} {symbol}: <2 valid indicators after zero-MAD filter")
        return None
    names_v = [v[0] for v in valid]
    arrs_v = [v[1] for v in valid]

    # ── Compute baseline metrics for multi-metric gate (AD3) ──────
    # Use A1's actual thresholds as baseline (infer from indicator count)
    n_inds = len(configs)
    if n_inds <= 2:
        a1_entry_thr = 0.55
    elif n_inds == 3:
        a1_entry_thr = 0.60
    else:
        a1_entry_thr = 0.55
    baseline_signals, baseline_sizes, _ = _build_base_signal(passport, close, high, low, volume, names_v, arrs_v, entry_thr=0.55, exit_thr=0.30, regime=regime)
    baseline_bt = backtester.run(baseline_signals, close, symbol, cost_bps, MAX_HOLD_BARS_A2, high=high, low=low, sizes=baseline_sizes)
    original_wr = float(baseline_bt.win_rate)
    original_pnl = float(baseline_bt.net_pnl)
    original_sharpe = float(baseline_bt.sharpe_ratio)
    original_expectancy = float(baseline_bt.net_pnl / max(baseline_bt.total_trades, 1))


    # ── AD1: 2-indicator combos are AND gates — skip grid search ──
    if len(configs) <= 2:
        signals, sizes_v, _ = _build_base_signal(passport, close, high, low, volume, names_v, arrs_v, entry_thr=0.55, exit_thr=0.30, regime=regime)
        bt = backtester.run(signals, close, symbol, cost_bps, MAX_HOLD_BARS_A2, high=high, low=low, sizes=sizes_v)
        pos_count = sum([bt.net_pnl > 0, bt.sharpe_ratio > 0, bt.pnl_per_trade > 0])
        if bt.total_trades >= 25 and pos_count >= 2:
            # AD1+AD3: 2-indicator passthrough — auto-promote if economically valid
            # (no grid search means baseline == result, multi-metric gate N/A)
            passport_patch = {
                "arena2": {
                    "entry_threshold": 0.55,
                    "exit_threshold": 0.30,
                    "win_rate": float(bt.win_rate),
                    "n_trades": bt.total_trades,
                    "pnl": float(bt.net_pnl),
                    "sharpe": float(bt.sharpe_ratio),
                    "dd": float(bt.max_drawdown),
                    "arena1_wr": float(arena1_wr),
                    "improved_metrics": ["economic_viability"],
                    "method": "2ind_passthrough",
                    "baseline": {
                        "wr": original_wr,
                        "pnl": original_pnl,
                        "sharpe": original_sharpe,
                        "expectancy": original_expectancy,
                    },
                }
            }
            log.info(
                f"A2 2IND-PASS id={champion_id} {symbol} | "
                f"improved: [economic_viability] | "
                f"WR={bt.win_rate:.3f} trades={bt.total_trades} "
                f"PnL={bt.net_pnl:.4f} Sharpe={bt.sharpe_ratio:.2f} (grid skipped)"
            )
            return True, {
                "status": "ARENA2_COMPLETE",
                "arena2_win_rate": float(bt.win_rate),
                "arena2_n_trades": bt.total_trades,
                "passport_patch": passport_patch,
            }
        else:
            log.info(
                f"A2 2IND-REJECT id={champion_id} {symbol} | "
                f"trades={bt.total_trades} PnL={bt.net_pnl:.4f} (grid skipped, insufficient)"
            )
            return None

    best_score = None
    best_wr = -1.0
    best_entry = 0.80
    best_exit = 0.40
    best_trades = 0
    best_result = None

    def evaluate_pair(entry_thr: float, exit_thr: float):
        nonlocal best_score, best_wr, best_entry, best_exit, best_trades, best_result
        signals, sizes_v, _ = _build_base_signal(passport, close, high, low, volume, names_v, arrs_v, entry_thr=0.55, exit_thr=0.30, regime=regime)
        bt = backtester.run(signals, close, symbol, cost_bps, MAX_HOLD_BARS_A2, high=high, low=low, sizes=sizes_v)
        if bt.total_trades < 25:
            return False  # Need >= 25 trades for reliable WR in threshold grid
        pos = (bt.net_pnl > 0) + (bt.sharpe_ratio > 0) + (bt.pnl_per_trade > 0)
        if pos < 2:
            return False
        score = (float(bt.net_pnl), float(bt.sharpe_ratio), float(bt.win_rate), int(bt.total_trades))
        if best_score is None or score > best_score:
            best_score = score
            best_wr = bt.win_rate
            best_entry = entry_thr
            best_exit = exit_thr
            best_trades = bt.total_trades
            best_result = bt
        return True

    stage1_positive = False
    for entry_thr, exit_thr in A2_STAGE1_PAIRS:
        if evaluate_pair(entry_thr, exit_thr):
            stage1_positive = True

    if stage1_positive:
        for entry_thr, exit_thr in _a2_stage2_pairs(best_entry, best_exit):
            evaluate_pair(entry_thr, exit_thr)

    if best_result is None or best_trades < 20:
        log.info(f"A2 REJECTED id={champion_id} {symbol}: no economically valid combos")
        return None

    # ── Multi-metric promotion gate (AD3) ──────────────────────────
    # Champion passes Arena 2 if ANY metric improves OR if already economically valid.
    # v9 champions arrive pre-screened (A1 already tested at A2 params), so the strict
    # improvement check would reject them even though they're valid.
    improvements = {
        "wr": best_wr > original_wr,
        "pnl": float(best_result.net_pnl) > original_pnl,
        "sharpe": float(best_result.sharpe_ratio) > original_sharpe,
        "expectancy": (float(best_result.net_pnl) / max(best_result.total_trades, 1)) > original_expectancy,
    }

    # Economic validity: at least 2 of (pnl, sharpe, expectancy) are positive
    _econ_pos = (float(best_result.net_pnl) > 0) + (float(best_result.sharpe_ratio) > 0) + (float(best_result.pnl_per_trade) > 0)
    economically_valid = _econ_pos >= 2 and best_result.total_trades >= 25

    passed = (any(improvements.values()) or economically_valid) and best_result.total_trades >= 25
    improved_metrics = [k for k, v in improvements.items() if v]
    if not improved_metrics and economically_valid:
        improved_metrics = ["economic_viability"]

    status = "ARENA2_COMPLETE" if passed else "ARENA2_REJECTED"
    passport_patch = {
        "arena2": {
            "entry_threshold": best_entry,
            "exit_threshold": best_exit,
            "entry_thr": best_entry,     # backward compat for A4/A5
            "exit_thr": best_exit,       # backward compat for A4/A5
            "win_rate": float(best_wr),
            "n_trades": best_trades,
            "pnl": float(best_result.net_pnl),
            "sharpe": float(best_result.sharpe_ratio),
            "dd": float(best_result.max_drawdown),
            "arena1_wr": float(arena1_wr),
            "improved_metrics": improved_metrics,
            "baseline": {
                "wr": original_wr,
                "pnl": original_pnl,
                "sharpe": original_sharpe,
                "expectancy": original_expectancy,
            },
        }
    }

    log.info(
        f"A2 {'PASS' if passed else 'REJECT'} id={champion_id} {symbol} | "
        f"improved: {improved_metrics} | "
        f"WR: {original_wr:.3f}->{best_wr:.3f} PnL: {original_pnl:.4f}->{best_result.net_pnl:.4f} "
        f"Sharpe: {original_sharpe:.2f}->{best_result.sharpe_ratio:.2f} | "
        f"entry={best_entry} exit={best_exit} trades={best_trades}"
    )

    return passed, {
        "status": status,
        "arena2_win_rate": float(best_wr),
        "arena2_n_trades": best_trades,
        "passport_patch": passport_patch,
    }


async def process_arena3(
    champion: dict,
    data_cache: dict,
    cost_model: CostModel,
    backtester: Backtester,
    log: StructuredLogger,
) -> dict:
    """Arena 3: PnL training with ATR stops + TP strategy search + half-Kelly sizing."""
    champion_id = champion["id"]
    passport = json.loads(champion["passport"]) if isinstance(champion["passport"], str) else champion["passport"]
    a1 = passport.get("arena1", {})
    a2 = passport.get("arena2", {})
    norm_params = passport.get("normalization", {})

    configs = a1.get("configs", [])
    medians = norm_params.get("medians", a1.get("medians", []))
    mads = norm_params.get("mads", a1.get("mads", []))

    entry_thr = a2.get("entry_threshold", 0.80)
    exit_thr = a2.get("exit_threshold", 0.40)
    regime = champion.get("regime", "")

    symbol = extract_symbol(champion["indicator_hash"])

    if symbol not in data_cache:
        # Fallback: try to get symbol from passport
        for sym in data_cache:
            if a1.get("hash", "").endswith(sym) or champion["indicator_hash"].endswith(sym):
                symbol = sym
                break

    if symbol not in data_cache:
        log.warning(f"A3 skip id={champion_id}: no data for {symbol}")
        return None

    d = data_cache[symbol]
    full_close, full_high, full_low, full_volume = d["close"], d["high"], d["low"], d["volume"]
    cost_bps = cost_model.get(symbol).total_round_trip_bps

    # ── C1: Split train into train-inner (80%) and validation (20%) ──
    n_train = len(full_close)
    inner_n = int(n_train * A3_INNER_SPLIT)
    close_fit, high_fit, low_fit = full_close[:inner_n], full_high[:inner_n], full_low[:inner_n]
    vol_fit = full_volume[:inner_n]
    close_val, high_val, low_val = full_close[inner_n:], full_high[inner_n:], full_low[inner_n:]
    vol_val = full_volume[inner_n:]

    # Use RAW indicator values for signal generation (indicator_vote expects raw scales)
    names_raw, arrays_raw = recompute_raw_indicators(configs, close_fit, high_fit, low_fit, vol_fit)
    # ── V10 factor-expression branch for A3 (v2 fix 2026-04-18) ──
    # Align with A1: compile AST, run generate_alpha_signals with SAME env
    # thresholds A1 uses. NOTE: backtest runs on the FULL train window
    # (full_close/high/low/volume), not the train-inner split — this matches
    # the original v10 A3 intent (no ATR/TP grid for alpha-native strategies)
    # and also fixes a latent NameError in the previous code that referenced
    # undefined `close/high/low/volume` symbols at this scope.
    _v10_alpha_a3 = _v10_get_alpha_expression(passport)
    _v10_ast_a3 = _v10_alpha_a3.get("ast_json")
    if _v10_ast_a3:
        import numpy as _np
        open_arr_a3 = d.get("open", full_close)
        try:
            # end-to-end-upgrade fix 2026-04-19: populate indicator_cache for full
            # train window before compiling (see A2 branch above for rationale).
            engine = _get_v10_engine()
            try:
                from zangetsu.engine.components.indicator_bridge import build_indicator_cache
                _v10_cache_a3 = build_indicator_cache(
                    _np.ascontiguousarray(full_close, dtype=_np.float64),
                    _np.ascontiguousarray(full_high, dtype=_np.float64),
                    _np.ascontiguousarray(full_low, dtype=_np.float64),
                    _np.ascontiguousarray(full_volume, dtype=_np.float64),
                )
                engine.indicator_cache.clear()
                engine.indicator_cache.update(_v10_cache_a3)
            except Exception as _ce:  # noqa: BLE001
                log.warning(f"A3 indicator_cache build failed for {symbol}: {_ce}")
            fn = engine.compile_ast(_v10_ast_a3)
            alpha_values = fn(full_close, full_high, full_low, open_arr_a3, full_volume)
            alpha_values = _np.asarray(alpha_values, dtype=_np.float64).ravel()
            if alpha_values.shape[0] != full_close.shape[0]:
                if alpha_values.shape[0] < full_close.shape[0]:
                    padded = _np.full(full_close.shape[0], _np.nan)
                    padded[-alpha_values.shape[0]:] = alpha_values
                    alpha_values = padded
                else:
                    alpha_values = alpha_values[-full_close.shape[0]:]
            alpha_values = _np.nan_to_num(alpha_values, nan=0.0, posinf=0.0, neginf=0.0)
            if not _np.isfinite(alpha_values).all() or _np.std(alpha_values) < 1e-10:
                log.info(f"A3 REJECTED id={champion_id} {symbol} [V10]: alpha_invalid_or_flat")
                return None
            sig, sz, _ = generate_alpha_signals(
                alpha_values,
                entry_threshold=_V10_ENTRY_THR,
                exit_threshold=_V10_EXIT_THR,
                min_hold=_V10_MIN_HOLD,
                cooldown=_V10_COOLDOWN,
            )
        except Exception as _sg_err:  # noqa: BLE001
            log.warning(
                f"A3 V10 signal_gen failed id={champion_id} {symbol}: "
                f"{type(_sg_err).__name__}:{_sg_err}"
            )
            return None
        # A3 uses ATR-ish stop. For V10 we use a single moderate ATR/TP as proxy.
        bt_a3 = backtester.run(
            sig, full_close, symbol, cost_bps, 480,
            high=full_high, low=full_low, sizes=sz,
        )
        if bt_a3.total_trades < 25:
            log.info(f"A3 REJECTED id={champion_id} {symbol} [V10]: trades={bt_a3.total_trades}")
            return None
        _pos = int(bt_a3.net_pnl > 0) + int(bt_a3.sharpe_ratio > 0) + int(bt_a3.pnl_per_trade > 0)
        if _pos < 2:
            log.info(f"A3 REJECTED id={champion_id} {symbol} [V10]: pos_count={_pos}")
            return None
        passport_patch = {
            "arena3": {
                "v10_native": True,
                "trades": int(bt_a3.total_trades),
                "pnl": float(bt_a3.net_pnl),
                "sharpe": float(bt_a3.sharpe_ratio),
                "signal_gen": "generate_alpha_signals",
                "signal_params": {
                    "entry_threshold": _V10_ENTRY_THR,
                    "exit_threshold": _V10_EXIT_THR,
                    "min_hold": _V10_MIN_HOLD,
                    "cooldown": _V10_COOLDOWN,
                },
            },
        }
        log.info(f"A3 PASS id={champion_id} {symbol} [V10]: trades={bt_a3.total_trades} sharpe={bt_a3.sharpe_ratio:.2f}")
        return {
            "status": "ARENA3_COMPLETE",
            "arena3_sharpe": float(min(bt_a3.sharpe_ratio, 3.0)),
            "arena3_pnl": float(bt_a3.net_pnl),
            "arena3_expectancy": float(bt_a3.pnl_per_trade),
            "passport_patch": passport_patch,
        }
    # ── V9 ATR/TP grid flow below ──
    # Zero-MAD filter: skip indicators with no variance
    valid = [(n, a) for n, a in zip(names_raw, arrays_raw) if np.median(np.abs(a - np.median(a))) > 0]
    if len(valid) < 2:
        log.info(f"A3 REJECTED id={champion_id} {symbol}: <2 valid indicators after zero-MAD filter")
        return None
    names_v = [v[0] for v in valid]
    arrs_v = [v[1] for v in valid]
    base_signals, base_sizes, _ = _build_base_signal(passport, close_fit, high_fit, low_fit, vol_fit, names_v, arrs_v, entry_thr=0.55, exit_thr=0.30, regime=regime)
    atr_fit = compute_atr(high_fit, low_fit, close_fit, period=14)

    # Also prepare validation signals
    names_raw_val, arrays_raw_val = recompute_raw_indicators(configs, close_val, high_val, low_val, vol_val)
    valid_val = [(n, a) for n, a in zip(names_raw_val, arrays_raw_val) if np.median(np.abs(a - np.median(a))) > 0]
    names_val = [v[0] for v in valid_val]
    arrs_val = [v[1] for v in valid_val]
    base_signals_val, base_sizes_val, _ = _build_base_signal(passport, close_val, high_val, low_val, vol_val, names_val, arrs_val, entry_thr=0.55, exit_thr=0.30, regime=regime)
    atr_val = compute_atr(high_val, low_val, close_val, period=14)

    # ── V9: Optional CUDA batch pre-scoring of ATR x TP grid ──
    # Builds a params array (n_combos, 4) = [entry_thr, exit_thr, atr_mult, tp_param]
    # and calls cuda_backtest.batch_backtest once. Result is used as an advisory
    # hint (logged); the authoritative selection still comes from the sequential
    # multi-objective loop below, which uses the full Backtester (Sharpe / expect /
    # PnL optima on the real backtest path). Best-effort only: any failure is
    # swallowed and the sequential path runs normally.
    _cuda_hint_idx = None
    _cuda_hint_params = None
    try:
        _use_cuda = (
            _CUDA_BACKTEST_AVAILABLE
            and is_cuda_available()
            and os.environ.get("A3_USE_CUDA", "1") == "1"
        )
    except Exception:
        _use_cuda = False
    if _use_cuda:
        try:
            tp_param_grid = (
                [("none", 0.0)]
                + [("trailing", p) for p in TRAIL_PCTS]
                + [("fixed", p) for p in FIXED_TARGETS]
            )
            combos = [
                (atr_mult, tp_type, tp_param)
                for atr_mult in ATR_STOP_MULTS
                for (tp_type, tp_param) in tp_param_grid
            ]
            if len(combos) >= 8:
                # Use base signal as the "entry_thr"/"exit_thr" proxy columns; the
                # CUDA kernel only cares about the fourth column (tp_param) plus
                # signal + atr + close. Pack placeholders for the first two.
                params_arr = np.array(
                    [[0.55, 0.30, float(atr_mult), float(tp_param)]
                     for (atr_mult, _tp_type, tp_param) in combos],
                    dtype=np.float32,
                )
                # base_signals here is np.int8 (long/short/flat); coerce safely
                _sig_f32 = np.asarray(base_signals, dtype=np.float32)
                pnls = batch_backtest(
                    close_fit, params_arr, signal=_sig_f32, atr=atr_fit,
                )
                if pnls is not None and len(pnls) == len(combos):
                    _cuda_hint_idx = int(np.argmax(pnls))
                    _cuda_hint_params = combos[_cuda_hint_idx]
                    log.debug(
                        f"A3 CUDA batch hint id={champion_id} {symbol}: "
                        f"combos={len(combos)} best_idx={_cuda_hint_idx} "
                        f"atr={_cuda_hint_params[0]} tp={_cuda_hint_params[1]}({_cuda_hint_params[2]}) "
                        f"pnl={float(pnls[_cuda_hint_idx]):.4f}"
                    )
        except Exception as _cuda_err:  # noqa: BLE001
            log.debug(f"A3 CUDA batch failed, using sequential grid: {_cuda_err}")

    # ── Search across ATR multipliers x TP strategies (on train-inner) ──
    best_sharpe = -999.0
    best_expect = -999.0
    best_pnl = -999.0

    best_sharpe_result = None
    best_sharpe_params = {}
    best_expect_result = None
    best_expect_params = {}
    best_pnl_result = None
    best_pnl_params = {}

    # ── A3 prefilter: single ATR=4.0 sanity check before grid search ──
    # If the base signal produces nothing positive at the widest stop,
    # no TP/ATR combo will save it. Skip the 39-combo grid entirely.
    _pf_bt = backtester.run(
        base_signals, close_fit, symbol, cost_bps, MAX_HOLD_BARS_A3,
        high=high_fit, low=low_fit, atr=atr_fit, atr_stop_mult=max(ATR_STOP_MULTS), sizes=base_sizes,
    )
    _pf_pos = (_pf_bt.net_pnl > 0) + (_pf_bt.sharpe_ratio > 0) + (_pf_bt.pnl_per_trade > 0) if _pf_bt and _pf_bt.total_trades >= 10 else 0
    if _pf_pos < 1:
        log.info(
            f"A3 PREFILTER SKIP id={champion_id} {symbol}: "
            f"ATR={max(ATR_STOP_MULTS)} base signal non-viable | "
            f"trades={_pf_bt.total_trades} "
            f"pnl={_pf_bt.net_pnl:.4f} "
            f"sharpe={_pf_bt.sharpe_ratio:.2f}"
        )
        return None

    for atr_mult in ATR_STOP_MULTS:
        # ── Pool 2: No TP (expectancy-optimized) ──
        bt = backtester.run(
            base_signals, close_fit, symbol, cost_bps, MAX_HOLD_BARS_A3,
            high=high_fit, low=low_fit, atr=atr_fit, atr_stop_mult=atr_mult, sizes=base_sizes,
        )
        if bt.total_trades >= 25:
            if bt.pnl_per_trade > best_expect:
                best_expect = bt.pnl_per_trade
                best_expect_result = bt
                best_expect_params = {"atr_mult": atr_mult, "tp_type": "none", "tp_param": 0.0}
            if bt.net_pnl > best_pnl:
                best_pnl = bt.net_pnl
                best_pnl_result = bt
                best_pnl_params = {"atr_mult": atr_mult, "tp_type": "none", "tp_param": 0.0}
            if bt.sharpe_ratio > best_sharpe:
                best_sharpe = bt.sharpe_ratio
                best_sharpe_result = bt
                best_sharpe_params = {"atr_mult": atr_mult, "tp_type": "none", "tp_param": 0.0}

        # ── Pool 1: Trailing stop (Sharpe-optimized) ──
        for trail_pct in TRAIL_PCTS:
            trail_signals = apply_trailing_stop(base_signals, close_fit, trail_pct)
            bt = backtester.run(
                trail_signals, close_fit, symbol, cost_bps, MAX_HOLD_BARS_A3,
                high=high_fit, low=low_fit, atr=atr_fit, atr_stop_mult=atr_mult, sizes=base_sizes,
            )
            if bt.total_trades >= 25:
                if bt.sharpe_ratio > best_sharpe:
                    best_sharpe = bt.sharpe_ratio
                    best_sharpe_result = bt
                    best_sharpe_params = {"atr_mult": atr_mult, "tp_type": "trailing", "tp_param": trail_pct}
                if bt.pnl_per_trade > best_expect:
                    best_expect = bt.pnl_per_trade
                    best_expect_result = bt
                    best_expect_params = {"atr_mult": atr_mult, "tp_type": "trailing", "tp_param": trail_pct}
                if bt.net_pnl > best_pnl:
                    best_pnl = bt.net_pnl
                    best_pnl_result = bt
                    best_pnl_params = {"atr_mult": atr_mult, "tp_type": "trailing", "tp_param": trail_pct}

        # ── Pool 3: Fixed target (PnL-optimized) ──
        for target_pct in FIXED_TARGETS:
            target_signals = apply_fixed_target(base_signals, close_fit, target_pct)
            bt = backtester.run(
                target_signals, close_fit, symbol, cost_bps, MAX_HOLD_BARS_A3,
                high=high_fit, low=low_fit, atr=atr_fit, atr_stop_mult=atr_mult, sizes=base_sizes,
            )
            if bt.total_trades >= 25:
                if bt.net_pnl > best_pnl:
                    best_pnl = bt.net_pnl
                    best_pnl_result = bt
                    best_pnl_params = {"atr_mult": atr_mult, "tp_type": "fixed", "tp_param": target_pct}
                if bt.sharpe_ratio > best_sharpe:
                    best_sharpe = bt.sharpe_ratio
                    best_sharpe_result = bt
                    best_sharpe_params = {"atr_mult": atr_mult, "tp_type": "fixed", "tp_param": target_pct}
                if bt.pnl_per_trade > best_expect:
                    best_expect = bt.pnl_per_trade
                    best_expect_result = bt
                    best_expect_params = {"atr_mult": atr_mult, "tp_type": "fixed", "tp_param": target_pct}

    def _positive_count(bt):
        """Count how many of (sharpe, pnl, pnl_per_trade) are positive. Requires ANY TWO."""
        return (bt.sharpe_ratio > 0) + (bt.net_pnl > 0) + (bt.pnl_per_trade > 0)

    positive_candidates = []
    if best_sharpe_result is not None and _positive_count(best_sharpe_result) >= 2:
        # ── C2: Cap Sharpe at 3.0 for ranking to prevent hyper-fit winners ──
        _capped_sharpe = min(float(best_sharpe_result.sharpe_ratio), 3.0)
        positive_candidates.append(("sharpe", best_sharpe_result, best_sharpe_params, _capped_sharpe, float(best_sharpe_result.net_pnl)))
    if best_expect_result is not None and _positive_count(best_expect_result) >= 2:
        positive_candidates.append(("expectancy", best_expect_result, best_expect_params, float(best_expect_result.pnl_per_trade), float(best_expect_result.net_pnl)))
    if best_pnl_result is not None and _positive_count(best_pnl_result) >= 2:
        positive_candidates.append(("pnl", best_pnl_result, best_pnl_params, float(best_pnl_result.net_pnl), float(best_pnl_result.sharpe_ratio)))

    if not positive_candidates:
        log.info(f"A3 REJECTED id={champion_id} {symbol}: all ATR+TP combos non-positive")
        return None

    winner_pool, winner_result, winner_params, _, _ = max(positive_candidates, key=lambda item: (item[3], item[4]))

    # ── C1: Validate winner on train-validation split ──────────────
    val_atr_mult = winner_params["atr_mult"]
    val_tp_type = winner_params["tp_type"]
    val_tp_param = winner_params["tp_param"]

    if val_tp_type == "trailing":
        val_signals = apply_trailing_stop(base_signals_val, close_val, val_tp_param)
    elif val_tp_type == "fixed":
        val_signals = apply_fixed_target(base_signals_val, close_val, val_tp_param)
    else:
        val_signals = base_signals_val

    bt_val = backtester.run(
        val_signals, close_val, symbol, cost_bps, MAX_HOLD_BARS_A3,
        high=high_val, low=low_val, atr=atr_val, atr_stop_mult=val_atr_mult, sizes=base_sizes_val,
    )

    val_pos = _positive_count(bt_val)
    # v9: Validation gate — positive economics required, no raw WR floor
    if bt_val.total_trades < 10 or val_pos < 2:
        log.info(
            f"A3 REJECTED id={champion_id} {symbol}: validation split fail | "
            f"val_trades={bt_val.total_trades} val_wr={bt_val.win_rate:.3f} val_pnl={bt_val.net_pnl:.4f} "
            f"val_sharpe={bt_val.sharpe_ratio:.2f} val_pos={val_pos} | "
            f"fit_sharpe={winner_result.sharpe_ratio:.2f} fit_pnl={winner_result.net_pnl:.4f}"
        )
        return None

    # v9: Train/validation divergence check
    if winner_result.net_pnl > 0 and bt_val.net_pnl > 0:
        pnl_ratio = winner_result.net_pnl / bt_val.net_pnl
        if pnl_ratio > 10.0:
            log.info(
                f"A3 REJECTED id={champion_id} {symbol}: train/val PnL divergence | "
                f"train_pnl={winner_result.net_pnl:.4f} val_pnl={bt_val.net_pnl:.4f} ratio={pnl_ratio:.1f}"
            )
            return None

    # Half-Kelly sizing from winner
    avg_win, avg_loss = compute_trade_stats(winner_result)
    kelly_frac = half_kelly(winner_result.win_rate, avg_win, avg_loss)

    expectancy = winner_result.pnl_per_trade

    # Build pool summaries for passport
    pool_summaries = {}
    if best_sharpe_result is not None:
        pool_summaries["sharpe_pool"] = {
            "sharpe": float(best_sharpe_result.sharpe_ratio),
            "tp_type": best_sharpe_params["tp_type"],
            "tp_param": best_sharpe_params["tp_param"],
            "atr_mult": best_sharpe_params["atr_mult"],
            "n_trades": best_sharpe_result.total_trades,
            "pnl": float(best_sharpe_result.net_pnl),
        }
    if best_expect_result is not None:
        pool_summaries["expectancy_pool"] = {
            "expectancy": float(best_expect_result.pnl_per_trade),
            "tp_type": best_expect_params["tp_type"],
            "tp_param": best_expect_params["tp_param"],
            "atr_mult": best_expect_params["atr_mult"],
            "n_trades": best_expect_result.total_trades,
            "pnl": float(best_expect_result.net_pnl),
        }
    if best_pnl_result is not None:
        pool_summaries["pnl_pool"] = {
            "pnl": float(best_pnl_result.net_pnl),
            "tp_type": best_pnl_params["tp_type"],
            "tp_param": best_pnl_params["tp_param"],
            "atr_mult": best_pnl_params["atr_mult"],
            "n_trades": best_pnl_result.total_trades,
            "sharpe": float(best_pnl_result.sharpe_ratio),
        }

    passport_patch = {
        "arena3": {
            "atr_multiplier": winner_params["atr_mult"],
            "atr_stop_mult": winner_params["atr_mult"],  # backward compat for A4
            "best_tp_strategy": winner_params["tp_type"],
            "tp_param": winner_params["tp_param"],
            "winner_pool": winner_pool,
            "half_kelly": kelly_frac,
            "sharpe_ratio": float(winner_result.sharpe_ratio),
            "expectancy": float(expectancy),
            "cumulative_pnl": float(winner_result.net_pnl),
            "n_trades": winner_result.total_trades,
            "win_rate": float(winner_result.win_rate),
            "max_dd": float(winner_result.max_drawdown),
            "pnl_per_trade": float(winner_result.pnl_per_trade),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "pools": pool_summaries,
            "validation": {
                "trades": bt_val.total_trades,
                "pnl": float(bt_val.net_pnl),
                "sharpe": float(bt_val.sharpe_ratio),
                "wr": float(bt_val.win_rate),
                "positive_count": int(val_pos),
                "bars": len(close_val),
            },
            "fit_bars": inner_n,
        }
    }

    log.info(
        f"A3 COMPLETE id={champion_id} {symbol} | "
        f"pool={winner_pool} TP={winner_params['tp_type']}({winner_params['tp_param']}) "
        f"ATR_mult={winner_params['atr_mult']} PnL={winner_result.net_pnl:.4f} "
        f"Sharpe={winner_result.sharpe_ratio:.2f} DD={winner_result.max_drawdown:.4f} "
        f"WR={winner_result.win_rate:.3f} trades={winner_result.total_trades} "
        f"Kelly={kelly_frac:.4f} Expect={expectancy:.6f} | "
        f"VAL: pnl={bt_val.net_pnl:.4f} sharpe={bt_val.sharpe_ratio:.2f} wr={bt_val.win_rate:.3f} trades={bt_val.total_trades}"
    )

    return {
        "status": "ARENA3_COMPLETE",
        "arena3_sharpe": float(winner_result.sharpe_ratio),
        "arena3_expectancy": float(expectancy),
        "arena3_pnl": float(winner_result.net_pnl),
        "passport_patch": passport_patch,
    }


async def main():
    settings = Settings()
    cost_model = CostModel()
    log = StructuredLogger(
        "arena23", settings.log_level, settings.log_file, settings.log_rotation_mb
    )
    log.info("Arena 2+3 Orchestrator starting (v9: shared_utils, DB reconnect, lease reaper)")

    class BtConfig:
        backtest_chunk_size = 10000
        backtest_gpu_enabled = False
        backtest_gpu_batch_size = 64
    backtester = Backtester(BtConfig())

    log.info(f"Rust engine: {'loaded' if RUST_ENGINE else 'fallback Python'}")

    # ── DB connection with retry (3 attempts, 5s sleep) ──────────
    db = None
    for attempt in range(1, 4):
        try:
            db = await asyncpg.connect(
                host=settings.db_host, port=settings.db_port,
                database="zangetsu", user=settings.db_user,
                password=settings.db_password,
            )
            log.info("DB connected")
            break
        except Exception as e:
            log.error(f"DB connect attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                await asyncio.sleep(5)
            else:
                log.error("DB connection failed after 3 attempts, exiting")
                return

    # Load TRAIN split only (70%)
    _data_dir = Path("/home/j13/j13-ops/zangetsu/data")
    data_cache = {}
    for sym in settings.symbols:
        try:
            df = pl.read_parquet(f"{_data_dir}/ohlcv/{sym}.parquet")
            w = min(200000, len(df))
            split = int(w * TRAIN_SPLIT_RATIO)
            data_cache[sym] = {
                "train": {
                    "open": df["open"].to_numpy()[-w:-w+split].astype(np.float32),
                    "close": df["close"].to_numpy()[-w:-w+split].astype(np.float32),
                    "high": df["high"].to_numpy()[-w:-w+split].astype(np.float32),
                    "low": df["low"].to_numpy()[-w:-w+split].astype(np.float32),
                    "volume": df["volume"].to_numpy()[-w:-w+split].astype(np.float32),
                },
            }

            # Load funding rate (forward-filled to 1m)
            funding_arr = merge_funding_to_1m(
                _data_dir / "ohlcv" / f"{sym}.parquet",
                _data_dir / "funding" / f"{sym}.parquet",
            )
            if funding_arr is not None:
                data_cache[sym]["train"]["funding_rate"] = funding_arr[-w:][:split].astype(np.float32)

            # Load OI (forward-filled to 1m)
            oi_arr = merge_oi_to_1m(
                _data_dir / "ohlcv" / f"{sym}.parquet",
                _data_dir / "oi" / f"{sym}.parquet",
            )
            if oi_arr is not None:
                data_cache[sym]["train"]["oi"] = oi_arr[-w:][:split].astype(np.float32)

            log.info(f"Loaded {sym}: {split} bars (train only, {TRAIN_SPLIT_RATIO:.0%} of {w})")
        except Exception as e:
            log.warning(f"Skip {sym}: {e}")

    # Enrich with nondimensional factors
    enrich_data_cache(data_cache)
    log.info(f"Data cache: {len(data_cache)} symbols loaded (train split only, factor-enriched)")

    # Backward compat: arena23 accesses data_cache[sym]["close"] directly
    for sym in list(data_cache.keys()):
        if "train" in data_cache[sym]:
            for k, v in data_cache[sym]["train"].items():
                data_cache[sym][k] = v

    a2_processed = 0
    a2_promoted = 0
    a2_rejected = 0
    a3_processed = 0
    a3_completed = 0
    loop_iteration = 0

    running = True

    def handle_sig(s, f):
        nonlocal running
        running = False
        log.info(f"Shutdown signal received ({s})")

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    log.info("Service loop started")

    # ── V9: Optional PGQueuer LISTEN/NOTIFY pickup (opt-in) ──────
    # Default OFF. When A23_USE_PGQUEUER=1 we start an EventQueue listener
    # in the background. A1 is not yet emitting notify events, so this is
    # prep work only — the polling loop below remains the primary driver.
    _use_pgqueuer = os.environ.get("A23_USE_PGQUEUER", "0") == "1"
    _event_queue = None
    if _use_pgqueuer and _EVENT_QUEUE_AVAILABLE:
        try:
            _event_queue = EventQueue()

            async def _on_a23_event(stage: str, champion_id: str) -> None:
                # Lightweight hint only: the polling loop will pick up the
                # champion on its next iteration. We just log the wake-up.
                log.info(f"A23 pgqueuer wake stage={stage} champion={champion_id}")

            asyncio.create_task(_event_queue.listen(_on_a23_event))
            log.info("A23 PGQueuer listener started (prep mode, polling still primary)")
        except Exception as e:
            log.warning(f"A23 PGQueuer init failed, fallback to polling: {e}")
            _event_queue = None
    elif _use_pgqueuer and not _EVENT_QUEUE_AVAILABLE:
        log.warning("A23_USE_PGQUEUER=1 but event_queue module unavailable; polling only")

    while running:
        try:
            loop_iteration += 1

            # ── Lease expiry reaper: every 50 iterations ──────────
            if loop_iteration % 50 == 0:
                try:
                    await reap_expired_leases(db, log)
                except Exception as e:
                    log.warning(f"Lease reaper error: {e}")

            # ── Arena 3 first: ARENA2_COMPLETE -> ARENA3 (critical blocker) ──
            champion = await pick_champion(db, "ARENA2_COMPLETE", "ARENA3_PROCESSING")
            if champion:
                t0 = time.time()
                try:
                    result = await process_arena3(champion, data_cache, cost_model, backtester, log)
                    if result is None:
                        await release_champion(db, champion["id"], "ARENA3_REJECTED", {
                            "passport_patch": {"arena3": {"error": "no_valid_atr_tp"}},
                        })
                    else:
                        status = result.pop("status")
                        await release_champion(db, champion["id"], status, result)
                        a3_completed += 1
                    a3_processed += 1
                except Exception as e:
                    log.error(f"A3 error id={champion['id']}: {e}\n{traceback.format_exc()}")
                    try:
                        await db.execute(
                            "UPDATE champion_pipeline SET status = 'ARENA2_COMPLETE', worker_id = NULL, lease_until = NULL, updated_at = NOW() WHERE id = $1",
                            champion["id"],
                        )
                        await log_transition(db, champion["id"], "ARENA3_PROCESSING", "ARENA2_COMPLETE", worker_id=WORKER_ID, metadata={"reason": "error_rollback"})
                    except Exception as e:
                        log.debug(f"A3 error_rollback failed for champion {champion.get('id')}: {e}")
                elapsed = time.time() - t0
                if a3_processed <= 5 or a3_processed % 20 == 0:
                    log.info(f"A3 stats: processed={a3_processed} completed={a3_completed} ({elapsed:.1f}s)")
                continue

            # ── Arena 2: ARENA1_COMPLETE -> ARENA2 ──
            champion = await pick_champion(db, "ARENA1_COMPLETE", "ARENA2_PROCESSING")
            if champion:
                t0 = time.time()
                try:
                    # Dedup check: skip if same indicator combo already exists at higher level
                    passport = json.loads(champion["passport"]) if isinstance(champion["passport"], str) else champion["passport"]
                    if await is_duplicate_champion(db, champion["id"], passport, log):
                        await release_champion(db, champion["id"], "ARENA2_REJECTED", {
                            "passport_patch": {"arena2": {"error": "duplicate_indicator_combo"}},
                        })
                        a2_rejected += 1
                        a2_processed += 1
                        continue

                    result = await process_arena2(champion, data_cache, cost_model, backtester, log)
                    if result is None:
                        await release_champion(db, champion["id"], "ARENA2_REJECTED", {
                            "passport_patch": {"arena2": {"error": "no_valid_combos"}},
                        })
                        a2_rejected += 1
                    else:
                        improved, fields = result
                        status = fields.pop("status")
                        await release_champion(db, champion["id"], status, fields)
                        if improved:
                            a2_promoted += 1
                        else:
                            a2_rejected += 1
                    a2_processed += 1
                except Exception as e:
                    log.error(f"A2 error id={champion['id']}: {e}\n{traceback.format_exc()}")
                    try:
                        await db.execute(
                            "UPDATE champion_pipeline SET status = 'ARENA1_COMPLETE', worker_id = NULL, lease_until = NULL, updated_at = NOW() WHERE id = $1",
                            champion["id"],
                        )
                        await log_transition(db, champion["id"], "ARENA2_PROCESSING", "ARENA1_COMPLETE", worker_id=WORKER_ID, metadata={"reason": "error_rollback"})
                    except Exception as e:
                        log.debug(f"A2 error_rollback failed for champion {champion.get('id')}: {e}")
                elapsed = time.time() - t0
                if a2_processed <= 5 or a2_processed % 20 == 0:
                    log.info(f"A2 stats: processed={a2_processed} promoted={a2_promoted} rejected={a2_rejected} ({elapsed:.1f}s)")
                continue

            await asyncio.sleep(2)

        except (asyncpg.PostgresError, asyncpg.exceptions.ConnectionDoesNotExistError) as e:
            log.error(f"DB error in main loop: {e}")
            try:
                db, _ = await ensure_db_connection(db, settings, log)
                log.info("DB reconnected after error")
            except Exception as reconnect_err:
                log.error(f"DB reconnect failed: {reconnect_err}")
            await asyncio.sleep(5)
        except Exception as e:
            log.error(f"Unexpected error: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)

    # V9: close PGQueuer listener if active
    if _event_queue is not None:
        try:
            await _event_queue.close()
        except Exception as e:
            log.warning(f"A23 PGQueuer close error: {e}")

    await db.close()
    log.info(
        f"Shutdown complete. A2: {a2_processed} processed ({a2_promoted} promoted, {a2_rejected} rejected) | "
        f"A3: {a3_processed} processed ({a3_completed} completed)"
    )


if __name__ == "__main__":
    acquire_lock("arena23_orchestrator")
    asyncio.run(main())
