# ADR 2026-04-22 — Mean-Reversion Generalization Test → NO — NOT CONFIRMED

## What was decided
Candidate `rank_window=250, entry_threshold=0.90, min_hold=60, exit_threshold=0.50` **不泛化** 到 Mean-Reversion family。Mean-Reversion 維持 unvalidated / fallback 狀態。不升級為 active。

## Why（決定性數據，policy-layer-routed 驗證，與 421-3 一致）
- A1 survivors：Control (fallback 500×0.80) = 0 · Candidate (overlay 250×0.90) = 0 → Δ = 0
- Symbol breadth：0 → 0
- Mean val Sharpe：−0.41 → **−0.50**（回歸 −0.09）
- Cells reaching val：38 → 46（+8），但這 8 個多出的全被 val_neg_pnl (+6) + val_low_wr (+2) 吸收
- `exit_atr=0` 兩臂皆然，差異全來自訊號生成非 exit 機制

## What was rejected
- 初稿 MIXED — PARTIALLY CONFIRMED（j13 糾正）。MIXED 需要「對某些重要指標有改善且改善面可以補償 trade-off」；此案 survivor 不增、breadth 不擴、val quality 回歸，沒有補償面。屬於「train 放寬→val 吸收更多死亡」的鏡像改善，不構成 decision-grade win
- Option A（global Wilson floor relaxation）→ 改為 narrow allow-list β path（見另一 ADR）

## Adversarial
- 相同結果在 421-3（未 routed）與 421-5（透過 policy layer）完全 bit-exact 一致 → 驗證 policy layer 路由不失真
- train-gate 寬 8 個 cell 屬於過程而非結果；無 A1_PASSED 新增就沒有 deployable

## Research
- 421-3 原始 MR test → NO
- 421-5 policy-layer rerun → same NO
- min_hold_ablation → min_hold=60 不是 blocker（next ADR）
- Wilson 0.48 trial on Volume → MIXED（另個議題）

## Q1 / Q2 / Q3
- Q1: 5 五維對抗全過（invariance 364/364 match）
- Q2: 路由正確（main fallback + overlay candidate_test）· 所有 proof 層齊
- Q3: 無多餘 arm、單 worker、same session

## Consequences
- `mean_reversion` 在 main registry 保持 `validated: false, route_status: unvalidated`
- Research mode → safe fallback 500×0.80
- Production mode → fail-closed（`sys.exit(3)`）
- 未來若要再挑戰 MR，須提 stronger-than-train-widen 證據
