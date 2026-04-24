# P7-PR4-LITE — Behavior Invariance Audit

## 1. Scope

All runtime instrumentation is trace-only. This audit documents that
P7-PR4-LITE cannot alter Arena behavior, thresholds, promotion, or
execution.

## 2. Audit table

| Forbidden area | Touched? | Evidence |
|----------------|----------|----------|
| Alpha generation | No | No files under formula / mutation / search policy touched. `diff_snapshots` shows 0 forbidden fields. |
| Threshold constants | No | `test_no_threshold_constants_changed_under_p7_pr4_lite` pins `A2_MIN_TRADES=25`, `A3_SEGMENTS=5`, `A3_MIN_TRADES_PER_SEGMENT=15`, `A3_MIN_WR_PASSES=4`, `A3_MIN_PNL_PASSES=4`, `A3_WR_FLOOR=0.45`. PASS. |
| Arena pass/fail branch conditions | No | `test_arena_pass_fail_behavior_unchanged_*` cases (too-few-trades, non-positive-pnl, edge-accept) all PASS with the same outcomes as the pinned baseline. |
| Rejection semantics | No | P7-PR4-LITE reuses `arena_rejection_taxonomy.classify()`; no remapping. |
| Champion promotion | No | `test_champion_promotion_not_affected_by_telemetry` PASS. |
| `deployable_count` semantics | No | Emitter requires caller-supplied `deployable_count`; never infers from `passed_count`. `test_trace_only_pass_events_do_not_inflate_deployable_count` PASS. `test_deployable_count_unavailable_by_default` PASS. |
| Execution / capital / risk | No | No execution, capital, or risk modules touched. |
| Service restart | No | No deploy / restart action taken. |
| CANARY | No | Not started. |
| Production rollout | No | Not started. |

## 3. Exception safety

- `_make_a1_batch_metrics_safe`, `_emit_a1_batch_metrics_safe`, and
  `_emit_a1_batch_metrics_from_stats_safe` all have outermost `try / except
  Exception: pass` wrappers — they never propagate exceptions upward into
  the Arena round loop.
- `safe_emit_arena_metrics(event, writer)` has its own outer wrapper.
- Import of `arena_pass_rate_telemetry` in `arena_pipeline.py` is guarded
  by `try / except` with `_ARENA_PASS_RATE_TELEMETRY_AVAILABLE` flag; a
  module-import failure leaves Arena behavior unchanged.

`test_runtime_behavior_invariant_when_telemetry_fails` simulates a
failing emitter and confirms Arena decisions proceed unchanged. PASS.

## 4. Provenance of invariance

The call site uses **only existing in-scope variables**:

- `len(alphas)` — already computed above.
- `round_champions` — already counted above.
- `stats` — already populated by Arena pass/fail branches.
- `round_number`, `sym`, `regime` — already in scope for the round-close log.
- `_pb.run_id` — via defensive `getattr`.

No branching, no conditional skipping, no re-evaluation. Adding or
removing the call cannot change the value of any of these variables.

## 5. Independent verification

Full test suite: **211 passed, 3 skipped** (excluding pre-existing
async-plugin failures in `test_integration.py` and
`policy/test_exception_overlay.py` module-level `sys.exit`).
Baseline before P7-PR4-LITE: 169 passed. New tests: 42.

Controlled-diff: **EXPLAINED_TRACE_ONLY**, 0 forbidden.
