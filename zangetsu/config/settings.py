"""All tunable constants, thresholds, and symbol configurations.

Every parameter that can be adjusted at runtime is centralized here.
Console API reads/writes these values; Arenas consume them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ── Arena 1: Indicator Discovery ─────────────────────────────────
ARENA1_ROUND_SIZE: int = 64                  # CONSOLE_HOOK: arena1_round_size
ARENA1_ADAPTIVE_MIN: int = 64                # CONSOLE_HOOK: arena1_adaptive_min
ARENA1_ADAPTIVE_MAX: int = 1024              # CONSOLE_HOOK: arena1_adaptive_max
ARENA1_STAGNATION_ROUNDS: int = 10           # CONSOLE_HOOK: arena1_stagnation_rounds
ARENA1_TOP_K: int = 20                       # CONSOLE_HOOK: arena1_top_k
ARENA1_DEDUP_CORR_THRESHOLD: float = 0.92    # CONSOLE_HOOK: arena1_dedup_corr_threshold

# ── Arena 2: Threshold Optimization ──────────────────────────────
ARENA2_ENTRY_THR_MIN: float = 0.80           # CONSOLE_HOOK: arena2_entry_thr_min
ARENA2_ENTRY_THR_MAX: float = 1.00           # CONSOLE_HOOK: arena2_entry_thr_max
ARENA2_ENTRY_THR_STEP: float = 0.05          # CONSOLE_HOOK: arena2_entry_thr_step
ARENA2_EXIT_THR_MIN: float = 0.50            # CONSOLE_HOOK: arena2_exit_thr_min
ARENA2_EXIT_THR_MAX: float = 0.80            # CONSOLE_HOOK: arena2_exit_thr_max
ARENA2_EXIT_THR_STEP: float = 0.05           # CONSOLE_HOOK: arena2_exit_thr_step
ARENA2_MIN_TRADES: int = 30                  # CONSOLE_HOOK: arena2_min_trades
ARENA2_WR_FLOOR: float = 0.52               # CONSOLE_HOOK: arena2_wr_floor

# ── Arena 3: PnL Training ────────────────────────────────────────
ARENA3_COST_BPS: float = 4.5                 # CONSOLE_HOOK: arena3_cost_bps
ARENA3_MAX_HOLD_BARS: int = 48               # CONSOLE_HOOK: arena3_max_hold_bars
ARENA3_MIN_PNL_PER_TRADE: float = 0.0005     # CONSOLE_HOOK: arena3_min_pnl_per_trade
ARENA3_SLIPPAGE_BPS: float = 1.0             # CONSOLE_HOOK: arena3_slippage_bps

# ── Arena 4: Validation Gate ─────────────────────────────────────
ARENA4_TRAIN_RATIO: float = 0.6              # CONSOLE_HOOK: arena4_train_ratio
ARENA4_VAL_RATIO: float = 0.2               # CONSOLE_HOOK: arena4_val_ratio
ARENA4_TEST_RATIO: float = 0.2              # CONSOLE_HOOK: arena4_test_ratio
ARENA4_MIN_WR_GATE: float = 0.53            # CONSOLE_HOOK: arena4_min_wr_gate
ARENA4_MIN_PNL_GATE: float = 0.001          # CONSOLE_HOOK: arena4_min_pnl_gate
ARENA4_MAX_DRAWDOWN: float = 0.15           # CONSOLE_HOOK: arena4_max_drawdown
ARENA4_MIN_SHARPE: float = 0.8              # CONSOLE_HOOK: arena4_min_sharpe

# ── Arena 5: ELO Tournament ──────────────────────────────────────
ARENA5_INITIAL_ELO: float = 1500.0           # CONSOLE_HOOK: arena5_initial_elo
ARENA5_K_FACTOR: float = 32.0               # CONSOLE_HOOK: arena5_k_factor
ARENA5_MATCH_ROUNDS: int = 100              # CONSOLE_HOOK: arena5_match_rounds
ARENA5_MIN_ELO_PROMOTE: float = 1600.0      # CONSOLE_HOOK: arena5_min_elo_promote
ARENA5_DECAY_PER_IDLE_ROUND: float = 5.0    # CONSOLE_HOOK: arena5_decay_per_idle_round

# ── Arena 13: Evolution Factory ───────────────────────────────────
ARENA13_POPULATION_SIZE: int = 128           # CONSOLE_HOOK: arena13_population_size
ARENA13_MUTATION_RATE: float = 0.15          # CONSOLE_HOOK: arena13_mutation_rate
ARENA13_CROSSOVER_RATE: float = 0.3          # CONSOLE_HOOK: arena13_crossover_rate
ARENA13_ELITE_KEEP: int = 8                 # CONSOLE_HOOK: arena13_elite_keep
ARENA13_MAX_GENERATIONS: int = 500           # CONSOLE_HOOK: arena13_max_generations
ARENA13_STAGNATION_LIMIT: int = 30           # CONSOLE_HOOK: arena13_stagnation_limit

# ── Scoring ──────────────────────────────────────────────────────
SCORING_WR_WEIGHT: float = 0.4              # CONSOLE_HOOK: scoring_wr_weight
SCORING_PNL_WEIGHT: float = 0.4             # CONSOLE_HOOK: scoring_pnl_weight
SCORING_STABILITY_WEIGHT: float = 0.2       # CONSOLE_HOOK: scoring_stability_weight
SCORING_DECAY_TAU: float = 30.0             # CONSOLE_HOOK: scoring_decay_tau
SCORING_DEFERRED_EVAL_BARS: int = 100       # CONSOLE_HOOK: scoring_deferred_eval_bars

# ── Voting ───────────────────────────────────────────────────────
VOTER_AGREEMENT_THRESHOLD: float = 0.80      # CONSOLE_HOOK: voter_agreement_threshold
VOTER_DEFAULT_K: int = 3                    # CONSOLE_HOOK: voter_default_k
VOTER_DEFAULT_N: int = 5                    # CONSOLE_HOOK: voter_default_n
VOTER_SHORT_CIRCUIT: bool = True            # CONSOLE_HOOK: voter_short_circuit

# ── Normalizer ───────────────────────────────────────────────────
NORMALIZER_DRIFT_THRESHOLD: float = 3.0     # CONSOLE_HOOK: normalizer_drift_threshold
NORMALIZER_WINDOW: int = 500                # CONSOLE_HOOK: normalizer_window
NORMALIZER_CLIP_SIGMA: float = 5.0          # CONSOLE_HOOK: normalizer_clip_sigma

# ── Backtester ───────────────────────────────────────────────────
BACKTEST_CHUNK_SIZE: int = 10000             # CONSOLE_HOOK: backtest_chunk_size
BACKTEST_GPU_ENABLED: bool = True            # CONSOLE_HOOK: backtest_gpu_enabled
BACKTEST_GPU_BATCH_SIZE: int = 4096          # CONSOLE_HOOK: backtest_gpu_batch_size

# ── GPU Pool ─────────────────────────────────────────────────────
GPU_VRAM_LIMIT_MB: int = 8192               # CONSOLE_HOOK: gpu_vram_limit_mb
GPU_MAX_CONCURRENT: int = 4                 # CONSOLE_HOOK: gpu_max_concurrent
GPU_HEALTH_CHECK_INTERVAL: int = 60         # CONSOLE_HOOK: gpu_health_check_interval

# ── Database ─────────────────────────────────────────────────────
DB_HOST: str = os.getenv("ZV5_DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("ZV5_DB_PORT", "5432"))
DB_NAME: str = os.getenv("ZV5_DB_NAME", "zangetsu")
DB_USER: str = os.getenv("ZV5_DB_USER", "zangetsu")
DB_PASSWORD: str = os.getenv("ZV5_DB_PASSWORD", "9c424966bebb05a42966186bb22d7480")  # TODO-SECURITY: rotate and set via env only, remove default
DB_POOL_MIN: int = 2                        # CONSOLE_HOOK: db_pool_min
DB_POOL_MAX: int = 10                       # CONSOLE_HOOK: db_pool_max
DB_STATEMENT_TIMEOUT: int = 30000           # CONSOLE_HOOK: db_statement_timeout_ms

# ── Data ─────────────────────────────────────────────────────────
PARQUET_DIR: str = os.getenv(
    "ZV5_PARQUET_DIR", "/home/j13/j13-ops/zangetsu/data/ohlcv"
)                                           # CONSOLE_HOOK: parquet_dir

# ── Symbols ──────────────────────────────────────────────────────
DEFAULT_SYMBOLS: List[str] = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
    "XRPUSDT", "DOGEUSDT", "LINKUSDT", "AAVEUSDT",
    "AVAXUSDT", "DOTUSDT", "FILUSDT",
    "1000PEPEUSDT", "1000SHIBUSDT", "GALAUSDT",
]                                           # CONSOLE_HOOK: symbols

# ── Indicator Engine ─────────────────────────────────────────────
INDICATOR_LIBRARY_PATH: str = os.getenv(
    "ZV5_INDICATOR_LIB",
    "/home/j13/j13-ops/zangetsu/indicator_engine/target/release/libzangetsu_indicators.so",
)                                           # CONSOLE_HOOK: indicator_library_path

# ── Logging ──────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("ZV5_LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("ZV5_LOG_FILE", "/home/j13/j13-ops/zangetsu/logs/engine.jsonl")
LOG_ROTATION_MB: int = 50                   # CONSOLE_HOOK: log_rotation_mb

# ── Health / Metrics ─────────────────────────────────────────────
HEALTH_PORT: int = int(os.getenv("ZV5_HEALTH_PORT", "9100"))
METRICS_EXPORT_INTERVAL: int = 15           # CONSOLE_HOOK: metrics_export_interval

# ── Checkpoint ───────────────────────────────────────────────────
CHECKPOINT_INTERVAL_ROUNDS: int = 5         # CONSOLE_HOOK: checkpoint_interval_rounds
CHECKPOINT_MAX_AGE_HOURS: int = 48          # CONSOLE_HOOK: checkpoint_max_age_hours

# ── Risk / ELO Global ────────────────────────────────────────────
RISK_MAX_POSITION_PCT: float = 0.02         # CONSOLE_HOOK: risk_max_position_pct
RISK_MAX_CORRELATED: int = 3               # CONSOLE_HOOK: risk_max_correlated
ELO_PROMOTION_THRESHOLD: float = 1600.0     # CONSOLE_HOOK: elo_promotion_threshold
ELO_RELEGATION_THRESHOLD: float = 1350.0    # CONSOLE_HOOK: elo_relegation_threshold


@dataclass
class Settings:
    """Runtime settings container. Initialized from module-level defaults,
    overridable via console API at runtime.

    Usage:
        settings = Settings()  # loads all defaults
        settings.arena1_round_size = 128  # override via console
    """

    # Arena 1
    arena1_round_size: int = ARENA1_ROUND_SIZE
    arena1_adaptive_min: int = ARENA1_ADAPTIVE_MIN
    arena1_adaptive_max: int = ARENA1_ADAPTIVE_MAX
    arena1_stagnation_rounds: int = ARENA1_STAGNATION_ROUNDS
    arena1_top_k: int = ARENA1_TOP_K
    arena1_dedup_corr_threshold: float = ARENA1_DEDUP_CORR_THRESHOLD

    # Arena 2
    arena2_entry_thr_min: float = ARENA2_ENTRY_THR_MIN
    arena2_entry_thr_max: float = ARENA2_ENTRY_THR_MAX
    arena2_entry_thr_step: float = ARENA2_ENTRY_THR_STEP
    arena2_exit_thr_min: float = ARENA2_EXIT_THR_MIN
    arena2_exit_thr_max: float = ARENA2_EXIT_THR_MAX
    arena2_exit_thr_step: float = ARENA2_EXIT_THR_STEP
    arena2_min_trades: int = ARENA2_MIN_TRADES
    arena2_wr_floor: float = ARENA2_WR_FLOOR

    # Arena 3
    arena3_cost_bps: float = ARENA3_COST_BPS
    arena3_max_hold_bars: int = ARENA3_MAX_HOLD_BARS
    arena3_min_pnl_per_trade: float = ARENA3_MIN_PNL_PER_TRADE
    arena3_slippage_bps: float = ARENA3_SLIPPAGE_BPS

    # Arena 4
    arena4_train_ratio: float = ARENA4_TRAIN_RATIO
    arena4_val_ratio: float = ARENA4_VAL_RATIO
    arena4_test_ratio: float = ARENA4_TEST_RATIO
    arena4_min_wr_gate: float = ARENA4_MIN_WR_GATE
    arena4_min_pnl_gate: float = ARENA4_MIN_PNL_GATE
    arena4_max_drawdown: float = ARENA4_MAX_DRAWDOWN
    arena4_min_sharpe: float = ARENA4_MIN_SHARPE

    # Arena 5
    arena5_initial_elo: float = ARENA5_INITIAL_ELO
    arena5_k_factor: float = ARENA5_K_FACTOR
    arena5_match_rounds: int = ARENA5_MATCH_ROUNDS
    arena5_min_elo_promote: float = ARENA5_MIN_ELO_PROMOTE
    arena5_decay_per_idle_round: float = ARENA5_DECAY_PER_IDLE_ROUND

    # Arena 13
    arena13_population_size: int = ARENA13_POPULATION_SIZE
    arena13_mutation_rate: float = ARENA13_MUTATION_RATE
    arena13_crossover_rate: float = ARENA13_CROSSOVER_RATE
    arena13_elite_keep: int = ARENA13_ELITE_KEEP
    arena13_max_generations: int = ARENA13_MAX_GENERATIONS
    arena13_stagnation_limit: int = ARENA13_STAGNATION_LIMIT

    # Scoring
    scoring_wr_weight: float = SCORING_WR_WEIGHT
    scoring_pnl_weight: float = SCORING_PNL_WEIGHT
    scoring_stability_weight: float = SCORING_STABILITY_WEIGHT
    scoring_decay_tau: float = SCORING_DECAY_TAU
    scoring_deferred_eval_bars: int = SCORING_DEFERRED_EVAL_BARS

    # Voter
    voter_agreement_threshold: float = VOTER_AGREEMENT_THRESHOLD
    voter_default_k: int = VOTER_DEFAULT_K
    voter_default_n: int = VOTER_DEFAULT_N
    voter_short_circuit: bool = VOTER_SHORT_CIRCUIT

    # Normalizer
    normalizer_drift_threshold: float = NORMALIZER_DRIFT_THRESHOLD
    normalizer_window: int = NORMALIZER_WINDOW
    normalizer_clip_sigma: float = NORMALIZER_CLIP_SIGMA

    # Backtest
    backtest_chunk_size: int = BACKTEST_CHUNK_SIZE
    backtest_gpu_enabled: bool = BACKTEST_GPU_ENABLED
    backtest_gpu_batch_size: int = BACKTEST_GPU_BATCH_SIZE

    # GPU
    gpu_vram_limit_mb: int = GPU_VRAM_LIMIT_MB
    gpu_max_concurrent: int = GPU_MAX_CONCURRENT
    gpu_health_check_interval: int = GPU_HEALTH_CHECK_INTERVAL

    # DB
    db_host: str = DB_HOST
    db_port: int = DB_PORT
    db_name: str = DB_NAME
    db_user: str = DB_USER
    db_password: str = DB_PASSWORD
    db_pool_min: int = DB_POOL_MIN
    db_pool_max: int = DB_POOL_MAX
    db_statement_timeout: int = DB_STATEMENT_TIMEOUT

    # Data
    parquet_dir: str = PARQUET_DIR
    symbols: List[str] = field(default_factory=lambda: list(DEFAULT_SYMBOLS))

    # Indicator
    indicator_library_path: str = INDICATOR_LIBRARY_PATH

    # Logging
    log_level: str = LOG_LEVEL
    log_file: str = LOG_FILE
    log_rotation_mb: int = LOG_ROTATION_MB

    # Health
    health_port: int = HEALTH_PORT
    metrics_export_interval: int = METRICS_EXPORT_INTERVAL

    # Checkpoint
    checkpoint_interval_rounds: int = CHECKPOINT_INTERVAL_ROUNDS
    checkpoint_max_age_hours: int = CHECKPOINT_MAX_AGE_HOURS

    # Risk
    risk_max_position_pct: float = RISK_MAX_POSITION_PCT
    risk_max_correlated: int = RISK_MAX_CORRELATED
    elo_promotion_threshold: float = ELO_PROMOTION_THRESHOLD
    elo_relegation_threshold: float = ELO_RELEGATION_THRESHOLD

    def to_dict(self) -> Dict[str, object]:
        """Serialize all settings for console API / checkpoint."""
        from dataclasses import asdict
        return asdict(self)

    def update(self, overrides: Dict[str, object]) -> List[str]:
        """Apply runtime overrides. Returns list of changed field names."""
        changed: List[str] = []
        for key, value in overrides.items():
            if hasattr(self, key):
                old = getattr(self, key)
                if old != value:
                    setattr(self, key, value)
                    changed.append(key)
        return changed
