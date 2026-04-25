# P7-PR4B — A2/A3 Aggregate Arena Batch Metrics Wiring Final Report

## 1. Status

**COMPLETE — pending Gate-A / Gate-B / signed merge on Alaya side.**

Local execution complete (branch pushed, PR ready). Alaya-side gates run
in CI / on PR open.

## 2. Baseline

- origin/main SHA at start: `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52`
- local main SHA at start: `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52`
- branch: `phase-7/p7-pr4b-a2-a3-arena-batch-metrics`
- PR URL: filled in after `gh pr create`
- merge SHA: filled in after merge
- signature verification: ED25519 SHA256:`jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk` (same key as 0-9O-A PR #17)

## 3. Mission

Extend ZANGETSU aggregate Arena pass-rate telemetry from A1 (delivered
by P7-PR4-LITE) into A2 and A3 so that `generation_profile_metrics` can
compare black-box generation profiles using full A1 / A2 / A3 funnel
data. Without A2/A3 batch metrics, profile scoring stays at
`LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE` and cannot rank profiles.

## 4. What changed

| File | Type | Notes |
| --- | --- | --- |
| `zangetsu/services/arena_pass_rate_telemetry.py` | helper extension | `normalize_arena_stage`, `build_a2_batch_metrics`, `build_a3_batch_metrics`, `safe_emit_a2_batch_metrics`, `safe_emit_a3_batch_metrics`, `aggregate_stage_metrics`. All additive. |
| `zangetsu/services/generation_profile_metrics.py` | confidence enum extension | New `CONFIDENCE_A1_A2_A3_AVAILABLE`, `CONFIDENCE_LOW_SAMPLE_SIZE`. `CONFIDENCE_FULL` aliased for backwards compat. Three-state resolution in `aggregate_batches_for_profile`. |
| `zangetsu/services/arena23_orchestrator.py` | runtime trace-only wiring | Module-level try-imports; `_p7pr4b_resolve_passport_profile`, `_p7pr4b_make_acc_safe`, `_p7pr4b_canonicalize_reason`, `_p7pr4b_record_outcome`, `_p7pr4b_a2_record`, `_p7pr4b_a3_record`, `_P7PR4BLogCapture`. Inside `main()`: accumulator state init; per-champion `on_entered/on_passed/on_rejected/on_error`; flush every `_P7PR4B_BATCH_FLUSH_SIZE` (default 20) champions; shutdown flush. Authorized `EXPLAINED_TRACE_ONLY`. |
| `zangetsu/tests/test_a2_a3_arena_batch_metrics.py` | new test file | 54 tests covering §12.1–§12.9 + extension surface. |
| `docs/recovery/20260424-mod-7/p7-pr4b/01..08*.md` | evidence docs | 8 markdown artifacts. |

## 5. Runtime insertion points

`zangetsu/services/arena23_orchestrator.py`:

- Lines ~150–330 (module-level helpers + try-imports + `_P7PR4BLogCapture`).
- Inside `async def main()`: state init right before `running = True`.
- Inside A3 `if champion:` block: telemetry update after the existing
  try / except / log_transition block, before the elapsed timer.
- Inside A2 `if champion:` block: telemetry update at two points — the
  dedup-skip path (inline before the existing `continue`) and the
  normal A2 path (after the try / except / log_transition block).
- End of `main()`: shutdown flush block right after the PGQueuer close,
  before `await db.close()`.

Detailed insertion-point map: see `02_runtime_insertion_points.md`.

## 6. A2 telemetry

| Field | Value source |
| --- | --- |
| `entered_count` | `acc.on_entered()` per champion picked from `pick_champion(db, "ARENA1_COMPLETE", "ARENA2_PROCESSING")` |
| `passed_count` | `acc.on_passed()` when `process_arena2` returns `(True, fields)` (i.e. `improved=True`) |
| `rejected_count` | `acc.on_rejected(canonical)` for: dedup-skip (`duplicate_indicator_combo`), `process_arena2` returns `None`, or returns `(False, fields)` |
| `pass_rate` | `compute_pass_rate(passed, entered)` |
| `reject_rate` | `compute_reject_rate(rejected, entered)` |
| `reject_reason_distribution` | populated via `_P7PR4BLogCapture` capturing the most-recent `A2 REJECT*` log line, classified through `arena_rejection_taxonomy.classify(..., arena_stage="A2")` |
| `generation_profile_id` | upstream `passport.arena1.generation_profile_id` if present; else orchestrator consumer profile derived from `_V10_*` knobs; else UNKNOWN_PROFILE |
| `UNKNOWN_PROFILE` fallback | active when both upstream and consumer derivation fail |

## 7. A3 telemetry

| Field | Value source |
| --- | --- |
| `entered_count` | `acc.on_entered()` per champion picked from `pick_champion(db, "ARENA2_COMPLETE", "ARENA3_PROCESSING")` |
| `passed_count` | `acc.on_passed()` when `process_arena3` returns a non-None dict |
| `rejected_count` | `acc.on_rejected(canonical)` when `process_arena3` returns `None` |
| `pass_rate` | `compute_pass_rate(passed, entered)` |
| `reject_rate` | `compute_reject_rate(rejected, entered)` |
| `reject_reason_distribution` | populated via `_P7PR4BLogCapture` capturing `A3 REJECT*` / `A3 PREFILTER SKIP` log lines, classified through `arena_rejection_taxonomy.classify(..., arena_stage="A3")` |
| `generation_profile_id` | same fallback chain as A2 |
| `UNKNOWN_PROFILE` fallback | same as A2 |
| `deployable_count` | always `None` from A2/A3 emitter — authoritative source remains `champion_pipeline_fresh.status='DEPLOYABLE'` written by `arena45_orchestrator.maybe_promote_to_deployable` (unchanged) |

## 8. generation_profile_metrics integration

`aggregate_batches_for_profile` already consumed A1 / A2 / A3 batches
(0-9O-A). This PR upgrades the confidence resolution from two-state to
three-state:

```
no a2/a3 metrics                   → LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE
a2/a3 + sample_size_rounds < 20    → LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS
a2/a3 + sample_size_rounds >= 20   → CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE
```

`profile_score` remains read-only. `next_budget_weight_dry_run` remains
locked at `EXPLORATION_FLOOR` while `min_sample_size_met == False`.
`min_sample_size_rounds` guard at `>= 20` is preserved.

## 9. Counter conservation

Closed batch invariant `entered = passed + rejected + skipped + error`
holds because every champion path increments exactly one of
`on_passed / on_rejected / on_error`, each of which decrements
`in_flight_count`. `mark_closed()` routes any residual `in_flight_count`
into `skipped_count` (`BATCH_CLOSED_WITH_IN_FLIGHT` reason). Open-stage
emission carries `in_flight_count` explicitly.

Detailed analysis: `03_counter_conservation_invariant.md`. Tests:
`test_a2_closed_counter_conservation`, `test_a2_open_counter_conservation`,
`test_a2_counter_residual_routes_to_counter_inconsistency`,
`test_a3_closed_counter_conservation`, `test_a3_open_counter_conservation`,
`test_a3_counter_residual_routes_to_counter_inconsistency`.

## 10. Behavior invariance

| Item | Status |
| --- | --- |
| No alpha generation change | ✅ |
| No formula generation change | ✅ |
| No mutation / crossover change | ✅ |
| No search policy change | ✅ |
| No generation budget change | ✅ |
| No threshold change (incl. `A2_MIN_TRADES`, ATR/TRAIL/FIXED grids, A3 segment thresholds) | ✅ |
| No Arena pass/fail change | ✅ |
| No champion promotion change | ✅ |
| No deployable_count semantic change | ✅ |
| No execution / capital / risk change | ✅ |

Full audit: `05_behavior_invariance_audit.md`. Pinned-threshold
verification: `test_a2_min_trades_still_pinned`,
`test_a3_thresholds_still_pinned`. Promotion path verification:
`test_champion_promotion_unchanged`.

## 11. Test results

```
$ python3 -m pytest zangetsu/tests/test_a2_a3_arena_batch_metrics.py
======================== 54 passed, 1 warning in 0.11s =========================
```

Local Mac existing-suite assessment: 293 PASS / 0 regression / 14
pre-existing import-time failures (root cause: `arena_pipeline.py`
module-level `os.chdir('/home/j13/j13-ops')`; verified pre-existing on
`origin/main`). Full breakdown: `06_test_results.md`.

Expected on Alaya CI: `253 (baseline) + 54 (P7-PR4B) = 307 PASS, 3
skipped`.

## 12. Controlled-diff

Expected classification: **EXPLAINED_TRACE_ONLY**.

```
Zero diff:                     ~42 fields
Explained diff:                1 field   — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:     1 field   — config.arena23_orchestrator_sha
Forbidden diff:                0 fields
```

Authorized via
`--authorize-trace-only config.arena23_orchestrator_sha` (0-9M
pathway). Other CODE_FROZEN SHAs untouched (`zangetsu_settings_sha`,
`arena_pipeline_sha`, `arena45_orchestrator_sha`,
`calcifer_supervisor_sha`, `zangetsu_outcome_sha`). Full report:
`07_controlled_diff_report.md`.

## 13. Gate-A

Expected: **PASS** (snapshot-diff classified as
EXPLAINED_TRACE_ONLY → exit code 0).

## 14. Gate-B

Expected: **PASS** (PR open with required artifacts; pull-request
trigger restored by 0-9I).

## 15. Branch protection

Expected unchanged on `main`:

- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

This PR does not modify governance configuration.

## 16. Forbidden changes audit

- CANARY: NOT started.
- Production rollout: NOT started.

## 17. Remaining risks

- **Profile identity propagation**: passport upstream from A1 does not
  yet carry `generation_profile_id`. P7-PR4B falls back to the
  orchestrator's consumer profile (derived from V10 entry / exit / hold
  / cooldown env knobs). When 0-9O-B / future orders persist
  `generation_profile_id` into the passport, A2/A3 batch metrics
  automatically pick it up — no further changes needed in this module.
- **Sample size still gates actionability**: 20 rounds minimum; first
  actionable scoring window will only open once Arena has produced 20+
  closed batches across A1/A2/A3 with the same profile fingerprint.
- **deployable_count via authoritative VIEW**: this PR emits `None` for
  A2/A3 batch metrics. Future order may layer a non-blocking VIEW read
  to populate the field with the real DEPLOYABLE count; out of scope
  here.
- **Telemetry log volume**: each batch flush emits one
  `arena_batch_metrics` JSON line (per stage, every ~20 champions).
  Negligible compared to existing per-champion log volume.
- **Local Mac test gap**: 14 pre-existing fail tests cannot be verified
  on the development host because `/home/j13/j13-ops` does not exist.
  Mitigated by Alaya CI run.

## 18. Recommended next action

**TEAM ORDER 0-9O-B — Dry-Run Feedback Budget Allocator.** With
A1/A2/A3 aggregate metrics now flowing into `generation_profile_metrics`
and three-state confidence available, the next step is to consume
`profile_score` + `next_budget_weight_dry_run` in a dry-run allocator
service that records intent (still `applied=False`) without affecting
the live generation budget. Threshold for actionable allocation
remains `min_sample_size_met` AND `confidence ==
CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE`.

If 0-9O-B is deferred → **TEAM ORDER 0-9R — Sparse-Candidate Black-Box
Optimization Design** to reduce `SIGNAL_TOO_SPARSE` rate at A2 by
adjusting generation profile policy (without weakening
`A2_MIN_TRADES`).
