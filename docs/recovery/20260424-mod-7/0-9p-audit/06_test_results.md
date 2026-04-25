# 06 — Test Results

## 1. New suite

`zangetsu/tests/test_profile_attribution_audit.py` — 56 tests.

```
$ python3 -m pytest zangetsu/tests/test_profile_attribution_audit.py
======================== 56 passed, 1 warning in 0.15s =========================
```

## 2. Coverage map (vs TEAM ORDER 0-9P-AUDIT §6)

| § | Required test | 實際 |
| --- | --- | --- |
| §6 | `test_attribution_audit_counts_passport_identity` | ✅ |
| §6 | `test_attribution_audit_counts_orchestrator_fallback` | ✅ |
| §6 | `test_attribution_audit_counts_unknown_profile` | ✅ |
| §6 | `test_attribution_audit_counts_unavailable_fingerprint` | ✅ |
| §6 | `test_attribution_audit_computes_unknown_profile_rate` | ✅ |
| §6 | `test_attribution_audit_computes_profile_mismatch_rate` | ✅ (`test_profile_mismatch_count_increases_on_mismatch` + `test_profile_mismatch_rate_zero_on_perfect_alignment`) |
| §6 | `test_attribution_audit_green_classification` | ✅ |
| §6 | `test_attribution_audit_yellow_classification` | ✅ |
| §6 | `test_attribution_audit_red_classification` | ✅ |
| §6 | `test_red_classification_blocks_consumer_phase` | ✅ |
| §6 | `test_replay_preserves_a1_a2_a3_stage_counts` | ✅ |
| §6 | `test_replay_groups_metrics_by_profile` | ✅ |
| §6 | `test_replay_keeps_unknown_profile_visible` | ✅ |
| §6 | `test_audit_does_not_modify_runtime_state` | ✅ |
| §6 | `test_audit_does_not_import_generation_runtime` | ✅ |
| §6 | `test_audit_does_not_import_arena_runtime_with_side_effects` | ✅ |

16 對應 + 40 extras (schema lock / source classification edge cases /
threshold constants / per-profile breakdown / replay edge cases /
JSON-line parser / behavior invariance).

## 3. Adjacent suites

```
$ python3 -m pytest \
    zangetsu/tests/test_passport_profile_attribution.py \
    zangetsu/tests/test_a2_a3_arena_batch_metrics.py \
    zangetsu/tests/test_feedback_budget_allocator.py \
    zangetsu/tests/test_profile_attribution_audit.py
========================== 212 passed in 0.27s =========================
```

P7-PR4B (54) + 0-9O-B (62) + 0-9P (40) + 0-9P-AUDIT (56) = 212 PASS.
0 regression.

## 4. Pre-existing local fail

8 pre-existing fail tests remain (unrelated to this PR; all caused
by `arena_pipeline.py` chdir to `/home/j13/j13-ops`). CI on Alaya
will pass.
