# 0-9O-A — Generation Profile Identity and Read-Only Scoring Final Report

## 1. Status

COMPLETE (PR / merge SHA fields filled post-merge).

## 2. Baseline

- origin/main SHA (pre-merge): `2e385097002d64446548a145dc88d05dcc9769ef`
  (P7-PR4-LITE merge)
- local main SHA (pre-merge): `2e385097002d64446548a145dc88d05dcc9769ef`
- branch: `phase-7/0-9o-a-generation-profile-identity-readonly-scoring`
- PR URL: *(filled after `gh pr create`)*
- merge SHA: *(filled after squash-merge)*
- signature verification: feature commit signed with Alaya ED25519 key
  `SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk`; GitHub-side
  verification pending PR.

## 3. Mission

Explain generation profile identity and read-only scoring.

ZANGETSU keeps alpha internals **black-box** (formulas, mutation
lineage, per-alpha semantics). 0-9O-A adds a **white-box** identity
layer over Arena pass-rate telemetry so:

- Arena metrics can be grouped by generation profile
- Read-only profile scores can compare profile performance
- Dry-run budget recommendations can be surfaced (but never applied)

No alpha generation, Arena, champion promotion, or execution behavior
changes.

## 4. What changed

Files changed (all additive / identity / telemetry / scoring-only):

| File | Change |
|------|--------|
| `zangetsu/services/generation_profile_identity.py` | NEW — identity helper |
| `zangetsu/services/generation_profile_metrics.py` | NEW — aggregator + read-only scoring |
| `zangetsu/services/feedback_decision_record.py` | NEW — dry-run decision record |
| `zangetsu/services/arena_pipeline.py` | ADDITIVE — identity import block + 2 new optional kwargs on A1 helper + identity dict in worker loop + kwargs passed at call site |
| `zangetsu/tests/test_generation_profile_identity_and_scoring.py` | NEW — 42 tests |
| `docs/recovery/20260424-mod-7/0-9o-a/01_..09_*.md` | NEW — 9 evidence docs |
| `docs/governance/snapshots/2026-04-24T140738Z-pre-0-9o-a.json` | NEW |
| `docs/governance/snapshots/2026-04-24T141442Z-post-0-9o-a.json` | NEW |

## 5. Generation profile identity

- `generation_profile_id`: `"gp_" + <first 16 hex chars of fingerprint>`
- `UNKNOWN_PROFILE` fallback: returned when config is None / empty or
  canonicalization fails.
- `profile_fingerprint`: `"sha256:" + <64 hex chars>` computed from
  canonical JSON (sorted keys, compact separators) of the volatile-
  stripped config.
- `UNAVAILABLE` fallback: returned when fingerprint cannot be computed.
- Canonical JSON contract: sorted keys, compact separators, volatile
  fields excluded recursively (`timestamp*`, `created_at`,
  `updated_at`, `run_id`, `batch_id`, `worker_id`, `now`, `ts`,
  `clock`, `nonce`).

## 6. Telemetry integration

In `arena_pipeline.py`:

1. Module import block loads
   `safe_resolve_profile_identity` and exposes it as
   `_safe_resolve_profile_identity` (with an inline fallback stub if
   the module import fails — telemetry can still emit with UNKNOWN).
2. Worker startup block builds a read-only identity dict from GP
   parameters (N_GEN, POP_SIZE, TOP_K, ENTRY_THR, EXIT_THR, MIN_HOLD,
   COOLDOWN, STRATEGY_ID) plus `generator_type="gp_v10"`.
3. A1 batch emission call site passes the identity's `profile_id` and
   `profile_fingerprint` into the existing P7-PR4-LITE helper via two
   new optional kwargs. Omitted kwargs fall back to UNKNOWN /
   UNAVAILABLE (backwards-compatible).
4. The helper propagates the kwargs into `ArenaStageMetrics`, which in
   turn populates `arena_batch_metrics`.

## 7. generation_profile_metrics

Schema + aggregation rules per
`03_generation_profile_metrics_schema.md`.

Current A2 / A3 limitation: P7-PR4-LITE only wired A1
`arena_batch_metrics`. A2 / A3 counts therefore aggregate to `0` and
rates to `0.0`; `confidence` reports
`LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE`. Full confidence is
gated on future P7-PR4B wiring A2 / A3.

## 8. Read-only scoring model

Formula, weights, guardrails, and LOW_CONFIDENCE state documented in
`04_read_only_scoring_model.md`. Weights match TEAM ORDER 2-3 §9
defaults. Score output is clamped to `[-1.0, 1.0]`. Dry-run budget
weight pins at `EXPLORATION_FLOOR = 0.05` until
`MIN_SAMPLE_SIZE_ROUNDS = 20` is met.

## 9. feedback_decision_record

`mode="DRY_RUN"`, `applied=False` invariant enforced at three layers:
constructor defaults, `__post_init__`, and `to_event()`. Any attempt
to construct `applied=True` or mutate the field post-construction is
overridden. Default `safety_constraints` auto-populated (8 items).

## 10. Behavior invariance

Explicit confirmations:

- No alpha generation behavior change.
- No formula generation behavior change.
- No mutation / crossover behavior change.
- No search policy behavior change.
- No generation budget change (no allocator exists in runtime yet).
- No threshold change (`test_no_threshold_constants_changed_under_0_9o_a`).
- No Arena pass/fail change
  (`test_arena_pass_fail_behavior_unchanged_a2_min_trades`).
- No champion promotion change (`test_champion_promotion_unchanged`).
- No `deployable_count` semantic change
  (`test_deployable_count_semantics_unchanged`).
- No execution / capital / risk change.

## 11. Test results

- Baseline: 211 passed.
- After 0-9O-A: **253 passed**, 3 skipped (42 new tests, zero
  regression).
- Dedicated 0-9O-A suite: 42/42 PASS.

```
$ python3 -m pytest \
    zangetsu/tests/test_generation_profile_identity_and_scoring.py -v
========================== 42 passed, 1 warning in 0.54s ==========================
```

## 12. Controlled-diff

Classification: **EXPLAINED_TRACE_ONLY** (0-9M pathway).

- Zero diff: 42 fields
- Explained diff: 1 field (`repo.git_status_porcelain_lines 1 → 7` —
  the 7 new / modified tracked paths)
- Explained TRACE_ONLY diff: 1 field
  (`config.arena_pipeline_sha` — authorized via
  `--authorize-trace-only config.arena_pipeline_sha`)
- Forbidden diff: **0**

See `08_controlled_diff_report.md`.

## 13. Gate-A

Expected PASS. Resolution link: *(filled after run)*.

## 14. Gate-B

Expected PASS. Resolution link: *(filled after run)*.

## 15. Branch protection

Confirmed intact:
- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

## 16. Forbidden changes audit

- CANARY not started.
- Production rollout not started.
- No alpha generation behavior change.
- No formula generation behavior change.
- No mutation / crossover behavior change.
- No search policy behavior change.
- No generation budget change.
- No threshold change.
- No Arena pass/fail change.
- No champion promotion change.
- No `deployable_count` semantic change.
- No execution / capital / risk change.

## 17. Remaining risks

- A2 / A3 batch metrics not wired yet — read-only scoring carries
  `LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE` marker until P7-PR4B.
- Read-only scoring is low confidence until `N >= 20` rounds per
  profile — `min_sample_size_met` guards this.
- Dry-run recommendations are never applied — enforced at 3 layers
  (constructor default, `__post_init__`, `to_event()`).
- Generation budget allocator remains a future order (0-9O-B); no
  runtime consumer of `next_budget_weight_dry_run` exists yet.

## 18. Recommended next action

**P7-PR4B — A2/A3 Aggregate Arena Batch Metrics Wiring** (unlocks
`CONFIDENCE_FULL` for generation profile metrics + enables real profile
comparison).

Alternatively, if A2 / A3 wiring is deferred, 0-9O-B dry-run budget
allocator is safe to start — it would surface a recommendation only,
still gated on `min_sample_size_met` and `confidence=FULL`.
