# 0-9L Controlled-Diff Exception Record

Per TEAM ORDER 0-9L-A §7.

## Status

- **Exception status**: DOCUMENTED / AUTHORIZED BY j13
- **Branch**: `phase-7/p7-pr3-lifecycle-trace-contract`
- **origin/main before commit**: `fe1b0a60448b408de0db105d027e9c14d4d8297a`
- **Local branch**: `phase-7/p7-pr3-lifecycle-trace-contract` (pre-commit)
- **Timestamp**: 2026-04-24T10:40Z (exception documentation)

## Controlled-Diff Result

- **Classification**: FORBIDDEN
- **Forbidden field**: `config.arena_pipeline_sha`
- **Old SHA**: `34a3791f1686cc5f7c50c5f2f7e6db7eb1afca7340166dec63a32c5b05273d83`
- **New SHA**: `888e2fdd4b4af5f6f6523256462d02ba012dafa64c968663fd6d8225bc749142`
- **Zero diff count**: 42
- **Explained diff count**: 1 (`repo.git_status_porcelain_lines`)
- **Forbidden diff count**: 1 (`config.arena_pipeline_sha`)

## Why the Exception Exists

- 0-9L-PLUS §11 **explicitly authorized** modification of `zangetsu/services/arena_pipeline.py` as a Primary Source File for P7-PR3 A1 trace-native lifecycle emission.
- P7-PR3 **requires** trace-native A1 lifecycle emission — the instrumentation cannot be added without touching `arena_pipeline.py`.
- `arena_pipeline.py` SHA change is a **direct, deterministic** consequence of the authorized trace insertion (+59 lines of additive emission scaffolding and 3 call sites).
- Legacy controlled-diff (`scripts/governance/diff_snapshots.py` + `docs/recovery/20260424-mod-5/state_diff_acceptance_rules.md`) enforces a **file-SHA tripwire** that flags any `arena_pipeline_sha` change as forbidden regardless of whether the change is behavior-invariant.
- This is a **governance policy mismatch between order authorization and tool classification**, NOT a behavior mutation.

## Exact Patch Nature

All changes to `arena_pipeline.py` are **additive** and **non-behavioral**:

| Insertion | Location | Lines added |
|---|---|---:|
| Trace contract import block + `_emit_a1_lifecycle_safe()` helper | After V10 alpha engine imports | +49 |
| A1_ENTRY emission | After alpha_hash computation (line ~722) | +5 |
| A1_EXIT_REJECT emission | At `reject_few_trades` path (line ~751) | +5 |
| A1_EXIT_PASS + A1_HANDOFF_TO_A2 emission | After `rbloom_add` post-insert (line ~942) | +10 |

**What changed**: the file gains ~70 lines of new additive code. No existing line of decision logic was modified.

**What did NOT change**:
- Threshold constants (`bt.total_trades < 30`, `bt_val.total_trades < 15`, `bt_val.net_pnl <= 0`, `bt_val.sharpe_ratio < 0.3`, `val_wilson < 0.52`) — all pinned to their pre-P7-PR3 values.
- A1 pass/fail predicates — untouched.
- A2_MIN_TRADES, A3_MIN_*, A3_WR_FLOOR — unchanged (enforced by `test_arena_gates_thresholds_still_pinned_under_p7_pr3`).
- Admission validator flow.
- Champion promotion rules.
- Bloom dedup behavior.
- Execution, capital, risk, runtime behavior — all unchanged.

## Behavior-Invariance Evidence

**150/150 tests PASS** (92 P7-PR1 + P7-PR2 baseline + 58 new P7-PR3):

| Test module | Count | Status |
|---|---:|---|
| `test_arena_rejection_taxonomy.py` | 30 | ✅ PASS |
| `test_arena_telemetry.py` | 19 | ✅ PASS |
| `test_p7_pr1_behavior_invariance.py` | 9 | ✅ PASS |
| `test_candidate_lifecycle_reconstruction.py` | 10 | ✅ PASS |
| `test_deployable_count_provenance.py` | 13 | ✅ PASS |
| `test_p7_pr2_behavior_invariance.py` | 11 | ✅ PASS |
| `test_lifecycle_trace_contract.py` | 23 | ✅ PASS |
| `test_p7_pr3_trace_native_a1_emission.py` | 14 | ✅ PASS |
| `test_p7_pr3_lifecycle_fullness_projection.py` | 9 | ✅ PASS |
| `test_p7_pr3_behavior_invariance.py` | 12 | ✅ PASS |
| **Total** | **150** | **✅ ALL PASS** |

Key invariance tests specifically exercised:
- `test_arena_gates_thresholds_still_pinned_under_p7_pr3` — A2_MIN_TRADES=25, A3_SEGMENTS=5, A3_MIN_TRADES_PER_SEGMENT=15, A3_MIN_WR_PASSES=4, A3_MIN_PNL_PASSES=4, A3_WR_FLOOR=0.45 all pinned.
- `test_arena2_pass_decision_unchanged_*` — `arena_gates.arena2_pass()` produces identical reason strings on edge inputs.
- `test_emit_helper_cannot_affect_caller_return_value` — the `_emit_a1_lifecycle_safe()` helper returns None and has no externally-visible side effect on the caller's control flow.
- `test_emit_helper_exception_safe_under_logger_failure` — if the logger raises, the helper swallows silently and the caller continues exactly as before.
- `test_deployable_count_not_inflated_by_trace_only_events` — a trace emission of A1 PASSED for a candidate does NOT count it as deployable unless the full chain A0..A3 == PASS.

## Authorization

- **j13 approved Option A** on 2026-04-24 via TEAM ORDER 0-9L-A.
- Exception is **limited** to this P7-PR3 `arena_pipeline_sha` diff.
- **Not a general controlled-diff bypass**.
- **Not permission to weaken governance**.
- controlled-diff logic (`scripts/governance/diff_snapshots.py`, `state_diff_acceptance_rules.md`) **remains unchanged** — no scripts modified in this PR.
- Future unauthorized `arena_pipeline_sha` changes will continue to be flagged FORBIDDEN by the legacy tripwire, as expected.

## Follow-Up

**Recommended next order**: `TEAM ORDER 0-9M — Phase 7 Controlled-Diff Acceptance Rules Upgrade`

Purpose: upgrade `scripts/governance/diff_snapshots.py` + `state_diff_acceptance_rules.md` from a pure file-SHA tripwire to a Phase 7-aware acceptance model that classifies `arena_pipeline_sha` / `arena23_orchestrator_sha` / etc. changes as EXPLAINED iff:

- an explicit Team Order authorizes the touched runtime file,
- behavior-invariance tests pass,
- no threshold diff,
- no alpha diff,
- no champion promotion diff,
- no execution/capital/risk/runtime mutation,
- Gate-A / Gate-B pass,
- signed PR-only flow is preserved.

This would eliminate the need for future exception records on P7-PR4, P7-PR5, and subsequent authorized module migrations.
