# ADR 2026-04-22 — Wilson WR 0.52→0.48 Trial → MIXED — borderline

## What was decided
不做 global Wilson WR floor 放寬（維持 0.52）。改為 narrow allow-list β path：用 policy-layer overlay 僅放行 2 個經驗證的 (symbol, formula) pairs（見另一 ADR）。

## Why（telemetry-only re-scoring 既有 140-cell volume_active.jsonl）

| 指標 | 實際 | YES 要求 | 通過 |
|---|---:|---|:---:|
| new survivors | 2 | ≥ 3 | ❌ |
| breadth | 2 (BTC, DOT) | ≥ 3 | ❌ |
| Acceptable rate | 100% | ≥ 70% | ✅ |
| mean val_sharpe | +2.27 | > 0 | ✅ |
| mean val_net_pnl | +0.30 | > 0 | ✅ |
| train-val pnl consistency | 100% | ≥ 80% | ✅ |

4/6 YES 條件過，但 count + breadth 差 1 cell/symbol。

### Boundary pool（0.48 ≤ wilson < 0.52）
實測 = 2 cells（與 17-cell counterfactual 預測 mismatch：17 個預測含整個 wilson < 0.52 分佈，median 0.37；落在 0.48-0.52 bracket 只有 2）。

### 兩個命中 cells（都是 `decay_20(volume)`）
- BTCUSDT：train +0.11/+0.59, val +0.32/+3.18, wilson 0.4913 → Acceptable
- DOTUSDT：train +0.32/+0.91, val +0.29/+1.36, wilson 0.4841 → Acceptable

## What was rejected
- **Option α (維持 0.52)**：把 2 個 Acceptable cells 丟掉不值
- **Option γ (繼續步到 0.44/0.40)**：counterfactual G7 顯示 46% junk，邊際報酬急降
- **Global floor 放寬**：會影響所有家族所有 cell，風險遠大於 2-cell allow-list

## Adversarial
- Wilson 分佈右偏、tail 重集中 0.37；本數據集「2 cell in 0.48-0.52 bracket」可能在其他 family / 其他 period 不同
- 兩命中都是同一 formula (`decay_20(volume)`) 在不同 symbol → 是一條 edge 展現在兩處，非獨立確認
- `val_sharpe` 在 val 段遠強於 train 段（+3.18 vs +0.59 for BTC）— 可能是 holdout-period favorability 而非穩定 edge；需 forward-OOS 驗證才能從 β 升為正式 active

## Research
- 延伸自 Val-Gate Counterfactual Audit：Table C 的 G2 17-cell pool 預測
- 實際發現預測 count 過大：counterfactual 計 wilson<0.52，trial 計 wilson∈[0.48,0.52)
- 教訓：counterfactual 預測應先計 key variable 分佈

## Q1 / Q2 / Q3
- Q1 full 8/8 unit test 在後續 overlay 落地 ADR
- Q2 telemetry-only，determinism 保持
- Q3 零 rerun、無新 threshold、純 post-processing

## Consequences
- Global Wilson floor 仍 **0.52**
- 2 個高品質 cells 以 candidate_exception overlay 放行（見下 ADR）
- 未來 MR / Breakout / momentum 等 family 類似 trial 套 same template
