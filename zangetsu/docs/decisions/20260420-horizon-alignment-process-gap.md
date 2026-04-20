# Horizon Alignment Process-Gap Fix v0.7.2 — 2026-04-20

## 診斷

v0.7.1 observation window 啟動 74 分鐘後，Calcifer cron 回報 RED：
fresh pool 0 rows；staging 0 rows；admission validator 從未被觸發。

深入 worker 日誌發現：

| Worker | alphas_evaled | inserted | reject_val_neg | 其他 val reject |
|---|---|---|---|---|
| W0 (j01 harmonic) | 500 | 0 | **460 (92%)** | sharpe=38, wr=2 |
| W2 (j02 ICIR) | 1000 | 0 | **1000 (100%)** | 0 |

不是 staging 拒、不是 admission_validator 拒 — 所有 alpha 都卡在 `arena_pipeline.py`
內部 A1 val gate 的 `reject_val_neg_pnl`（holdout 驗證 PnL 為負），在到達
staging 之前就被擋。

## 根因 — Patch G 的半拉子修復

2026-04-20 早上的 Patch G 把 GP fitness 的 `_forward_returns` 從 1-bar 改 60-bar，
意圖對齊 `alpha_signal.min_hold=60`。**但只改了 fitness**，回測層的 `max_hold` 沒跟著動：

| 階段 | 變數 | 值 | 正確？ |
|---|---|---|---|
| Fitness 評估 | `ALPHA_FORWARD_HORIZON` | 60 | ✓ |
| 訊號持倉下限 | `alpha_signal.min_hold` | 60 | ✓ |
| A1 訓練回測 | 硬編 | **480** | ✗（8× fitness horizon） |
| A1 驗證回測 | 硬編 | **480** | ✗ |
| A2 回測 | `MAX_HOLD_BARS_A2` | 120 | ✗（2× 不一致） |
| A3 回測 | `MAX_HOLD_BARS_A3` | 480 | ✗ |
| A4 回測 | `A4_MAX_HOLD_BARS` | 480 | ✗ |

## 機制

GP 演化出 alpha A，在前 60 bar 有 IC 邊際（fitness 只獎勵這段）。進場 long 後：

1. `min_hold=60`：持倉至少 60 bar
2. 第 61 bar 開始，alpha 值進入 noise 區（fitness 沒獎勵這段）
3. `max_hold=480`：若 alpha 仍 > exit_threshold，位置持續到第 480 bar
4. 第 60-480 bar 的價格是 random walk → 期望回歸 + 交易成本 → 平倉 PnL 必負

**100% val_neg 的數學必然**，與 fitness 公式、GP 演化品質無關。

## 修復（v0.7.2）

把 `MAX_HOLD_BARS` 納入**策略配置**（j01/config/thresholds.py +
j02/config/thresholds.py），初值 `120`（Gemini 建議 2× fitness horizon
作為中庸值，允許少量 alpha 驅動的持倉延伸，但不讓 noise 積累到 8×）。

所有 backtest 呼叫改讀 **per-champion 的 strategy_id 對應值**：

- `arena_pipeline.py`：`_STRATEGY_MAX_HOLD` from `_strategy_thresholds.MAX_HOLD_BARS`
  （worker-level 固定，因為 worker 專屬某 strategy）
- `arena23_orchestrator.py`：`_strategy_max_hold(champion['strategy_id'])`
  lazy cache loader（每 champion 查其 strategy_id 對應值）
- `arena45_orchestrator.py`：同 arena23，`champ['strategy_id']`

## Governance 邊界確認

**不是 fitness 改動**：
- 沒動 `j01/fitness.py` 或 `j02/fitness.py` 的公式
- 沒解除 `.githooks/pre-commit` 的 fitness lock
- 是執行橫線 (backtest horizon) 對齊 fitness horizon 的 process-gap 修復
- 落在 governance rule #4 允許範圍（「任一證據不達標 → 不調 fitness，
  必須先定位 process 缺口並完成修復」）

## Q1 Adversarial 5 維

1. **Input boundary** — `_strategy_max_hold` 對未知 strategy_id 立即
   raise，不 silently fallback。PASS。
2. **Silent failure propagation** — 每個 backtest 呼叫顯式傳 max_hold；
   若 strategy 拆出新 bundle 沒補 MAX_HOLD_BARS 必 AttributeError 早 fail。PASS。
3. **External dependency failure** — import `j{01,02}.config.thresholds`
   失敗 → orchestrator crash，systemd/watchdog 會 respawn + 可見錯誤日誌。PASS。
4. **Concurrency & race** — 每個 worker 獨立 cache dict；
   orchestrator loader cache 是單 process 讀取，strategies 常數永不變。PASS。
5. **Scope creep** — 只動 MAX_HOLD_BARS 的來源（策略 config）+ 所有呼叫
   端的讀取方式。未動 fitness / GP primitives / admission_validator /
   VIEW schema / miniapp / Calcifer watch。PASS。

## 預測

套用 v0.7.2 後 1-2 hr 內：
- `reject_val_neg_pnl` 應從 100%→0% 範圍明顯下降（預估 40-70%，仍會有
  真實 OOS 失效的 alpha）
- `champion_pipeline_staging` 開始有 rows
- `admission_validator` 開始被呼叫
- `engine_telemetry` 開始有 `admitted_count` / `rejected_count` 非零值
- Calcifer 從 RED 轉 YELLOW/GREEN

若 1-2 hr 內 staging 仍然 0：代表 120-bar max_hold 還不夠，real 問題不是
horizon；需要追根因（例如 val cache 仍 bug、fitness 本身不產生真 OOS
穩定 alpha 等）。

## 後續 (v0.7.2 → v0.7.3 觀察)

- 24-72h 觀察窗口繼續
- 雙證據 VIEWs 不改，繼續觀察 outcome + process
- 若 j01 產出顯著多於 j02 → 可接受（設計內，j02 更嚴）
- 若 72h 內兩者皆 0 → **不要調 fitness**，先深度追 reject 分類的其他桶
  （reject_val_sharpe / reject_val_wr / reject_val_few_trades）
