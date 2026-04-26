# 11 — Parameter Drift Matrix

## Legend

- **NO_DRIFT** — current value matches expected from latest approved orders
- **EXPECTED_CHANGE** — value changed but with documented decision/PR
- **UNDOCUMENTED_DRIFT** — value changed without governance trail
- **CONFLICTING_SOURCES** — multiple sources disagree
- **MISSING_VALUE** — expected present but absent
- **UNKNOWN** — cannot determine

## A1 Generation

| Parameter | Expected | Source | Runtime | Drift | Severity |
| --- | --- | --- | --- | --- | --- |
| `N_GEN` | 20 | `arena_pipeline.py:751` = 20 | env not set | NO_DRIFT | — |
| `POP_SIZE` | 100 | line 752 = 100 | env not set | NO_DRIFT | — |
| `TOP_K` | 10 | line 753 = 10 | env not set | NO_DRIFT | — |
| Mutation/crossover | (defaults in AlphaEngine) | n/a | n/a | UNKNOWN | LOW |
| Indicator universe | 126 terminals | engine output | "AlphaEngine ready: 126 indicator terminals, 35 operators" | NO_DRIFT | — |
| Symbol universe | 14 syms (3 tiers) | cost_model.py | A1 cycles BTC/ETH/SOL/XRP/...; A23 reports 14 loaded | NO_DRIFT | — |

## Signal-to-Trade

| Parameter | Expected | Source | Runtime | Drift | Severity |
| --- | --- | --- | --- | --- | --- |
| `ENTRY_THR` | 0.80 | line 754 = 0.80 | env not set | NO_DRIFT | — |
| `EXIT_THR` | 0.50 | line 755 = 0.50 | env not set | NO_DRIFT | — |
| `MIN_HOLD` | 60 | line 756 = 60 | env not set | NO_DRIFT | — |
| `COOLDOWN` | 60 | line 757 = 60 | env not set | NO_DRIFT | — |
| `rank_window` | 500 | `alpha_signal.py:20` = 500 | n/a | NO_DRIFT | — |
| Direction mapping | rank>0.5 LONG, <0.5 SHORT | `alpha_signal.py:63-66` | confirmed via PR #40 forward-return diagnostic | NO_DRIFT | — |

## Validation / Backtest

| Parameter | Expected | Source | Runtime | Drift | Severity |
| --- | --- | --- | --- | --- | --- |
| `TRAIN_SPLIT_RATIO` | 0.7 | `arena_pipeline.py:283` = 0.7 | hardcoded | NO_DRIFT | — |
| `val_neg_pnl` gate | active, `<= 0` rejected | line 1036 active | active | NO_DRIFT | — |
| `val_few_trades` gate | active, < 15 rejected | line 1033 | active | NO_DRIFT | — |
| `val_low_sharpe` gate | active, < 0.3 rejected | line 1039 | active | NO_DRIFT | — |
| `val_low_wr` gate | active, wilson_lb < 0.52 rejected | line 1043 | active | NO_DRIFT | — |
| `train_pnl > 0` gate | **expected from PR #41 NG2** | NOT IMPLEMENTED | absent | **MISSING_VALUE** | **HIGH** |
| `combined_sharpe ≥ 0.4` gate | **expected from PR #41 NG2** | NOT IMPLEMENTED | absent | **MISSING_VALUE** | **HIGH** |
| Cross-symbol consistency ≥ 2/3 | **expected from PR #41 NG3** | NOT IMPLEMENTED | absent | **MISSING_VALUE** | **HIGH** |

## Cost / Horizon

| Parameter | Expected | Source | Runtime | Drift | Severity |
| --- | --- | --- | --- | --- | --- |
| Stable tier RT cost | 11.5 bps | `cost_model.py` | actual lookup at line 877 | NO_DRIFT | — |
| Diversified tier RT cost | 14.5 bps | cost_model.py | active | NO_DRIFT | — |
| High-Vol tier RT cost | 23.0 bps | cost_model.py | active | NO_DRIFT | — |
| Funding component | 1.0 bps flat per RT | cost_model.py | active | NO_DRIFT (modeling caveat: over-counts at typical hold) | LOW |
| `MAX_HOLD_BARS` (j01) | 120 | `j01/config/thresholds.py` | `_STRATEGY_MAX_HOLD = 120` | NO_DRIFT | — |
| `MAX_HOLD_BARS` (j02) | 120 | `j02/config/thresholds.py` | n/a (j02 not currently active) | NO_DRIFT | — |
| `ALPHA_FORWARD_HORIZON` (j01) | 60 | `j01/config/thresholds.py` | matches alpha_signal.min_hold | NO_DRIFT | — |

## Arena

| Parameter | Expected | Source | Runtime | Drift | Severity |
| --- | --- | --- | --- | --- | --- |
| `A2_MIN_TRADES` | 25 | `arena_gates.py:48` + `settings.py:29` + j01/j02 thresholds.py + tests/* | 25 | NO_DRIFT | — |
| `A2_MIN_TOTAL_PNL` | 0.0 | j01/j02 thresholds.py | n/a (A23 idle) | NO_DRIFT | — |
| A3 segments | 5 | j01/j02 | n/a (A23 idle) | NO_DRIFT | — |
| A3_MIN_TRADES_PER_SEGMENT | 15 | j01/j02 | n/a | NO_DRIFT | — |
| A3_WR_FLOOR | 0.45 | j01/j02 | n/a | NO_DRIFT | — |
| A4_REGIME_WR_FLOOR | 0.40 | j01 | n/a (A45 idle) | NO_DRIFT | — |
| Champion promotion | `champion_pipeline_fresh` write target | `arena_pipeline.py:685, 821` | **table missing** | **MISSING_VALUE** | **HIGH** |
| `deployable_count` semantics | derived from `champion_pipeline_fresh` per v0.7.1 | code references | **DB pipeline broken** | **MISSING_VALUE** | **HIGH** |

## DB / Schema

| Parameter | Expected | Source | Runtime | Drift | Severity |
| --- | --- | --- | --- | --- | --- |
| `champion_pipeline` (legacy) | renamed to `champion_legacy_archive` per v0.7.1 | migration script | **STILL EXISTS as TABLE** (v0.7.1 not applied) | **DB_STALE_STATE** | **CRITICAL** |
| `champion_pipeline_fresh` | TABLE | per v0.7.1 | **DOES NOT EXIST** | **MISSING_VALUE** | **CRITICAL** |
| `champion_pipeline_staging` | TABLE | per v0.7.1 | **DOES NOT EXIST** | **MISSING_VALUE** | **CRITICAL** |
| `champion_pipeline_rejected` | TABLE | per v0.7.1 | **DOES NOT EXIST** | **MISSING_VALUE** | **CRITICAL** |
| `champion_legacy_archive` | TABLE | per v0.7.1 | **DOES NOT EXIST** | **MISSING_VALUE** | **CRITICAL** |
| `engine_telemetry` | TABLE | per v0.7.1 | **DOES NOT EXIST** | **MISSING_VALUE** | **CRITICAL** |
| `admission_validator(BIGINT)` function | plpgsql function | per v0.7.1 | **DOES NOT EXIST** | **MISSING_VALUE** | **CRITICAL** |
| `fresh_insert_guard` trigger | trigger | per v0.7.1 | **DOES NOT EXIST** | **MISSING_VALUE** | **CRITICAL** |
| `zangetsu.admission_active` session var | exists | per v0.7.1 | **NOT REGISTERED** | **MISSING_VALUE** | **CRITICAL** |
| `champion_pipeline` row count | grow over time | n/a | **0 rows** | NO_DRIFT (consistent with empty pipeline) | — |

## Telemetry

| Parameter | Expected | Source | Runtime | Drift | Severity |
| --- | --- | --- | --- | --- | --- |
| `engine.jsonl` | active | `zangetsu/logs/engine.jsonl` | WRITING (3.2 MB, mtime 17:32Z) | NO_DRIFT | — |
| A1 worker logs | active | `/tmp/zangetsu_a1_w*.log` | WRITING (4 × 11+ MB) | NO_DRIFT | — |
| `arena_batch_metrics` events | per-batch JSONL | A1 logs | YES, parseable | NO_DRIFT | — |
| `engine_telemetry` DB inserts | succeed | line 329 | **silently swallowed** | **MISSING_VALUE** | HIGH |
| `run_id` provenance field | populated | provenance bundle | observed empty `""` in batch metrics | UNDOCUMENTED_DRIFT | MEDIUM |
| A23/A45 logs | active when promoting | `/tmp/zangetsu_a*.log` | STALE (8h) — consistent with empty pipeline | NO_DRIFT (root: empty pipeline) | — |

## Cold-Start Tooling

| Tool | Expected status | Current status | Drift | Severity |
| --- | --- | --- | --- | --- |
| `alpha_zoo_injection.py` | dry-run capable + validator-gated | dry-run flag parsed but unimplemented; validator function MISSING | **MISSING_VALUE** | **HIGH** |
| `seed_101_alphas.py` | DEPRECATED guard | DEPRECATED guard active | NO_DRIFT | — |
| `seed_101_alphas_batch2.py` | DEPRECATED guard | DEPRECATED guard active | NO_DRIFT | — |
| `factor_zoo.py` | DEPRECATED guard | DEPRECATED guard active | NO_DRIFT | — |
| `alpha_discovery.py` | DEPRECATED but cron-running | DEPRECATED guard + still cron-running every */30 min | **CONFLICTING_SOURCES** | **MEDIUM** |

## Governance

| Control | Expected | Actual | Drift | Severity |
| --- | --- | --- | --- | --- |
| Branch protection (5 flags) | all set | all set | NO_DRIFT | — |
| Gate-A workflow | active | active | NO_DRIFT | — |
| Gate-B workflow | active | active | NO_DRIFT | — |
| Signed commits | enforced | enforced | NO_DRIFT | — |
| Pre-commit fitness lock | active | active | NO_DRIFT | — |

## Drift Summary

| Severity | Count | Examples |
| --- | --- | --- |
| **CRITICAL** | **9** | DB schema gap (8 missing tables/functions/triggers/sessionvars) + champion_pipeline class drift |
| **HIGH** | **5** | train_pnl gate, combined_sharpe gate, cross-symbol gate, alpha_zoo_injection safety, deployable_count broken |
| **MEDIUM** | 2 | run_id empty, alpha_discovery cron+DEPRECATED conflict |
| **LOW** | 2 | mutation/crossover unknown, funding component bias |

## Key Conflict: V0.7.1 Code vs V0.7.0 DB

The codebase claims v0.7.2 (per VERSION_LOG) and references the v0.7.1 governance schema (champion_pipeline_fresh, staging, rejected, engine_telemetry, admission_validator). The live database is at **pre-v0.7.1 state** — only the legacy `champion_pipeline` exists. This is the **single largest risk factor**.

→ **Phase 11 output: parameter_drift_matrix.json** (data artifact) records all rows above in machine-readable form.
