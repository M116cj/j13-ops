# 04 — Anti-Overfit Guardrails

## 1. 原則

reduce SIGNAL_TOO_SPARSE 是手段，**不是目標**。目標是
deployable_count / OOS robustness 維持或提升。任何 intervention 若以
削弱 edge quality 為代價降低 sparse rate，都必須 rollback。

## 2. Hard guardrails（不可協商）

| Guardrail | 規則 |
| --- | --- |
| G1 | A2 pass_rate **不可**作為唯一目標；必須與 A3 pass_rate + deployable_count 同時觀察。 |
| G2 | A3 pass_rate `degradation tolerance ≤ 5%` (相對於 baseline 的 absolute pp drop)；超過則 rollback。 |
| G3 | `deployable_count` **不可**下降；理想為提升。任何 intervention 如導致 7-day rolling deployable 中位數下降 ≥ 1，則 rollback。 |
| G4 | `unknown_reject_rate` 必須 < 0.05；上升至 ≥ 0.05 必須先修 taxonomy，不能繼續 sparse intervention。 |
| G5 | `oos_fail_rate` 不得 material 增加（≤ 3% absolute pp 增加是噪音；≥ 5% 視為 material → rollback）。 |
| G6 | `profile_score` 必須使用 ≥ 20 round 的 smoothing window；不可 per-batch 直接驅動 intervention。 |
| G7 | 結果必須依 regime 拆分（bull / bear / range / volatile），如有 regime tag 可用；防止單一 regime 主導改善假象。 |
| G8 | 結果必須依 time-split 拆分（日 / 週）；防止短期巧合。 |
| G9 | `EXPLORATION_FLOOR = 0.05` 必須**永遠**保留；任何 intervention 都不可使任何 profile 跌破 floor。 |
| G10 | 任何 profile **不可**被永久 kill；必須有 cooldown（≥ 14 days）+ re-entry rule（PB-RESURRECT）。 |
| G11 | sparse 改善**不可**來自 threshold 放寬（`A2_MIN_TRADES`、Arena gate condition）。 |
| G12 | sparse 改善**不可**來自 fake `passed_count`（重複計數、virtual passes、stat manipulation）。 |
| G13 | sparse 改善**不可**來自 `deployable_count` semantic 變動（變寬以包含 CANDIDATE 等）。 |

## 3. Pass-rate overfitting

### 3.1 風險

A2 pass_rate 提升而 A3 pass_rate / deployable_count 持平或下降 →
表面 KPI 改善，實際 edge quality 變差。

### 3.2 偵測

- 計算「A2 pass_rate Δ」與「A3 pass_rate Δ」的 30-day rolling
  correlation。負相關 ≤ −0.3 → flag。
- `passed_count_a2 / entered_count_a2 - passed_count_a3 / entered_count_a3`
  spread 擴大 ≥ 10 pp → flag。

### 3.3 Mitigation

- A/B treatment 必須以 `composite_score = 0.4 * a2_pass_rate +
  0.4 * a3_pass_rate + 0.2 * deployable_density`（暫定權重；future
  tuning）為主指標，**不**單看 A2。
- A3 degradation > G2 → 自動 rollback。

## 4. Trade-count inflation

### 4.1 風險

intervention 讓 candidate 在 holdout 上產生大量 trade（>>25），但
平均 sharpe / pnl_per_trade 顯著下降 → over-trading；通過 A2 但
A3 OOS_FAIL 上升、deployable_count 下降。

### 4.2 偵測

- 比較 baseline 與 treatment 的 `mean_trades_per_passed_a2`；
  上升 ≥ 100% 為 flag。
- 比較 `pnl_per_trade` 中位數；treatment - baseline ≤ -20% 為 flag。

### 4.3 Mitigation

- Pre-A2 density screen（PRE-A2-SCREEN）只能在 j13 顯式 order 啟動，
  並必須附帶 over-trading detector。
- PB-SHIFT 不應使任一 profile 的 budget 一次提升 ≥ 50%（max-step
  limit）。

## 5. Weaker signal quality

### 5.1 風險

EXPLORATION_FLOOR 不足以保留 rare-but-good signal；intervention 把
budget 集中在「容易產生 trade」的 profile，rare-event alpha 被
稀釋掉。

### 5.2 Mitigation

- PB-DIV 強制 profile diversity floor（每個 profile ≥ floor）。
- PB-RESURRECT 給被 quarantine 的 profile 重生機會。
- A/B 評估時計算 `champion regime diversity` —
  treatment 的 champion 來源 regime 數不可少於 baseline。

## 6. Regime concentration

### 6.1 風險

intervention 在某一 regime（如 bull）改善 sparse rate，但在其他
regime（bear / range）degradation；總體看似改善，分 regime 看是 net 損失。

### 6.2 Mitigation

- A/B 評估**必須**做 per-regime breakdown。
- 若 regime tag 不可得，至少做 time-split breakdown（30-day windows）。
- 任何 regime 的 deployable_count drop ≥ 1（中位數）→ rollback。

## 7. Sample-size insufficiency

### 7.1 風險

allocator gate `MIN_SAMPLE_SIZE_ROUNDS = 20` 是必要不是充分。在某些
regime 內可能仍不足。

### 7.2 Mitigation

- 0-9R-IMPL 啟動條件：每 profile **per regime** 也需 ≥ 10 round
  observation；如 regime tag 不可用，整體 ≥ 30 round。
- 任何 intervention 對個別 profile 的調整需 ≥ 5 連續 actionable
  allocation（見 §03 §3）。

## 8. Profile collapse

### 8.1 風險

intervention 讓 weight 集中在 1–2 個 profile，其他 profile 因低 budget
無法累積樣本，long-term 失去多樣性。

### 8.2 Mitigation

- PB-DIV 強制 minimum diversity（建議 ≥ floor for ≥ floor_n profiles，
  即至少 N 個 profile 維持 floor）。
- A/B 評估的 success criterion 包含「treatment 結束時 actionable
  profile 數 ≥ baseline」。

## 9. OOS degradation

OOS_FAIL 是 sparse intervention 的主要 false-positive 來源。

### 9.1 偵測

- A3 `oos_fail_rate` treatment - baseline ≥ 5% absolute pp → flag。
- A4 holdout pass rate（CANDIDATE → DEPLOYABLE）下降 ≥ 5% pp → flag。
- A5 ELO 中位 sharpe 下降 ≥ 0.1 → flag（如 A5 已上線）。

### 9.2 Mitigation

- 任一 flag 觸發 → 24-hour rollback window，期間繼續觀察；2 個 flag
  同時觸發 → 立即 rollback。

## 10. Counter-inconsistency drift

### 10.1 風險

intervention 改變 candidate 分布後，原本對應到既有 reject reason 的
log line 不再 match → unknown_reject 上升 → allocator 開始把
intervention 對象標 NON_ACTIONABLE。

### 10.2 Mitigation

- 啟動 intervention 後 7 天內 unknown_reject_rate 連續 < 0.05 才算
  穩定。
- 若 ≥ 0.05 → 暫停 intervention，先修 `arena_rejection_taxonomy`。

## 11. Watchdog responsibilities

未來 runtime consumer + Calcifer 需自動執行：

- 每日計算 G1–G13 metrics → 寫 outcome log。
- 任一 hard guardrail violation → 立即 rollback intervention（runtime
  consumer 切回 baseline weights）+ Telegram alert。
- weekly summary report → docs/governance/reports/。
- A/B treatment 終止條件：success / failure / 30 day timeout。

## 12. 不可使用的「sparse 改善」來源

明確拒絕（再次強調）：

| 來源 | 拒絕理由 |
| --- | --- |
| 降低 `A2_MIN_TRADES` | G11 / §3.10 |
| 弱化 `arena2_pass` / `arena3_pass` | G11 |
| 改 `pos_count >= 2` 條件 | G11 |
| 改 A3 OOS validation gate | G11 / §3.11 |
| 重複計算 trades 達到 `>= 25` | G12 |
| 把 CANDIDATE 視為 DEPLOYABLE | G13 / §3.13 |
| Hide reject events from telemetry | telemetry 完整性違規 |
| Disable A4 holdout validation | execution / risk 違規 |

任何提案如基於上述來源，0-9R 的 red-team 將標 STOP。
