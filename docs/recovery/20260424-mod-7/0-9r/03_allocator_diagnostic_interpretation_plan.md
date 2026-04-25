# 03 — Allocator Diagnostic Interpretation Plan

## 1. 範圍

定義如何**解讀** 0-9O-B `feedback_budget_allocator.allocate_dry_run_budget`
的輸出 `DryRunBudgetAllocation`，但**不**將其連接到 generation
runtime。所有解讀規則僅供：

- 0-9R-IMPL 設計者
- offline reports / 儀表板
- CANARY (0-9S) 評估者

使用。

## 2. Allocator output 對映表

| Allocation field | 解讀規則 |
| --- | --- |
| `confidence` | 第一層 gate。除 `CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE` 之外的值一律視為 **non-actionable**。 |
| `allocator_version` | 必須為 `"0-9O-B"` 才採用。版本不符 → 拒絕推薦。 |
| `mode` / `applied` | 必須 `"DRY_RUN"` / `False`；任一為其他值 → 拒絕並啟動 incident review（applied=True 違反 §3.27）。 |
| `input_profile_count` | 至少 ≥ 2（避免單 profile 自比）。 |
| `actionable_profile_count` | ≥ 2 才考慮 weight shift。1 個 actionable → only PB-FLOOR / PB-DIV 可考慮（記錄 baseline）；0 個 → blocked。 |
| `proposed_profile_weights_dry_run` | 視為**建議方向**而非命令。實作時要做 §04 anti-overfit 的全部 guardrail。 |
| `profile_ranks` | 1-based，by `profile_score` desc。`rank == 1` 不必然要加 budget — 仍須通過所有 anti-overfit gate。 |
| `non_actionable_reasons` | per-profile reason 字典。任一含 `COUNTER_INCONSISTENCY`、`MISSING_A2_A3_METRICS` → 該 profile 完全停手；不可 quarantine 也不可 boost。 |
| `observed_bottleneck` | 6 種枚舉；用於選擇 intervention class（見 §4 mapping table）。 |
| `top_reject_reasons` | aggregate sorted reasons；用於 sanity check observed_bottleneck 沒有判錯（leader_share ≥ 0.40 才 dominant）。 |

## 3. 多時間視窗解讀

單一 `DryRunBudgetAllocation` 不足以授權 intervention。需要連續觀察：

| 觀察項 | 最小視窗 |
| --- | --- |
| `observed_bottleneck` 持續為相同 dominant label | ≥ 3 連續 allocation runs |
| 所有 actionable profile 的 weight shift 方向一致 | ≥ 5 連續 runs |
| `confidence == CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE` 持續 | ≥ 3 runs |
| `UNKNOWN_REJECT` 維持低（< 0.05） | 整段觀察期 |

如何計算「連續」：以 `decision_id` 排序、`created_at` 為 tie-break。
任意一個 run 中斷則計數歸零，重新累積。

## 4. Bottleneck → intervention mapping

| `observed_bottleneck` | 推薦 intervention class | 注意 |
| --- | --- | --- |
| `SIGNAL_TOO_SPARSE_DOMINANT` | PB-SHIFT (dry-run) → PB-SUPPRESS (CANARY) | 永遠保 `EXPLORATION_FLOOR`，不 quarantine sparse-prone profile 直到 ≥ 5 連續觀察。 |
| `OOS_FAIL_DOMINANT` | **不啟動 sparse-candidate intervention**；轉接 `0-9V` (OOS-robustness, future) | OOS_FAIL 是 robustness 問題，不是 sparse 問題；治標誤判。 |
| `UNKNOWN_REJECT_DOMINANT` | **不啟動 intervention**；先補 rejection taxonomy | 高 unknown rate = 觀察盲區，任何 intervention 都會誤判。先做 0-9P (taxonomy completeness) 類補強 order。 |
| `LOW_SAMPLE_SIZE` | block intervention，等 sample 累積 | 不可 j13 override 加速（除非有獨立 generation 加速 order） |
| `MISSING_A2_A3_METRICS` | block intervention | 由 P7-PR4B 已上線；如再次出現代表 telemetry 退化，需修 telemetry。 |
| `NO_ACTIONABLE_PROFILE` | block intervention | 全 fallback；不可動 |
| `UNKNOWN`（dominance < 0.40） | block intervention，繼續觀察 | 沒有單一主導 bottleneck，貿然 intervention 易誤判 |

## 5. UNKNOWN_PROFILE 處理規則

`generation_profile_id == "UNKNOWN_PROFILE"` 的 batch 來源未明：

- allocator 已 cap 在 `EXPLORATION_FLOOR` 之下，不可能 dominate。
- 解讀者**不應**把 UNKNOWN_PROFILE 視為一個獨立 strategy；它是觀察盲區。
- 若 UNKNOWN_PROFILE 比例（`non_actionable_reasons` 數 / total）持續高，
  代表 0-9O-A 的 identity propagation 沒覆蓋到所有 batch，需 telemetry
  fix 而非 sparse intervention。

## 6. Counter-inconsistency veto

當任一 profile 的 `unknown_reject_rate >= UNKNOWN_REJECT_VETO (= 0.20)`：

- allocator 已標 `REASON_COUNTER_INCONSISTENCY` 並 block actionable。
- 解讀者**不可**把該 profile 列入任何 intervention 對象（包括 boost、
  suppress、quarantine）— 觀察值不可信。
- 必須**先**修 taxonomy / arena_rejection_taxonomy.RAW_TO_REASON
  table，把 unknown 拉到 < 0.05，再重新跑允許條件。

## 7. Stability vs sensitivity 取捨

allocator 用 `raw = max(score+1, 0)` 線性 transform；對 score 變動相對
敏感。解讀規則：

- 對 `proposed_profile_weights_dry_run` 採用「方向 only」判讀：
  記錄 each profile 的 sign-of-delta vs `previous_profile_weights`。
- 連續 ≥ 5 runs 同方向才視為穩定 signal。
- weight magnitude 變動絕對值僅供 ranking，不直接 apply（apply 須由
  runtime consumer 做 EMA 平滑、並有 max-step limit；屬於 0-9R-IMPL
  範疇）。

## 8. 不可做的解讀方式

- **不可**從單一 `DryRunBudgetAllocation` 推出生產級的 budget 變動建議。
- **不可**根據 allocator 推薦反推單一 alpha 的問題（per-alpha lineage
  不存在；§3.25 禁止）。
- **不可**把 `confidence != CONFIDENCE_A1_A2_A3_AVAILABLE` 的 allocation
  視為 actionable 並 j13 override（除非另一個 order 明示）。
- **不可**讓 dashboard / 報告 link allocator output 到 production
  generation pipeline（§3.27）。
- **不可**用 allocator output 作為 `champion_pipeline.status` 變動的
  依據（§3.14）。

## 9. 未來實作端的 read-only 查詢規則

當 0-9R-IMPL 啟動 runtime consumer 時，consumer 必須：

- 訂閱 `dry_run_budget_allocation` events（log line / event bus）。
- 自帶 EMA window（建議 `α = 0.2`、≥ 5 events 平滑）。
- 自帶 max-step limit（單一 round 內 weight 變動 ≤ 10% absolute）。
- 自帶 hard floor（per profile ≥ 0.05）。
- 自帶 sanity check（sum=1.0；任何違反 → fall back to previous weights）。

任何違反上述守則的 consumer 設計都不算 0-9R / 0-9R-IMPL 合規範圍。
