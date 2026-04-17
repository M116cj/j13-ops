"""Arena Pipeline V9 — High-throughput optimized A1 with bloom filter dedup + A2 pre-screen.

Changes from v4/v5 (unified V9):
- O1: Bloom filter full-history dedup (all statuses, not just active)
- O2: A2-aligned pre-screen (max_hold=120 + positive_count>=2) before DB insert
- O3: Adaptive early exit (stop after 80 contestants if strong champion found)
- O4: Two-stage backtest (quick 50k screen → full 140k confirm)
- O5: Regime hard cap (max 25% per regime, force rotation)
- O6: 3-indicator exploration bias (60% weight on 3-ind combos)
"""
import sys, os, asyncio, signal, time, random, json, math, hashlib
sys.path.insert(0, '/home/j13/j13-ops')
sys.path.insert(0, '/home/j13/j13-ops/zangetsu_v5/indicator_engine/target/release')
os.chdir('/home/j13/j13-ops')

import numpy as np
from zangetsu_v5.services.pidlock import acquire_lock
import os as _os; acquire_lock(f"arena_pipeline_w{_os.environ.get('A1_WORKER_ID', '0')}")

# --- Regime classification from 1m data ---
from zangetsu_v5.engine.components.p_value import load_baseline, compute_p_value, compute_pnl_p_value, is_significant
from zangetsu_v5.engine.components.data_preprocessor import enrich_data_cache
from zangetsu_v5.services.data_collector import merge_funding_to_1m, merge_oi_to_1m
from pathlib import Path
# V9: LABEL_TO_REGIME and L1_ALLOWED live in market_state.py (single source of truth)
# V9: _ema is imported from shared_utils below (which re-exports from regime_labeler)

from zangetsu_v5.services.shared_utils import wilson_lower
from zangetsu_v5.services.shared_utils import (
    compute_momentum, compute_volatility, compute_volume_score,
    compute_funding, compute_oi, compute_extreme_flags,
    compute_atr, _ema,
)
from zangetsu_v5.services.market_state import build_market_state




# Indicator weights based on historical hit rate analysis
INDICATOR_WEIGHTS = {
    "tsi": 2.0,
    "macd": 2.0,
    "zscore": 1.8,
    "ppo": 1.8,
    "cci": 1.5,
    "trix": 1.5,
    "cmo": 1.2,
    "roc": 1.2,
    "rsi": 1.0,
    "stochastic_k": 1.0,
    "obv": 1.0,
    "mfi": 1.2,
    "vwap": 1.0,
}

EXPLORE_RATE = 0.50  # 50% pure random, 50% weighted toward proven performers

# ── A13 Feedback Guidance ──
A13_GUIDANCE_PATH = "/home/j13/j13-ops/zangetsu_v5/config/a13_guidance.json"
_guidance_cache = {"weights": None, "cool_off": set(), "regime_boosts": {}, "explore_rate": EXPLORE_RATE, "loaded_at": 0}

def load_a13_guidance(log=None):
    """Load A13 feedback guidance. V9: always overwrite cache (no stale partial fields).
    Cheap mtime check short-circuits if file unchanged."""
    import os
    try:
        if not os.path.exists(A13_GUIDANCE_PATH):
            return
        mtime = os.path.getmtime(A13_GUIDANCE_PATH)
        if mtime <= _guidance_cache["loaded_at"]:
            return  # Already loaded this version
        with open(A13_GUIDANCE_PATH, "r") as f:
            g = json.load(f)
        # V9 FIX (Codex #3): unconditional overwrite to avoid stale fields when transitions clear lists
        _guidance_cache["weights"] = g.get("indicator_weights") or None
        _guidance_cache["cool_off"] = set(g.get("cool_off_hashes", []))
        _guidance_cache["regime_boosts"] = g.get("regime_boosts", {})
        _guidance_cache["mode"] = g.get("mode", "observe")  # V9 FIX (Codex #4)
        _guidance_cache["period_preferences"] = g.get("period_preferences", {})
        _guidance_cache["explore_rate"] = max(g.get("diversity_floor", EXPLORE_RATE), 0.20)
        _guidance_cache["loaded_at"] = mtime
        if log:
            n_w = len(_guidance_cache["weights"]) if _guidance_cache["weights"] else 0
            top = sorted((_guidance_cache["weights"] or {}).items(), key=lambda x: -x[1])[:3]
            log.info(f"A13 guidance loaded: mode={_guidance_cache['mode']} weights={n_w} "
                     f"cool_off={len(_guidance_cache['cool_off'])} "
                     f"regime_boosts={len(_guidance_cache['regime_boosts'])} "
                     f"top: {', '.join(f'{k}={v}' for k,v in top)}")
    except Exception as e:
        if log:
            log.warning(f"A13 guidance load failed (using defaults): {e}")


def weighted_sample(indicators, weights, k):
    """Weighted random sample without replacement."""
    pool = list(indicators)
    w = [weights.get(x, 1.0) for x in pool]
    selected = []
    for _ in range(min(k, len(pool))):
        total = sum(w)
        r = random.random() * total
        cumulative = 0
        for i, (item, weight) in enumerate(zip(pool, w)):
            cumulative += weight
            if r <= cumulative:
                selected.append(item)
                pool.pop(i)
                w.pop(i)
                break
    return selected



# --- Signal group diversity constraint (ISS-02 fix) ---
SIGNAL_GROUPS = {
    "zero_cross": ["macd", "roc", "ppo", "cmo", "tsi", "trix"],  # v>0=buy, v<0=sell
    "overbought": ["rsi", "stochastic_k"],                         # extreme levels
    "zscore": ["zscore"],                                           # mean-reversion
    "trend": ["cci", "adx"],                                       # different thresholds
    "fisher": ["fisher", "awesome_osc"],                            # zero-cross but distinct waveform
    "volume": ["obv", "mfi", "vwap"],                               # volume-based
}

IND_TO_GROUP = {}
for _grp, _inds in SIGNAL_GROUPS.items():
    for _ind in _inds:
        IND_TO_GROUP[_ind] = _grp


def sample_diverse_indicators(indicators, weights, k):
    """Weighted sample ensuring no two indicators from the same signal group."""
    pool = list(indicators)
    random.shuffle(pool)
    w = {x: weights.get(x, 1.0) for x in pool}
    selected = []
    used_groups = set()
    candidates = sorted(pool, key=lambda x: w[x] + random.random() * 0.5, reverse=True)
    for ind in candidates:
        group = IND_TO_GROUP.get(ind, ind)
        if group not in used_groups:
            selected.append(ind)
            used_groups.add(group)
        if len(selected) >= k:
            break
    return selected


TRAIN_SPLIT_RATIO = 0.7

# ── O5: Regime hard cap — no single regime exceeds 25% of total champions ──
REGIME_CAP_PCT = 0.25


# ── O1: Bloom Filter for full-history dedup ──
class BloomFilter:
    """Memory-efficient probabilistic set for dedup. ~1MB for 100k entries at 0.1% FPR."""

    def __init__(self, capacity: int = 200_000, fp_rate: float = 0.001):
        self.size = self._optimal_size(capacity, fp_rate)
        self.k = self._optimal_k(self.size, capacity)
        self.bits = bytearray(self.size // 8 + 1)
        self.count = 0

    @staticmethod
    def _optimal_size(n, p):
        m = -n * math.log(p) / (math.log(2) ** 2)
        return int(m) + 1

    @staticmethod
    def _optimal_k(m, n):
        k = (m / max(n, 1)) * math.log(2)
        return max(1, int(k))

    def _hashes(self, key: str):
        h1 = int(hashlib.md5(key.encode()).hexdigest(), 16)
        h2 = int(hashlib.sha1(key.encode()).hexdigest(), 16)
        for i in range(self.k):
            yield (h1 + i * h2) % self.size

    def add(self, key: str):
        for pos in self._hashes(key):
            self.bits[pos // 8] |= (1 << (pos % 8))
        self.count += 1

    def __contains__(self, key: str) -> bool:
        return all(
            self.bits[pos // 8] & (1 << (pos % 8))
            for pos in self._hashes(key)
        )


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except Exception:
        return default


async def main():
    from zangetsu_v5.config.settings import Settings
    from zangetsu_v5.config.cost_model import CostModel
    from zangetsu_v5.engine.components.backtester import Backtester
    from zangetsu_v5.engine.components.signal_utils import generate_threshold_signals
    from zangetsu_v5.engine.components.logger import StructuredLogger

    settings = Settings()
    cost_model = CostModel()
    log = StructuredLogger("arena_pipeline", settings.log_level, settings.log_file, settings.log_rotation_mb)
    worker_count = _env_int("A1_WORKER_COUNT", 1, 1)
    worker_id = min(_env_int("A1_WORKER_ID", 0, 0), worker_count - 1)
    checkpoint_arena = f"arena1_pipeline_w{worker_id}" if worker_count > 1 else "arena1_pipeline"

    log.info(f"Arena Pipeline V9 starting — bloom dedup + A2 pre-screen + early exit | worker={worker_id+1}/{worker_count}")

    try:
        import zangetsu_indicators as zi
        rust = True
        log.info("Rust engine loaded")
    except ImportError:
        rust = False

    class C:
        backtest_chunk_size=10000; backtest_gpu_enabled=False; backtest_gpu_batch_size=64
    backtester = Backtester(C())

    # Load random baseline for p-value computation
    try:
        baseline = load_baseline()
        log.info(f"Random baseline loaded: WR_mean={baseline['wr_mean']:.4f} WR_std={baseline['wr_std']:.4f} n={baseline['n_simulations']}")
    except FileNotFoundError:
        baseline = None
        log.warning("Random baseline not found -- p-values will not be computed")

    import asyncpg
    db = await asyncpg.connect(
        host=settings.db_host, port=settings.db_port,
        database='zangetsu', user=settings.db_user,
        password=settings.db_password,
    )

    DIRECTIONAL = ["rsi","stochastic_k","cci","roc","ppo","cmo",
                   "zscore","trix","tsi","obv","mfi","vwap",
                   "normalized_atr","realized_vol","bollinger_bw",
                   "relative_volume","vwap_deviation",
                   "funding_rate","funding_zscore","oi_change","oi_divergence"]
    REGIMES = ["BULL_TREND","BEAR_TREND","CONSOLIDATION","BULL_PULLBACK","BEAR_RALLY",
               "ACCUMULATION","DISTRIBUTION","SQUEEZE","CHOPPY_VOLATILE",
               "TOPPING","BOTTOMING",
               "LIQUIDITY_CRISIS","PARABOLIC"]

    import polars as pl
    data_cache = {}
    _data_dir = Path("/home/j13/j13-ops/zangetsu_v5/data")
    for sym in settings.symbols:
        try:
            df = pl.read_parquet(f"{_data_dir}/ohlcv/{sym}.parquet")
            w = min(200000, len(df))
            all_open = df["open"].to_numpy()[-w:].astype(np.float32)
            all_close = df["close"].to_numpy()[-w:].astype(np.float32)
            all_high = df["high"].to_numpy()[-w:].astype(np.float32)
            all_low = df["low"].to_numpy()[-w:].astype(np.float32)
            all_volume = df["volume"].to_numpy()[-w:].astype(np.float32)

            split = int(w * TRAIN_SPLIT_RATIO)
            data_cache[sym] = {
                "train": {
                    "open": all_open[:split],
                    "close": all_close[:split],
                    "high": all_high[:split],
                    "low": all_low[:split],
                    "volume": all_volume[:split],
                },
                "holdout": {
                    "open": all_open[split:],
                    "close": all_close[split:],
                    "high": all_high[split:],
                    "low": all_low[split:],
                    "volume": all_volume[split:],
                },
                "total_bars": w,
                "train_bars": split,
                "holdout_bars": w - split,
            }

            # Load funding rate (forward-filled to 1m)
            funding_arr = merge_funding_to_1m(
                _data_dir / "ohlcv" / f"{sym}.parquet",
                _data_dir / "funding" / f"{sym}.parquet",
            )
            if funding_arr is not None:
                data_cache[sym]["train"]["funding_rate"] = funding_arr[-w:][:split].astype(np.float32)
                data_cache[sym]["holdout"]["funding_rate"] = funding_arr[-w:][split:].astype(np.float32)

            # Load OI (forward-filled to 1m)
            oi_arr = merge_oi_to_1m(
                _data_dir / "ohlcv" / f"{sym}.parquet",
                _data_dir / "oi" / f"{sym}.parquet",
            )
            if oi_arr is not None:
                data_cache[sym]["train"]["oi"] = oi_arr[-w:][:split].astype(np.float32)
                data_cache[sym]["holdout"]["oi"] = oi_arr[-w:][split:].astype(np.float32)

            fr_status = "yes" if funding_arr is not None else "no"
            oi_status = "yes" if oi_arr is not None else "no"
            log.info(f"Loaded {sym}: {w} bars (train: {split}, holdout: {w - split}) funding={fr_status} oi={oi_status}")
        except Exception as e:
            log.warning(f"Skip {sym}: {e}")

    # ── Nondimensionalization: enrich data_cache with all 5 factor categories ──
    enrich_data_cache(data_cache)
    log.info("Factor enrichment complete: F1(momentum) F2(volatility) F3(volume) F4(funding) F5(OI)")

    all_symbols = list(data_cache.keys())
    if worker_count > 1:
        symbols = [sym for idx, sym in enumerate(all_symbols) if idx % worker_count == worker_id]
    else:
        symbols = all_symbols
    if not symbols:
        raise RuntimeError(f"worker {worker_id} has no symbols to process")

    # ── O4: Pre-compute quick-screen data (first 50k bars of train) ──
    quick_data_cache = {}
    QUICK_BARS = 50000
    for sym in symbols:
        d = data_cache[sym]["train"]
        qlen = min(QUICK_BARS, len(d["close"]))
        quick_data_cache[sym] = {
            "close": d["close"][:qlen],
            "high": d["high"][:qlen],
            "low": d["low"][:qlen],
            "volume": d["volume"][:qlen],
        }

    # ── 5-Factor Regime Detection v2 (PRIMARY) ──
    symbol_regimes = {}
    symbol_market_states = {}
    for sym in symbols:
        d = data_cache[sym]["train"]
        try:
            close, high, low, vol_arr = d["close"], d["high"], d["low"], d["volume"]
            fund_raw = d.get("funding_rate")
            oi_raw = d.get("oi")

            mom = compute_momentum(close)
            volatility = compute_volatility(close, high, low)
            vm = compute_volume_score(vol_arr)
            fund = compute_funding(fund_raw)
            oi_score = compute_oi(oi_raw, close)
            ext = compute_extreme_flags(close, high, low, vol_arr, fund_raw, oi_raw)

            ms = build_market_state(
                mom=float(mom[-1]), vol=float(volatility[-1]), vm=float(vm[-1]),
                fund=float(fund[-1]) if fund is not None else None,
                oi=float(oi_score[-1]) if oi_score is not None else None,
                ext_flags={k: bool(v[-1]) for k, v in ext.items()},
            )

            symbol_regimes[sym] = ms.regime
            symbol_market_states[sym] = ms
            data_cache[sym]["train"]["market_state"] = {
                "momentum": mom, "volatility": volatility, "volume": vm,
                "funding": fund, "oi": oi_score, "extreme_flags": ext,
            }
            log.info(f"Regime {sym}: {ms.regime} (L1={ms.regime_l1}, conf={ms.regime_confidence:.2f}, "
                     f"mom={ms.momentum:.2f} vol={ms.volatility:.2f} vm={ms.volume:.2f} "
                     f"fund={ms.funding:.2f} oi={ms.open_interest:.2f})")
        except Exception as e:
            import traceback
            symbol_regimes[sym] = "CONSOLIDATION"
            symbol_market_states[sym] = None
            log.error(f"5-factor regime FAILED for {sym}: {type(e).__name__}: {e} | "
                      f"data_shapes: close={len(d.get(close,[]))} "
                      f"funding={yes if d.get(funding_rate) is not None else NONE} "
                      f"oi={yes if d.get(oi) is not None else NONE} "
                      f"| trace: {traceback.format_exc()[:500]}")

    round_number = 0; total_champions = 0
    running = True

    def handle_sig(s, f):
        nonlocal running; running = False
    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    period_choices = [7, 14, 20, 30, 48, 50, 100, 200]


    # ── Compute derived factor indicators from raw data ──
    for _sym in symbols:
        _d = data_cache[_sym]["train"]
        _close, _high, _low, _vol = _d["close"], _d["high"], _d["low"], _d["volume"]

        # normalized_atr
        _atr = compute_atr(_high, _low, _close, 14)
        _d["normalized_atr"] = _atr / np.maximum(_close, 1e-10)

        # realized_vol (20-bar rolling std of returns)
        _rets = np.zeros(len(_close)); _rets[1:] = np.diff(_close) / np.maximum(_close[:-1], 1e-10)
        _rv = np.zeros(len(_close))
        for _i in range(20, len(_close)):
            _rv[_i] = np.std(_rets[_i-20:_i])
        _d["realized_vol"] = _rv

        # bollinger_bw (20-period)
        _sma = np.convolve(_close, np.ones(20)/20, mode="same")
        _std = np.zeros(len(_close))
        for _i in range(20, len(_close)):
            _std[_i] = np.std(_close[_i-20:_i])
        _d["bollinger_bw"] = 2 * _std / np.maximum(_sma, 1e-10)

        # relative_volume
        _vol_ema = _ema(_vol.astype(np.float64), 50)
        _d["relative_volume"] = _vol / np.maximum(_vol_ema, 1e-10)

        # vwap_deviation
        _cum_pv = np.cumsum(_close * _vol)
        _cum_v = np.cumsum(_vol)
        _vwap = _cum_pv / np.maximum(_cum_v, 1e-10)
        _d["vwap_deviation"] = (_close - _vwap) / np.maximum(_vwap, 1e-10)

        # funding_zscore
        _fr = _d.get("funding_rate")
        if _fr is not None:
            _fr64 = _fr.astype(np.float64)
            _fm = _ema(_fr64, 720)
            _fs = np.zeros(len(_fr64))
            for _i in range(720, len(_fr64)):
                _fs[_i] = np.std(_fr64[_i-720:_i])
            _d["funding_zscore"] = (_fr64 - _fm) / np.maximum(_fs, 1e-10)

        # oi_change
        _oi = _d.get("oi")
        if _oi is not None:
            _oi64 = _oi.astype(np.float64)
            _oi_pct = np.zeros(len(_oi64))
            _oi_pct[1:] = np.diff(_oi64) / np.maximum(_oi64[:-1], 1e-10)
            _d["oi_change"] = _oi_pct

            # oi_divergence (OI direction vs price direction)
            _p_dir = np.sign(np.diff(_close, prepend=_close[0]))
            _oi_dir = np.sign(_oi_pct)
            _d["oi_divergence"] = (_oi_dir - _p_dir) / 2  # [-1, 1]

        log.info(f"Factor indicators computed for {_sym}: natr={_d.get('normalized_atr') is not None} "
                 f"rvol={_d.get('realized_vol') is not None} bbw={_d.get('bollinger_bw') is not None} "
                 f"relvol={_d.get('relative_volume') is not None} vwap={_d.get('vwap_deviation') is not None} "
                 f"fzscore={_d.get('funding_zscore') is not None} oic={_d.get('oi_change') is not None} "
                 f"oidiv={_d.get('oi_divergence') is not None}")

    # Factor indicators are pre-computed in data_cache, not via Rust engine
    _FACTOR_INDICATORS = frozenset({
        "normalized_atr", "realized_vol", "bollinger_bw",
        "relative_volume", "vwap_deviation",
        "funding_rate", "funding_zscore", "oi_change", "oi_divergence",
    })

    # ── O4: Two indicator caches — quick (50k) and full (140k) ──
    symbol_indicator_cache = {}       # full 140k bars
    symbol_indicator_cache_quick = {} # quick 50k bars
    for sym in symbols:
        # Full cache
        d = data_cache[sym]["train"]
        close, high, low, vol = d["close"], d["high"], d["low"], d["volume"]
        indicator_cache = {}
        for nm in DIRECTIONAL:
            if nm in _FACTOR_INDICATORS:
                # Pre-computed factor: register for ALL periods so random sampling hits
                vals = d.get(nm)
                if vals is not None and len(vals) > 0:
                    mad = np.median(np.abs(vals - np.median(vals)))
                    if mad > 0:
                        indicator_cache[(nm, 0)] = (vals, mad)
                        for _p in period_choices:
                            indicator_cache[(nm, _p)] = (vals, mad)
                continue
            for period in period_choices:
                try:
                    # V9 X2: shm-first lookup, compute only if missing.
                    try:
                        from services.indicator_precompute import get_shared_indicator as _sgi_full
                        vals = _sgi_full(sym, nm, period)
                    except Exception:
                        vals = None
                    if vals is None:
                        vals = zi.compute(nm, {"period": period}, close, high, low, vol) if rust else np.zeros(len(close))
                    mad = np.median(np.abs(vals - np.median(vals)))
                    if mad > 0:
                        indicator_cache[(nm, period)] = (vals, mad)
                except Exception as _e:
                    log.debug(f"Indicator {nm}(p={period}) failed for {sym}: {_e}")
                    continue
        symbol_indicator_cache[sym] = indicator_cache

        # Quick cache (first 50k bars)
        qd = quick_data_cache[sym]
        qclose, qhigh, qlow, qvol = qd["close"], qd["high"], qd["low"], qd["volume"]
        quick_cache = {}
        for nm in DIRECTIONAL:
            if nm in _FACTOR_INDICATORS:
                # Factor indicators: slice to quick length, register ALL periods
                vals = d.get(nm)
                if vals is not None and len(vals) > 0:
                    qvals = vals[:len(qclose)]
                    mad = np.median(np.abs(qvals - np.median(qvals)))
                    if mad > 0:
                        quick_cache[(nm, 0)] = (qvals, mad)
                        for _p in period_choices:
                            quick_cache[(nm, _p)] = (qvals, mad)
                continue
            for period in period_choices:
                try:
                    # V9 X2: shm-first lookup, fall back to compute.
                    try:
                        from services.indicator_precompute import get_shared_indicator as _sgi_quick
                        _full = _sgi_quick(sym, nm, period)
                        vals = _full[:len(qclose)] if _full is not None else None
                    except Exception:
                        vals = None
                    if vals is None:
                        vals = zi.compute(nm, {"period": period}, qclose, qhigh, qlow, qvol) if rust else np.zeros(len(qclose))
                    mad = np.median(np.abs(vals - np.median(vals)))
                    if mad > 0:
                        quick_cache[(nm, period)] = (vals, mad)
                except Exception:
                    continue
        symbol_indicator_cache_quick[sym] = quick_cache
        log.info(f"Indicator cache ready for {sym}: {len(indicator_cache)} full + {len(quick_cache)} quick entries")

    # Log regime distribution
    from collections import Counter
    regime_dist = Counter(symbol_regimes.values())
    log.info(f"Regime distribution: {dict(regime_dist)}")

    # Regime-balanced symbol selection: track champions per regime
    regime_champion_counts = {r: 0 for r in regime_dist}

    # ── O1: Initialize bloom filter and load ALL existing config hashes ──
    bloom = BloomFilter(capacity=200_000, fp_rate=0.001)
    try:
        existing_hashes = await db.fetch("""
            SELECT DISTINCT regime, passport->'arena1'->>'config_hash' as ch
            FROM champion_pipeline
            WHERE status NOT LIKE 'LEGACY%'
              AND passport->'arena1'->>'config_hash' IS NOT NULL
        """)
        for row in existing_hashes:
            bloom_key = f"{row['regime']}|{row['ch']}"
            bloom.add(bloom_key)
        log.info(f"Bloom filter loaded: {bloom.count} unique (regime,hash) pairs from ALL statuses")
    except Exception as e:
        log.warning(f"Bloom filter load failed: {e}")

    # ── Load A13 guidance on startup ──
    load_a13_guidance(log)

    # Track stats for logging
    stats = {
        "bloom_hits": 0, "early_exits": 0, "quick_rejects": 0,
        "a2_prescreen_rejects": 0, "full_backtests": 0, "champions_inserted": 0,
        "reject_few_trades": 0, "reject_low_wr": 0, "reject_neg_pnl": 0, "reject_low_score": 0,
    }

    log.info(
        f"Pipeline v6 running — worker={worker_id+1}/{worker_count}, "
        f"{len(symbols)} shard symbols, bloom={bloom.count} entries, "
        f"quick_bars={QUICK_BARS}, regime_cap={REGIME_CAP_PCT*100:.0f}%"
    )

    # --- Checkpoint: load on startup ---
    try:
        ckpt_row = await db.fetchrow(
            "SELECT results_json, contestant_idx FROM round_checkpoints WHERE arena = $1 ORDER BY created_at DESC LIMIT 1",
            checkpoint_arena
        )
        if ckpt_row:
            ckpt_data = ckpt_row["results_json"] if isinstance(ckpt_row["results_json"], dict) else json.loads(ckpt_row["results_json"])
            round_number = ckpt_data.get("round_number", 0)
            total_champions = ckpt_data.get("total_champions", 0)
            log.info(f"Resumed from checkpoint: round={round_number}, champions={total_champions}")
    except Exception as e:
        log.warning(f"Checkpoint load failed (starting fresh): {e}")

    while running:
        round_number += 1
        # V9 FIX (Codex #2): refresh A13 guidance every round (mtime-gated, cheap)
        load_a13_guidance(log)
        # --- Checkpoint: save every 50 rounds ---
        if round_number % 50 == 0 and round_number > 0:
            try:
                ckpt_id = f"arena1_w{worker_id}_ckpt_{round_number}"
                await db.execute("""
                    INSERT INTO round_checkpoints (round_id, arena, regime, contestant_idx, results_json, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, NOW(), NOW())
                    ON CONFLICT (round_id) DO UPDATE SET
                        results_json = EXCLUDED.results_json,
                        contestant_idx = EXCLUDED.contestant_idx,
                        updated_at = NOW()
                """, ckpt_id, checkpoint_arena, "checkpoint", round_number,
                    json.dumps({"round_number": round_number, "total_champions": total_champions, "stats": stats}))
            except Exception as e:
                log.warning(f"Checkpoint save failed: {e}")

        # ── Bloom periodic refresh: sync cross-worker discoveries every 200 rounds ──
        if round_number % 200 == 0 and round_number > 0:
            try:
                _rows = await db.fetch("""
                    SELECT DISTINCT regime, passport->'arena1'->>'config_hash' as ch
                    FROM champion_pipeline
                    WHERE status NOT LIKE 'LEGACY%'
                      AND passport->'arena1'->>'config_hash' IS NOT NULL
                """)
                _added = 0
                for _r in _rows:
                    _bk = f"{_r['regime']}|{_r['ch']}"
                    if _bk not in bloom:
                        bloom.add(_bk)
                        _added += 1
                if _added > 0:
                    log.info(f"Bloom refresh: +{_added} new entries from DB (total={bloom.count})")
            except Exception as e:
                log.warning(f"Bloom refresh failed: {e}")

            # V9 FIX (Codex #2): load_a13_guidance moved to every round (mtime-gated, cheap)
            # Cool-off bloom sync stays in 200-round block since bloom is in-memory persistent
            for _ck in _guidance_cache.get("cool_off", set()):
                if _ck not in bloom:
                    bloom.add(_ck)

        t0 = time.time()

        # ── O5: Regime-first balanced selection with HARD CAP ──
        _regime_to_syms = {}
        for _s in symbols:
            _r = symbol_regimes.get(_s, "CONSOLIDATION")
            _regime_to_syms.setdefault(_r, []).append(_s)
        _available_regimes = list(_regime_to_syms.keys())

        # Hard cap: exclude regimes that exceeded their share
        _total_champs = max(sum(regime_champion_counts.values()), 1)
        _eligible_regimes = [
            _r for _r in _available_regimes
            if regime_champion_counts.get(_r, 0) / _total_champs < REGIME_CAP_PCT
            or _total_champs < len(_available_regimes) * 4  # allow free exploration in early rounds
        ]
        if not _eligible_regimes:
            _eligible_regimes = _available_regimes  # fallback: don't deadlock

        # Among eligible, pick the one with fewest champions
        _min_count = min(regime_champion_counts.get(_r, 0) for _r in _eligible_regimes)
        _candidates = [_r for _r in _eligible_regimes if regime_champion_counts.get(_r, 0) <= _min_count + 2]
        regime = random.choice(_candidates)
        sym = random.choice(_regime_to_syms[regime])

        d = data_cache[sym]["train"]
        close, high, low, vol = d["close"], d["high"], d["low"], d["volume"]
        cost_bps = cost_model.get(sym).total_round_trip_bps

        # Quick-screen data for O4
        qd = quick_data_cache[sym]
        qclose, qhigh, qlow = qd["close"], qd["high"], qd["low"]

        best_score = -999.0; best_champion = None; best_configs = None; best_arrs = None
        indicator_cache = symbol_indicator_cache.get(sym, {})
        quick_cache = symbol_indicator_cache_quick.get(sym, {})
        if not indicator_cache:
            await asyncio.sleep(0)
            continue

        # ── O3: Adaptive early exit parameters ──
        EARLY_EXIT_AFTER = 80          # check after 80 contestants
        EARLY_EXIT_SCORE_THR = 0.55    # Wilson WR 0.55 → stop exploring

        for c in range(200):
            # ── O3: Early exit if strong champion found ──
            if c >= EARLY_EXIT_AFTER and best_champion is not None:
                if best_champion["wilson_wr"] >= EARLY_EXIT_SCORE_THR:
                    stats["early_exits"] += 1
                    break

            # ── O6: 3-indicator bias — weighted draw ──
            # 20% chance 2-ind, 60% chance 3-ind, 20% chance 4-ind
            _r = random.random()
            if _r < 0.20:
                n_ind = 2
            elif _r < 0.80:
                n_ind = 3
            else:
                n_ind = 4

            # V9 FIX (Codex #4): respect A13 mode. Only use guided weights when soft/active.
            _a13_mode = _guidance_cache.get("mode", "observe")
            _guided = _guidance_cache.get("weights")
            if _a13_mode in ("soft", "active") and _guided:
                _active_weights = _guided
            else:
                _active_weights = INDICATOR_WEIGHTS
            if random.random() < EXPLORE_RATE:
                names = sample_diverse_indicators(DIRECTIONAL, {x: 1.0 for x in DIRECTIONAL}, min(n_ind, len(DIRECTIONAL)))
            else:
                names = sample_diverse_indicators(DIRECTIONAL, _active_weights, n_ind)
            periods = [random.choice(period_choices) for _ in names]
            # Safety: deduplicate indicator names
            seen = set()
            deduped = [(n, p) for n, p in zip(names, periods) if n not in seen and not seen.add(n)]
            if len(deduped) < 2:
                continue
            names, periods = zip(*deduped)
            names, periods = list(names), list(periods)

            # ── O1: Bloom filter pre-check BEFORE any computation ──
            _sorted_key = "|".join(sorted(f"{n}_{p}" for n, p in zip(names, periods)))
            _config_hash = hashlib.md5(_sorted_key.encode()).hexdigest()[:16]
            _bloom_key = f"{regime}|{_config_hash}"
            if _bloom_key in bloom:
                stats["bloom_hits"] += 1
                continue

            arrs_quick = []
            arrs_full = []
            configs = []
            for nm, period in zip(names, periods):
                cached_full = indicator_cache.get((nm, period))
                cached_quick = quick_cache.get((nm, period))
                if cached_full is None or cached_quick is None:
                    continue
                vals_full, mad = cached_full
                if mad <= 0:
                    continue
                arrs_full.append(vals_full)
                arrs_quick.append(cached_quick[0])
                configs.append({"name": nm, "period": period})
            if len(configs) < 2:
                continue

            # Adaptive entry threshold
            n_ind_actual = len(configs)
            if n_ind_actual <= 2:
                entry_thr = 0.55
            elif n_ind_actual == 3:
                entry_thr = 0.60
            else:
                entry_thr = 0.55

            # ── O4: Stage 1 — Quick screen on 50k bars ──
            signals_q, _sz_q, _agr_q = generate_threshold_signals(
                [c["name"] for c in configs], arrs_quick,
                entry_threshold=0.55, exit_threshold=0.30, min_hold=60, cooldown=60, regime=regime,
            )
            bt_q = backtester.run(signals_q, qclose, sym, cost_bps, 480, high=qhigh, low=qlow, sizes=_sz_q)

            if bt_q.total_trades < 10:
                stats["quick_rejects"] += 1
                continue
            q_wr = wilson_lower(bt_q.winning_trades, bt_q.total_trades)
            if q_wr < 0.38:
                stats["quick_rejects"] += 1
                continue

            # ── O4: Stage 2 — Full backtest on 140k bars (only if quick screen passes) ──
            stats["full_backtests"] += 1
            signals, _sizes_full, _agr_full = generate_threshold_signals(
                [c["name"] for c in configs], arrs_full,
                entry_threshold=0.55, exit_threshold=0.30, min_hold=60, cooldown=60, regime=regime,
            )
            bt = backtester.run(signals, close, sym, cost_bps, 480, high=high, low=low, sizes=_sizes_full)

            if bt.total_trades < 30:
                stats["reject_few_trades"] += 1
                continue

            adjusted_wr = wilson_lower(bt.winning_trades, bt.total_trades)

            # Gate 1: Minimum WR (Wilson-adjusted)
            if adjusted_wr < 0.35:  # V9: lowered from 0.40 (88% reject rate)
                stats["reject_low_wr"] += 1
                continue

            # Gate 2: PnL floor
            if float(bt.net_pnl) < -1.0:  # V9 oneshot A1: relaxed from -0.3 (70% reject rate)
                stats["reject_neg_pnl"] += 1
                continue

            # ── O2: A2-aligned pre-screen — positive_count >= 2 ──
            _pos_count = (float(bt.net_pnl) > 0) + (float(bt.sharpe_ratio) > 0) + (float(bt.pnl_per_trade) > 0)
            if _pos_count < 2:
                stats["a2_prescreen_rejects"] += 1
                continue

            score = adjusted_wr * max(float(bt.net_pnl) + 1.0, 0.01)

            if score <= best_score:
                stats["reject_low_score"] += 1
            if score > best_score:
                best_score = score
                _matrix = np.column_stack(arrs_full)
                _medians = np.median(_matrix, axis=0).tolist()
                _mads = (np.median(np.abs(_matrix - np.median(_matrix, axis=0)), axis=0) * 1.4826).tolist()
                best_champion = {
                    "configs": configs,
                    "indicator_names": [cfg["name"] for cfg in configs],
                    "hash": f"v9_w{worker_id}_r{round_number}_c{c}_{sym}",
                    "wr": float(bt.win_rate),
                    "wilson_wr": float(adjusted_wr),
                    "pnl": float(bt.net_pnl),
                    "trades": int(bt.total_trades),
                    "sharpe": float(bt.sharpe_ratio),
                    "dd": float(bt.max_drawdown),
                    "expectancy": float(bt.pnl_per_trade),
                    "medians": _medians,
                    "mads": _mads,
                }
                best_configs = configs
                best_arrs = arrs_full


        elapsed = time.time() - t0

        if not best_champion or best_champion.get("trades", 0) < 30:
            if round_number % 10 == 0:
                log.info(f"R{round_number} | {sym}/{regime} | no champion | {elapsed:.1f}s")
            continue

        # ── O1: Bloom filter check (definitive, replaces DB query for most cases) ──
        _configs = best_champion["configs"]
        _sorted_key = "|".join(sorted(f"{c['name']}_{c.get('period', 14)}" for c in _configs))
        _config_hash = hashlib.md5(_sorted_key.encode()).hexdigest()[:16]
        _bloom_key = f"{regime}|{_config_hash}"

        if _bloom_key in bloom:
            stats["bloom_hits"] += 1
            continue

        # ── O2: A2-aligned confirmation — run with max_hold=120 (A2 params) ──
        signals_a2, _sz_a2, _agr_a2 = generate_threshold_signals(
            [c["name"] for c in best_configs], best_arrs,
            entry_threshold=0.55, exit_threshold=0.30, min_hold=60, cooldown=60, regime=regime,
        )
        bt_a2 = backtester.run(signals_a2, close, sym, cost_bps, 120, high=high, low=low, sizes=_sz_a2)
        _a2_pos = (float(bt_a2.net_pnl) > 0) + (float(bt_a2.sharpe_ratio) > 0) + (float(bt_a2.pnl_per_trade) > 0)
        if bt_a2.total_trades < 25 or _a2_pos < 2:
            stats["a2_prescreen_rejects"] += 1
            # Still add to bloom to prevent re-evaluation
            bloom.add(_bloom_key)
            continue

        # ── DB INSERTION ──
        total_champions += 1
        stats["champions_inserted"] += 1
        regime_champion_counts[regime] = regime_champion_counts.get(regime, 0) + 1
        bloom.add(_bloom_key)

        if total_champions % 200 == 0:
            log.info(f"Regime balance at champion #{total_champions}: {dict(regime_champion_counts)}")

        sym_info = data_cache[sym]
        passport = json.dumps({
            "arena1": {
                **{k: v for k, v in best_champion.items() if k not in ("medians", "mads")},
                "indicator_names": best_champion.get("indicator_names", [c["name"] for c in best_champion["configs"]]),
                "wilson_wr": best_champion["wilson_wr"],
                "raw_wr": best_champion["wr"],
                "config_hash": _config_hash,
                    "lane": _os.environ.get("A1_LANE", "baseline"),
                "a2_prescreen": {
                    "max_hold": 120,
                    "trades": bt_a2.total_trades,
                    "pnl": float(bt_a2.net_pnl),
                    "sharpe": float(bt_a2.sharpe_ratio),
                    "positive_count": int(_a2_pos),
                },
            },
            "normalization": {
                "medians": best_champion["medians"],
                "mads": best_champion["mads"],
            },
            "market_state": symbol_market_states.get(_s, {}).to_dict() if symbol_market_states.get(_s) else {},
            "data_split": {
                "train_bars": sym_info["train_bars"],
                "holdout_bars": sym_info["holdout_bars"],
                "split_ratio": TRAIN_SPLIT_RATIO,
            },
        })
        try:
            await db.execute("""
                INSERT INTO champion_pipeline
                (regime, indicator_hash, status, n_indicators, arena1_score, arena1_win_rate,
                 arena1_pnl, arena1_n_trades, passport, engine_hash, arena1_completed_at)
                VALUES ($1, $2, 'ARENA1_COMPLETE', $3, $4, $5, $6, $7, $8::jsonb, $9, NOW())
            """,
                regime, best_champion["hash"], len(best_champion["configs"]),
                best_score, best_champion["wilson_wr"], best_champion["pnl"],
                best_champion["trades"], passport, "zv5_v9",
            )
        except Exception as e:
            log.error(f"DB: {e}")

        if total_champions <= 20 or total_champions % 50 == 0:
            log.info(
                f"R{round_number} CHAMPION #{total_champions} | {sym}/{regime} | "
                f"WR={best_champion['wr']:.3f} Wilson={best_champion['wilson_wr']:.3f} "
                f"PnL={best_champion['pnl']:.4f} Sharpe={best_champion['sharpe']:.2f} "
                f"Trades={best_champion['trades']} | "
                f"A2pre: pnl={bt_a2.net_pnl:.4f} sharpe={bt_a2.sharpe_ratio:.2f} pos={_a2_pos} | "
                f"{elapsed:.1f}s"
            )

        # ── Stats logging every 500 rounds ──
        if round_number % 500 == 0:
            log.info(
                f"v6 STATS W{worker_id} R{round_number} | bloom_hits={stats['bloom_hits']} "
                f"quick_rej={stats['quick_rejects']} a2_pre_rej={stats['a2_prescreen_rejects']} "
                f"full_bt={stats['full_backtests']} early_exit={stats['early_exits']} "
                f"inserted={stats['champions_inserted']} | "
                f"bloom_size={bloom.count}"
            )

    await db.close()
    log.info(f"Stopped. rounds={round_number} champions={total_champions} | final_stats={json.dumps(stats)}")

if __name__ == "__main__":
    asyncio.run(main())
