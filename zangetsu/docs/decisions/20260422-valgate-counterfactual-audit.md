# ADR 2026-04-22 — Volume C6 Val-Gate Counterfactual Truth Audit → MIXED（gate calibration 有效但 upstream 仍主導）

## What was decided
Val gate 校準（`val_low_wr`）**可** unlock 有意義的 borderline pool（17 cells、12 symbols），但 **絕對主瓶頸仍在 upstream signal quality**（72% cells 死於 train_neg_pnl）。雙工作流並存；本案判定 **MIXED**。

## Why — 8-scenario counterfactual（G0…G7，wrapper/telemetry-only）

### Gate attribution（val-blocked = 37）
- **EXCLUSIVE val_low_wr: 17**（獨家擋這 17 個 cell，其他 val gate 都讓通）
- EXCLUSIVE val_neg_pnl: **0**（never exclusive）
- EXCLUSIVE val_low_sharpe: **0**（never exclusive）
- 全部 37 個 val-blocked cell 都 `fail_val_low_wr`（**100%**）
- `val_neg_pnl` 和 `val_low_sharpe` 單獨移除都 = 0 new survivors（完全被 val_low_wr redundant cover）

### Counterfactual G2（單獨移除 val_low_wr）
- +17 new survivors，breadth 2 → 12 symbols
- G2 unlock 池：17/17 borderline（train-val-coherent 正 pnl 正 sharpe，但 wilson ~0.38）
- 符號不集中於 1-2 symbol

### G7（all three 移除）
- +37 new，但 17 為 junk、20 borderline、0 viable

### Upstream 絕對主導
- 101/140 = **72%** 死於 `train_neg_pnl`，val gate 根本沒機會介入

## What was rejected
- 純 "gate calibration is next" (YES) — 忽視 72% upstream 死亡率
- 純 "gates are not the blocker" (NO) — 忽視 val_low_wr 排他擋 17 個 non-junk

## Adversarial
- Wrapper-only / telemetry-only — 零 production gate-logic 改動
- Determinism 保證：同 JSONL 多次 counterfactual 解析 bit-exact 一致
- alpha_hash + formula 雙軌 key 防誤判

## Research
- 衍生出 Wilson 0.48 trial 的具體假設（17 borderline cells 是否真能 deploy？）
- 對照 min_hold_ablation：exit_atr=0 再次確認 A1 ATR stop 已死，差異來自訊號

## Q1 / Q2 / Q3
- Q1 五維全過
- Q2 每個 counterfactual 可重現 + alpha_hash 對應 + symbol 歸屬
- Q3 單 140-cell source JSONL、zero rerun cost

## Consequences
- Wilson WR 0.52 → 0.48 trial（獨立 ADR）
- `val_neg_pnl` 與 `val_low_sharpe` 在 Volume C6 為 redundant gates — 值得考慮未來精簡（**但本案未改**）
- Upstream signal quality workstream（72% train 死亡）需獨立 task
