# TEAM ORDER 0-9L-PLUS — P7-PR3 Lifecycle Trace Contract Report

## 1. Status

| Field | Value |
|---|---|
| 0-9L-PLUS status | **COMPLETE** (with documented controlled-diff exception per 0-9L-A) |
| Branch | `phase-7/p7-pr3-lifecycle-trace-contract` |
| PR URL | _filled post-PR-open_ |
| Pre-merge signed commit | _filled post-commit_ |
| Post-merge main SHA | _filled post-merge_ |
| origin/main (pre) | `fe1b0a60448b408de0db105d027e9c14d4d8297a` |
| Pre-snapshot manifest | `586ee757ff2c36aa02f5a942ccef8574e4f19c31482a0f78da9e27266f9c5ee9` |
| Post-snapshot manifest | `c3cca8f432b32c3ab48d821b2dbc46d76737e91cdda881fdb0b3fedb61bc1fc3` |

## 2. Inherited state

- MOD-7 = ACTIVE; Phase 7 = STARTED.
- P7-PR1 / P7-PR1 SHADOW / P7-PR1 CANARY / P7-PR2 = all COMPLETE.
- UNKNOWN_REJECT = 0.00 %; Arena 2 visibility = GREEN.
- P7-PR2 lifecycle provenance = PARTIAL (root cause: A1 per-candidate events not emitted in current runtime).
- Gate-A + Gate-B both trigger + pass on pull_request (post-0-9I).
- Branch protection intact.

## 3. Subagent findings (consolidated)

- **repo-cartographer**: located A1 insertion points in `arena_pipeline.py` (alpha_hash computation @ ~722, reject_few_trades path @ ~751, champion insert @ ~942). `alpha_hash` is the A1-era identity; database `candidate_id` is assigned later by `admission_validator`.
- **lifecycle-auditor**: closure matrix — A1_ENTRY/EXIT fills `arena_1_entry` / `arena_1_exit` (previously 1,678/1,678 missing in P7-PR2). A2/A3 gaps are structural (legacy log format); closable by future P7-PR4+ with A2/A3 trace-native emission.
- **arena-auditor**: A1 decision logic is unchanged. Insertion is exception-safe via wrapper helper. `bt.total_trades < 30` predicate unchanged; `reject_few_trades` counter increment unchanged; all `continue` targets unchanged.
- **telemetry-architect**: unified `LifecycleTraceEvent` dataclass with forward-compatible stage vocabulary (A0..A5 + UNKNOWN). Event-type marker `candidate_lifecycle` for reconstruction identification. Builder validates; parser tolerant; emitter non-blocking.
- **invariant-guardian**: no alpha / threshold / pass-fail / champion promotion / execution mutation. All Arena gate thresholds pinned.
- **test-forger**: 58 new test cases + 92 preserved (150/150).
- **implementation-agent**: 3 files extended + 4 new test files + 5 docs + 1 exception record.
- **shadow-validator**: historical PARTIAL (0-9K baseline unchanged); synthetic FULL PROVEN on trace-native fixture.
- **governance-verifier**: signing + branch protection + Gate-A/B all intact pre-commit.
- **red-team-reviewer**: trace emission failure cannot alter Arena behavior (tested). Event emission for trace-only A1 PASS does NOT inflate deployable_count (tested). Historical logs still honestly PARTIAL.

## 4. Lifecycle trace contract schema

`LifecycleTraceEvent` (in `zangetsu/services/candidate_trace.py`):

```python
@dataclass
class LifecycleTraceEvent:
    event_type: str = "candidate_lifecycle"
    arena_stage: str = "UNKNOWN"       # A0 / A1 / A2 / A3 / A4 / A5 / UNKNOWN
    stage_event: str = "ENTRY"         # ENTRY / EXIT / HANDOFF / SKIP / ERROR
    status: str = "ENTERED"            # ENTERED / PASSED / REJECTED / SKIPPED / ERROR / COMPLETE
    timestamp_utc: str = ""
    candidate_id, alpha_id, formula_hash, source_pool: Optional[str]
    run_id, commit_sha: Optional[str]
    reject_reason, reject_category, reject_severity: Optional[str]
    next_stage: Optional[str]          # e.g. "A2" on A1_HANDOFF
    deployable_candidate: Optional[bool]
    notes: Optional[str]
    extras: Optional[Dict[str, Any]]
```

Constants: `EVENT_TYPE_CANDIDATE_LIFECYCLE = "candidate_lifecycle"`, `STAGE_EVENT_*` (5), `STATUS_*` (6), `_VALID_TRACE_STAGES = ("A0", "A1", "A2", "A3", "A4", "A5", "UNKNOWN")`.

## 5. Builder / parser / emitter design

- `build_lifecycle_trace_event(...)` — validates required fields (arena_stage / stage_event / status vocabularies), auto-fills RFC3339 timestamp, never mutates caller state.
- `parse_lifecycle_trace_event(obj)` — tolerant parser. Accepts dict or JSON string; returns None on malformed input (never raises); stores unknown fields in `extras`.
- `emit_lifecycle_trace_event(event, writer=None)` — non-blocking emission. Try/except wraps both serialization and writer call; returns True on success, False on any failure. Writer defaults to stdout when None.

## 6. Future stage extension plan

The same contract extends to A2 / A3 / A4 / A5 with no schema change:
- A2_ENTRY / A2_EXIT_PASS / A2_EXIT_REJECT / A2_HANDOFF_TO_A3 → requires emission insertion in `arena23_orchestrator.py` (future P7-PR4).
- A3_ENTRY / A3_COMPLETE / A3_EXIT_REJECT / A3_HANDOFF_TO_A4 → requires emission in `arena23_orchestrator.py` (same file; future P7-PR4 could bundle both).
- A4 / A5 → future orders.

When all stages emit trace-native events, reconstruction produces FULL provenance for every candidate — eliminating the P7-PR2 PARTIAL structural limitation.

## 7. Files changed

| File | Scope | Lines |
|---|---|---:|
| `zangetsu/services/candidate_trace.py` | additive: `LifecycleTraceEvent` + constants + builder/parser/emitter | +285 |
| `zangetsu/services/candidate_lifecycle_reconstruction.py` | additive: `reconstruct_lifecycles_from_trace_events()` | +157 |
| `zangetsu/services/arena_pipeline.py` | additive: `_emit_a1_lifecycle_safe()` helper + 3 A1 emission call sites | +69 / -0 |
| `zangetsu/tests/test_lifecycle_trace_contract.py` | new | +193 |
| `zangetsu/tests/test_p7_pr3_trace_native_a1_emission.py` | new | +176 |
| `zangetsu/tests/test_p7_pr3_lifecycle_fullness_projection.py` | new | +198 |
| `zangetsu/tests/test_p7_pr3_behavior_invariance.py` | new | +187 |
| 5 docs in `docs/recovery/20260424-mod-7/` | new | +~800 |

No existing Arena decision file modified. No Arena threshold file modified. No champion promotion file touched.

## 8. Tests run

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
→ 150 passed, 0 failed, 1 pre-existing warning
```

## 9. Controlled-diff

- **Classification**: **FORBIDDEN** by legacy file-SHA tripwire
- **Exception field**: `config.arena_pipeline_sha`
- **Old SHA** → **New SHA**: `34a3791f1686...` → `888e2fdd4b4a...`
- Zero-diff: 42 fields / Explained diff: 1 field / Forbidden diff: 1 field
- **Exception status**: DOCUMENTED / AUTHORIZED BY j13 via TEAM ORDER 0-9L-A
- **Reason**: 0-9L-PLUS explicitly authorized `arena_pipeline.py` for additive P7-PR3 A1 trace-native lifecycle emission; the legacy controlled-diff tripwire treats any `arena_pipeline_sha` change as forbidden.
- **controlled-diff logic unchanged** (`scripts/governance/diff_snapshots.py` and `state_diff_acceptance_rules.md` not modified in this PR).
- Full record: `docs/recovery/20260424-mod-7/0-9l_controlled_diff_exception_record.md`.

## 10. Gate-A / Gate-B

_Filled post-PR-open_. Expected: both trigger on pull_request event (post-0-9F + post-0-9I path coverage includes `zangetsu/**` and `docs/recovery/**`). Gate-A expected PASS (8/8 steps). Gate-B expected PASS with noop-success (no `zangetsu/src/modules/**` paths changed).

## 11. Forbidden changes verification

| Forbidden change | Verified NOT occurred |
|---|---|
| Alpha formula / generation | ✓ |
| Arena pass/fail predicate | ✓ (150/150 tests enforce) |
| Arena thresholds | ✓ (A2_MIN_TRADES=25, A3_* pinned) |
| Arena 2 relaxation | ✓ |
| Champion promotion | ✓ |
| Execution / capital / risk / runtime | ✓ (no service restart) |
| Branch protection | ✓ (all 5 fields unchanged) |
| controlled-diff logic | ✓ (tool unchanged) |
| state_diff_acceptance_rules.md | ✓ (unchanged) |
| P7-PR3 CANARY | ✓ NOT STARTED |
| Production rollout | ✓ NOT STARTED |

## 12. Residual risks

- **Legacy controlled-diff tripwire continues flagging** future authorized `arena_pipeline_sha` changes as FORBIDDEN until `TEAM ORDER 0-9M` upgrades the framework. Mitigation: each authorized runtime-file change requires a documented exception like this one.
- **A2 / A3 / A4 / A5 still emit legacy log format**. Full FULL-capable provenance requires future orders to extend trace-native emission to those stages.
- **arena_pipeline.py is long (1,060 lines)** and touching it carries inherent risk. Mitigation: behavior invariance tests (150/150) + exception-safe emission wrapper + no decision logic modification.

## 13. Final verdict

```
VERDICT = GREEN with documented controlled-diff exception

Reason:
- Lifecycle trace contract: COMPLETE.
- A1 trace-native emission: COMPLETE.
- Historical reconstruction: PARTIAL (unchanged — honest).
- Synthetic trace-native FULL path: PROVEN on fixtures.
- Behavior invariance: 150/150 tests PASS.
- Branch protection: INTACT.
- controlled-diff: FORBIDDEN by legacy file-SHA tripwire on arena_pipeline_sha.
  Exception DOCUMENTED / AUTHORIZED BY j13 per 0-9L-A.
```

STOP after final report.
