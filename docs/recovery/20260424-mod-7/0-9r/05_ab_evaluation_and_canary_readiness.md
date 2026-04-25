# 05 — A/B Evaluation and CANARY Readiness

## 1. 範圍

定義未來 0-9R-IMPL 的 sparse-candidate intervention 必須通過的 A/B
比較與 CANARY readiness 條件。本檔只是設計；不啟動 CANARY、不啟動
production rollout。

## 2. Cohort 結構

### 2.1 Baseline cohort

- 採用當前 generation pipeline（截至 0-9O-B 為止的設定）。
- profile budget 維持當前 GP knob（無 PB-SHIFT / PB-SUPPRESS）。
- A2_MIN_TRADES = 25。
- arena2_pass / arena3_pass / arena4_pass 不變。
- `STRATEGY_ID = j01`（j02 平行運作但不混算）。

### 2.2 Treatment cohort

- 採用 0-9R-IMPL 的 generation-profile policy intervention（任一
  PB-SHIFT / PB-SUPPRESS / PB-QUARANTINE 組合，由 j13 顯式選擇）。
- 同 strategy_id，與 baseline 共享資料源、同時段運行。
- 必須與 baseline 用 **同一個 A1/A2/A3 telemetry pipeline**（即
  P7-PR4B 已上線的 batch metrics emission）。

### 2.3 Cohort 切分方式

- 若可用：cohort tag 寫入 passport（如
  `passport.experiment.cohort = "0-9R-IMPL/treatment-v1"`）。
- 否則：以 worker_id 切分（odd → treatment、even → baseline）；
  記錄 mapping 到 docs/governance/reports/。
- **不可**讓 cohort 影響 Arena pass/fail logic — Arena 必須對所有
  cohort 一視同仁。

## 3. 最低觀察視窗

| 指標 | 最低需求 |
| --- | --- |
| Round count per cohort | ≥ 20 |
| 每 profile 在每 cohort 的 round | ≥ 20 (allocator gate) |
| 每 profile 在每 regime（如 tag 可用）的 round | ≥ 10 |
| 連續穩定 `confidence == CONFIDENCE_A1_A2_A3_AVAILABLE` 視窗 | ≥ 20 round |
| Hard min total elapsed time | ≥ 7 calendar days |

樣本不足 → blocked，不可 j13 override（除非另一個獨立 generation
acceleration order）。

## 4. 必要 metrics

每個 cohort 都必須採集（per-batch event）：

```
A1:  entered_count, passed_count, pass_rate
A2:  entered_count, passed_count, pass_rate, signal_too_sparse_rate,
     signal_too_sparse_count, top_reject_reason
A3:  entered_count, passed_count, pass_rate, oos_fail_rate, oos_fail_count
A4:  candidate_count, deployable_promotion_count
A5 (if live): elo_winner_count, elo_match_count
deployable_count (authoritative VIEW): per-day, per-cohort
unknown_reject_count / rate (cross-stage)
profile_score (per profile, smoothed)
dry_run_budget_allocation stability (allocation runs / day)
```

## 5. Composite scoring

設計用 composite score 而非單一 KPI：

```
composite = 0.40 * a2_pass_rate
          + 0.40 * a3_pass_rate
          + 0.20 * deployable_density
where deployable_density = deployable_count_7d / a3_passed_7d
```

權重為設計提案；0-9R-IMPL 啟動前由 j13 確認最終權重。

## 6. Success criteria

未來 intervention **同時**滿足：

| # | 條件 |
| --- | --- |
| S1 | A2 SIGNAL_TOO_SPARSE rate decrease（treatment vs baseline，相對改善 ≥ 20%） |
| S2 | A2 pass_rate improve（absolute pp ↑ ≥ 3 pp 或相對 ≥ 15%） |
| S3 | A3 pass_rate **不**material degrade（≤ −2 pp absolute；理想 ≥ 0） |
| S4 | OOS_FAIL **不**material increase（≤ +3 pp absolute） |
| S5 | deployable_count **不**degrade，理想 improve（rolling 7-day median ≥ baseline） |
| S6 | UNKNOWN_REJECT 維持 < 0.05 |
| S7 | 無 threshold change（A2_MIN_TRADES、ATR/TRAIL/FIXED 等全部 unchanged） |
| S8 | 無 Arena pass/fail 條件 change |
| S9 | 無 champion promotion criteria change |
| S10 | 無 execution / capital / risk change |
| S11 | regime breakdown 上每個 regime 的 deployable_count 不 degrade |
| S12 | composite score ↑（treatment > baseline，至少 1 sigma above noise） |

任一 S1–S12 失敗 → 不算 success；不可在 j13 不確認的情況下 promote。

## 7. Failure criteria

intervention 失敗（必須 rollback）：

| # | 條件 |
| --- | --- |
| F1 | A2 pass_rate improve **但** A3 pass_rate collapse（A3 down ≥ 5 pp absolute） |
| F2 | A2 pass_rate improve 但 deployable_count down（7-day rolling median 下降 ≥ 1） |
| F3 | OOS_FAIL increase ≥ 5 pp absolute |
| F4 | UNKNOWN_REJECT 增加（≥ baseline + 2 pp） |
| F5 | trade-count inflation（mean_trades_per_passed_a2 上升 ≥ 100% 且 pnl_per_trade 下降 ≥ 20%） |
| F6 | profile collapse（actionable profile 數 < baseline 的 50%） |
| F7 | exploration floor 違反（任何 profile < 0.05） |
| F8 | 結果由單一 regime / 單一 time slice 主導（其他 regime 全 degrade） |

任一 F1–F8 觸發 → 立即 rollback runtime consumer 到 baseline weights，
**不可** j13 override 維持 treatment。

## 8. Rollback procedure

0-9R-IMPL 必須隨附 runnable rollback：

1. Runtime consumer 切回 baseline weights（hot-swap，無需 service
   restart）。
2. Telegram alert：「0-9R-IMPL rollback triggered: <flag list>」。
3. Calcifer 寫 incident log → docs/governance/incidents/YYYYMMDD-rollback.md。
4. 24-hour 內 j13 review；review 結束前 treatment 不重啟。
5. AKASHA witness record 更新：treatment ended, reason, snapshot SHA。

Rollback 必須**可逆**：treatment cohort 恢復後，intervention design
可調整再做下一輪 A/B。

## 9. CANARY readiness criteria

0-9S CANARY 啟動的最低條件（在 0-9R-IMPL 通過 dry-run 後）：

| # | 條件 |
| --- | --- |
| CR1 | 0-9R-IMPL 在 dry-run mode 下穩定運行 ≥ 7 days，無 G1–G13 violation |
| CR2 | dry-run allocator 在這 7 days 內每天 ≥ 1 個 actionable allocation |
| CR3 | 每個 actionable profile 通過 §03 multi-window 條件（≥ 5 連續 sign-stable） |
| CR4 | runtime consumer 已通過 isolation tests（與 0-9O-B allocator 相同等級） |
| CR5 | rollback path 已端到端演練（dry-run 切換 baseline ↔ treatment ≥ 3 次成功） |
| CR6 | Calcifer outcome watchdog 已對 sparse-related metrics 加 alert |
| CR7 | branch protection 未弱化；signed PR-only flow 正常 |
| CR8 | controlled-diff 在 dry-run 期間維持 EXPLAINED 或 EXPLAINED_TRACE_ONLY |
| CR9 | j13 顯式授權 0-9S CANARY |

CR1–CR9 全數滿足才能進 0-9S。

## 10. Production readiness（0-9T 預備）

0-9T production rollout 的最低條件：

| # | 條件 |
| --- | --- |
| PR1 | 0-9S CANARY 通過 success criteria S1–S12 |
| PR2 | CANARY 至少 14 天無 rollback 事件 |
| PR3 | deployable_count 7-day median 改善 ≥ baseline |
| PR4 | 無未解 incident |
| PR5 | j13 顯式 production order |
| PR6 | branch protection / signed PR / controlled-diff 全部 intact |

未滿足任一條件不可進 production。

## 11. Off-cycle controls

- A/B treatment 進行中，**不可**並行其他 generation-policy 改動
  （sequential ordering only）。
- A/B treatment 期間 j13 可隨時 STOP；STOP 後 treatment 立刻終止，
  baseline 接手。
- treatment 預期最長 30 天；超過必須由 j13 確認延長或 STOP。
