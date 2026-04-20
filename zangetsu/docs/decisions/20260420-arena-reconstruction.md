# Arena 重構 v0.6.0 — 2026-04-20 決策記錄

## 背景
Zangetsu 30 天 0 DEPLOYABLE。A1 原 fitness = `|IC|` on full
train window → 可通過者中 99.7% 在 A2 val_neg_pnl 被拒，根因是「訓練目標
（1-bar 方向性）」 與「執行目標（60-bar 持倉）」錯配，以及 A3 退化成
A2 複製、A4 DSR 門檻隨機性過高、A5 僅內部 ELO 錦標無真實市場驗證。

j13 2026-04-20 明確要求：
> 我要訓練的冠軍是要確保在真實的狀況之下可以有穩定的
> pnl/勝率/交易次數。

三個量化指標都要，穩定比漂亮重要。

## 決策

### 新 A1 fitness（`engine/components/alpha_engine.py:_evaluate`）
```
split training window in half
ic_early = spearman(alpha[:mid], forward_returns[:mid])
ic_late  = spearman(alpha[mid:], forward_returns[mid:])
if sign(ic_early) != sign(ic_late): fitness = 0
else: fitness = |ic_early| * |ic_late| - abs(|ic_early| - |ic_late|) - 0.001*tree_height
```
`_forward_returns` 維持 60-bar（對齊 `alpha_to_signal.min_hold`）。

### 新五段 Arena（`services/arena_gates.py`，純函數）
| Gate | 資料 | 規則 |
|---|---|---|
| A1 | 訓練窗 | 新 fitness 同向穩定 |
| A2 | Holdout 前 1/3 | trades ≥ 25 AND total PnL > 0 |
| A3 | Holdout 中 1/3，5 段 | ≥ 4/5 段 WR > 0.45 AND ≥ 4/5 段 PnL > 0 |
| A4 | Holdout 末 1/3，regime-tagged | training regime WR > 0.40 AND ≥ 1 other regime WR > 0.40 |
| A5 | 14 天 live paper-trade shadow | 僅 A5 通過者可 auto-active |

### DEPLOYABLE tier 制（DB schema + VIEW）
`champion_pipeline.deployable_tier ∈ {historical, fresh, live_proven}`

- `historical` — legacy 池用新 A2-A4 重評通過。**不自動上 live**，需 j13 批准。
- `fresh` — 新 GP（新 A1 fitness）native 產出，通過既有 pipeline + arena45。
- `live_proven` — A5 14 天 shadow 生還，才可 auto-active。

`zangetsu_status` VIEW 拆三欄（`deployable_historical/fresh/live_proven`），
§17.1 所有 hook / watchdog / 頒布訊息必讀此 VIEW 而非 inline count。

## 什麼被刪除（無墓碑註解）
- `_evaluate` 舊 `|IC| - 0.001*height` fitness。
- `_forward_returns` Patch G 10 行長篇歷史 docstring（保留一句功能說明）。
- `arena45_orchestrator.py`：`deflated_sharpe_ratio` import、`A4_MIN_DSR`、
  `A4_MIN_TRIALS_FOR_DSR` 常數、DSR 計算 block、DSR 失敗 reason、
  passport 的 `dsr/dsr_num_trials` 欄位。

## 什麼**沒**刪除（標註 scope 外）
- `arena23_orchestrator.py` V9 indicator-combo 分支（line 523+, 837+）仍在
  —它處理歷史 V9 passport，貿然刪除會破壞 LEGACY champion 重處理。
  下一個 session 單獨 Q1 審查後清理。
- 既有 `process_arena2/3/4` 的 V10 path 仍用 pos_count / Wilson LB /
  variability，**未全量改呼叫 `arena_gates` 模組**。原因：
  3-way holdout 切分需要重構 `data_cache` 建構（arena23 用 train-only、
  arena45 用 holdout-only），是深度重構，超出本 session 時間。新
  `arena_gates` 模組目前由 `rescan_legacy_with_new_gates.py` 和未來
  A5 shadow service 使用；orchestrators 在後續 vN.M 整合。

## Q1 Adversarial 五維
1. **Input boundary** — `_evaluate` 中 `mid < 100` 直接 return 0；
   `arena2_pass` 處理空 trade list；`arena3_pass` 處理 segment 不足；
   `arena4_pass` 處理 regime 無資料。全部 PASS。
2. **Silent failure propagation** — 所有 gate return `GateResult(passed, reason, metrics)`，
   `reason` 必填、`metrics` 結構化。PASS。
3. **External dependency failure** — rescan 腳本 DB 斷線會由 asyncpg
   raise，不吞錯誤。PASS。
4. **Concurrency & race** — 新 gate 純函數無共享狀態；
   `alpha_engine._evaluate` 在 DEAP worker 局部執行。PASS。
5. **Scope creep** — 本次未改 backtester / indicator_engine / data layer /
   V9 分支 / miniapp 以外的服務。PASS。

## Q2 / Q3
- Q2 Structural — `run_gates_on_holdout` 逐段 early-return；trade 抽取與
  gate 判斷明確分離；PASS。
- Q3 Efficiency — 新 rescan 1564 alphas in < 1s（包含 signal
  reconstruction warning path）；新 fitness 計算是舊 fitness 的 ~2x（兩次 IC
  而非一次），可接受；PASS。

## 驗收狀態
- T9 rescan 全池：0 個 legacy alpha 通過新 A2（99.6% 卡在 A2），
  851 個 signal reconstruction 直接失敗（passport 引用已不存在 primitive）。
  結論：legacy pool 死；今天第一顆 DEPLOYABLE 必須來自 `tier=fresh`。
- T8 workers 已重啟載入新 A1 fitness，bake 時間 2–6h，背景監看。
- §17.1 VIEW 已 deployed，三 tier 全部可見（目前全為 0）。
- miniapp 新增 Zangetsu 卡顯示 tier 分解。

## 延後項目（下一個 session 處理）
- arena23 V9 indicator-combo 分支刪除 + Q1 審查
- orchestrators 全量切換到 `arena_gates` 模組（搭配 data_cache 3-way split）
- A5 live paper-trade shadow service 建置（D+3 起動 2-3 天工）
- Legacy passport 版本修補工具（可選，讓 851 個 AST 引用失敗的 legacy 可重建）

## Consequences
- **正面**：GP 不再獎勵單段暴衝 alpha；門檻與真實執行對齊；
  DEPLOYABLE label 分層，不再對「已部署」一詞過擬合。
- **負面**：歷史 legacy 池無法挽救，tier=historical 短期為 0；
  orchestrators 舊邏輯仍在，需要下個 session 清理。
- **風險**：新 A1 fitness 對兩半 IC 同向要求嚴格，fresh 產出率可能下降。
  若 24h 後 fresh 仍為 0，放寬為 `|ic_early| * |ic_late|` 即可（移除
  sign 一致性門檻），作為備援調整。
