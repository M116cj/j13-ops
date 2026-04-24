# P7-PR1 Final Verdict

Per TEAM ORDER 0-9E §19.

This verdict is authored in two phases:

1. **Pre-merge** (this file as committed in the signed PR) — records the local + CI-preparation outcome and the expected merge result.
2. **Post-merge amendment** — a follow-up signed commit on this branch appends the actual PR merge SHA, Gate-A/B run IDs, and post-merge origin/main state.

## 1. Pre-merge summary

| Field | Value |
|---|---|
| MOD-7 status | IN PROGRESS (P7-PR1 executing) |
| Phase 7 status | STARTED (governance mode = SIGNED_PR_ONLY) |
| P7-PR1 status | Ready to commit + merge |
| Branch | `phase-7/p7-pr1-arena-rejection-telemetry` |
| Base | `origin/main @ 966cd59326b970055d1c398f2a9d45215bbfbc49` (MOD-7C) |
| New files added | 12 (3 source + 3 tests + 6 docs) |
| Existing files modified | 0 |
| Tests | 46 / 46 pass (local) |
| Controlled-diff | EXPLAINED, 0 forbidden |
| GitHub signature (local) | Good, ED25519 `SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk` |

## 2. Rejected candidate taxonomy status

- **Canonical vocabulary**: 18 reasons × 14 categories × 4 severities defined.
- **Coverage of existing Arena runtime reject strings**: 20 raw keys mapped in `RAW_TO_REASON` (sourced from `arena_gates.py`, `arena_pipeline.py`, `arena23_orchestrator.py`, `arena13_feedback.py`).
- **UNKNOWN_REJECT fallback**: present, exercised, and guarded by `test_classify_does_not_return_unknown_when_deterministic_mapping_available` against regression.

## 3. Arena 2 visibility status

- `TelemetryCollector.arena2_breakdown()` provides per-reason count breakdown at Arena 2 stage.
- `derive_deployable_count(lifecycles)` provides structured provenance for `deployable_count == 0` — answers "why is Arena 2 rejecting candidates?" (0-9E §5 Q9) and "why is deployable_count zero?" (Q8).
- Actual Arena 2 live breakdown cannot be measured by this PR — it requires SHADOW activation (separate future order per `p7_pr1_shadow_plan.md`).

## 4. UNKNOWN_REJECT percentage

- **At PR time**: N/A (no telemetry run has occurred; collectors are empty).
- **SHADOW target**: < 10 % — if exceeded, extend `RAW_TO_REASON` before CANARY.
- **CANARY ceiling**: < 15 % — exceeding this is a CANARY abort condition.

## 5. Rollback readiness

- All 12 additions are **additive-only**. No existing file modified.
- Rollback = `git revert <merge_commit_sha>` — single command, no data migration, no service restart required.
- Since no Arena runtime file changed, reverting does not affect live candidate survival outcomes.
- See `p7_pr1_canary_plan.md §6` for the matching CANARY rollback runbook.

## 6. Forbidden changes verification

| Forbidden change | Verified NOT occurred |
|---|---|
| Alpha formula modified | ✓ (arena_pipeline SHA unchanged; no Arena code touched) |
| Alpha generation modified | ✓ (same) |
| Arena thresholds modified | ✓ (`test_arena_gates_thresholds_unchanged` pins all 6 thresholds) |
| Arena 2 relaxed | ✓ (`test_arena2_pass_*` tests confirm decision parity) |
| Champion promotion rule modified | ✓ (no file under promotion path touched) |
| Trade execution logic modified | ✓ (no execution-engine file touched) |
| Production capital behavior modified | ✓ (no capital/position code touched) |
| Risk limits modified | ✓ (no risk-limit file touched) |
| Live runtime behavior mutated | ✓ (no systemd unit restarted) |
| Rejection hidden under generic labels | ✓ (UNKNOWN_REJECT never returned when deterministic mapping exists — test-enforced) |
| Arena 2 claimed "fixed" | ✓ (this PR adds visibility; makes no fix claim) |
| Arena 0 regression lock started | ✓ (not touched) |
| Arena 1 scoring refactor | ✓ (not touched) |
| Arena 2 root-cause fix | ✓ (not touched) |
| Arena 3 migration | ✓ (not touched) |
| Branch protection weakened | ✓ (all 5 protection fields unchanged) |

## 7. Actual merge outcome (filled post-merge)

- **PR URL**: _to be filled_
- **Signed commit SHA (pre-merge)**: _to be filled_
- **GitHub signature verification**: _to be filled_ (expected: `verified:true / reason:valid`)
- **Merge strategy**: squash (chosen because `required_signatures=true` rejects rebase merges that GitHub cannot web-flow-sign — pattern established in MOD-7B/7C)
- **Merge commit SHA on main**: _to be filled_
- **Merge commit verification**: _to be filled_ (expected: `verified:true` via GitHub web-flow auto-sign)
- **Merged at**: _to be filled_

## 8. Correct success wording (per 0-9E §19)

Upon successful merge, the following wording is authorized:

```
MOD-7 = ACTIVE
Phase 7 = STARTED
Governance mode = SIGNED_PR_ONLY
P7-PR1 = COMPLETE
First migration target = Arena rejection taxonomy + telemetry baseline
Arena runtime optimization = NOT AUTHORIZED IN THIS ORDER
Production rollout = NOT STARTED
Next action = separate order for SHADOW execution or P7-PR2
STOP
```

The following wording is **forbidden** (per 0-9E §19):
- "All Arenas fixed."
- "Arena 2 fixed."
- "Champion generation restored."
- "Production rollout started."
- "Thresholds optimized."

None of those claims are made anywhere in this PR.

## 9. Next authorized action

Per 0-9E §26: **STOP after P7-PR1 report. Do not start P7-PR2 without separate authorization.**

Subsequent orders may authorize:
- P7-PR1 SHADOW activation (exercise the telemetry against a real Arena log stream to measure `unknown_reject_ratio`).
- P7-PR1 CANARY activation (bounded observation window).
- P7-PR2 (next module migration — out of scope for this order).
