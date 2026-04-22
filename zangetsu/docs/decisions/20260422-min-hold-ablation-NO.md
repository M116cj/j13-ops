# ADR 2026-04-22 — min_hold Ablation 3-Arm → NO — `min_hold=60` 不是殘餘阻塞因子

## What was decided
在 Volume best-known candidate `rank_window=250, entry_threshold=0.90, exit_threshold=0.50` 下，`min_hold=60` **維持** 為 production floor。不放寬至 30 或 15。

## Why（3-arm 順序 60 → 30 → 15，single-worker、same commit、same DOE）

| Arm | A1 survivors | Breadth (symbols) | Mean val Sharpe | Mean train Sharpe | Total trades |
|---|---:|---:|---:|---:|---:|
| **C=60 (control)** | **2** | **2** (SOL, LINK) | **+0.21** | −0.45 | 9,264 |
| B=30 | 1 | 1 (DOT) | −0.33 | −0.34 | 12,108 |
| A=15 | 1 | 1 (GALA) | **−0.52** | **−0.82** | 14,003 |

關鍵觀察：
- Survivor 隨 min_hold 降**而減少**（2 → 1 → 1），不增
- 倖存 symbol 完全不重疊 — noise-driven 非 hold-floor-mediated edge
- Mean val Sharpe **單調惡化** +0.21 → −0.33 → −0.52
- Arm B 是經典陷阱：train gate 放寬（−16 train_neg_pnl reject）但 +16 cells 全被 val_neg_pnl 吸收（類比 MR 案例）
- Arm A 連 train gate 都崩（train_neg_pnl 反增 +7）

## What was rejected
- Hypothesis: 「min_hold=60 是 A1/val 主導阻塞」→ **否決**
- 任何 lower-floor deployment — 特別是 30-bar floor 是陷阱，會降 survivor 並惡化 val

## Adversarial
- 單 worker 序列執行、同 commit、同 DOE、同 symbol universe — 唯一變數 ALPHA_MIN_HOLD ✓
- invariance 546/546 match ✓
- A4/A5 可能 hard-code min_hold=60 — 已記錄；本實驗 bottleneck 在 A1，仍有效

## Research / cross-task consistency
- 本結果與 421-3 的「train 寬 val 吸收」殘餘 pattern 一致
- 與 Val-Gate Counterfactual Audit（同日）指向同一瓶頸方向：val-side，不是 exit mechanics

## Q1 / Q2 / Q3
- Q1 五維全過（input boundary / silent propagation / external / concurrency / scope creep）
- Q2 full telemetry (piles + percentiles + exit counters)
- Q3 3 arm × 140 cells，無 grid

## Consequences
- Production 維持 `min_hold=60`
- Policy Layer registry 硬編 `min_hold: 60`（所有家族）
- A1/val 殘餘阻塞方向轉向 **val gate**（val_low_wr 主導，見 valgate audit ADR）
