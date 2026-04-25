# 05 — Test Results

## 1. New test suite

`zangetsu/tests/test_passport_profile_attribution.py` — 40 tests
covering passport persistence + attribution precedence + reader
compatibility + behavior invariance.

```
$ python3 -m pytest zangetsu/tests/test_passport_profile_attribution.py
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/a13/dev/j13-ops/zangetsu
collected 40 items

zangetsu/tests/test_passport_profile_attribution.py ......................... [62%]
...............                                                                [100%]

======================== 40 passed, 1 warning in 0.11s =========================
```

## 2. 對照 §4 required tests

| Required test | 實際 |
| --- | --- |
| `test_passport_persists_generation_profile_id` | ✅ |
| `test_passport_persists_generation_profile_fingerprint` | ✅ |
| `test_passport_profile_identity_round_trips` | ✅ (renamed `test_passport_identity_round_trips_through_attribution_chain`) |
| `test_passport_identity_is_metadata_only` | ✅ (`test_passport_profile_id_is_metadata_only`) |
| `test_a2_telemetry_prefers_passport_profile_identity` | ✅ (`test_a2_a3_reader_prefers_passport_arena1_first`) |
| `test_a3_telemetry_prefers_passport_profile_identity` | ✅ (同上) |
| `test_a2_falls_back_to_orchestrator_profile_when_passport_missing` | ✅ (`test_orchestrator_fallback_when_passport_missing_identity` + `test_a2_a3_reader_falls_back_to_orchestrator`) |
| `test_a3_falls_back_to_orchestrator_profile_when_passport_missing` | ✅ (同上) |
| `test_unknown_profile_fallback_when_all_identity_missing` | ✅ |
| `test_unavailable_fingerprint_fallback_when_all_identity_missing` | ✅ (`test_unavailable_fingerprint_fallback`) |
| `test_passport_identity_failure_does_not_block_telemetry` | ✅ |
| `test_passport_identity_does_not_change_arena_decisions` | ✅ |
| `test_passport_identity_does_not_change_candidate_admission` | ✅ |
| `test_passport_identity_does_not_change_rejection_semantics` | ✅ |
| `test_passport_identity_does_not_change_deployable_count` | ✅ |
| `test_no_formula_lineage_added` | ✅ |
| `test_no_parent_child_ancestry_added` | ✅ |
| `test_no_threshold_constants_changed` | ✅ |
| `test_a2_min_trades_still_pinned` | ✅ |
| `test_a3_thresholds_still_pinned` | ✅ |
| `test_champion_promotion_unchanged` | ✅ |
| `test_generation_budget_unchanged` | ✅ |
| `test_sampling_weights_unchanged` | ✅ |

22 對應 + 18 extra = 40 / 40 PASS。落在 order 規定的 30–50 區間內。

## 3. Adjacent suites（無 regression）

```
$ python3 -m pytest \
    zangetsu/tests/test_a2_a3_arena_batch_metrics.py \
    zangetsu/tests/test_feedback_budget_allocator.py \
    zangetsu/tests/test_passport_profile_attribution.py
========================== 156 passed in 0.20s =========================
```

P7-PR4B (54) + 0-9O-B (62) + 0-9P (40) = 156 PASS / 0 regression。

## 4. Local Mac pre-existing fail

8 個 fail 屬於 `arena_pipeline.py:18` `os.chdir('/home/j13/j13-ops')`
pre-existing 問題（已在 P7-PR4B / 0-9O-B 期間驗證為 main 上同樣 fail）。
與本 PR 無關。CI 於 Alaya 路徑存在的環境下將 PASS。

## 5. Local Mac 終局統計

- **新增 0-9P suite**: 40 PASS / 0 FAIL
- **既有可執行 suite**: 156 PASS / 0 regression
- **既有 pre-existing fail（與本 PR 無關）**: 8

CI 於 Alaya 預期：所有 prior tests + 40 new = full PASS。
