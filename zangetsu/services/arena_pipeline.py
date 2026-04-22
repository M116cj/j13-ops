"""Arena Pipeline V10 — GP Alpha Expression Engine (replaces V9 indicator voting).

Key changes from V9:
- REMOVED: V9SearchCoordinator (Bayesian indicator combo search) — replaced by GP alpha evolution
- REMOVED: sample_diverse_indicators / weighted_sample / SIGNAL_GROUPS — no more combo voting
- REMOVED: generate_threshold_signals flow (kept available for A2 side, not used here)
- ADDED: AlphaEngine per-symbol evolution (GP on close/high/low/volume/returns)
- ADDED: build_indicator_cache (Rust-backed, shared across all alpha evals for this symbol/cycle)
- ADDED: generate_alpha_signals (rolling-rank → entry/exit signal)
- KEPT: DIRECTIONAL / REGIMES lists, regime detection, bloom dedup, A13 guidance, checkpoints

Alpha hash now drives dedup key (replaces config_hash).
engine_hash = 'zv5_v10_alpha'
"""
import sys, os, asyncio, signal, time, random, json, math, hashlib
sys.path.insert(0, '/home/j13/j13-ops')
sys.path.insert(0, '/home/j13/j13-ops/zangetsu/indicator_engine/target/release')
os.chdir('/home/j13/j13-ops')

import numpy as np
from zangetsu.services.pidlock import acquire_lock

# --- Regime classification from 1m data ---
from zangetsu.engine.components.p_value import load_baseline, compute_p_value, compute_pnl_p_value, is_significant
from zangetsu.engine.components.data_preprocessor import enrich_data_cache
from zangetsu.services.data_collector import merge_funding_to_1m, merge_oi_to_1m
from pathlib import Path

from zangetsu.services.shared_utils import wilson_lower
from zangetsu.services.shared_utils import (
    compute_momentum, compute_volatility, compute_volume_score,
    compute_funding, compute_oi, compute_extreme_flags,
    compute_atr, _ema,
)
from zangetsu.services.market_state import build_market_state
from zangetsu.services.bloom_service import (
    bloom_init as rbloom_init,
    bloom_add as rbloom_add,
    bloom_madd as rbloom_madd,
    bloom_count as rbloom_count,
)

# V10: GP alpha engine imports (replace V9SearchCoordinator)
from zangetsu.engine.components.alpha_engine import AlphaEngine
from zangetsu.engine.provenance import build_bundle, DirtyTreeError, ProvenanceBundle

# v0.7.1 governance: process-local telemetry counters flushed periodically
_telemetry_counters = {
    "compile_success_count": 0,
    "compile_exception_count": 0,
    "evaluate_success_count": 0,
    "evaluate_exception_count": 0,
    "indicator_terminal_call_count": 0,
    "indicator_terminal_exception_count": 0,
    "cache_hit_count": 0,
    "cache_miss_count": 0,
    "nan_inf_count": 0,
    "zero_variance_count": 0,
    "admitted_count": 0,
    "rejected_count": 0,
}
_provenance_bundle: ProvenanceBundle | None = None
_last_telemetry_flush_ts = 0.0

from zangetsu.engine.components.alpha_signal import generate_alpha_signals
from zangetsu.engine.components.indicator_bridge import build_indicator_cache

# Strategy-specific fitness injection (v0.7.0 engine split).
# STRATEGY_ID env must be set by the launcher (zangetsu_ctl.sh) to
# select which strategy project supplies the fitness function. Engine
# (zangetsu) is neutral; strategies (j01=harmonic, j02=icir, ...) own
# their own fitness contract.
STRATEGY_ID = os.environ.get("STRATEGY_ID", "j01")
if STRATEGY_ID == "j01":
    from j01.fitness import fitness_fn as _strategy_fitness_fn
elif STRATEGY_ID == "j02":
    from j02.fitness import fitness_fn as _strategy_fitness_fn
    from j02.config import thresholds as _strategy_thresholds
else:
    raise RuntimeError(
        f"Unknown STRATEGY_ID={STRATEGY_ID!r}. Supported: j01, j02."
    )
if STRATEGY_ID == "j01":
    from j01.config import thresholds as _strategy_thresholds  # noqa: E402
# Horizon alignment (v0.7.2): backtest max_hold comes from strategy config,
# not hardcoded 480. Must be >= min_hold and reasonable multiple of fitness horizon.
_STRATEGY_MAX_HOLD = int(_strategy_thresholds.MAX_HOLD_BARS)


TRAIN_SPLIT_RATIO = 0.7

# ── O5: Regime hard cap — no single regime exceeds 25% of total champions ──
REGIME_CAP_PCT = 0.25

# ── A13 Feedback Guidance (kept; regime_boosts / cool_off still usable) ──
A13_GUIDANCE_PATH = "/home/j13/j13-ops/zangetsu/config/a13_guidance.json"
_guidance_cache = {
    "weights": None,
    "cool_off": set(),
    "regime_boosts": {},
    "explore_rate": 0.50,
    "loaded_at": 0,
}


def _get_or_build_provenance(engine, worker_id: int, seed: int):
    global _provenance_bundle
    if _provenance_bundle is None:
        from zangetsu.config.settings import Settings
        settings_obj = Settings()
        _provenance_bundle = build_bundle(
            strategy_id=STRATEGY_ID,
            worker_id=worker_id,
            seed=seed,
            operator_names=engine._operator_names,
            indicator_terminal_names=engine._indicator_terminal_names,
            settings_obj=settings_obj,
        )
    return _provenance_bundle


async def _flush_telemetry(db):
    global _last_telemetry_flush_ts, _telemetry_counters
    import time as _t
    now = _t.time()
    if _last_telemetry_flush_ts > 0 and (now - _last_telemetry_flush_ts) < 300:
        return
    if _provenance_bundle is None:
        return
    rows = [
        (_provenance_bundle.run_id, _provenance_bundle.worker_id, STRATEGY_ID, k, float(v))
        for k, v in _telemetry_counters.items()
    ]
    try:
        await db.executemany(
            "INSERT INTO engine_telemetry (run_id, worker_id, strategy_id, metric_name, value) VALUES ($1, $2, $3, $4, $5)",
            rows,
        )
        _last_telemetry_flush_ts = now
        # Keep running counters (don't reset) — VIEWs look at last 1h window
    except Exception as _e:  # noqa: BLE001
        pass


def load_a13_guidance(log=None):
    """Load A13 feedback guidance. V10: still used for regime_boosts + cool_off hashes.
    Cheap mtime check short-circuits if file unchanged."""
    try:
        if not os.path.exists(A13_GUIDANCE_PATH):
            return
        mtime = os.path.getmtime(A13_GUIDANCE_PATH)
        if mtime <= _guidance_cache["loaded_at"]:
            return
        with open(A13_GUIDANCE_PATH, "r") as f:
            g = json.load(f)
        _guidance_cache["weights"] = g.get("indicator_weights") or None
        _guidance_cache["cool_off"] = set(g.get("cool_off_hashes", []))
        _guidance_cache["regime_boosts"] = g.get("regime_boosts", {})
        _guidance_cache["mode"] = g.get("mode", "observe")
        _guidance_cache["explore_rate"] = max(g.get("diversity_floor", 0.50), 0.20)
        _guidance_cache["loaded_at"] = mtime
        if log:
            log.info(
                f"A13 guidance loaded: mode={_guidance_cache['mode']} "
                f"cool_off={len(_guidance_cache['cool_off'])} "
                f"regime_boosts={len(_guidance_cache['regime_boosts'])}"
            )
    except Exception as e:
        if log:
            log.warning(f"A13 guidance load failed (using defaults): {e}")


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
    from zangetsu.config.settings import Settings
    from zangetsu.config.cost_model import CostModel
    from zangetsu.engine.components.backtester import Backtester
    from zangetsu.engine.components.logger import StructuredLogger

    settings = Settings()
    cost_model = CostModel()
    log = StructuredLogger(
        "arena_pipeline", settings.log_level, settings.log_file, settings.log_rotation_mb
    )
    worker_count = _env_int("A1_WORKER_COUNT", 1, 1)
    worker_id = min(_env_int("A1_WORKER_ID", 0, 0), worker_count - 1)
    checkpoint_arena = (
        f"arena1_pipeline_w{worker_id}" if worker_count > 1 else "arena1_pipeline"
    )

    log.info(
        f"Arena Pipeline V10 starting — GP alpha engine + bloom dedup | "
        f"worker={worker_id + 1}/{worker_count}"
    )

    try:
        import zangetsu_indicators as zi  # noqa: F401 — used indirectly via indicator_bridge
        rust = True
        log.info("Rust engine loaded")
    except ImportError:
        rust = False
        log.warning("Rust engine unavailable — indicator cache will be empty")

    class C:
        backtest_chunk_size = 10000
        backtest_gpu_enabled = False
        backtest_gpu_batch_size = 64

    backtester = Backtester(C())

    # Load random baseline for p-value computation (kept for downstream arenas)
    try:
        baseline = load_baseline()
        log.info(
            f"Random baseline loaded: WR_mean={baseline['wr_mean']:.4f} "
            f"WR_std={baseline['wr_std']:.4f} n={baseline['n_simulations']}"
        )
    except FileNotFoundError:
        baseline = None
        log.warning("Random baseline not found -- p-values will not be computed")

    import asyncpg
    # MEDIUM-M5: replace single connection with connection pool.
    # Daemon runs indefinitely; a single conn has no reconnect path on transient
    # network/PG blips. Pool auto-reconnects individual conns on failure.
    # min_size=2 keeps warm conns; max_size=10 bounded to avoid exhausting
    # server-side max_connections across 4 workers (=40 total cap).
    # Pool exposes .fetch/.fetchrow/.fetchval/.execute as high-level methods
    # that auto-acquire/release, so existing call sites work unchanged.
    db = await asyncpg.create_pool(
        host=settings.db_host,
        port=settings.db_port,
        database='zangetsu',
        user=settings.db_user,
        password=settings.db_password,
        min_size=2,
        max_size=10,
    )

    # V10: DIRECTIONAL retained only for indicator_bridge cache keys reference;
    # no longer used for combo sampling.
    DIRECTIONAL = [
        "rsi", "stochastic_k", "cci", "roc", "ppo", "cmo",
        "zscore", "trix", "tsi", "obv", "mfi", "vwap",
        "normalized_atr", "realized_vol", "bollinger_bw",
        "relative_volume", "vwap_deviation",
        "funding_rate", "funding_zscore", "oi_change", "oi_divergence",
    ]
    REGIMES = [
        "BULL_TREND", "BEAR_TREND", "CONSOLIDATION", "BULL_PULLBACK", "BEAR_RALLY",
        "ACCUMULATION", "DISTRIBUTION", "SQUEEZE", "CHOPPY_VOLATILE",
        "TOPPING", "BOTTOMING",
        "LIQUIDITY_CRISIS", "PARABOLIC",
    ]
    _ = REGIMES  # retained for future gate logic; not used directly

    # ── Data loading (unchanged from V9) ──
    import polars as pl
    data_cache = {}
    _data_dir = Path("/home/j13/j13-ops/zangetsu/data")
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

            funding_arr = merge_funding_to_1m(
                _data_dir / "ohlcv" / f"{sym}.parquet",
                _data_dir / "funding" / f"{sym}.parquet",
            )
            if funding_arr is not None:
                data_cache[sym]["train"]["funding_rate"] = funding_arr[-w:][:split].astype(np.float32)
                data_cache[sym]["holdout"]["funding_rate"] = funding_arr[-w:][split:].astype(np.float32)

            oi_arr = merge_oi_to_1m(
                _data_dir / "ohlcv" / f"{sym}.parquet",
                _data_dir / "oi" / f"{sym}.parquet",
            )
            if oi_arr is not None:
                data_cache[sym]["train"]["oi"] = oi_arr[-w:][:split].astype(np.float32)
                data_cache[sym]["holdout"]["oi"] = oi_arr[-w:][split:].astype(np.float32)

            fr_status = "yes" if funding_arr is not None else "no"
            oi_status = "yes" if oi_arr is not None else "no"
            log.info(
                f"Loaded {sym}: {w} bars (train: {split}, holdout: {w - split}) "
                f"funding={fr_status} oi={oi_status}"
            )
        except Exception as e:
            log.warning(f"Skip {sym}: {e}")

    # ── Nondimensionalization: enrich data_cache with all 5 factor categories ──
    enrich_data_cache(data_cache)
    log.info(
        "Factor enrichment complete: F1(momentum) F2(volatility) F3(volume) F4(funding) F5(OI)"
    )

    all_symbols = list(data_cache.keys())
    if worker_count > 1:
        symbols = [sym for idx, sym in enumerate(all_symbols) if idx % worker_count == worker_id]
    else:
        symbols = all_symbols
    if not symbols:
        raise RuntimeError(f"worker {worker_id} has no symbols to process")

    # ── 5-Factor Regime Detection v2 (unchanged) ──
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
                mom=float(mom[-1]),
                vol=float(volatility[-1]),
                vm=float(vm[-1]),
                fund=float(fund[-1]) if fund is not None else None,
                oi=float(oi_score[-1]) if oi_score is not None else None,
                ext_flags={k: bool(v[-1]) for k, v in ext.items()},
            )

            symbol_regimes[sym] = ms.regime
            symbol_market_states[sym] = ms
            data_cache[sym]["train"]["market_state"] = {
                "momentum": mom,
                "volatility": volatility,
                "volume": vm,
                "funding": fund,
                "oi": oi_score,
                "extreme_flags": ext,
            }
            log.info(
                f"Regime {sym}: {ms.regime} (L1={ms.regime_l1}, conf={ms.regime_confidence:.2f}, "
                f"mom={ms.momentum:.2f} vol={ms.volatility:.2f} vm={ms.volume:.2f} "
                f"fund={ms.funding:.2f} oi={ms.open_interest:.2f})"
            )
        except Exception as e:
            import traceback
            symbol_regimes[sym] = "CONSOLIDATION"
            symbol_market_states[sym] = None
            log.error(
                f"5-factor regime FAILED for {sym}: {type(e).__name__}: {e} | "
                f"trace: {traceback.format_exc()[:500]}"
            )

    round_number = 0
    total_champions = 0
    running = True

    def handle_sig(s, f):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    # ── V10: Build indicator cache ONCE per symbol at startup ──
    # (Rust-backed; ~len(DIRECTIONAL) * len(PERIODS) arrays per symbol.)
    # Kept in memory; reused across all GP evolutions for that symbol.
    # Patch E 2026-04-19: build TWO caches per symbol — one for the train slice
    # (used during GP evolve + train backtest) and one for the holdout slice
    # (swapped in for the v0.5.9 val backtest so indicator terminals evaluate
    # against holdout OHLCV, not stale train-window indicator values).
    symbol_indicator_cache = {}
    holdout_indicator_cache = {}
    for sym in symbols:
        d_train = data_cache[sym]["train"]
        d_hold = data_cache[sym]["holdout"]
        try:
            cache_train = build_indicator_cache(
                close=d_train["close"],
                high=d_train["high"],
                low=d_train["low"],
                volume=d_train["volume"],
                funding=d_train.get("funding_rate"),
                oi=d_train.get("oi"),
            )
            symbol_indicator_cache[sym] = cache_train
            log.info(f"Indicator cache built for {sym}: {len(cache_train)} arrays (train)")
        except Exception as e:
            log.warning(f"Indicator cache (train) failed for {sym}: {e}")
            symbol_indicator_cache[sym] = {}
        try:
            cache_hold = build_indicator_cache(
                close=d_hold["close"],
                high=d_hold["high"],
                low=d_hold["low"],
                volume=d_hold["volume"],
                funding=d_hold.get("funding_rate"),
                oi=d_hold.get("oi"),
            )
            holdout_indicator_cache[sym] = cache_hold
            log.info(f"Indicator cache built for {sym}: {len(cache_hold)} arrays (holdout)")
        except Exception as e:
            log.warning(f"Indicator cache (holdout) failed for {sym}: {e}")
            holdout_indicator_cache[sym] = {}

    # Log regime distribution
    from collections import Counter
    regime_dist = Counter(symbol_regimes.values())
    log.info(f"Regime distribution: {dict(regime_dist)}")

    # Regime-balanced symbol selection: track champions per regime
    regime_champion_counts = {r: 0 for r in regime_dist}

    # ── O1: Initialize bloom filter and load ALL existing alpha hashes ──
    bloom = BloomFilter(capacity=200_000, fp_rate=0.001)
    await rbloom_init(capacity=200_000, fp_rate=0.001)
    try:
        existing_hashes = await db.fetch("""
            SELECT DISTINCT regime, alpha_hash
            FROM champion_pipeline_fresh
            WHERE status NOT LIKE 'LEGACY%'
              AND alpha_hash IS NOT NULL
        """)
        _rbloom_batch = []
        for row in existing_hashes:
            bloom_key = f"{row['regime']}|{row['alpha_hash']}"
            bloom.add(bloom_key)
            _rbloom_batch.append(bloom_key)
        if _rbloom_batch:
            await rbloom_madd(_rbloom_batch)
        log.info(
            f"Bloom filter loaded: {bloom.count} local / "
            f"RedisBloom={await rbloom_count()} (regime,alpha_hash) pairs"
        )
    except Exception as e:
        log.warning(f"Bloom filter load failed: {e}")

    # ── Load A13 guidance on startup ──
    load_a13_guidance(log)

    stats = {
        "bloom_hits": 0,
        "evolutions_run": 0,
        "alphas_evaluated": 0,
        "reject_few_trades": 0,
        "reject_neg_pnl": 0,
        "reject_val_constant": 0,
        "reject_val_error": 0,
        "reject_val_few_trades": 0,
        "reject_val_neg_pnl": 0,
        "reject_val_low_sharpe": 0,
        "reject_val_low_wr": 0,
        "champions_inserted": 0,
        "alpha_compile_errors": 0,
    }

    log.info(
        f"Pipeline V10 running — worker={worker_id + 1}/{worker_count}, "
        f"{len(symbols)} shard symbols, bloom={bloom.count} entries, "
        f"regime_cap={REGIME_CAP_PCT * 100:.0f}%"
    )

    # --- Checkpoint: load on startup ---
    try:
        ckpt_row = await db.fetchrow(
            "SELECT results_json, contestant_idx FROM round_checkpoints "
            "WHERE arena = $1 ORDER BY created_at DESC LIMIT 1",
            checkpoint_arena,
        )
        if ckpt_row:
            ckpt_data = (
                ckpt_row["results_json"]
                if isinstance(ckpt_row["results_json"], dict)
                else json.loads(ckpt_row["results_json"])
            )
            round_number = ckpt_data.get("round_number", 0)
            total_champions = ckpt_data.get("total_champions", 0)
            log.info(
                f"Resumed from checkpoint: round={round_number}, "
                f"champions={total_champions}"
            )
    except Exception as e:
        log.warning(f"Checkpoint load failed (starting fresh): {e}")

    # ── V10 GP evolution parameters ──
    N_GEN = _env_int("ALPHA_N_GEN", 20, 5)
    POP_SIZE = _env_int("ALPHA_POP_SIZE", 100, 20)
    TOP_K = _env_int("ALPHA_TOP_K", 10, 1)
    ENTRY_THR = float(os.environ.get("ALPHA_ENTRY_THR", "0.80"))
    EXIT_THR = float(os.environ.get("ALPHA_EXIT_THR", "0.50"))
    MIN_HOLD = _env_int("ALPHA_MIN_HOLD", 60, 1)
    COOLDOWN = _env_int("ALPHA_COOLDOWN", 60, 1)

    while running:
        round_number += 1
        load_a13_guidance(log)

        # --- Checkpoint: save every 50 rounds ---
        if round_number % 50 == 0 and round_number > 0:
            try:
                ckpt_id = f"arena1_w{worker_id}_ckpt_{round_number}"
                await db.execute(
                    """
                    INSERT INTO round_checkpoints
                        (round_id, arena, regime, contestant_idx, results_json, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, NOW(), NOW())
                    ON CONFLICT (round_id) DO UPDATE SET
                        results_json = EXCLUDED.results_json,
                        contestant_idx = EXCLUDED.contestant_idx,
                        updated_at = NOW()
                    """,
                    ckpt_id,
                    checkpoint_arena,
                    "checkpoint",
                    round_number,
                    json.dumps(
                        {
                            "round_number": round_number,
                            "total_champions": total_champions,
                            "stats": stats,
                        }
                    ),
                )
            except Exception as e:
                log.warning(f"Checkpoint save failed: {e}")

        # ── Bloom periodic refresh: sync cross-worker discoveries ──
        # MEDIUM-M4: 4 workers with local Bloom filters drift apart between refreshes;
        # 200 rounds is too sparse — by then duplicates already slipped through all 4.
        # Tightened to 20 rounds (10x more frequent). Each refresh is a single DB fetch
        # against indexed columns (status, alpha_hash), cost is negligible relative to
        # one GP evolution round. Redis shared Bloom = follow-up PR.
        _BLOOM_REFRESH_EVERY = int(os.environ.get("ZV_BLOOM_REFRESH_EVERY", "20"))
        if round_number % _BLOOM_REFRESH_EVERY == 0 and round_number > 0:
            try:
                _rows = await db.fetch("""
                    SELECT DISTINCT regime, alpha_hash
                    FROM champion_pipeline_fresh
                    WHERE status NOT LIKE 'LEGACY%'
                      AND alpha_hash IS NOT NULL
                """)
                _added = 0
                for _r in _rows:
                    _bk = f"{_r['regime']}|{_r['alpha_hash']}"
                    if _bk not in bloom:
                        bloom.add(_bk)
                        await rbloom_add(_bk)
                        _added += 1
                if _added > 0:
                    log.info(
                        f"Bloom refresh: +{_added} new entries from DB "
                        f"(total={bloom.count})"
                    )
            except Exception as e:
                log.warning(f"Bloom refresh failed: {e}")

            for _ck in _guidance_cache.get("cool_off", set()):
                if _ck not in bloom:
                    bloom.add(_ck)
                    await rbloom_add(_ck)

        t0 = time.time()

        # ── O5: Regime-first balanced selection with HARD CAP ──
        _regime_to_syms = {}
        for _s in symbols:
            _r = symbol_regimes.get(_s, "CONSOLIDATION")
            _regime_to_syms.setdefault(_r, []).append(_s)
        _available_regimes = list(_regime_to_syms.keys())

        _total_champs = max(sum(regime_champion_counts.values()), 1)
        _eligible_regimes = [
            _r for _r in _available_regimes
            if regime_champion_counts.get(_r, 0) / _total_champs < REGIME_CAP_PCT
            or _total_champs < len(_available_regimes) * 4
        ]
        if not _eligible_regimes:
            _eligible_regimes = _available_regimes

        _min_count = min(regime_champion_counts.get(_r, 0) for _r in _eligible_regimes)
        _candidates = [
            _r for _r in _eligible_regimes
            if regime_champion_counts.get(_r, 0) <= _min_count + 2
        ]
        regime = random.choice(_candidates)
        sym = random.choice(_regime_to_syms[regime])

        d = data_cache[sym]["train"]
        close_f32 = d["close"]
        high_f32 = d["high"]
        low_f32 = d["low"]
        open_f32 = d["open"]
        vol_f32 = d["volume"]
        cost_bps = cost_model.get(sym).total_round_trip_bps

        # Float64 views for GP (DEAP primitives expect plain numpy arrays)
        close_f64 = close_f32.astype(np.float64)
        high_f64 = high_f32.astype(np.float64)
        low_f64 = low_f32.astype(np.float64)
        vol_f64 = vol_f32.astype(np.float64)
        returns_f64 = np.zeros_like(close_f64)
        returns_f64[1:] = (close_f64[1:] - close_f64[:-1]) / np.maximum(close_f64[:-1], 1e-10)

        # ── V10: Evolve alphas for this symbol / regime ──
        # end-to-end-upgrade fix 2026-04-19: pass pre-built indicator cache so the
        # 126 indicator terminals are not silently pruned to zeros by GP tournament
        # selection (was the latent cause of V10 path producing 0 A4-passing alphas).
        try:
            engine = AlphaEngine(indicator_cache=symbol_indicator_cache.get(sym, {}), fitness_fn=_strategy_fitness_fn)
            alphas = engine.evolve(
                close_f64, high_f64, low_f64, vol_f64, returns_f64,
                n_gen=N_GEN, pop_size=POP_SIZE, top_k=TOP_K,
            )
            stats["evolutions_run"] += 1
        except Exception as e:
            log.warning(f"AlphaEngine.evolve failed for {sym}/{regime}: {e}")
            await asyncio.sleep(0)
            continue

        if not alphas:
            log.debug(f"R{round_number} {sym}/{regime}: evolve produced no alphas")
            continue

        round_champions = 0
        for alpha_result in alphas:
            stats["alphas_evaluated"] += 1

            # ── Compile alpha AST → callable ──
            try:
                func = engine.ast_to_callable(alpha_result.ast_json)
                alpha_values = func(close_f64, high_f64, low_f64, close_f64, vol_f64)
                alpha_values = np.nan_to_num(
                    alpha_values, nan=0.0, posinf=0.0, neginf=0.0
                ).astype(np.float32)
            except Exception as _ce:
                stats["alpha_compile_errors"] += 1
                log.debug(f"Alpha compile/eval failed ({alpha_result.hash}): {_ce}")
                continue

            if np.std(alpha_values) < 1e-10:
                # Constant-output alpha — skip
                continue

            # ── Bloom dedup: (regime, alpha_hash) ──
            alpha_hash = alpha_result.hash or hashlib.md5(
                alpha_result.formula.encode()
            ).hexdigest()[:12]
            _bloom_key = f"{regime}|{alpha_hash}"
            if _bloom_key in bloom:
                stats["bloom_hits"] += 1
                continue

            # ── Convert alpha values to trade signals ──
            try:
                signals, sizes, agreements = generate_alpha_signals(
                    alpha_values,
                    entry_threshold=ENTRY_THR,
                    exit_threshold=EXIT_THR,
                    min_hold=MIN_HOLD,
                    cooldown=COOLDOWN,
                )
            except Exception as _se:
                log.debug(f"alpha→signal failed ({alpha_hash}): {_se}")
                continue

            # ── Backtest (unchanged Arena 1 gates) ──
            try:
                bt = backtester.run(
                    signals, close_f32, sym, cost_bps, _STRATEGY_MAX_HOLD,
                    high=high_f32, low=low_f32, sizes=sizes,
                )
            except Exception as _be:
                log.debug(f"backtest failed ({alpha_hash}): {_be}")
                continue

            if bt.total_trades < 30:
                stats["reject_few_trades"] += 1
                continue

            # ── v0.5.9: VAL backtest on holdout slice (prevents overfit flooding A4) ──
            # Gate calibration:
            #   val_trades >= 15   (CI half-width < 0.15 at WR=0.55)
            #   val_net_pnl > 0    (OOS profitable, non-negotiable honesty floor)
            #   val_sharpe >= 0.3  (positive risk-adjusted edge; leaves A4 0.5 margin)
            #   val_wilson_wr >= 0.52  (strictly > A4 promote_wilson_lb=0.50)
            d_val = data_cache[sym]["holdout"]
            # Patch E 2026-04-19: swap engine.indicator_cache to holdout slice
            # for the val evaluation, restore train cache via finally on ALL exits
            # (exception, continue, normal). Without this, indicator terminals return
            # TRAIN-window values while OHLCV is HOLDOUT → systemic val_neg_pnl
            # rejection (5353/5500 @ R50000 prior to this patch).
            engine.indicator_cache.clear()
            engine.indicator_cache.update(holdout_indicator_cache.get(sym, {}))
            try:
                av_val = func(
                    d_val["close"].astype(np.float64),
                    d_val["high"].astype(np.float64),
                    d_val["low"].astype(np.float64),
                    d_val["close"].astype(np.float64),
                    d_val["volume"].astype(np.float64),
                )
                av_val = np.nan_to_num(av_val, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
                if np.std(av_val) < 1e-10:
                    stats["reject_val_constant"] += 1
                    continue
                sig_v, sz_v, _ = generate_alpha_signals(
                    av_val,
                    entry_threshold=ENTRY_THR,
                    exit_threshold=EXIT_THR,
                    min_hold=MIN_HOLD,
                    cooldown=COOLDOWN,
                )
                bt_val = backtester.run(
                    sig_v,
                    d_val["close"].astype(np.float32),
                    sym,
                    cost_bps, _STRATEGY_MAX_HOLD,
                    high=d_val["high"].astype(np.float32),
                    low=d_val["low"].astype(np.float32),
                    sizes=sz_v,
                )
            except Exception as _ve:
                stats["reject_val_error"] += 1
                log.debug(f"val backtest failed ({alpha_hash}): {_ve}")
                continue
            finally:
                # Patch E: restore train cache on every exit path (success, except, continue).
                engine.indicator_cache.clear()
                engine.indicator_cache.update(symbol_indicator_cache.get(sym, {}))

            if bt_val.total_trades < 15:
                stats["reject_val_few_trades"] += 1
                continue
            if float(bt_val.net_pnl) <= 0:
                stats["reject_val_neg_pnl"] += 1
                continue
            if float(bt_val.sharpe_ratio) < 0.3:
                stats["reject_val_low_sharpe"] += 1
                continue
            val_wilson = wilson_lower(bt_val.winning_trades, bt_val.total_trades)
            if float(val_wilson) < 0.52:
                stats["reject_val_low_wr"] += 1
                continue

            adjusted_wr = wilson_lower(bt.winning_trades, bt.total_trades)
            # Score weighted by val_wilson (OOS) not train (prevents overfit score inflation).
            # Gemini 2026-04-19: clamp PnL contribution so a single lucky 15-trade outlier
            # cannot skew ELO pool. Cap at +5.0 (equivalent to strong-but-not-absurd alpha).
            _pnl_component = max(0.01, min(float(bt_val.net_pnl) + 1.0, 5.0))
            score = float(val_wilson) * _pnl_component

            # ── Build V10 passport with alpha_expression ──
            sym_info = data_cache[sym]
            passport = {
                "arena1": {
                    "alpha_expression": alpha_result.to_dict(),
                    "alpha_hash": alpha_hash,
                    "formula": alpha_result.formula,
                    "ic": float(alpha_result.ic),
                    "wr": float(bt.win_rate),
                    "wilson_wr": float(adjusted_wr),
                    "pnl": float(bt.net_pnl),
                    "sharpe": float(bt.sharpe_ratio),
                    "dd": float(bt.max_drawdown),
                    "expectancy": float(bt.pnl_per_trade),
                    "trades": int(bt.total_trades),
                    "hash": f"zv10_{alpha_hash}_{sym}",
                    "symbol": sym,
                    "regime": regime,
                    "lane": os.environ.get("A1_LANE", "baseline"),
                    "entry_threshold": ENTRY_THR,
                    "exit_threshold": EXIT_THR,
                    "min_hold": MIN_HOLD,
                    "cooldown": COOLDOWN,
                },
                "market_state": (
                    symbol_market_states.get(sym).to_dict()
                    if symbol_market_states.get(sym) is not None
                    else {}
                ),
                "data_split": {
                    "train_bars": sym_info["train_bars"],
                    "holdout_bars": sym_info["holdout_bars"],
                    "split_ratio": TRAIN_SPLIT_RATIO,
                },
                "val_metrics": {
                    "trades": int(bt_val.total_trades),
                    "net_pnl": float(bt_val.net_pnl),
                    "sharpe": float(bt_val.sharpe_ratio),
                    "win_rate": float(bt_val.win_rate),
                    "wilson_wr": float(val_wilson),
                    "max_drawdown": float(bt_val.max_drawdown),
                },
            }

            indicator_hash = f"zv10_{alpha_hash}_{sym}"

            # v0.7.1 governance: INSERT goes to staging, then validator
            _pb = _get_or_build_provenance(engine, worker_id, int(os.environ.get("A1_WORKER_SEED", str(worker_id))))
            try:
                staging_id = await db.fetchval(
                    """
                    INSERT INTO champion_pipeline_staging (
                        regime, indicator_hash, alpha_hash, status, n_indicators,
                        arena1_score, arena1_win_rate, arena1_pnl, arena1_n_trades,
                        passport, engine_hash, arena1_completed_at, strategy_id,
                        engine_version, git_commit, config_hash, grammar_hash,
                        fitness_version, patches_applied, run_id, worker_id,
                        seed, epoch
                    ) VALUES (
                        $1, $2, $3, 'ARENA1_COMPLETE', $4,
                        $5, $6, $7, $8,
                        $9::jsonb, 'zv5_v10_alpha', NOW(), $10,
                        $11, $12, $13, $14,
                        $15, $16, $17, $18,
                        $19, $20
                    )
                    RETURNING id
                    """,
                    regime,
                    indicator_hash,
                    alpha_hash,
                    1,
                    float(score),
                    float(bt.win_rate),
                    float(bt.net_pnl),
                    int(bt.total_trades),
                    json.dumps(passport),
                    STRATEGY_ID,
                    _pb.engine_version,
                    _pb.git_commit,
                    _pb.config_hash,
                    _pb.grammar_hash,
                    _pb.fitness_version,
                    _pb.patches_applied,
                    _pb.run_id,
                    _pb.worker_id,
                    _pb.seed,
                    _pb.epoch,
                )
                # Promote through validator
                verdict = await db.fetchval(
                    "SELECT admission_validator($1)", staging_id,
                )
                if verdict == "admitted":
                    _telemetry_counters["admitted_count"] += 1
                elif verdict.startswith("rejected:"):
                    _telemetry_counters["rejected_count"] += 1
                await _flush_telemetry(db)
            except Exception as e:
                log.error(f"DB insert failed ({alpha_hash}): {e}")
                continue

            # Mark bloom AFTER successful insert
            bloom.add(_bloom_key)
            await rbloom_add(_bloom_key)

            total_champions += 1
            round_champions += 1
            stats["champions_inserted"] += 1
            regime_champion_counts[regime] = regime_champion_counts.get(regime, 0) + 1

            if total_champions <= 20 or total_champions % 50 == 0:
                log.info(
                    f"R{round_number} CHAMPION #{total_champions} | {sym}/{regime} | "
                    f"alpha={alpha_hash} IC={alpha_result.ic:.4f} | "
                    f"WR={bt.win_rate:.3f} Wilson={adjusted_wr:.3f} "
                    f"PnL={bt.net_pnl:.4f} Sharpe={bt.sharpe_ratio:.2f} "
                    f"Trades={bt.total_trades}"
                )

        elapsed = time.time() - t0

        if round_number % 10 == 0:
            log.info(
                f"R{round_number} | {sym}/{regime} | "
                f"champions={round_champions}/{len(alphas)} | {elapsed:.1f}s | "
                f"rejects: few_trades={stats['reject_few_trades']} "
                f"val_few={stats['reject_val_few_trades']} "
                f"val_neg_pnl={stats['reject_val_neg_pnl']} "
                f"val_sharpe={stats['reject_val_low_sharpe']} "
                f"val_wr={stats['reject_val_low_wr']}"
            )

        if total_champions > 0 and total_champions % 200 == 0:
            log.info(
                f"Regime balance at champion #{total_champions}: "
                f"{dict(regime_champion_counts)}"
            )

        if round_number % 500 == 0:
            log.info(
                f"V10 STATS W{worker_id} R{round_number} | "
                f"evolutions={stats['evolutions_run']} "
                f"alphas_evaled={stats['alphas_evaluated']} "
                f"bloom_hits={stats['bloom_hits']} "
                f"compile_err={stats['alpha_compile_errors']} "
                f"inserted={stats['champions_inserted']} | "
                f"reject_few_trades={stats['reject_few_trades']} "
                f"reject_neg_pnl={stats['reject_neg_pnl']} "
                f"reject_val_few={stats['reject_val_few_trades']} "
                f"reject_val_neg={stats['reject_val_neg_pnl']} "
                f"reject_val_sharpe={stats['reject_val_low_sharpe']} "
                f"reject_val_wr={stats['reject_val_low_wr']} "
                f"reject_val_err={stats['reject_val_error']} "
                f"reject_val_const={stats['reject_val_constant']} | "
                f"bloom_size={bloom.count}"
            )

    await db.close()
    log.info(
        f"Stopped. rounds={round_number} champions={total_champions} | "
        f"final_stats={json.dumps(stats)}"
    )


if __name__ == "__main__":
    acquire_lock(f"arena_pipeline_w{os.environ.get('A1_WORKER_ID', '0')}")
    asyncio.run(main())
