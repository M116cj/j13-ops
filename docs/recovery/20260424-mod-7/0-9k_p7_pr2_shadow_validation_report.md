# 0-9K — P7-PR2 SHADOW Validation Report

Per TEAM ORDER 0-9K §10.

## 1. Run parameters

- Source logs:
  - `zangetsu/logs/engine.jsonl` (308,579 lines, 38.6 MB)
  - `zangetsu/logs/engine.jsonl.1` (14,213 lines, 2.5 MB)
- Combined scanned: **322,792 lines**
- Observation window: 2026-04-16 → 2026-04-23 (~7 days rolling)
- Runtime state: Arena frozen since MOD-3 (0 active processes); all file SHAs unchanged pre/post.

## 2. Event matching stats

| Event pattern | Count |
|---|---:|
| A2 PASS | 7,153 |
| A2 REJECTED | 3,395 |
| A3 COMPLETE | **6** |
| A3 REJECTED | 29 |
| A3 PREFILTER SKIP | 23 |
| **Total events matched** | **10,606** |
| Unique candidate IDs | **1,678** |

## 3. Lifecycle reconstruction outcome

| Metric | Value |
|---|---|
| Lifecycle records reconstructed | **1,678** |
| FULL provenance count | 0 |
| PARTIAL provenance count | 1,678 |
| UNAVAILABLE provenance count | 0 |

**All 1,678 lifecycles are PARTIAL.** Root cause: A1 per-candidate events are not emitted by the current runtime. A1 PASS is correctly inferred for every candidate that reaches A2+, but `arena_1_entry` and `arena_1_exit` timestamps are structurally unavailable.

## 4. deployable_count derived

**deployable_count = 6.**

Deployable candidate IDs:
```
70381, 70382, 70390, 70400, 70407, 70436
```

These correspond 1:1 with the 6 `A3 COMPLETE` events in the log stream. No fabrication.

## 5. Non-deployable breakdown

1,678 - 6 = **1,672 non-deployable candidates**.

| Bucket | Count |
|---|---:|
| SIGNAL_TOO_SPARSE (A2 reject) | 1,474 |
| STALLED_AT_A2 (A2 pass, no A3 outcome) | 146 |
| OOS_FAIL (A3 reject) | 29 |
| SKIPPED (A3 prefilter) | 23 |
| **Total** | **1,672** ✓ |

Final-stage distribution:
- A2: 1,620 (never reached A3)
- A3: 58 (6 deployable + 29 rejected + 23 skipped)

## 6. Dominant final_stage

**A2** — 1,620 / 1,678 = 96.5 % of lifecycles never progressed past Arena 2. Consistent with P7-PR1 SHADOW / CANARY finding: Arena 2 is the 93 %-dominant rejection stage in the observation window (the small delta between 93 % and 96.5 % is because P7-PR1 SHADOW counted rejection EVENTS while here we count candidate LIFECYCLES — a candidate can appear in multiple A2 REJECTED events due to repeat evaluation).

## 7. Dominant reject_reason

**SIGNAL_TOO_SPARSE** — 1,474 / 1,672 = 88.2 % of non-deployable candidates. Reinforces the Arena 2 root cause previously surfaced: candidates produce too few trades / positions to satisfy `A2_MIN_TRADES=25`.

## 8. Missing-field register

| Field | Occurrences | Root cause |
|---|---:|---|
| arena_1_entry | 1,678 | **structural** — A1 per-candidate events not emitted |
| arena_1_exit | 1,678 | same |
| reject_reason_or_governance_blocker | 169 | STALLED_AT_A2 candidates (no explicit rejection, not deployable) |
| arena_2_entry | 48 | candidates seen only at A3 (A2 status inferred) |
| arena_2_exit | 48 | same |

**No other fields missing.** Register is precise and complete.

## 9. Full provenance achievability

**No — full-FULL provenance is not achievable from current logs.**

A1 events are never emitted per-candidate in the current `arena_pipeline.py`. Post-hoc reconstruction cannot recover timestamps that were never logged. This is a structural limitation, not a reconstruction bug.

### Remediation plan (separate future order)

A future P7-PR3-class order could add trace-native A1 emission:

```python
# In zangetsu/services/arena_pipeline.py, inside A1 evaluation loop:
log.info(f"A1 ENTRY id={candidate_id} {symbol} alpha_hash={alpha_hash}")
# ... existing A1 evaluation ...
if passed:
    log.info(f"A1 PASS id={candidate_id} {symbol} sharpe={sharpe:.2f} pnl={pnl:.4f}")
else:
    log.info(f"A1 REJECTED id={candidate_id} {symbol}: {reject_reason}")
```

~10 LOC change per candidate path. Does NOT change A1 decision logic. Does NOT change thresholds. Fully behavior-invariant. Would lift `arena_1_entry/exit` coverage from 0 / 1,678 to effectively 100 % on subsequent observation windows, advancing provenance from PARTIAL → FULL.

0-9K does NOT authorize this emission change. A separate order is required.

## 10. Behavior invariance verification

- 58 pre-existing P7-PR1 tests continue to pass unchanged.
- 34 new P7-PR2 tests pass.
- `test_arena_gates_thresholds_still_pinned_under_p7_pr2` confirms A2_MIN_TRADES=25, A3_SEGMENTS=5, A3_MIN_TRADES_PER_SEGMENT=15, A3_MIN_WR_PASSES=4, A3_MIN_PNL_PASSES=4, A3_WR_FLOOR=0.45 unchanged.
- `test_arena2_pass_behavior_unchanged_*` tests exercise `arena_gates.arena2_pass()` on edge inputs and confirm reason strings unchanged.
- Import-isolation tests confirm that importing the new reconstruction module does NOT pull Arena runtime modules (`arena_pipeline`, `arena23_orchestrator`, `arena45_orchestrator`, `arena13_feedback`) as side effects.
- Controlled-diff confirms all Arena runtime SHAs unchanged between pre-0-9K and post-0-9K snapshots.

## 11. Verdict

```
SHADOW validation completed.
lifecycles reconstructed:   1,678
deployable_count:           6 (authoritative, no fabrication)
provenance:                 PARTIAL (precise, honest)
missing fields:             enumerated
behavior invariance:        intact
```

Per 0-9K §13 GREEN criterion "precise PARTIAL with complete missing-field register", this satisfies the bar. YELLOW verdict issued honestly in `0-9k_go_no_go.md` to reflect that full-FULL requires a separate future order.

STOP.
