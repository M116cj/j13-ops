# P7-PR1 Execution Report — Arena Rejection Taxonomy + Telemetry Baseline

- **Scope**: Implement Arena rejection taxonomy + telemetry baseline per TEAM ORDER 0-9E.
- **Phase**: Phase 7 / P7-PR1 (first Phase 7 migration).
- **Authorization**: TEAM ORDER 0-9E.
- **Base commit**: `966cd59326b970055d1c398f2a9d45215bbfbc49` (origin/main post-MOD-7C).
- **Feature branch**: `phase-7/p7-pr1-arena-rejection-telemetry`.
- **Core rule**: Instrumentation only — no decision behavior mutation.

## 1. Strategy

All new content is additive: 3 new Python modules + 3 new test modules + 6 new docs. No existing file in `zangetsu/services/`, `zangetsu/tests/`, `calcifer/`, `scripts/`, or `.github/workflows/` is modified. Behavior invariance is therefore enforced structurally: since no Arena runtime file changes, no decision path can mutate.

## 2. Files added

### Source (zangetsu/services/)
- `arena_rejection_taxonomy.py` — 18 canonical rejection reasons × 14 categories × 4 severities, plus `classify()` function and `RAW_TO_REASON` map from existing Arena runtime reject-strings.
- `arena_telemetry.py` — `RejectionTrace` dataclass (20 required fields + 11 Arena-2 extras per 0-9E §7), `TelemetryCollector` aggregator, JSON-safe serialization.
- `candidate_trace.py` — `CandidateLifecycle` dataclass, `derive_deployable_count()` provenance function (answers 0-9E §5 Q7/Q8/Q10).

### Tests (zangetsu/tests/)
- `test_arena_rejection_taxonomy.py` — 18 tests: taxonomy completeness, metadata consistency, classifier determinism.
- `test_arena_telemetry.py` — 19 tests: RejectionTrace JSON round-trip, TelemetryCollector aggregation, CandidateLifecycle semantics, deployable_count provenance.
- `test_p7_pr1_behavior_invariance.py` — 9 tests: prove new modules don't pull Arena runtime; pin Arena gate thresholds (`A2_MIN_TRADES=25`, `A3_SEGMENTS=5`, `A3_MIN_TRADES_PER_SEGMENT=15`, `A3_MIN_WR_PASSES=4`, `A3_MIN_PNL_PASSES=4`, `A3_WR_FLOOR=0.45`); exercise `arena2_pass()` decision path unchanged.

### Docs (docs/recovery/20260424-mod-7/)
- `p7_pr1_execution_report.md` — this file.
- `p7_pr1_gate_results.md` — Gate-A / Gate-B results (filled post-run).
- `p7_pr1_controlled_diff_report.md` — controlled-diff pre/post result.
- `p7_pr1_shadow_plan.md` — SHADOW mode plan.
- `p7_pr1_canary_plan.md` — CANARY mode plan.
- `p7_pr1_final_verdict.md` — final verdict (filled post-gate).

## 3. How P7-PR1 answers the 10 questions in 0-9E §5

| # | Question | Mechanism |
|---|---|---|
| 1 | Which candidate was rejected? | `RejectionTrace.candidate_id` |
| 2 | Which alpha_id was rejected? | `RejectionTrace.alpha_id` |
| 3 | At which Arena stage? | `RejectionTrace.arena_stage` |
| 4 | What exact reason caused rejection? | `RejectionTrace.reject_reason` (canonical enum) |
| 5 | Which category? | `RejectionTrace.reject_category` (14 canonical) |
| 6 | Formula/data/score/cost/regime/promotion/governance? | `RejectionCategory` enum covers all 7 branches |
| 7 | How many per reason? | `TelemetryCollector.counts_by_reason()` |
| 8 | Why is deployable_count zero? | `derive_deployable_count(lifecycles)` returns breakdown_by_stage + breakdown_by_reject_reason + non_deployable_reasons |
| 9 | Why is Arena 2 rejecting? | `TelemetryCollector.arena2_breakdown()` |
| 10 | How much UNKNOWN_REJECT? | `TelemetryCollector.unknown_reject_ratio()` — fraction 0..1 |

## 4. Rejection taxonomy summary (18 canonical reasons)

```
FORMULA_QUALITY:  INVALID_FORMULA, UNSUPPORTED_OPERATOR
DATA_QUALITY:     WINDOW_INSUFFICIENT, NAN_INF_OUTPUT
CAUSALITY:        NON_CAUSAL_RISK
BACKTEST_SCORE:   LOW_BACKTEST_SCORE
RISK:             HIGH_DRAWDOWN
COST:             HIGH_TURNOVER, COST_NEGATIVE
FRESH_VALIDATION: FRESH_FAIL
OOS_VALIDATION:   OOS_FAIL
REGIME:           REGIME_FAIL
SIGNAL_DENSITY:   SIGNAL_TOO_SPARSE, SIGNAL_TOO_DENSE
CORRELATION:      CORRELATION_DUPLICATE
PROMOTION:        PROMOTION_BLOCKED
GOVERNANCE:       GOVERNANCE_BLOCKED
UNKNOWN:          UNKNOWN_REJECT (fallback only; UNKNOWN_REJECT never returned when a deterministic mapping exists — enforced by test)
```

## 5. Classifier mapping coverage

`RAW_TO_REASON` maps 20 existing raw reject-strings emitted by current Arena runtime to canonical reasons:

- **arena_gates.py** (`GateResult.reason` strings): `too_few_trades` → SIGNAL_TOO_SPARSE; `non_positive_pnl` → COST_NEGATIVE; `wrong_segment_count` → WINDOW_INSUFFICIENT.
- **arena_pipeline.py** (A1 counter keys): `reject_few_trades` → SIGNAL_TOO_SPARSE; `reject_neg_pnl` → COST_NEGATIVE; `reject_val_constant/reject_val_error` → INVALID_FORMULA; `reject_val_few_trades` → SIGNAL_TOO_SPARSE; `reject_val_neg_pnl` → COST_NEGATIVE; `reject_val_low_sharpe/reject_val_low_wr` → LOW_BACKTEST_SCORE.
- **arena23_orchestrator.py** (A2/A3 log-line substrings): `alpha_invalid_or_flat` → INVALID_FORMULA; `no economically valid combos` → COST_NEGATIVE; `all ATR+TP combos non-positive` → COST_NEGATIVE; `validation split fail` → OOS_FAIL; `train/val PnL divergence` → OOS_FAIL; `zero-MAD filter` → SIGNAL_TOO_SPARSE.
- **arena13_feedback.py** (weight-sanity gate): `a13_weight_sanity_rejected` / `weight sanity REJECTED` → GOVERNANCE_BLOCKED.

Classifier uses exact-match first, then substring match, with UNKNOWN_REJECT as only fallback when no mapping exists.

## 6. Tests run

Command:
```
python3 -m pytest zangetsu/tests/test_arena_rejection_taxonomy.py \
                  zangetsu/tests/test_arena_telemetry.py \
                  zangetsu/tests/test_p7_pr1_behavior_invariance.py -v
```

Result: **46 passed, 0 failed, 1 warning (pre-existing asyncio_mode warning, unrelated)** in 0.15s.

Behavior invariance tests specifically verified (0-9E §11):
- Importing new modules does NOT pull `arena_pipeline`, `arena23_orchestrator`, `arena13_feedback`, `arena45_orchestrator`.
- Arena gate thresholds (`A2_MIN_TRADES`, `A3_*`) all pinned to main @ 966cd593 values.
- `arena2_pass()` decision path exercised and produces identical reason strings for edge inputs.
- `classify()` recognizes every raw-reason string currently emitted by `arena_gates.py`.

## 7. Controlled-diff result

See `p7_pr1_controlled_diff_report.md`. Summary:
- Classification: **EXPLAINED**
- Zero diff: 40 fields
- Explained diff: 4 fields (calcifer runtime state SHA + its ts_iso, git porcelain line count from 1→8 matching the 6 new files + 1 pre-existing calcifer state + 1 pre-snapshot artifact)
- Forbidden diff: **0**
- Arena runtime file SHAs (`arena_pipeline`, `arena23_orchestrator`, `arena45_orchestrator`, `supervisor.py`, `zangetsu_outcome.py`) — all unchanged.

## 8. Runtime effect

**Zero.** No Arena runtime file was modified; no service restart is triggered; no live telemetry is emitted by this PR. Collectors are passive dataclasses waiting to be populated. Actual wiring into Arena runtime is deferred to a future P7-PR2+ order that explicitly authorizes instrumentation calls at Arena reject paths.

## 9. What P7-PR1 does NOT change (explicit)

- No alpha formula changes.
- No alpha generation logic changes.
- No Arena threshold changes (A2_MIN_TRADES still 25; A3_WR_FLOOR still 0.45; etc.).
- No Arena 2 behavior relaxation.
- No champion promotion rule changes.
- No trade execution logic changes.
- No production capital behavior changes.
- No risk limit changes.
- No runtime configuration changes (`zangetsu/config/settings.py` SHA unchanged).
- No branch protection changes (`enforce_admins=true`, `required_signatures=true`, `linear=true` preserved).

## 10. Post-merge expectation

- origin/main gains 3 new Python modules + 3 new test modules + 6 new docs, all under authorized paths.
- No runtime service restart required.
- A separate authorized order (P7-PR1 SHADOW activation or P7-PR2 wiring) is required before any telemetry record is emitted in production.
