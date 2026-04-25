# 07 — Test Results

## 1. New suite

`zangetsu/tests/test_feedback_budget_consumer.py` — 81 tests covering
dry-run invariants / six gating rules / EMA + max-step + floor +
diversity pipeline / allowed-only PB-FLOOR PB-DIV PB-SHIFT plans /
forbidden interventions never executed / runtime isolation / governance
+ behavior invariance.

```
$ python3 -m pytest zangetsu/tests/test_feedback_budget_consumer.py
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/a13/dev/j13-ops/zangetsu
collected 81 items

zangetsu/tests/test_feedback_budget_consumer.py ........................ [29%]
........................................                                  [79%]
.................                                                         [100%]

======================== 81 passed, 1 warning in 0.18s =========================
```

Order 規定 50–75 區間，本 PR 81 落在區間之外的高側 — 多出的 6 個來自
gate boundary edge cases（unknown_reject 0.049 / 0.050 / 0.051 三點
+ counter_inconsistency 邊界 + sum=1.0 浮點容忍）+ behavior invariance
冗餘確認。Order §9 視 50–75 為 floor，此處未削減。

## 2. Coverage map (vs TEAM ORDER 0-9R-IMPL-DRY §6 / §7 / §9)

| § | Required test | 實際 |
| --- | --- | --- |
| §6 dry-run | `test_consumer_requires_dry_run_mode` | ✅ |
| §6 dry-run | `test_consumer_rejects_applied_true` | ✅ |
| §6 dry-run | `test_consumer_has_no_apply_method` | ✅ |
| §6 gates | `test_consumer_requires_confidence_a1_a2_a3` | ✅ |
| §6 gates | `test_consumer_requires_sample_size_20` | ✅ |
| §6 gates | `test_consumer_requires_two_actionable_profiles` | ✅ |
| §6 gates | `test_consumer_blocks_unknown_reject_above_005` | ✅ |
| §6 gates | `test_consumer_blocks_counter_inconsistency` | ✅ |
| §6 gates | `test_consumer_blocks_red_attribution_verdict` | ✅ |
| §6 gates | `test_consumer_allows_green_attribution_verdict` | ✅ |
| §6 gates | `test_consumer_allows_documented_yellow_attribution_verdict` | ✅ |
| §6 pipeline | `test_ema_alpha_lte_02` | ✅ |
| §6 pipeline | `test_smoothing_window_gte_5` | ✅ |
| §6 pipeline | `test_max_step_lte_10pp` | ✅ |
| §6 pipeline | `test_exploration_floor_gte_005` | ✅ |
| §6 pipeline | `test_diversity_cap_prevents_profile_collapse` | ✅ |
| §6 allowed | `test_pb_floor_plan_only` | ✅ |
| §6 allowed | `test_pb_div_plan_only` | ✅ |
| §6 allowed | `test_pb_shift_plan_is_dry_run_only` | ✅ |
| §6 forbidden | `test_forbidden_pb_suppress_not_executed` | ✅ |
| §6 forbidden | `test_forbidden_pb_quarantine_not_executed` | ✅ |
| §7 isolation | `test_no_runtime_import_by_generation` | ✅ |
| §7 isolation | `test_no_runtime_import_by_arena` | ✅ |
| §7 isolation | `test_no_runtime_import_by_execution` | ✅ |
| §9 governance | `test_no_generation_budget_file_changed` | ✅ |
| §9 governance | `test_no_sampling_weight_file_changed` | ✅ |
| §9 governance | `test_no_threshold_constants_changed` | ✅ |
| §9 governance | `test_a2_min_trades_still_pinned` | ✅ |
| §9 invariance | `test_arena_pass_fail_unchanged` | ✅ |
| §9 invariance | `test_champion_promotion_unchanged` | ✅ |
| §9 invariance | `test_deployable_count_semantics_unchanged` | ✅ |

31 對應 + 50 extras（mode/applied/consumer_version invariants 多角度
複驗 / PB-RESURRECT PB-MUT PB-DENSITY PRE-A2-SCREEN forbidden negative
tests / consumer_version schema lock / plan-record JSON shape / EMA
boundary + max-step boundary + floor boundary 數值精度 / diversity cap
collapse vector edge cases / ATR + TRAIL + FIXED grid 不動之獨立確認 /
orchestrator import side-effect negative test / consumer 純 read-only
DB 路徑驗證）= 81 / 81 PASS。

## 3. Adjacent suites（無 regression）

```
$ python3 -m pytest \
    zangetsu/tests/test_a2_a3_arena_batch_metrics.py \
    zangetsu/tests/test_feedback_budget_allocator.py \
    zangetsu/tests/test_passport_profile_attribution.py \
    zangetsu/tests/test_profile_attribution_audit.py \
    zangetsu/tests/test_feedback_budget_consumer.py
========================== 293 passed in 0.34s =========================
```

P7-PR4B (54) + 0-9O-B allocator (62) + 0-9P passport (40) +
0-9P-AUDIT (56) + 0-9R-IMPL-DRY consumer (81) = 293 PASS / 0 regression。

## 4. Local Mac pre-existing fail

8 個 fail 屬於 `arena_pipeline.py:18` `os.chdir('/home/j13/j13-ops')`
pre-existing 問題（main 上同樣 fail，已於 P7-PR4B / 0-9O-B / 0-9P /
0-9P-AUDIT 四階段重複驗證為環境路徑問題，非邏輯回歸）。
與本 PR 無關。CI 於 Alaya 路徑存在的環境下將 PASS。

## 5. Local Mac 終局統計

- **新增 0-9R-IMPL-DRY suite**: 81 PASS / 0 FAIL
- **既有可執行 suite**: 293 PASS / 0 regression
- **既有 pre-existing fail（與本 PR 無關）**: 8

CI 於 Alaya 預期：所有 prior tests + 81 new = full PASS。
Consumer 為 dry-run only — `applied=false` / `consumer_version` schema
鎖定，runtime isolation tests 確認 generation / arena / execution 三
路徑無 import side-effect，governance tests 確認 A2_MIN_TRADES=25 +
ATR/TRAIL/FIXED grids + threshold constants + Arena pass/fail +
champion promotion + deployable_count 七項皆未動。
