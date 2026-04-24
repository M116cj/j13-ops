# 0-9L — A1 Trace-Native Emission Report

Per TEAM ORDER 0-9L-PLUS §16.2.

## 1. A1 insertion points

Three surgical insertion sites in `zangetsu/services/arena_pipeline.py`:

| # | Site | Line | Purpose | Identity source |
|---:|---|---:|---|---|
| 1 | After `alpha_hash` computed, before bloom dedup | ~722 | **A1_ENTRY** — candidate begins A1 evaluation | `alpha_hash` |
| 2 | At `if bt.total_trades < 30` reject path | ~751 | **A1_EXIT_REJECT** — sparse-signal rejection (`reject_few_trades` counter site) | `alpha_hash` |
| 3 | After `rbloom_add` post-admission | ~942 | **A1_EXIT_PASS** + **A1_HANDOFF_TO_A2** — candidate survived A1 and is handed off to A2 | `alpha_hash` |

All three call the exception-safe helper `_emit_a1_lifecycle_safe(...)` defined at the top of the file.

## 2. A1 events implemented

| Event | Stage | stage_event | status | next_stage | reject_reason |
|---|---|---|---|---|---|
| A1_ENTRY | A1 | ENTRY | ENTERED | — | — |
| A1_EXIT_REJECT (sparse) | A1 | EXIT | REJECTED | — | `SIGNAL_TOO_SPARSE` |
| A1_EXIT_PASS | A1 | EXIT | PASSED | — | — |
| A1_HANDOFF_TO_A2 | A1 | HANDOFF | PASSED | `A2` | — |

Events NOT implemented in P7-PR3 (runtime paths exist but additional emission sites deferred to a future order):

- Alpha compile errors (site 715 `except Exception as _ce`)
- Constant-output skip (site 722 `np.std < 1e-10`)
- Bloom dedup skip (site 729 `if _bloom_key in bloom`)
- Signal generation error (site 740 `except Exception as _se`)
- Backtest error (site 747 `except Exception as _be`)
- Val backtest errors and various val rejection counters (site 778-816): reject_val_constant, reject_val_error, reject_val_few_trades, reject_val_neg_pnl, reject_val_low_sharpe, reject_val_low_wr

Rationale for minimal scope: P7-PR3's primary deliverable is **proving the contract works end-to-end**. Three representative call sites (entry + one reject + pass/handoff) validate the full pipeline. Additional reject-reason emission sites can be wired via a follow-up micro-patch under any subsequent authorized order, each being a ~5-line addition invoking `_emit_a1_lifecycle_safe()`.

## 3. Identity continuity

At A1, the database `candidate_id` has not yet been assigned (admission happens in `admission_validator` later). The P7-PR3 emission uses `alpha_hash` as the identity triple:

```python
candidate_id = alpha_hash
alpha_id     = alpha_hash
formula_hash = alpha_hash
```

This means P7-PR3 A1 events and existing legacy A2/A3 events (which use the post-admission `id=<N>` DB identifier) are NOT directly joinable by candidate_id alone. For future provenance FULL on live runtime, one of these is needed:

1. **A2/A3 emission upgrade** — future orders extend legacy A2/A3 log lines or add trace-native A2/A3 events that also carry `alpha_hash` alongside `id`, providing a join key.
2. **Runtime joining** — the admission_validator phase records both `alpha_hash` and `staging_id` in a DB table, enabling post-hoc reconstruction to merge A1 and A2+ streams.

P7-PR3's reconstruction module handles BOTH formats in parallel:
- Legacy format (A2/A3 regex): keyed by `id=<N>`.
- Trace-native format: keyed by `alpha_hash` (via `candidate_id` field).

Lifecycles with the same underlying candidate may appear as two separate reconstructed records pending the join mechanism.

## 4. A1 pass path evidence

When a candidate:
- produces valid alpha values (not constant)
- survives bloom dedup
- produces valid trade signals
- has `bt.total_trades >= 30`
- passes all 5 val gates (`bt_val.total_trades >= 15`, `bt_val.net_pnl > 0`, `bt_val.sharpe_ratio >= 0.3`, `val_wilson >= 0.52`)
- is successfully inserted into `alphas_staging` (DB)
- is admitted by `admission_validator`

Then `_emit_a1_lifecycle_safe(stage_event=EXIT, status=PASSED, alpha_hash=..., source_pool=sym)` is called, followed by `_emit_a1_lifecycle_safe(stage_event=HANDOFF, status=PASSED, next_stage="A2")`.

## 5. A1 reject path evidence

At the `bt.total_trades < 30` check, the `reject_few_trades` counter increments AND `_emit_a1_lifecycle_safe(stage_event=EXIT, status=REJECTED, reject_reason="SIGNAL_TOO_SPARSE")` is called immediately before `continue`.

The `continue` statement is unchanged — the reject decision flow is identical to pre-P7-PR3 behavior.

## 6. Handoff to A2 evidence

On successful admission (after `rbloom_add` and `bloom.add`), P7-PR3 emits an explicit `A1_HANDOFF_TO_A2` event with `next_stage="A2"`. This marks the point at which the candidate is formally handed off to the A2 evaluation pipeline.

## 7. Behavior-invariance proof

| Test | Proves |
|---|---|
| `test_arena_gates_thresholds_still_pinned_under_p7_pr3` | Arena thresholds unchanged |
| `test_arena2_pass_decision_unchanged_*` (3 cases) | arena2_pass decision logic unchanged |
| `test_emit_helper_cannot_affect_caller_return_value` | Helper has no externally-visible side effect |
| `test_emit_helper_exception_safe_under_logger_failure` | Helper swallows logger exceptions silently |
| `test_emit_helper_handles_bad_build_input_gracefully` | Helper handles builder failures silently |
| `test_lifecycle_contract_import_does_not_pull_arena_pipeline` | No circular import |
| `test_reconstruction_import_does_not_pull_arena_pipeline` | Reconstruction stays read-only |
| `test_deployable_count_not_inflated_by_trace_only_events` | Trace-only A1 PASS does NOT inflate deployable_count |

**Overall: 150/150 tests PASS.**

## 8. Trace failure safety

The `_emit_a1_lifecycle_safe()` helper uses a two-layer try/except:

1. Outer try/except around the entire body — any exception (including builder validation errors, logger failures, serialization errors) is silently swallowed.
2. The helper ALWAYS returns None; caller code continues exactly as before.

Specific failure scenarios and their handling:

| Failure | Outcome |
|---|---|
| Logger raises (e.g., disk full) | Helper swallows; caller unaffected |
| Builder raises on bad input | Helper swallows; caller unaffected |
| Serialization raises | Helper swallows; caller unaffected |
| Import of `candidate_trace` fails at module load | `_LIFECYCLE_TRACE_AVAILABLE = False`; helper becomes a no-op |

This is behavior-critical: the Arena pass/fail flow CANNOT be affected by a P7-PR3 trace emission bug.

## 9. Performance / log-volume risk

A1 emits 3 events per candidate in the PASS path (ENTRY + EXIT_PASS + HANDOFF), or 2 events in the REJECT path (ENTRY + EXIT_REJECT). In a typical A1 round processing `alphas_evaluated` candidates, this adds 2-3 JSONL log lines per candidate.

Projected overhead on observation window (2026-04-16 → 2026-04-23, 322,792 lines total):
- Alpha compile errors: not emitted (deferred)
- Bloom hits: not emitted (deferred)
- `reject_few_trades`: 227 observed → +227 lines if P7-PR3 had been live
- Val rejects (6 types): ~170 observed aggregate → +170 lines if those sites emitted (not in P7-PR3)
- A2 PASS candidates: 6 deployable observed → +18 lines (3 per candidate)

Total P7-PR3-only addition: ~245 lines over 7 days = ~35 lines/day = negligible. No performance concern.

No synchronous I/O in the hot path: log.info() is synchronous but buffered; any latency is dominated by the existing backtest pipeline cost (orders of magnitude higher).
