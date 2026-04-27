# 07 — Parameter Source-of-Truth Matrix (Track F)

Adapted and extended from PR #42 (`docs/recovery/.../0-9x-system-parameter-integrity-audit/`). Updated to reflect Tracks D + E code changes from this PR.

## A1 Generation

| Parameter | Canonical source | Effective value | Env override | Drift |
| --- | --- | --- | --- | --- |
| `N_GEN` | `arena_pipeline.py:751` (default 20) | 20 | `ALPHA_N_GEN` (not set) | NO_DRIFT |
| `POP_SIZE` | line 752 (default 100) | 100 | `ALPHA_POP_SIZE` (not set) | NO_DRIFT |
| `TOP_K` | line 753 (default 10) | 10 | `ALPHA_TOP_K` (not set) | NO_DRIFT |
| Mutation/crossover rates | AlphaEngine internals | unknown | none | UNKNOWN_LOW |
| Indicator universe | engine startup output | 126 terminals × 35 operators | none | NO_DRIFT |
| Symbol universe | `cost_model.py` table | 14 (3 tiers) | none | NO_DRIFT |
| Worker count | `arena_pipeline.py` workers | 4 (per cron watchdog) | none | NO_DRIFT |
| Random seed | `A1_WORKER_SEED` env (fallback worker_id) | per-worker deterministic | optional env | NO_DRIFT |

## Signal-to-Trade

| Parameter | Source | Value | Drift |
| --- | --- | --- | --- |
| `ENTRY_THR` | line 754 | 0.80 | NO_DRIFT |
| `EXIT_THR` | line 755 | 0.50 | NO_DRIFT |
| `MIN_HOLD` | line 756 | 60 | NO_DRIFT |
| `COOLDOWN` | line 757 | 60 | NO_DRIFT |
| `rank_window` | `alpha_signal.py:20` | 500 | NO_DRIFT |
| Direction mapping | `alpha_signal.py:63-66` | rank>0.5 LONG, <0.5 SHORT | NO_DRIFT (verified by PR #40 forward-return diagnostic) |

## Backtest / Validation (UPDATED for Track D)

| Parameter | Source | Value | Drift |
| --- | --- | --- | --- |
| `TRAIN_SPLIT_RATIO` | `arena_pipeline.py:283` | 0.7 | NO_DRIFT |
| `cost_bps` per symbol | `cost_model.py:total_round_trip_bps` | 11.5 / 14.5 / 23.0 bps | NO_DRIFT |
| `MAX_HOLD_BARS` | `j01/config/thresholds.py` | 120 | NO_DRIFT |
| `val_neg_pnl` gate | `arena_pipeline.py:1046` | active (`<= 0` rejected) | NO_DRIFT |
| `val_few_trades` gate | line 1043 | active (`< 15`) | NO_DRIFT |
| `val_low_sharpe` gate | line 1049 | active (`< 0.3`) | NO_DRIFT |
| `val_low_wr` gate | line 1053 | active (`wilson_lb < 0.52`) | NO_DRIFT |
| **NEW `train_neg_pnl` gate** | `arena_pipeline.py:982` (PR #43) | **active (`<= 0`)** | **EXPECTED_CHANGE — strengthens contract** |
| **NEW `combined_sharpe_low` gate** | `arena_pipeline.py:1059` (PR #43) | **active (`< 0.4`)** | **EXPECTED_CHANGE — strengthens contract** |
| `cross_symbol_consistency` gate | not implemented | DEFERRED | DEFERRED to architectural refactor order |

## Arena (UNCHANGED)

| Parameter | Source | Value | Drift |
| --- | --- | --- | --- |
| `A2_MIN_TRADES` | `arena_gates.py:48` + `settings.py:29` + j01/j02 + tests | **25** | **NO_DRIFT** (verified across 5 source locations) |
| `A2_MIN_TOTAL_PNL` | j01/j02 thresholds.py | 0.0 | NO_DRIFT |
| `A3_SEGMENTS` | j01/j02 thresholds.py | 5 | NO_DRIFT |
| `A3_MIN_TRADES_PER_SEGMENT` | j01/j02 | 15 | NO_DRIFT |
| `A3_WR_FLOOR` | j01/j02 | 0.45 | NO_DRIFT |
| `A4_REGIME_WR_FLOOR` | j01 | 0.40 | NO_DRIFT |
| Champion promotion semantics | `arena45_orchestrator.py` + j01 thresholds | unchanged | NO_DRIFT |
| `deployable_count` semantics | `j01_status` view (per v0.7.1) | semantics intact in code; DB pipeline broken (Track A) | DEFERRED |

## DB / Session

| Parameter | Expected | Actual | Drift |
| --- | --- | --- | --- |
| `champion_pipeline_fresh` | TABLE per v0.7.1 | MISSING | **CRITICAL — Track A BLOCKED** |
| `champion_pipeline_staging` | TABLE per v0.7.1 | MISSING | **CRITICAL** |
| `admission_validator()` | function per v0.7.1 | MISSING | **CRITICAL** |
| `zangetsu.admission_active` session var | registered | MISSING | **CRITICAL** |

## Cold-Start (NEW for Track E)

| Parameter | Source | Default | Drift |
| --- | --- | --- | --- |
| `--inspect-only` | `alpha_zoo_injection.py` argparse | OFF | NEW (added PR #43) |
| `--dry-run` | argparse | OFF | NEW (added PR #43) |
| `--no-db-write` | argparse | **ON** (default) | NEW (added PR #43) |
| `--confirm-write` | argparse | OFF (default deny) | NEW (added PR #43) |
| Default mode | argparse | inspect-only behavior or abort | EXPECTED_CHANGE — was unsafe-by-default, now safe |

## Governance

| Item | Status |
| --- | --- |
| Branch protection 5/5 | INTACT |
| Required signatures | INTACT |
| Linear history | INTACT |
| Force pushes disabled | INTACT |
| Deletions disabled | INTACT |
| Gate-A workflow | INTACT |
| Gate-B workflow | INTACT |
| Pre-commit fitness lock | INTACT |
| Signed commit (ED25519) | INTACT |

## Critical Drift Summary

| Severity | Count | Items |
| --- | --- | --- |
| **CRITICAL** | 4 | All DB schema gaps from Track A BLOCKED |
| EXPECTED_CHANGE | 4 | New val gates + new alpha_zoo flags (PR #43) — all stricter, not weaker |
| **NO_DRIFT** | majority | A1/Signal/Cost/Horizon/Arena/Governance |
| UNKNOWN_LOW | 1 | mutation/crossover rates inside AlphaEngine |
| DEFERRED | 2 | cross-symbol gate, DB pipeline materialization |

→ **No critical parameter conflict. No undocumented runtime override. A2_MIN_TRADES = 25 verified unchanged. APPLY mode absent.**

→ **Phase F verdict: PARAMETERS_ALIGNED_EXCEPT_DB_BLOCKED.** 4 CRITICAL items all converge on Track A; resolved by completing the multi-stage migration order.
