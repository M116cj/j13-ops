# 05 — Final Report

Order: TEAM ORDER 0-9X-A1-REJECT-TAXONOMY-HOTFIX
Phase: 6
Date (UTC): 2026-04-27
Author: Claude Lead

## 1. Final Verdict

**FINAL_VERDICT: COMPLETE_TAXONOMY_HOTFIX_MAPPED_PR43_REJECTS**

UNKNOWN_REJECT taxonomy bug from PR #43 is **closed**. The two missing keys are now deterministically mapped to existing canonical reasons. The existing `UNKNOWN_REJECT` fallback contract is preserved for genuinely unknown raw reject reasons. No validator behavior changed.

## 2. HEAD before

`9f4bf8a44a05dd3dd68f371b8806e8d1195a3021` (main, Mac and Alaya at parity)

## 3. Patch files changed

| File | LOC delta | Type |
|---|---|---|
| `zangetsu/services/arena_rejection_taxonomy.py` | +10 / -1 | 2 RAW_TO_REASON entries + 2 explanatory comment blocks + 1 stale line-number fix in comment |
| `zangetsu/tests/test_arena_rejection_taxonomy.py` | +60 / 0 | 5 new contract tests appended below existing block |

Plus 6 evidence docs in `docs/recovery/20260424-mod-7/0-9x-a1-reject-taxonomy-hotfix/`. No other files modified.

## 4. Exact mappings added

| Raw key | Canonical reason |
|---|---|
| `reject_train_neg_pnl` | `RejectionReason.COST_NEGATIVE` |
| `reject_combined_sharpe_low` | `RejectionReason.LOW_BACKTEST_SCORE` |

No new enum members added. The 18-member `RejectionReason` enum is preserved (locked by pre-existing test `test_taxonomy_reason_count_unchanged_after_v10_patch`).

## 5. classify() before / after

Before patch (Mac, pre-edit):
```
'reject_train_neg_pnl':       in_map=False classify=UNKNOWN_REJECT
'reject_combined_sharpe_low': in_map=False classify=UNKNOWN_REJECT
RAW_TO_REASON map size = 22
```

After patch (Mac, post-edit, post-reload):
```
'reject_train_neg_pnl':       in_map=True classify=COST_NEGATIVE
'reject_combined_sharpe_low': in_map=True classify=LOW_BACKTEST_SCORE
'unknown_future_reason':      in_map=False classify=UNKNOWN_REJECT  (fallback intact)
RAW_TO_REASON map size = 24
```

## 6. Tests result

| Suite | Result |
|---|---|
| `pytest -q zangetsu/tests/test_arena_rejection_taxonomy.py` | **35 / 35 PASS** (30 pre-existing + 5 new) |
| `pytest -q zangetsu/tests -k "taxonomy or rejection or reject_reason or arena_batch_metrics"` | 3 skipped, 623 deselected, 2 collection errors (pre-existing Alaya-only path artifacts; not caused by this hotfix) |

Verdict: **POST_PATCH_TESTS_PASS_PRE_EXISTING_FAILURES** — see `02_contract_test_report.md`.

## 7. Live observability classification

**IMPORT_CLASSIFY_PASS** on Mac (verified via direct module reload + classify() assertions). **LIVE_NEW_MAPPING_VISIBLE deferred** until next worker restart cycle — the running A1/A23/A45 workers (alive since 2026-04-27T08:04Z) hold the pre-patch `RAW_TO_REASON` in memory; the next restart will naturally pick up the patched source. Do-not-force-restart policy chosen per order Phase 4 guidance. Detail in `03_live_observability_check.md`.

## 8. Controlled diff result

**CONTROLLED_DIFF_PASS** — see `04_controlled_diff_report.md` (governance-verifier subagent).

| Dimension | Outcome |
|---|---|
| arena_rejection_taxonomy.py | EXPLAINED_TAXONOMY_ONLY (2 mappings + 2 comment blocks + 1 stale-comment fix) |
| test file | EXPLAINED_TEST_ONLY (5 new tests appended; no semantic change to existing tests) |
| docs | EXPLAINED_DOCS_ONLY |
| arena_pipeline.py / arena_gates.py / config/settings.py | unchanged (diff stat empty) |
| A2_MIN_TRADES | 25 unchanged (`arena_gates.py:48`, `settings.py:29`) |
| alpha_zoo_injection.py | `--no-db-write` default=True, `--confirm-write` default=False — intact |
| apply path | 0 real apply paths added (all matches pre-existing test forbidden-list literals) |

## 9. Forbidden ops status

**0**

- No alpha formula generation / mutation / crossover / search policy / generation budget / sampling weights / validation thresholds change
- No A2_MIN_TRADES / Arena pass-fail / champion promotion / deployable_count change
- No execution / capital / risk change
- No alpha_zoo DB write enabled
- No live CANARY started
- No production rollout started
- No runtime calibration change
- No DB guard weakening
- No admission_validator change
- COUNTER_INCONSISTENCY accounting bug NOT touched (explicitly out of scope per order)
- No worker killed
- No hard reset
- No force-push

## 10. Validator behavior changed?

**No.** The validator code paths read `stats[reject_*]` integers (raw counters) directly to decide pass/fail. The canonical reason assigned by `classify()` is consumed only by the telemetry emitter (`_emit_a1_batch_metrics_from_stats_safe`) when building `arena_batch_metrics.reject_reason_distribution`. Changing the canonical-reason mapping changes which bucket each rejection falls into in the telemetry distribution; it does not change which candidates pass or fail.

## 11. UNKNOWN_REJECT root cause closed?

**Yes, for the PR #43 keys.** Both `reject_train_neg_pnl` and `reject_combined_sharpe_low` now map to non-UNKNOWN canonical reasons. The `UNKNOWN_REJECT` fallback bucket remains available for any future genuinely-unknown raw reject reason (intended behavior, locked in by `test_unknown_reject_fallback_still_works`).

After the next worker restart cycle, the live `arena_batch_metrics.reject_reason_distribution` should show:
- `UNKNOWN_REJECT` ≈ 0 contribution from these two keys
- `COST_NEGATIVE` and `LOW_BACKTEST_SCORE` increase to absorb the relabeled rejections
- `COUNTER_INCONSISTENCY` ≈ unchanged (separate root cause)

## 12. Remaining known issue

**`COUNTER_INCONSISTENCY` accounting bug is still pending.** Diagnosed in `0-9x-a1-reject-distribution-shift-diagnosis/05_counter_inconsistency_root_cause.md`: `stats` dict at `arena_pipeline.py:707-723` is worker-lifetime cumulative; `entered_count = len(alphas)` is per-round; cumulative `rejected_count >> entered_count` after warmup, so the conservation check at lines 226-232 trips into the negative-residual branch every emit. This is **explicitly out of scope** for the present hotfix per order Forbidden-actions list ("Do not patch COUNTER_INCONSISTENCY accounting in this order").

## 13. Next recommended order

**`TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX`** — refactor `_emit_a1_batch_metrics_from_stats_safe` to use per-round delta semantics (or per-emit reset), add residual=0 regression test.

Suggested options outlined in `0-9x-a1-reject-distribution-shift-diagnosis/05_counter_inconsistency_root_cause.md` §"Recommended remediation".

## 14. Q1 / Q2 / Q3 self-check

- **Q1 Adversarial (5-dim)**:
  - Input boundary: PASS — both new keys verified mapped; fallback verified intact for unknown keys
  - Silent failure: PASS — `classify()` never raises (per docstring); 2 new mappings deterministic; failure mode = falls back to UNKNOWN_REJECT, which is the documented contract
  - External dependency: PASS — module-level constant edit; no DB/network/import dependency added
  - Concurrency: PASS — `RAW_TO_REASON` is a module-level read-only constant; no cross-worker contention
  - Scope creep: PASS — only taxonomy file + new tests + docs; arena_pipeline.py / arena_gates.py / config/settings.py untouched
- **Q2 Structural**: PASS — existing UNKNOWN_REJECT fallback preserved (test `test_unknown_reject_fallback_still_works` enforces); existing 22 mappings unchanged (test `test_existing_core_mappings_unchanged` enforces)
- **Q3 Efficiency**: PASS — 2-line patch (+ 2 comment blocks), 5 contract tests appended to existing test file, 6 evidence docs (target ≤ 7)

## 15. Telegram status

Phase 9 message will be sent to Thread 356 after PR merge.
