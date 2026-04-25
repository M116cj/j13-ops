# 01 — Sparse-Candidate Root-Cause Model

## 1. 範圍

把 `SIGNAL_TOO_SPARSE` 視為 **Arena-level，profile-level
bottleneck**，不是 formula-lineage 問題。本檔不打開單一 alpha 的
formula，也不要求 per-alpha lineage。

## 2. Operational definition

**SIGNAL_TOO_SPARSE**：candidate 在 Arena 階段產生的交易訊號太稀疏，
以致無法在 Arena gate 下產生足夠的統計樣本（trades / positions），
導致該 candidate 被以「資料不足」為由 reject。

Canonical taxonomy entry（`zangetsu/services/arena_rejection_taxonomy.py`）：

```
RejectionReason.SIGNAL_TOO_SPARSE
  category = SIGNAL_DENSITY
  severity = BLOCKING
  default_arena_stage = A2
  description = "Signal fires too few trades for statistical significance."
```

## 3. Where it appears

主要 emission 點：

- **A2 (V10 path)**：`arena23_orchestrator.process_arena2` 兩條 reject
  log line：
  - `[V10]: trades=N < 25` → mapped to `SIGNAL_TOO_SPARSE`
  - `[V10]: pos_count=N` → mapped to `SIGNAL_TOO_SPARSE`
- **A2 (V9 path)**：
  - `<2 valid indicators after zero-MAD filter` → `SIGNAL_TOO_SPARSE`
  - `2IND-REJECT` 路徑（`trades < 25`）
- **A1 (validation split)**：`reject_few_trades`、`reject_val_few_trades`
  → 也被 taxonomy 對應到 `SIGNAL_TOO_SPARSE`
- **A3 (V10 path)**：`[V10]: trades=N < 25`、`[V10]: pos_count=N`、
  `<2 valid indicators` 也對應到 `SIGNAL_TOO_SPARSE`

## 4. Why it blocks A2

Arena gate 規則（不可修改 — `arena_gates.arena2_pass`）要求：

- A2 V10 path：`bt.total_trades >= 25` AND
  `pos_count(net_pnl, sharpe, pnl_per_trade) >= 2`
- A2 V9 indicator-combo path：similarly `>= 25` trades + multi-metric
  improvement

當 candidate signal density 太低（generate_alpha_signals 在 holdout
window 上只產生 0~24 trades），就會被剛性的 trade-count 守門。
這個守門 **不是 bug** — 它是 statistical-significance 的下限保護。
任何 sparse-candidate intervention 都不可繞過或弱化它。

## 5. How it affects deployable_count

漏斗鏈：

```
A1 entered → A1 passed → A2 entered → A2 passed → A3 entered → A3 passed
                                                           → champion_pipeline (CANDIDATE)
                                                           → A4 holdout validation
                                                           → status = 'DEPLOYABLE' (authoritative)
```

A2 SIGNAL_TOO_SPARSE 直接削減 A2 passed_count → 削減 A3 entered_count
→ 最終削減 deployable_count。

**重要**：直接降低 A2 SIGNAL_TOO_SPARSE rate 不必然提高
deployable_count。如果 sparse-prone candidate 經 intervention 變得
trade-rich 但 pnl/sharpe 變差，A3 OOS_FAIL rate 會上升，總
deployable_count 反而下降。詳見 §04_anti_overfit_guardrails.md。

## 6. How it is measured in arena_batch_metrics

P7-PR4B 已交付 A1/A2/A3 aggregate
`arena_batch_metrics.reject_reason_distribution[SIGNAL_TOO_SPARSE]`，
每 N=20 champions（per stage、per orchestrator instance）emit 一個
batch event。

關鍵欄位（每個 batch event）：

```
arena_stage             : "A1" / "A2" / "A3"
entered_count           : int
passed_count            : int
rejected_count          : int
reject_reason_distribution["SIGNAL_TOO_SPARSE"] : int
top_reject_reason       : str (often "SIGNAL_TOO_SPARSE")
generation_profile_id   : str
generation_profile_fingerprint : str
deployable_count        : int | None (None for A2/A3 — authoritative source is champion_pipeline VIEW)
```

P7-PR4B 並未把 SIGNAL_TOO_SPARSE 計數寫入 passport、也未引入
per-alpha lineage。所有觀察都是 aggregate。

## 7. How it appears in generation_profile_metrics

`generation_profile_metrics.aggregate_batches_for_profile` 把所有
batch event 依 `generation_profile_id` 聚合，曝露：

```
signal_too_sparse_count : int  (sum over A1/A2/A3 batch events)
signal_too_sparse_rate  : signal_too_sparse_count / total_rejects
total_entered_a2 / total_passed_a2 / total_rejected_a2
total_entered_a3 / total_passed_a3 / total_rejected_a3
avg_a1_pass_rate / avg_a2_pass_rate / avg_a3_pass_rate
```

`profile_score` 中 SIGNAL_TOO_SPARSE 已被 `w5_signal_too_sparse_penalty
= 0.25` 懲罰（read-only diagnostic）。

## 8. How allocator labels it

0-9O-B `feedback_budget_allocator.classify_bottleneck`：

- **Aggregate dominance**：當 `signal_too_sparse_count` 在
  `(sparse + oos + unknown)` 中 share ≥ `BOTTLENECK_DOMINANCE_THRESHOLD
  (= 0.40)`，`observed_bottleneck = SIGNAL_TOO_SPARSE_DOMINANT`。
- **Per-profile**：高 `signal_too_sparse_rate` 經 `profile_score`
  懲罰，導致該 profile 的 `proposed_profile_weights_dry_run` 降低。
  但 allocator **不會**自動 quarantine 該 profile — 那是 0-9R-IMPL 的
  範圍，且必須走 j13 授權。

## 9. What evidence is sufficient before intervention

未來 0-9R-IMPL 可啟動 sparse-candidate intervention 的最低證據：

1. `generation_profile_metrics.confidence == "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"`
   且 `sample_size_rounds >= 20` per profile。
2. `observed_bottleneck == "SIGNAL_TOO_SPARSE_DOMINANT"` 連續 ≥ 3
   個 dry-run allocation 視窗（防止偶發雜訊）。
3. 至少 2 個獨立 generation profile 同時表現 SIGNAL_TOO_SPARSE
   dominance（防止 single-profile 偽訊號）。
4. `profile_score` 三態 confidence 已穩定在 `CONFIDENCE_A1_A2_A3_AVAILABLE`。
5. UNKNOWN_REJECT rate < 0.05（taxonomy 完整、無觀察盲區）。
6. dry-run 推薦的 weight shift 在 ≥ 5 個連續 allocator run
   中保持方向一致（sign stability）。

任何**單一**指標都不足以授權 intervention。

## 10. What evidence is insufficient

以下情形不可作為 intervention 的依據：

- 單一 batch / 單一 round 觀察。
- `confidence != CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE`。
- `sample_size_rounds < 20`。
- A2/A3 metrics 缺漏（`MISSING_A2_A3_METRICS` bottleneck）。
- UNKNOWN_REJECT rate ≥ 0.20（counter-inconsistency veto；有觀察盲區，
  問題可能不是 sparse）。
- 只看 A2 pass_rate，不看 A3 pass_rate / deployable_count / OOS_FAIL。
- 看到 SIGNAL_TOO_SPARSE rate 高但沒看 regime/time-split 拆分（單一
  regime 主導可能是巧合）。
- 來自非 production-equivalent 環境（CANARY 上的觀察須獨立累積）。

## 11. 不可採取的「捷徑」

明確拒絕：

| 捷徑 | 拒絕理由 |
| --- | --- |
| Lower `A2_MIN_TRADES` (從 25 → 10) | 直接弱化 statistical-significance 守門；OOS / deployable degradation 風險高；違反 §3.10 / §17.21 |
| 弱化 Arena pass/fail（取消 `pos_count >= 2`） | 弱化 economic validity gate；違反 §3.12 |
| 把 A2 reject reduction 視為自動成功 | 只看 surface metric；OOS / deployable 是真正裁判 |
| 只 optimize A2 pass_rate | 過擬合 A2 而 sacrifice A3 / deployable |
| 強制讓所有 candidate 都通過某個最低 trade 數 | 迫使 generator 產生 trade-count-padded candidate，本質是 fake passing |
| Fake passed_count（重複計數 / 偽造 entered） | counter-inconsistency 違規；違反 telemetry-only 契約 |
| 改 `deployable_count` semantics（變寬為包含 CANDIDATE） | 違反 §3.13；CANDIDATE → DEPLOYABLE 由 A4/A5 promotion gate 守 |

## 12. 結論

SIGNAL_TOO_SPARSE 是 generation-profile-level 的 systemic bottleneck，
**唯一**安全的修正路徑是 generation profile policy 的調整 —
讓 generator 在 profile 維度上偏向 density-aware 的設定，使 candidate
在 holdout window 上產生足夠的 trade，**同時**保持 sharpe/pnl 質量。
任何走捷徑的方案都會在 A3 / deployable_count 上付出代價。
