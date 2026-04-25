# 07 — Red-Team Risk Register

## 1. 範圍

對 0-9R 的 sparse-candidate optimization design 做對抗性審查。每一條
risk 給出：**敘述 → 後果 → 觸發測試 → mitigation**。

## 2. R-01：間接弱化 Arena

**敘述**：intervention 名義上不改 `A2_MIN_TRADES`，但 `PRE-A2-SCREEN`
density screen 過濾後，實質上只剩「容易產生 ≥ 25 trade」的 candidate
進入 A2。等同於把 A2 的篩選往上游搬，弱化 Arena 的 ground truth
觀察能力。

**後果**：A2 pass_rate 改善是錯覺；A3/deployable degradation 可能
延遲出現；難以 rollback 因為 candidate pool 已被 truncate。

**觸發測試**：

- treatment 期間 `total_entered_a1` vs `total_entered_a2` ratio 是否
  顯著下降（screen 過濾比例上升）。
- baseline candidate set 與 treatment candidate set 的 hash overlap
  是否 < 60%。

**Mitigation**：

- 任何 PRE-A2-SCREEN 必須有 fallback pool（被 screen 掉的也仍保留
  exploration_floor 的 budget），允許持續觀察被排除 candidate 的
  A2 表現。
- A/B 評估的 success criterion 包含「baseline 與 treatment 的
  candidate diversity 不顯著下降」。

## 3. R-02：純 pass-rate 優化

**敘述**：intervention 把 budget 集中在「歷史 A2 pass_rate 高」的
profile，忽略 profit quality。短期 pass_rate 提升，長期 deployable
質量下降。

**後果**：champion_pipeline 充滿 shallow-edge candidate；OOS_FAIL
rate 上升。

**觸發測試**：

- treatment 的 `mean_pnl_per_trade` 中位數 vs baseline。
- A4 holdout pass rate（CANDIDATE → DEPLOYABLE）是否 degrade。

**Mitigation**：

- composite score 必須含 deployable_density 權重（見 §05 §5）。
- F1–F2 failure criteria 直接 rollback。

## 4. R-03：隱性 threshold 改動

**敘述**：intervention 在 PR description 上不寫「改 threshold」，但
runtime consumer 內部加了一個「sparse-prone profile 的 trade-count
relaxation factor」，實質上等同於每個 profile 有自己的有效
A2_MIN_TRADES。

**後果**：governance 失靈；audit trail 看不到 threshold change，
但行為已變。

**觸發測試**：

- diff_snapshots `config.zangetsu_settings_sha` 必須 zero-diff。
- runtime consumer 的 source code 不可包含 `A2_MIN_TRADES` 字串
  以外的形式（grep test）。

**Mitigation**：

- 0-9R-IMPL 的 controlled-diff 規則：runtime consumer 變動歸類為
  **EXPLAINED_TRACE_ONLY** 必須伴隨 governance review；任何疑似
  threshold modification 都必須升級為 critical-class order。
- 設計 `test_no_per_profile_min_trades_override` 強制檢查。

## 5. R-04：隱性 sampling 改動

**敘述**：intervention 沒寫「改 sampling weight」，但 PB-MUT 修改了
mutation probability，等同於改了候選分布。

**後果**：generator behavior 變動但 audit trail 看不出。

**觸發測試**：

- alpha_engine 的 mutation/crossover knob 是否 zero-diff。
- 候選 hash distribution 在 treatment vs baseline 是否顯著不同
  （KS test < 0.05 → flag）。

**Mitigation**：

- 0-9R-IMPL 啟動前列出所有 alpha_engine knob 的 expected pre/post
  SHA；任一變動需獨立 generation-policy order。

## 6. R-05：繞過 applied=false

**敘述**：runtime consumer 訂閱 `dry_run_budget_allocation` event，
但忽略 `applied=false` 欄位，直接套用 weight。等同於把 0-9O-B 的
不變式打掉。

**後果**：dry-run 與 production 的界線被破壞；任何下游後果都不可逆。

**觸發測試**：

- runtime consumer 的源碼必須包含
  `if event["applied"] is not False: skip` 這類 guard。
- PR review 必須對 runtime consumer source 做 line-by-line 審查。

**Mitigation**：

- runtime consumer 必須走 0-9R-IMPL（high-risk）order；單獨 PR；
  含完整 isolation tests（與 0-9O-B 同等級）。
- runtime consumer 不可在 same PR 內附帶 allocator scoring 變動，
  scope creep 一律拒絕。

## 7. R-06：dry-run 與 runtime 模糊

**敘述**：runtime consumer 有 dual-mode（dry-run / apply），靠
config flag 切換。flag 預設值若被誤改為 apply，立即實質化。

**後果**：governance 失靈；可能無 PR 紀錄就 apply。

**觸發測試**：

- runtime consumer 必須 hard-code mode；flag-based switch 視為
  違規。
- 切換 mode 必須走 PR；config flag 不可在 production 直接改。

**Mitigation**：

- 0-9R-IMPL 規定：mode 決策必須在 source-code level（compile-time）
  決定；不接受 runtime config flag。
- CANARY 與 production 用獨立 binary path 區分（如 separate systemd
  unit）。

## 8. R-07：對近期 log 過度擬合

**敘述**：allocator 的 EMA window 太短或 sample size 太小（< 20），
導致 weight shift 反映短期雜訊。treatment 結果受 lookback bias 影響，
無法外推。

**後果**：表面上 treatment 改善 sparse rate，實際上是 baseline
window 偏弱的巧合；上 production 後 regression。

**觸發測試**：

- A/B 評估必須有 ≥ 7 天 + ≥ 20 round 的最低樣本。
- treatment 與 baseline 必須 cover 至少 2 個 macro regime（如可用）。

**Mitigation**：

- §05 §3 強制最低觀察視窗；allocator 內部已有
  `MIN_SAMPLE_SIZE_ROUNDS = 20` gate；runtime consumer 必須
  inherit 同 gate。

## 9. R-08：sparse-prone profile dominate

**敘述**：intervention 反其道而行，竟把 budget 增加給 sparse-prone
profile 試圖「給機會」；結果 sparse rate 不降反升。

**後果**：sparse 問題加劇；budget 集中在最差的 profile。

**觸發測試**：

- treatment 啟動後 7 天內 sparse rate 不下降 → flag。
- profile_score 排序：treatment 中收到較高 budget 的 profile 是否
  也是 baseline 中 sparse rate 較低的 profile（方向 sanity）。

**Mitigation**：

- 0-9R-IMPL 必須要求 weight shift 方向 sanity check：weight 增加的
  profile 必須有 baseline `signal_too_sparse_rate` 較低（或至少
  not 較高）。

## 10. R-09：抑制有用的 rare-event alpha

**敘述**：sparse rate 的另一面是「rare-but-good signal」。過度抑制
sparse-prone profile 等同於把 black-swan-like alpha 連根拔除。

**後果**：champion diversity 下降；極端市況下沒有 alpha 可派。

**觸發測試**：

- treatment 的 champion regime diversity 是否下降。
- treatment 期間「高 sharpe + 低 trade」candidate（如 sharpe ≥ 2.5
  AND trades ≈ 30）的數量是否顯著下降。

**Mitigation**：

- PB-FLOOR 永久保留 exploration_floor。
- PB-RESURRECT 給被 quarantine 的 profile 重生機會（cooldown 後
  重啟 floor budget）。
- A/B success criterion 含 champion diversity 不下降。

## 11. R-10：UNKNOWN_REJECT 漂移誤判 sparse

**敘述**：intervention 的副作用使 reject log line 的格式微變，
原 `arena_rejection_taxonomy.RAW_TO_REASON` 失去 match，更多 reject
被歸到 UNKNOWN_REJECT。看似 SIGNAL_TOO_SPARSE 下降，其實只是
reclassification。

**後果**：metrics 失真；不真實的「改善」掩蓋實際問題。

**觸發測試**：

- treatment 啟動後 unknown_reject_rate 變化；上升 ≥ 2 pp 即可疑。
- top_reject_reasons 的組成是否大幅改變。

**Mitigation**：

- §04 G4：unknown_reject_rate ≥ 0.05 → block intervention。
- 0-9R-IMPL 啟動前必須先 audit `RAW_TO_REASON` table 完整性
  （由 P7-PR1 / 0-9H 已建立的 taxonomy 持續維護）。

## 12. R-11：CANARY 與 production 環境差異

**敘述**：CANARY 在 small cohort 上看起來成功，production 上 fail。
原因可能是 CANARY 樣本不足、regime 不全、或 candidate pool 太小。

**後果**：rollout 後規模化的 deployable degradation。

**觸發測試**：

- 0-9S CANARY 必須跨 ≥ 14 天並涵蓋 ≥ 2 regime。
- CANARY 樣本量必須 ≥ baseline 的 30%。

**Mitigation**：

- §05 §10 PR1–PR6 production readiness criteria。
- 0-9T production rollout 不可省略 CANARY 階段。

## 13. R-12：rollback 不可逆

**敘述**：runtime consumer 修改 weight 後，generator 已產生大量
treatment-shape candidate；rollback 後 baseline 看到的 candidate
distribution 與啟動 treatment 前不同（pool poisoning）。

**後果**：rollback 表面成功，但 baseline metrics 已被污染，無法做
clean comparison。

**觸發測試**：

- 啟動 treatment 前必須 snapshot candidate pool hash distribution。
- rollback 後 ≥ 7 天再做 baseline 重新校準。

**Mitigation**：

- 0-9R-IMPL 必須包含 candidate pool 的 pre-treatment snapshot；
  rollback 後重新 calibrate。
- treatment 預設最長 30 天；超過必須 j13 重新確認。

## 14. R-13：multi-strategy 互相污染

**敘述**：j01 + j02 共用 generation pipeline。對 j01 啟動的
intervention 不慎影響 j02 candidate distribution。

**後果**：j02 deployable_count 受連帶影響。

**觸發測試**：

- treatment 期間每個 strategy_id 的 deployable_count 獨立追蹤。
- 任一 strategy 的 deployable_count drop ≥ 1 即 flag。

**Mitigation**：

- 0-9R-IMPL 必須以 `STRATEGY_ID` 為 cohort 隔離單位。
- 不允許「對所有 strategy 一視同仁」的 global intervention。

## 15. R-14：Audit trail 不完整

**敘述**：treatment 的決策、結果、rollback 紀錄分散，無單一可追溯的
audit trail。事後 j13 review 無法重建決策鏈。

**後果**：governance 信任度下降；類似事件再發生時無法 reuse 經驗。

**Mitigation**：

- §06 §10 audit trail rules：所有決策必須沉澱到指定路徑；
  AKASHA witness 必須記錄。

## 16. 紅隊結論

0-9R 設計目前**無**內生致命漏洞，但**所有**未來 0-9R-IMPL
啟動前都必須通過：

1. 上述 14 條 risk mitigation。
2. §04 anti-overfit guardrails 全部 active。
3. §05 A/B success criteria 全部觀察。
4. §06 governance permission matrix 對應分級正確。
5. j13 顯式 order。

任一條件未滿足，0-9R-IMPL 不可啟動。
