# P7-PR4-LITE — Aggregate Arena Pass-Rate Telemetry Final Report

## 1. Status

COMPLETE (post-merge summary filled at PR-close time; placeholder
sections below are resolved in the PR thread and in section §22 of the
Claude CLI handoff).

## 2. Baseline

- origin/main SHA (pre-merge): `6b718411f0aca57fadf396e4d86edece7b073bb1`
  (0-9N merge)
- local main SHA (pre-merge): `6b718411f0aca57fadf396e4d86edece7b073bb1`
- branch: `phase-7/p7-pr4-lite-arena-pass-rate-telemetry`
- PR URL: *(filled after `gh pr create`)*
- merge SHA: *(filled after squash-merge)*
- signature verification: signed with Alaya ED25519 key
  `SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk`; GitHub-side
  verification pending PR.

## 3. Mission

Explain black-box alpha + white-box Arena pass-rate telemetry:

- Alpha generation, formula internals, mutation lineage, and per-alpha
  explainability stay **black-box**.
- Arena-level aggregate pass-rate, reject-rate, rejection distribution,
  `deployable_count`, and `generation_profile_id` linkage become
  **white-box** — emitted as `arena_batch_metrics` + `arena_stage_summary`
  events.

## 4. What changed

Files changed (all additive / trace-only):

| File | Change |
|------|--------|
| `zangetsu/services/arena_pass_rate_telemetry.py` | NEW — aggregate telemetry helper module. |
| `zangetsu/services/arena_pipeline.py` | ADDITIVE — module-level import + 3 exception-safe helper functions + 1 call site after the existing A1 round-close log. No change to Arena pass/fail branching. |
| `zangetsu/tests/test_arena_pass_rate_telemetry.py` | NEW — 42 tests. |
| `docs/recovery/20260424-mod-7/p7-pr4-lite/` | NEW — 7 evidence docs. |
| `docs/governance/snapshots/2026-04-24T131935Z-pre-p7-pr4-lite.json` | NEW — pre-snapshot. |
| `docs/governance/snapshots/2026-04-24T133337Z-post-p7-pr4-lite.json` | NEW — post-snapshot. |

## 5. Runtime insertion points

`zangetsu/services/arena_pipeline.py`:

- Lines ~95–145: import block + `_make_a1_batch_metrics_safe`,
  `_emit_a1_batch_metrics_safe`,
  `_emit_a1_batch_metrics_from_stats_safe` (all exception-safe; all never
  raise).
- Line ~1142: single call site
  `_emit_a1_batch_metrics_from_stats_safe(run_id=..., batch_id=...,
  entered_count=len(alphas), passed_count=round_champions, stats=stats,
  log=log)` immediately after the existing round-close log line.

A2 / A3 orchestrators are not modified in P7-PR4-LITE.

## 6. Telemetry schemas

- `arena_batch_metrics` — 20 fields, `TELEMETRY_VERSION="1"`. See
  `01_aggregate_arena_pass_rate_telemetry_design.md` §3.1.
- `arena_stage_summary` — 16 fields. See
  `01_aggregate_arena_pass_rate_telemetry_design.md` §3.2.

## 7. Counter conservation

Invariant:

- Closed: `entered = passed + rejected + skipped + error`, `in_flight=0`.
- Open: `entered = passed + rejected + skipped + error + in_flight`.

Enforced by `validate_counter_conservation()` and accumulator API in
`ArenaStageMetrics`. Residuals routed to `COUNTER_INCONSISTENCY` bucket
rather than raised. 7 dedicated tests PASS.

## 8. Behavior invariance

Explicit confirmations:

- No alpha generation change.
- No threshold change (`test_no_threshold_constants_changed_under_p7_pr4_lite`).
- No Arena pass/fail change
  (`test_arena_pass_fail_behavior_unchanged_*`).
- No champion promotion change
  (`test_champion_promotion_not_affected_by_telemetry`).
- No `deployable_count` semantic change
  (`test_trace_only_pass_events_do_not_inflate_deployable_count`,
  `test_deployable_count_unavailable_by_default`,
  `test_deployable_count_uses_authoritative_source`).
- No execution / capital / risk change (no files in these areas touched).

## 9. Test results

- Baseline: 169 passed.
- After P7-PR4-LITE: **211 passed**, 3 skipped (42 new tests, zero
  regression).
- Dedicated P7-PR4-LITE suite: 42/42 PASS.

```
$ python3 -m pytest zangetsu/tests/test_arena_pass_rate_telemetry.py -v
========================== 42 passed, 1 warning in 0.52s ==========================
```

Pre-existing `test_integration.py` async failures (3) and
`policy/test_exception_overlay.py` module-level `sys.exit` are unrelated
and were present at baseline.

## 10. Controlled-diff

Classification: **EXPLAINED_TRACE_ONLY** (0-9M pathway).

- Zero diff: 42 fields
- Explained diff: 1 field (`repo.git_status_porcelain_lines 1 → 5` — the 5
  new / modified tracked files)
- Explained TRACE_ONLY diff: 1 field
  (`config.arena_pipeline_sha` — authorized via
  `--authorize-trace-only config.arena_pipeline_sha`)
- Forbidden diff: **0**

See `06_controlled_diff_report.md` for full output.

## 11. Gate-A

Expected PASS. Resolution link: *(filled after run)*.

## 12. Gate-B

Expected PASS. Resolution link: *(filled after run)*.

## 13. Branch protection

Confirmed intact:
- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

## 14. Forbidden changes audit

- CANARY not started.
- Production rollout not started.
- No alpha generation change.
- No threshold change.
- No Arena pass/fail change.
- No champion promotion change.
- No `deployable_count` semantic change.
- No execution / capital / risk change.

## 15. Remaining risks

- `generation_profile_id` / `fingerprint` are always
  `UNKNOWN_PROFILE` / `UNAVAILABLE` until 0-9O wires profile IDs through
  candidate generation; this is the designed fallback.
- Only A1 is currently emitting `arena_batch_metrics`; A2 / A3
  orchestrators retain existing telemetry only. Extending A2 / A3 with
  `arena_batch_metrics` is deferred to a subsequent trace-only order.
- The `_pb.run_id` access uses defensive `getattr`; runs where `_pb` does
  not expose `run_id` emit `run_id=""`. Not a correctness issue; noted
  for visibility.

## 16. Recommended next action

**TEAM ORDER 0-9O — Generation Profile Scoring and Feedback-Guided Budget
Allocator.**

Rationale:
- Consumes the `arena_batch_metrics` / `arena_stage_summary` streams
  delivered here.
- Implements the §03 profile scoring / §04 budget allocator designs from
  0-9N.
- Does not weaken Arena pass/fail — operates upstream of Arena.
