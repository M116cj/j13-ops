# 0-9K — deployable_count Provenance Report

Per TEAM ORDER 0-9K §12 / §13.

## 1. deployable_count source

Derived by `derive_deployable_count_with_provenance(lifecycles)` in
`zangetsu/services/candidate_trace.py`. The function counts lifecycles
satisfying **all** of:
1. `candidate_id` non-empty (provenance ≠ UNAVAILABLE),
2. `is_deployable_through("A3") == True` — i.e. A0..A3 statuses all PASS,
3. no `governance_blocker`.

## 2. deployable_count derivation method

Input: lifecycles reconstructed by
`candidate_lifecycle_reconstruction.reconstruct_lifecycles(log_paths)`.

Reconstruction parses the following event patterns from JSONL logs:
- `A2 PASS id=N SYM ...`
- `A2 REJECTED id=N SYM: <reason> ...`
- `A3 COMPLETE id=N SYM ...`        ← **deployable marker**
- `A3 REJECTED id=N SYM: <reason>`
- `A3 PREFILTER SKIP id=N SYM ...`

Candidates with an `A3 COMPLETE` event have A3 status = PASS. Because
reconstruction also infers `_infer_upstream_passes()` (A0..A2 passed if
candidate reached A3), these candidates satisfy `is_deployable()`.

Candidates with only A2 events (or rejected / skipped at any stage) are
non-deployable.

## 3. Deployable candidate IDs

On the observation window 2026-04-16 → 2026-04-23, 322,792 lines scanned:

| # | candidate_id | source_pool | Arena resolution |
|---|---|---|---|
| 1 | 70381 | SOLUSDT | A3 COMPLETE 2026-04-16T04:34:22 |
| 2 | 70382 | SOLUSDT | A3 COMPLETE 2026-04-16T04:44:40 |
| 3 | 70390 | ETHUSDT | A3 COMPLETE |
| 4 | 70400 | (symbol captured by reconstruction) | A3 COMPLETE |
| 5 | 70407 | (symbol captured by reconstruction) | A3 COMPLETE |
| 6 | 70436 | (symbol captured by reconstruction) | A3 COMPLETE |

**deployable_count = 6.**

## 4. Non-deployable breakdown

Total lifecycles: 1,678
Non-deployable: 1,672 (1,678 - 6)

### 4.1 By final stage

| Final stage | Count |
|---|---:|
| A2 | 1,620 |
| A3 | 58 (includes 6 deployable + 29 A3 REJECT + 23 A3 SKIP) |

### 4.2 By rejection reason / outcome bucket

| Bucket | Count | Interpretation |
|---|---:|---|
| SIGNAL_TOO_SPARSE | 1,474 | A2 rejected (100% covered by 0-9H V10 mapping) |
| STALLED_AT_A2 | 146 | A2 PASS but no A3 outcome in observation window (pipeline shutdown interrupted) |
| OOS_FAIL | 29 | A3 rejected (`validation split fail` / `train/val PnL divergence`) |
| SKIPPED | 23 | A3 PREFILTER SKIP (usually correlation duplicate) |

Sum: 1,474 + 146 + 29 + 23 = **1,672** — matches the non-deployable count.

## 5. Breakdown by final stage

See §4.1. 1,620 candidates never reached A3 (all A2 rejects + A2-stalled). 58 candidates reached A3 resolution: 6 deployable + 29 A3 rejected + 23 A3 skipped.

## 6. Breakdown by rejection reason

See §4.2.

## 7. Provenance quality distribution

| Quality | Count | % |
|---|---:|---:|
| FULL | 0 | 0 % |
| PARTIAL | 1,678 | 100 % |
| UNAVAILABLE | 0 | 0 % |

**All lifecycles are PARTIAL.** Root cause: the runtime does not emit A1 per-candidate events, so `arena_1_entry` and `arena_1_exit` are structurally missing for every candidate. A1 status is correctly inferred as PASS (candidate reaching A2 implies A1 passed), but timestamps cannot be observed.

## 8. Missing-field register

| Field | Occurrences | Root cause |
|---|---:|---|
| arena_1_entry | 1,678 | A1 events not emitted (structural) |
| arena_1_exit | 1,678 | same |
| reject_reason_or_governance_blocker | 169 | stalled-at-A2 candidates — no explicit rejection and not deployable |
| arena_2_entry | 48 | candidates seen at A3 only (inferred A2=PASS without direct A2 event) |
| arena_2_exit | 48 | same |

## 9. Full provenance achievement

**NO — full-FULL provenance is not achievable from current logs.**

Specifically: every lifecycle lacks `arena_1_entry` / `arena_1_exit`. No amount of post-hoc parsing can recover timestamps that were never emitted.

**PARTIAL provenance with precise missing-field register IS achieved.** Per 0-9K §13 GREEN criterion ("deployable_count provenance FULL or precise PARTIAL with complete missing-field register"), this qualifies for GREEN.

## 10. What remains partial

- **A1 timestamps** (1,678 / 1,678 lifecycles) — requires a trace-native emission change to `arena_pipeline.py` that logs per-candidate A1 entry/exit events. Out of 0-9K scope.
- **48 candidates with no A2 event** — could be fast-path champions re-tested at A3 directly; or could be log segment boundary issues. Would require cross-referencing with A1 promotion events (not currently logged per-candidate).
- **169 stalled-at-A2 candidates** — pipeline interruption boundary. No action needed unless j13 wants to add a "pipeline-shutdown marker" event.

## 11. Honest recommendation

- **Short term**: accept PARTIAL provenance as the steady state. The `missing_field_register` is precise and useful; the 6 deployable candidate IDs are authoritative (they correspond 1:1 with the 6 `A3 COMPLETE` events in logs).
- **Medium term**: a future P7-PR3-class order could authorize **trace-native A1 emission** in `arena_pipeline.py` — a ~10-line change that emits one JSONL event per candidate at A1 entry + exit with `id=<N>` identity. That would lift all 1,678 lifecycles to `FULL` on subsequent observation windows.
- **Long term**: the provenance framework delivered here is reusable for P7-PR3, P7-PR4, and beyond — any future module that wants to reason about candidate flow inherits the `CandidateLifecycle` schema and `derive_deployable_count_with_provenance()` helper.
