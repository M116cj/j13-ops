# 0-9L — P7-PR3 SHADOW Validation Report

Per TEAM ORDER 0-9L-PLUS §14.

## 1. Three-layer validation

### Layer A — Historical Compatibility

Run reconstruction against existing logs:

- Source: `zangetsu/logs/engine.jsonl` (308,579 lines) + `zangetsu/logs/engine.jsonl.1` (14,213 lines)
- Combined: 322,792 lines
- Window: 2026-04-16 → 2026-04-23

| Metric | Result |
|---|---:|
| Lifecycles reconstructed | 1,678 |
| FULL | 0 |
| **PARTIAL** | **1,678** |
| UNAVAILABLE | 0 |
| deployable_count | **6** (unchanged — 70381, 70382, 70390, 70400, 70407, 70436) |
| Confidence | **PARTIAL** |
| Missing-field register | `arena_1_entry` × 1,678, `arena_1_exit` × 1,678, `reject_reason_or_governance_blocker` × 169, `arena_2_entry` × 48, `arena_2_exit` × 48 |

**Historical logs remain PARTIAL — as expected.** P7-PR3 adds trace-native emission for future runtime; it does NOT fabricate history. This matches the P7-PR2 baseline exactly.

### Layer B — Synthetic Trace-Native FULL Fixture

Constructed synthetic event stream for candidate `DPL-X`:

```
A1_ENTRY           @ 2026-05-01T00:00:00Z
A1_EXIT_PASS       @ 2026-05-01T00:00:05Z
A1_HANDOFF_TO_A2   @ 2026-05-01T00:00:06Z  next_stage=A2
A2_ENTRY           @ 2026-05-01T00:01:00Z
A2_EXIT_PASS       @ 2026-05-01T00:01:10Z
A3_ENTRY           @ 2026-05-01T00:02:00Z
A3_EXIT_COMPLETE   @ 2026-05-01T00:02:30Z
```

With `arena_0_status = PASS` inferred (A0 is formula-validation prerequisite, not runtime-emitted):

| Metric | Result |
|---|---|
| Provenance quality | **FULL** |
| Missing fields | `[]` (none) |
| deployable_count | 1 (DPL-X) |
| Confidence | FULL |

**✅ FULL provenance path is PROVEN on trace-native fixture.**

Additional fixture cases:

| Fixture | Provenance |
|---|---|
| A1 full (ENTRY + EXIT_REJECT with reject_reason) | FULL for A1-reject lifecycle |
| A2-only events (no A1 trace) | PARTIAL (arena_1_entry/exit missing) |
| Empty identity (no candidate_id/alpha_id/formula_hash) | UNAVAILABLE (`_no_identity` bucket) |
| Duplicate A1_ENTRY events (same candidate_id) | deduplicate to single lifecycle (earliest-wins for entry) |
| Conflicting A1 statuses (REJECTED then PASSED) | conflict register entry: `"A1 conflict: prior=REJECT new=PASS"` |

### Layer C — Optional Unit-Level Dry Run

**SKIPPED per §14 Layer C.** Arena is frozen since MOD-3 — running the production arena_pipeline.py would require:

- Full DB + data cache setup
- All environment variables (ENTRY_THR, EXIT_THR, MIN_HOLD, etc.)
- Potentially trigger live backtests

Per 0-9L-PLUS §14: "If dry run is not safe: Skip and document why. Do not force runtime execution."

Dry run is skipped because:
- Live execution would mutate production state (not safe).
- Behavior invariance is already validated by 150/150 unit tests.
- The trace emission helper is exception-safe — even if arena_pipeline were run, emission failures cannot alter Arena decisions.

## 2. deployable_count validation

Validated non-inflation:

- `test_deployable_count_not_inflated_by_trace_only_events`: trace-only A1 PASS event for a candidate does NOT count toward deployable_count.
- `test_deployable_count_not_inflated_by_trace_only_events` (integration path): reconstruction from synthetic A1-only events → `derive_deployable_count_with_provenance()` returns `deployable_count=0`.
- Historical reconstruction: `deployable_count = 6` unchanged from P7-PR2 baseline.

## 3. Trace failure safety validation

| Test | Result |
|---|---|
| Logger raises → helper swallows | PASS |
| Builder raises → helper swallows | PASS |
| Helper returns None always | PASS |
| Module import of candidate_trace without arena_pipeline side effect | PASS |
| Module import of reconstruction without arena_pipeline side effect | PASS |

## 4. Test invocation

```
pytest zangetsu/tests/test_arena_rejection_taxonomy.py \
       zangetsu/tests/test_arena_telemetry.py \
       zangetsu/tests/test_p7_pr1_behavior_invariance.py \
       zangetsu/tests/test_candidate_lifecycle_reconstruction.py \
       zangetsu/tests/test_deployable_count_provenance.py \
       zangetsu/tests/test_p7_pr2_behavior_invariance.py \
       zangetsu/tests/test_lifecycle_trace_contract.py \
       zangetsu/tests/test_p7_pr3_trace_native_a1_emission.py \
       zangetsu/tests/test_p7_pr3_lifecycle_fullness_projection.py \
       zangetsu/tests/test_p7_pr3_behavior_invariance.py

Result: 150 passed, 0 failed, 1 pre-existing warning (0.58s)
```

## 5. Summary

| Validation layer | Result |
|---|---|
| Layer A (historical) | PARTIAL — honest; unchanged from P7-PR2 baseline |
| Layer B (synthetic trace-native FULL) | **PROVEN** — fixture reaches PROVENANCE_FULL |
| Layer C (live dry run) | SKIPPED — documented as unsafe under frozen-Arena regime |
| deployable_count inflation | **NONE** — tests enforce |
| Trace failure safety | **PROVEN** — exception-safe |

## 6. Verdict

P7-PR3 validation **meets the 0-9L-PLUS §14 requirements**. FULL provenance path is available; historical backward compatibility is preserved; deployable_count derivation is not compromised.
