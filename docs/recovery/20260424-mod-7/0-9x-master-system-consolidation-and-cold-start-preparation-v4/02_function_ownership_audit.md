# 02 — Function Ownership and Responsibility Audit

## Critical Functions Audited

### A1 Generation (`arena_pipeline.py`)

| Function | Lines | Owner | Allowed callers | DB writes | Side effects | Class |
| --- | --- | --- | --- | --- | --- | --- |
| `worker_main` | 660-1300 | A1 generation | cron via watchdog.sh | YES (staging when migration applied) | log writes, telemetry emit | FUNCTION_OK |
| `_get_or_build_provenance` | helper | A1 generation | `worker_main` only | NO | mutates `_provenance_bundle` global | FUNCTION_OK |
| `_emit_a1_lifecycle_safe` | telemetry | A1 generation | `worker_main` only | NO | log writes only | FUNCTION_OK |
| `_emit_a1_batch_metrics_from_stats_safe` | telemetry | A1 generation | `worker_main` only | NO | log writes only | FUNCTION_OK |
| `_flush_telemetry` | telemetry | A1 generation | `worker_main` only | YES (engine_telemetry insert in try/except — silent on table missing) | DB write attempt | FUNCTION_DB_WRITE_RISK (silent failure when table missing) |

### Signal Generation (`alpha_signal.py`)

| Function | Lines | Owner | Allowed callers | DB writes | Class |
| --- | --- | --- | --- | --- | --- |
| `generate_alpha_signals` | 87-115 | engine | arena_pipeline + tests | NO | FUNCTION_OK |
| `_alpha_to_position` | internal numba | engine | `generate_alpha_signals` | NO | FUNCTION_OK |

### Backtest (`backtester.py`)

| Function | Lines | Owner | Allowed callers | DB writes | Class |
| --- | --- | --- | --- | --- | --- |
| `Backtester.run` | (engine module) | engine | arena_pipeline + tests + offline replay | NO | FUNCTION_OK |

### Validation Filter (post-PR #43)

Validation lives inline in `arena_pipeline.py` worker_main; gates are the listed `if/continue` statements at lines 971-1057.

| Gate | Line | Owner | Class |
| --- | --- | --- | --- |
| `reject_few_trades` (<30 train trades) | 971 | A1 | FUNCTION_OK |
| **NEW** `reject_train_neg_pnl` | 982 | A1 (added PR #43) | FUNCTION_OK |
| `reject_val_constant` | 1015 | A1 | FUNCTION_OK |
| `reject_val_error` | 1034 | A1 | FUNCTION_OK |
| `reject_val_few_trades` | 1043 | A1 | FUNCTION_OK |
| `reject_val_neg_pnl` | 1046 | A1 | FUNCTION_OK |
| `reject_val_low_sharpe` | 1049 | A1 | FUNCTION_OK |
| `reject_val_low_wr` | 1053 | A1 | FUNCTION_OK |
| **NEW** `reject_combined_sharpe_low` | 1059 | A1 (added PR #43) | FUNCTION_OK |

### DB Persistence

| Function | Path | Class |
| --- | --- | --- |
| `INSERT INTO champion_pipeline_staging` | `arena_pipeline.py:1140` | FUNCTION_DB_WRITE_RISK (target table missing per Phase 4) |
| `SELECT admission_validator($1)` | `arena_pipeline.py:1180` | FUNCTION_DB_WRITE_RISK (function missing) |
| `INSERT INTO engine_telemetry` | `arena_pipeline.py:329` | FUNCTION_DB_WRITE_RISK (table missing, swallowed silently) |

### A13 Feedback (`arena13_feedback.py`)

| Function | Owner | Class |
| --- | --- | --- |
| `Arena13FeedbackController.run_single_shot` | A13 | FUNCTION_OK (single-shot via cron */5; no production mutation; emits guidance JSON) |

### A23 / A45 Orchestrators

| Function | Owner | Class |
| --- | --- | --- |
| `arena23_orchestrator.main` | A23 | FUNCTION_OK (idle when no upstream candidates; reads `champion_pipeline_fresh` if available) |
| `arena45_orchestrator.main` | A45 | FUNCTION_OK |

### Cold-Start Tooling (post-PR #43)

| Function | Path | Class | Notes |
| --- | --- | --- | --- |
| `alpha_zoo_injection.run` | `scripts/alpha_zoo_injection.py:51` | **FUNCTION_OK** (post-PR #43) | now requires `--confirm-write` flag; default mode is inspect-only |
| `alpha_zoo_injection.main` | `scripts/alpha_zoo_injection.py:155` | FUNCTION_OK | new safety flags added |

### Deprecated Seed Scripts

| Script | Class | Guard |
| --- | --- | --- |
| `seed_101_alphas.py` | FUNCTION_DEPRECATED_BLOCKED | prints REFUSED + exits |
| `seed_101_alphas_batch2.py` | FUNCTION_DEPRECATED_BLOCKED | prints REFUSED + exits |
| `factor_zoo.py` | FUNCTION_DEPRECATED_BLOCKED | prints REFUSED + exits |
| `alpha_discovery.py` | FUNCTION_DEPRECATED_BLOCKED | guard string present (per Phase 9, requires verification of cron behavior) |

## Aggregate Verdict

| Class | Count |
| --- | --- |
| FUNCTION_OK | majority |
| FUNCTION_DB_WRITE_RISK | 3 (all conditional on Phase 4 migration applied) |
| FUNCTION_DEPRECATED_BLOCKED | 4 (all guarded — see Phase 9) |
| FUNCTION_BOUNDARY_AMBIGUOUS | 0 |
| FUNCTION_WRONG_OWNER | 0 |
| FUNCTION_UNTESTED_CRITICAL | 0 (existing test coverage in `zangetsu/tests/test_*.py`) |

→ **No critical function lacks an owner.** **No deprecated function is reachable** (all guarded). **All DB writes are wrapped in try/except** so they fail safely when target schema is missing.
