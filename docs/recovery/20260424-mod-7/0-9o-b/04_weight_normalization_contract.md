# 0-9O-B — Weight Normalization Contract

## 1. Transform

對每一個 actionable profile：

```
raw_weight = max(profile_score + 1.0, 0.0)
```

`profile_score` 在上游 `compute_profile_score()` 已 clamp 到
`[-1.0, 1.0]`；本 transform 對 out-of-range 也 robust（floor 0.0）。

## 2. UNKNOWN_PROFILE cap

特殊處理：`generation_profile_id == "UNKNOWN_PROFILE"` 的 raw_weight
不可超過 `EXPLORATION_FLOOR (= 0.05)`。在 normalize 之前 cap：

```
if pid == UNKNOWN_PROFILE_ID:
    raw_weight = min(raw_weight, exploration_floor)
```

防止「身分未知的觀察結果壟斷預算」。

## 3. Normalize-with-floor

`_normalize_with_floor(raw_weights, floor=0.05, cap_overrides={...})`：

```
n = len(profiles)
floor_total = floor * n

if floor_total >= 1.0:
    weights = {pid: 1/n for pid in profiles}     # floor saturates budget

else:
    remainder = 1.0 - floor_total
    if sum(raw) <= 0:
        weights = {pid: floor + remainder/n for pid in profiles}
    else:
        weights = {pid: floor + remainder * raw[pid]/sum(raw)
                   for pid in profiles}

# Renormalize so the final sum is exactly 1.0 (numerical safety):
total = sum(weights.values())
weights = {pid: w / total for pid, w in weights.items()}
```

性質：

- `sum(weights) == 1.0`（誤差 < 1e-9）
- 每個 profile `w >= floor - epsilon`
- 不可能出現負值
- key 排序固定（內部以 `sorted(raw_weights)` 處理）→ deterministic

## 4. 測試覆蓋

- `test_weights_sum_to_one`
- `test_weight_calculation_is_deterministic`
- `test_weight_calculation_does_not_mutate_inputs`
- `test_exploration_floor_enforced`
- `test_negative_scores_do_not_create_negative_weights`
- `test_unknown_profile_does_not_dominate_allocation`
- `test_compute_proposed_weights_zero_score_uses_floor_only`
- `test_compute_proposed_weights_handles_empty_input`
- `test_equal_weight_fallback_deterministic_and_normalized`

## 5. 全 non-actionable fallback

當 `actionable_count == 0`：

```
1. 若 caller 提供 previous_profile_weights：
     - 取出非負值
     - 若 sum > 0 → 重新 normalize 到 1.0
     - 若 sum <= 0 → 用 equal_weight_fallback(keys)
2. 否則：
     equal_weight_fallback(觀察到的 profile id list)
```

`confidence = "NO_ACTIONABLE_PROFILE"`、`applied = False`、
`expected_effect = "DRY_RUN_NON_ACTIONABLE_NO_RECOMMENDATION_APPLIED"`。

對應測試：

- `test_all_non_actionable_profiles_use_safe_fallback`
- `test_previous_profile_weights_used_as_fallback`

## 6. 不引入額外 mutation

`compute_proposed_weights` 對輸入 list 不做 in-place mutation；
allocate_dry_run_budget 內部以 `dict(metric)` 拷貝後再操作。
驗證於 `test_weight_calculation_does_not_mutate_inputs`（snapshot
JSON before/after 比對）。
