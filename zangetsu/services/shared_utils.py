"""Zangetsu V9 Shared Utilities — Single source of truth for cross-arena logic.

Eliminates duplicated implementations across arena_pipeline, arena23, arena45.
All arenas MUST import from here to ensure semantic consistency.
"""
import math
import hashlib
import json
import numpy as np


# ═══════════════════════════════════════════════════════════════════
# Wilson Score
# ═══════════════════════════════════════════════════════════════════

def wilson_lower(wins: int, total: int, z: float = 1.96) -> float:
    """Wilson score interval lower bound (95% confidence)."""
    if total == 0:
        return 0.0
    p = wins / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    adjust = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - adjust) / denominator


# ═══════════════════════════════════════════════════════════════════
# ATR Computation (Wilder's smoothing)
# ═══════════════════════════════════════════════════════════════════

def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute Average True Range using Wilder's smoothing.

    Handles edge cases: first `period-1` bars are filled with the first valid ATR value
    to avoid NaN propagation in downstream ATR stop calculations.
    """
    n = len(close)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    atr = np.zeros(n, dtype=np.float64)
    atr[:period] = np.nan
    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    first_valid = atr[period - 1]
    atr[:period - 1] = first_valid
    return atr


# ═══════════════════════════════════════════════════════════════════
# Config Hash (order-independent, used for dedup across all arenas)
# ═══════════════════════════════════════════════════════════════════

def compute_config_hash(configs: list) -> str:
    """Compute a stable, order-independent hash of indicator configs.

    Format: sorted pipe-joined "name_period" strings → MD5[:16].
    This is the CANONICAL format — all arenas must use this.
    """
    config_key = "|".join(sorted(f"{c['name']}_{c.get('period', 14)}" for c in configs))
    return hashlib.md5(config_key.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════
# Trailing Stop (unrealized PnL tracking, supports long + short)
# ═══════════════════════════════════════════════════════════════════

def apply_trailing_stop(signals: np.ndarray, close: np.ndarray, trail_pct: float) -> np.ndarray:
    """Modify signals to exit when unrealized profit drops trail_pct from peak.

    Semantics:
    - Tracks unrealized PnL as fraction of entry price, adjusted for position direction.
    - Long: profit = (price - entry) / entry
    - Short: profit = (entry - price) / entry
    - Exits when peak_pnl > trail_pct AND (peak_pnl - current_pnl) >= trail_pct.

    This is the CANONICAL implementation — A3 optimizes with it, A4/A5 must replay with it.
    """
    n = len(signals)
    out = signals.copy()
    position = 0
    entry_price = 0.0
    peak_pnl = 0.0

    for i in range(1, n):
        if position == 0:
            if out[i] != 0:
                position = int(out[i])
                entry_price = close[i]
                peak_pnl = 0.0
        else:
            unrealized = (close[i] - entry_price) / entry_price * position
            if unrealized > peak_pnl:
                peak_pnl = unrealized

            if peak_pnl > trail_pct and (peak_pnl - unrealized) >= trail_pct:
                out[i] = 0
                position = 0
                peak_pnl = 0.0
            elif out[i] == 0 or out[i] == -position:
                position = 0
                peak_pnl = 0.0
    return out


# ═══════════════════════════════════════════════════════════════════
# Fixed Target TP
# ═══════════════════════════════════════════════════════════════════

def apply_fixed_target(signals: np.ndarray, close: np.ndarray, target_pct: float) -> np.ndarray:
    """Modify signals to exit when unrealized profit >= target_pct.

    Supports long + short positions (uses position direction for PnL calc).
    """
    n = len(signals)
    out = signals.copy()
    position = 0
    entry_price = 0.0

    for i in range(1, n):
        if position == 0:
            if out[i] != 0:
                position = int(out[i])
                entry_price = close[i]
        else:
            unrealized = (close[i] - entry_price) / entry_price * position
            if unrealized >= target_pct:
                out[i] = 0
                position = 0
            elif out[i] == 0 or out[i] == -position:
                position = 0
    return out


def apply_tp_strategy(signals: np.ndarray, close: np.ndarray, tp_type: str, tp_param: float) -> np.ndarray:
    """Apply the TP strategy specified in passport. Returns modified signals."""
    if tp_type == "trailing" and tp_param > 0:
        return apply_trailing_stop(signals, close, tp_param)
    elif tp_type == "fixed" and tp_param > 0:
        return apply_fixed_target(signals, close, tp_param)
    return signals


# ═══════════════════════════════════════════════════════════════════
# Indicator Computation (shared across A4/A5)
# ═══════════════════════════════════════════════════════════════════

def compute_indicators(configs: list, close: np.ndarray, high: np.ndarray,
                       low: np.ndarray, vol: np.ndarray, rust_engine) -> list:
    """Compute indicator values from passport configs using Rust engine."""
    arrs = []
    for cfg in configs:
        name = cfg["name"]
        period = cfg.get("period", 14)
        try:
            if rust_engine is not None:
                vals = rust_engine.compute(name, {"period": period}, close, high, low, vol)
            else:
                vals = np.zeros(len(close))
            arrs.append(np.asarray(vals, dtype=np.float64))
        except Exception:
            continue
    return arrs


def compute_raw_indicators(configs: list, close: np.ndarray, high: np.ndarray,
                           low: np.ndarray, vol: np.ndarray, rust_engine) -> tuple:
    """Compute indicators and return (names, raw_arrays) for signal generation."""
    names = []
    arrays = []
    for cfg in configs:
        name = cfg["name"]
        period = cfg.get("period", 14)
        try:
            if rust_engine is not None:
                vals = rust_engine.compute(name, {"period": period}, close, high, low, vol)
            else:
                vals = np.zeros(len(close))
            names.append(name)
            arrays.append(np.asarray(vals, dtype=np.float64))
        except Exception:
            names.append(name)
            arrays.append(np.zeros(len(close), dtype=np.float64))
    return names, arrays


def filter_zero_variance(names: list, arrays: list, min_count: int = 2) -> tuple:
    """Filter out indicators with zero MAD. Returns (filtered_names, filtered_arrays) or None if < min_count."""
    valid = [(n, a) for n, a in zip(names, arrays) if np.median(np.abs(a - np.median(a))) > 0]
    if len(valid) < min_count:
        return None
    return [v[0] for v in valid], [v[1] for v in valid]


# ═══════════════════════════════════════════════════════════════════
# Passport Param Extraction (single source of truth for reading A3 params)
# ═══════════════════════════════════════════════════════════════════

# Canonical A3 max_hold — all downstream arenas must use this
A3_MAX_HOLD_BARS = 480


def extract_a3_params(passport: dict) -> dict:
    """Extract Arena 3 parameters from passport for faithful replay in A4/A5.

    Returns dict with: atr_stop_mult, tp_type, tp_param, max_hold.
    All downstream arenas (A4, A5) MUST use these params — never hardcode.
    """
    arena3 = passport.get("arena3", {})
    return {
        "atr_stop_mult": float(arena3.get("atr_multiplier", arena3.get("atr_stop_mult", 2.0))),
        "tp_type": arena3.get("best_tp_strategy", "none"),
        "tp_param": float(arena3.get("tp_param", 0.0) or 0.0),
        "max_hold": A3_MAX_HOLD_BARS,  # Always 480, matching A3's optimization
    }


def extract_a2_params(passport: dict) -> dict:
    """Extract Arena 2 parameters from passport."""
    arena2 = passport.get("arena2", {})
    return {
        "entry_thr": float(arena2.get("entry_threshold", arena2.get("entry_thr", 0.80))),
        "exit_thr": float(arena2.get("exit_threshold", arena2.get("exit_thr", 0.40))),
    }


# ═══════════════════════════════════════════════════════════════════
# Symbol Extraction
# ═══════════════════════════════════════════════════════════════════

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
    "LINKUSDT", "AAVEUSDT", "AVAXUSDT", "DOTUSDT", "FILUSDT",
    "1000PEPEUSDT", "1000SHIBUSDT", "GALAUSDT",
]


def extract_symbol(indicator_hash: str) -> str:
    """Extract symbol from indicator_hash (e.g., 'v9_w2_r277_c11_AVAXUSDT')."""
    for sym in SYMBOLS:
        if indicator_hash.endswith(sym):
            return sym
    parts = indicator_hash.split("_")
    return parts[-1] if parts else indicator_hash


# ═══════════════════════════════════════════════════════════════════
# Half-Kelly Sizing
# ═══════════════════════════════════════════════════════════════════

def half_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Compute half-Kelly fraction, clamped to [0.005, 0.10]. Returns 0 if negative edge."""
    if avg_loss == 0 or win_rate <= 0:
        return 0.0
    b = avg_win / avg_loss
    kelly = win_rate - (1 - win_rate) / b
    hk = max(kelly / 2.0, 0.0)
    if hk <= 0:
        return 0.0
    return min(max(hk, 0.005), 0.10)


# ═══════════════════════════════════════════════════════════════════
# Backtest Slice (shared between A4 and A5)
# ═══════════════════════════════════════════════════════════════════

def backtest_with_a3_params(backtester, signals: np.ndarray, close: np.ndarray,
                            high: np.ndarray, low: np.ndarray, symbol: str,
                            cost_bps: float, a3_params: dict, atr: np.ndarray = None):
    """Run backtest using A3 params faithfully. Used by A4 and A5.

    a3_params should come from extract_a3_params(passport).
    """
    if len(signals) < 50:
        return None
    kwargs = {"high": high, "low": low}
    if atr is not None and a3_params.get("atr_stop_mult"):
        kwargs["atr"] = atr[:len(signals)]
        kwargs["atr_stop_mult"] = a3_params["atr_stop_mult"]
    return backtester.run(signals, close, symbol, cost_bps, a3_params["max_hold"], **kwargs)


# ═══════════════════════════════════════════════════════════════════
# DB Reconnect Helper
# ═══════════════════════════════════════════════════════════════════

async def ensure_db_connection(db, settings, log):
    """Check if DB connection is alive, reconnect if not. Returns (connection, reconnected)."""
    import asyncpg
    try:
        await db.fetchval("SELECT 1")
        return db, False
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError):
        log.warning("DB connection lost, reconnecting...")
        try:
            await db.close()
        except Exception as e:
            log.debug(f"DB close during reconnect ignored: {e}")
        try:
            new_db = await asyncpg.connect(
                host=settings.db_host, port=settings.db_port,
                database='zangetsu', user=settings.db_user,
                password=settings.db_password,
            )
            log.info("DB reconnected")
            return new_db, True
        except Exception as e:
            log.error(f"DB reconnect failed: {e}")
            raise


# ═══════════════════════════════════════════════════════════════════
# Lease Expiry Reaper (P1-J: atomic CTE + FOR UPDATE SKIP LOCKED)
# ═══════════════════════════════════════════════════════════════════

async def reap_expired_leases(db, log, lease_minutes: int = 15):
    """Reset champions stuck in *_PROCESSING status past their lease expiry.

    P1-J fix: single atomic UPDATE with a CTE that does FOR UPDATE SKIP LOCKED,
    then a CASE expression to revert each *_PROCESSING row back to the PREVIOUS
    arena's _COMPLETE state. Eliminates the two-step race window where
    pick_champion (also SKIP LOCKED) could snatch a row between the old
    REPLACE step and the per-row revert step, and also avoids reaper-crash
    mid-transition leaving rows mis-staged.

    Semantics preserved:
        ARENA2_PROCESSING -> ARENA1_COMPLETE
        ARENA3_PROCESSING -> ARENA2_COMPLETE
        ARENA4_PROCESSING -> ARENA3_COMPLETE
        other             -> REPLACE('_PROCESSING', '_COMPLETE') fallback

    Negative / zero lease_minutes is clamped to 1 minute to prevent a
    catastrophic full-table reclaim if a caller passes a bad value.

    Run periodically (every few minutes). Safe under concurrent reapers.
    """
    # Defensive clamp: lease_minutes <= 0 would reclaim every PROCESSING row
    # (lease_until < NOW() + positive interval => always true). Floor at 1.
    lease_minutes = max(int(lease_minutes), 1)
    try:
        rows = await db.fetch("""
            WITH expired AS (
                SELECT id, status
                FROM champion_pipeline_fresh
                WHERE status LIKE '%_PROCESSING'
                  AND lease_until IS NOT NULL
                  AND lease_until < NOW() - INTERVAL '1 minute' * $1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE champion_pipeline_fresh cp
            SET status = CASE expired.status
                    WHEN 'ARENA2_PROCESSING' THEN 'ARENA1_COMPLETE'
                    WHEN 'ARENA3_PROCESSING' THEN 'ARENA2_COMPLETE'
                    WHEN 'ARENA4_PROCESSING' THEN 'ARENA3_COMPLETE'
                    ELSE REPLACE(expired.status, '_PROCESSING', '_COMPLETE')
                END,
                worker_id = NULL,
                lease_until = NULL,
                updated_at = NOW()
            FROM expired
            WHERE cp.id = expired.id
            RETURNING cp.id, expired.status AS prev_status, cp.status AS new_status
        """, lease_minutes)

        if rows:
            log.info(f"Lease reaper: reset {len(rows)} stuck PROCESSING entries")
        return len(rows)
    except Exception as e:
        log.warning(f"Lease reaper error: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════
# Five-Factor Market State Computation
# ═══════════════════════════════════════════════════════════════════

# V9: Import _ema and _ema_slope from single source (regime_labeler) — deduplicated
from zangetsu.engine.components.regime_labeler import _ema, _ema_slope


def rolling_percentile_rank(arr, window=720):
    """Percentile rank of current value within rolling window. Returns [0, 1].
    No lookahead — each bar uses only data up to and including itself.
    First `window` bars use expanding window."""
    n = len(arr)
    result = np.zeros(n, dtype=np.float64)
    for i in range(n):
        start = max(0, i - window + 1)
        w = arr[start:i+1]
        result[i] = np.sum(w <= arr[i]) / len(w)
    return result


def compute_momentum(close, period_short=20, period_long=50, adx_period=14):
    """Momentum score [-1, 1]. Combines EMA direction, ADX strength, and RSI confirmation."""
    ema_s = _ema(close, period_short)
    ema_l = _ema(close, period_long)
    direction = np.sign(ema_s - ema_l)

    # ADX for strength (reuse existing _adx needs high/low — use ATR proxy)
    # Simplified: use EMA slope magnitude as strength proxy
    slope = _ema_slope(close, period_short)
    strength = np.clip(np.abs(slope) / np.maximum(np.abs(np.mean(slope)), 1e-10) * 0.5, 0, 1)

    # RSI confirmation
    n = len(close)
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _ema(gain, 14)
    avg_loss = _ema(loss, 14)
    rs = avg_gain / np.maximum(avg_loss, 1e-10)
    rsi = 100 - 100 / (1 + rs)
    rsi_norm = (rsi - 50) / 50.0  # [-1, 1]

    return np.clip(direction * strength * 0.6 + rsi_norm * 0.4, -1, 1)


def compute_volatility(close, high, low, window=720):
    """Volatility score [0, 1]. Percentile rank of ATR/close."""
    atr = compute_atr(high, low, close, 14)
    atr_norm = atr / np.maximum(close, 1e-10)  # price-normalized
    return rolling_percentile_rank(atr_norm, window)


def compute_volume_score(volume, window=720):
    """Volume score [0, 1]. Log relative volume vs rolling median."""
    # Rolling median approximation using EMA
    vol_ema = _ema(volume, 50)
    rel = np.log1p(volume / np.maximum(vol_ema, 1e-10))
    return np.clip(rolling_percentile_rank(rel, window), 0, 1)


def compute_funding(funding_rate, window=720):
    """Funding score [-1, 1]. tanh-compressed z-score. Returns None if input is None.
    Handles NaN/Inf in input by treating them as 0.0 (no funding signal)."""
    if funding_rate is None:
        return None
    # Defend against NaN/Inf from data_collector edge cases
    funding_rate = np.nan_to_num(np.asarray(funding_rate, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    n = len(funding_rate)
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    result = np.zeros(n, dtype=np.float64)
    for i in range(n):
        start = max(0, i - window + 1)
        w = funding_rate[start:i+1]
        mu = np.mean(w)
        std = np.std(w)
        if std < 1e-12:
            result[i] = 0.0
        else:
            result[i] = np.tanh((funding_rate[i] - mu) / std * 0.5)
    return result


def compute_oi(oi, close, window=720):
    """Open Interest score [-1, 1]. OI change direction + price divergence. Returns None if input is None.
    Handles NaN/Inf in input by treating them as 0.0 (no OI signal)."""
    if oi is None:
        return None
    oi = np.nan_to_num(np.asarray(oi, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    close = np.nan_to_num(np.asarray(close, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    n = len(oi)
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    oi_pct = np.zeros(n, dtype=np.float64)
    oi_pct[1:] = np.diff(oi) / np.maximum(oi[:-1], 1e-10)

    oi_rank = rolling_percentile_rank(oi_pct, window) * 2 - 1  # [-1, 1]

    # Divergence: OI rising + price falling or vice versa
    price_ret = np.zeros(n, dtype=np.float64)
    price_ret[1:] = np.diff(close) / np.maximum(close[:-1], 1e-10)
    price_dir = np.sign(price_ret)
    oi_dir = np.sign(oi_pct)
    divergence = np.where(oi_dir != price_dir, -oi_dir * 0.3, 0.0)

    return np.clip(oi_rank * 0.7 + divergence, -1, 1)


def compute_extreme_flags(close, high, low, volume, funding_rate, oi, window=720):
    """Compute boolean extreme flags. NEVER filter — only flag.
    Returns dict of boolean arrays. funding/oi flags are all-False if inputs are None."""
    n = len(close)
    atr = compute_atr(high, low, close, 14)
    returns = np.zeros(n, dtype=np.float64)
    returns[1:] = np.abs(np.diff(close) / np.maximum(close[:-1], 1e-10))

    atr_p99 = np.array([np.percentile(atr[max(0,i-window+1):i+1], 99) for i in range(n)])
    ret_p995 = np.array([np.percentile(returns[max(0,i-window+1):i+1], 99.5) for i in range(n)])

    flags = {
        "ext_vol": atr > atr_p99,
        "ext_move": returns > ret_p995,
        "ext_fund": np.zeros(n, dtype=bool),
        "ext_oi": np.zeros(n, dtype=bool),
    }

    if funding_rate is not None:
        fund_score = compute_funding(funding_rate, window)
        flags["ext_fund"] = np.abs(fund_score) > 0.80

    if oi is not None:
        oi_pct = np.zeros(n, dtype=np.float64)
        oi_pct[1:] = np.abs(np.diff(oi) / np.maximum(oi[:-1], 1e-10))
        oi_p99 = np.array([np.percentile(oi_pct[max(0,i-window+1):i+1], 99) for i in range(n)])
        flags["ext_oi"] = oi_pct > oi_p99

    return flags


# ═══════════════════════════════════════════════════════════════════
# V9: Multi-Window Walk-Forward Validation
# ═══════════════════════════════════════════════════════════════════

def walk_forward_validate(backtester, signals_fn, close, high, low, vol, symbol,
                          cost_bps, max_hold, n_windows=4, purge_bars=60,
                          atr=None, atr_stop_mult=2.0, tp_type='none', tp_param=0.0):
    """Run walk-forward validation with multiple chronological windows.
    
    Splits data into n_windows+1 segments. For each window i:
      - Train on segments [0..i]
      - Test on segment [i+1]
      - Purge 'purge_bars' between train and test (embargo)
    
    Returns dict with per-window results and aggregate metrics.
    Returns None if insufficient windows pass.
    """
    from engine.components.backtester import BacktestResult
    
    n = len(close)
    seg_size = n // (n_windows + 1)
    if seg_size < 500:
        return None  # too short for meaningful WFO
    
    window_results = []
    
    for i in range(n_windows):
        # Test segment boundaries
        test_start = (i + 1) * seg_size + purge_bars
        test_end = (i + 2) * seg_size if i < n_windows - 1 else n
        
        if test_start >= test_end or test_end - test_start < 200:
            continue
        
        # Generate signals on test segment
        test_signals = signals_fn(test_start, test_end)
        if test_signals is None:
            continue
        
        test_close = close[test_start:test_end]
        test_high = high[test_start:test_end]
        test_low = low[test_start:test_end]
        
        # Apply TP strategy if specified
        if tp_type != 'none' and tp_param > 0:
            test_signals = apply_tp_strategy(test_signals, test_close, tp_type, tp_param)
        
        # Run backtest
        bt = backtester.run(test_signals, test_close, symbol, cost_bps, max_hold,
                           high=test_high, low=test_low,
                           atr=atr[test_start:test_end] if atr is not None else None,
                           atr_stop_mult=atr_stop_mult)
        
        if bt is None or bt.total_trades < 5:
            window_results.append({"sharpe": 0.0, "pnl": 0.0, "wr": 0.0, "trades": 0, "pass": False})
        else:
            passed = bt.net_pnl > 0 and bt.total_trades >= 5
            window_results.append({
                "sharpe": float(bt.sharpe_ratio),
                "pnl": float(bt.net_pnl),
                "wr": float(bt.win_rate),
                "trades": int(bt.total_trades),
                "pass": passed,
            })
    
    if len(window_results) < 2:
        return None
    
    n_passed = sum(1 for w in window_results if w["pass"])
    avg_sharpe = sum(w["sharpe"] for w in window_results) / len(window_results)
    avg_pnl = sum(w["pnl"] for w in window_results) / len(window_results)
    avg_wr = sum(w["wr"] for w in window_results) / len(window_results)
    
    return {
        "windows": window_results,
        "n_windows": len(window_results),
        "n_passed": n_passed,
        "pass_rate": n_passed / len(window_results),
        "avg_sharpe": avg_sharpe,
        "avg_pnl": avg_pnl,
        "avg_wr": avg_wr,
        "robust": n_passed >= len(window_results) * 0.6,  # 60%+ windows must pass
    }


# ═══════════════════════════════════════════════════════════════════
# Ensemble Candidate Builder (A3.5 stage)
# ═══════════════════════════════════════════════════════════════════

def build_ensemble_candidates(db_rows: list, min_size: int = 3, max_size: int = 5, max_correlation: float = 0.3) -> list:
    """Build ensemble groups from A3-passed strategies.
    Groups strategies with low pairwise correlation of their indicator sets.
    Returns list of groups, each group is a list of champion IDs."""
    import itertools
    if len(db_rows) < min_size:
        return []

    # Extract indicator names per champion
    champions = []
    for row in db_rows:
        passport = row.get("passport", {})
        if isinstance(passport, str):
            passport = json.loads(passport)
        a1 = passport.get("arena1", {})
        names = set(a1.get("indicator_names", []))
        champions.append({"id": row["id"], "names": names, "sharpe": row.get("arena3_sharpe", 0)})

    # Jaccard distance as proxy for signal correlation
    groups = []
    for combo in itertools.combinations(champions, min_size):
        # Check pairwise Jaccard similarity
        all_low = True
        for i, j in itertools.combinations(range(len(combo)), 2):
            intersection = len(combo[i]["names"] & combo[j]["names"])
            union = len(combo[i]["names"] | combo[j]["names"])
            jaccard = intersection / max(union, 1)
            if jaccard > max_correlation:
                all_low = False
                break
        if all_low:
            avg_sharpe = sum(c["sharpe"] for c in combo) / len(combo)
            groups.append({
                "ids": [c["id"] for c in combo],
                "avg_sharpe": avg_sharpe,
                "size": len(combo),
            })

    # Sort by avg_sharpe descending
    groups.sort(key=lambda g: g["avg_sharpe"], reverse=True)
    return groups[:10]  # Top 10 ensemble candidates


# ═══════════════════════════════════════════════════════════════════
# Deflated Sharpe Ratio (multiple-testing correction)
# ═══════════════════════════════════════════════════════════════════

def deflated_sharpe_ratio(observed_sr: float, sr_std: float, num_trials: int, T: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """Compute probability that observed Sharpe ratio is genuine after multiple testing.
    Returns DSR in [0, 1]. Higher = more likely to be real."""
    from scipy.stats import norm

    if num_trials <= 1 or sr_std < 1e-10 or T <= 1:
        return 0.0

    # Expected max SR under null
    gamma = 0.5772156649015329  # Euler-Mascheroni
    z = norm.ppf(1 - 1.0 / num_trials)
    sr0 = sr_std * ((1 - gamma) * z + gamma * norm.ppf(1 - 1.0 / (num_trials * np.e)))

    # Variance of SR estimator
    sr_var = (1 - skew * observed_sr + ((kurt - 1) / 4) * observed_sr ** 2) / (T - 1)

    return float(norm.cdf((observed_sr - sr0) / max(np.sqrt(sr_var), 1e-10)))
