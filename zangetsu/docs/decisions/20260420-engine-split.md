# Zangetsu Engine Split v0.7.0 — 2026-04-20

## 背景

v0.6.0 在 session 內做了：Arena 5-gate 重構、DEPLOYABLE tier 制、secret/
遷移、repo history 密碼清洗。但**單一 fitness 函數 hardcoded 在
`alpha_engine.py._evaluate`** — 無法同時探索多個策略假設。Gemini 對抗審查
又發現該 fitness 數學有誤（線性懲罰碾壓乘法獎勵 → zombie alpha 風險）。

三個 research agent（業界、學界、ML 理論）交叉驗證後，共識是：
- 不該只有單一 fitness。
- J01（harmonic K=2）與 J02（ICIR K=5）代表兩種不同的 stability 哲學，
  各有文獻支持與典型產出差異。
- 最佳策略是**兩者都跑、獨立儀表、獨立輸出**。

j13 決策：把 Zangetsu 從「有 fitness 的策略」升級為「中性訓練引擎」，
J01 / J02 作為獨立策略項目共用引擎但各自擁有 fitness / config / VIEW /
docs / 儀表卡。

## 決策

### 架構分層

```
Zangetsu (engine, neutral)
├── engine/components/       data + GP framework + backtester + indicators
├── services/                arena gates + orchestrators + signal reconstruction
├── config/sql/              engine-level VIEWs (zangetsu_engine_status rollup)
└── migrations/postgres/     DB schema evolution

J01 (strategy, harmonic K=2)
├── fitness.py               sign-gated harmonic mean of |IC_early| / |IC_late|
├── config/thresholds.py     per-strategy A2-A5 thresholds
├── config/sql/              j01_status VIEW (§17.1)
└── docs/                    strategy-scoped ADR / retro

J02 (strategy, ICIR K=5)
├── fitness.py               mean(|IC_k|) - lambda*std(|IC_k|), K=5 folds
├── config/thresholds.py
├── config/sql/              j02_status VIEW (§17.1)
└── docs/
```

### 執行期組合
- `zangetsu_ctl.sh start` 啟動 4 個 arena_pipeline workers：
  - w0, w1 → `STRATEGY_ID=j01`
  - w2, w3 → `STRATEGY_ID=j02`
- `arena_pipeline.py` 讀 env，依策略 import 對應 fitness_fn 注入
  `AlphaEngine(fitness_fn=...)`。
- Arena23 / Arena45 orchestrators 保持單實例，跨策略處理
  （champion_pipeline.strategy_id 隨 row 流動）。

### DB schema
`champion_pipeline` 加 `strategy_id text` + CHECK + 索引。舊有 V10
champions 自動繼承 `j01`；V9 LEGACY 繼承 `zangetsu_legacy`。

### 三個單一真相 VIEW
- `zangetsu_engine_status` — 跨策略 rollup（Calcifer health 用）
- `j01_status` — §17.1 合規，J01 專屬
- `j02_status` — §17.1 合規，J02 專屬
- `zangetsu_status` — backward-compat 彙總保留

### Miniapp
3 張卡：Zangetsu Engine（workers/version/errors）、J01、J02
（各自 tier 分解 + last live age + champions_last_1h）。

## Q1 Adversarial（五維）

1. **Input boundary** — `fitness_fn` 對 `mid < MIN_HALF_BARS`（J01）/ `n <
   K*MIN_FOLD_BARS`（J02）直接回 0.0；`STRATEGY_ID` 未知時 arena_pipeline
   開機 raise。PASS。
2. **Silent failure propagation** — J01/J02 都用 magnitude floor + sign
   gate 雙守。DB strategy_id 有 CHECK constraint。VIEW 查無資料回 0 不
   拋錯但不會「偽報」成功。PASS。
3. **External dependency failure** — fitness_fn 純 numpy，無外部呼叫；
   engine import 失敗 fail-fast。PASS。
4. **Concurrency & race** — 每個 worker 只寫自己 `strategy_id` 的 row；
   arena23/45 pick-champion 以 FOR UPDATE SKIP LOCKED 防雙取。PASS。
5. **Scope creep** — 本次只動：alpha_engine 參數化、arena_pipeline 加
   STRATEGY_ID 路由、DB schema 加欄位 + VIEW、ctl.sh 分軌、miniapp 加卡。
   **沒碰**：arena23 V9 分支、indicator_engine、data 層、backtester。PASS。

## Q2 / Q3

- Q2 Structural — 策略 ↔ 引擎唯一介面是 `fitness_fn` callable +
  `strategy_id` 字串，無其他耦合。測試：J01/J02 fitness 獨立 import 可用。
- Q3 Efficiency — fitness_fn 每次 GP eval 呼叫一次，內聯 Spearman 無 scipy
  開銷；K=5 的 J02 是 J01 的 ~2.5× 計算成本，可接受。

## 文獻支持

研究 archive：`zangetsu/docs/research/research-gp-fitness-stability-20260420.md`
核心引用：
- Harmonic mean / F1 analogue：en.wikipedia.org/wiki/F-score；Yu et al.
  NeurIPS 2020 PCGrad。
- ICIR / era-Sharpe：AlphaForge arXiv 2406.18394；Warm-Start GP arXiv
  2412.00896；Numerai Signals scoring docs。
- Deflated Sharpe Ratio（J02 v0.2.0 backlog）：Bailey & López de Prado
  2014 SSRN 2460551。
- K=5 NSGA-II SOTA：Shi et al. 2025 Computational Economics
  10.1007/s10614-025-11289-1。

## Consequences

### 正面
- Zangetsu 可不改一行支援第三、第四策略（只要寫 `fitness.py` + 在
  `ctl.sh` 加 case）。
- Live 6 個月後有 J01 vs J02 真實績效數據 → 下代策略有依據。
- §17.1 紀律：每個策略都有自己的 VIEW，不同策略的「產出」不會彼此混淆。
- Miniapp 每策略一卡，j13 可一眼對比。

### 負面 / 待辦（v0.7.1–v0.8.0 backlog）
- `arena23 V9 indicator-combo` 分支未清（仍處理 `zangetsu_legacy` rows）。
- orchestrators 尚未整合 `arena_gates.py` 模組（仍用 v0.5 內嵌邏輯 + v0.6
  DSR 移除）；要等 arena_gates 完全接管再移除 V9。
- J02 沒有 DSR post-hoc 濾器（下個 session 加入 A5 stage）。
- J02 需要 K=5 holdout 切分（目前仍用 2-split，因為 holdout 切分在
  data_cache 建構層；深度重構屬 engine 的 v0.8.0 工作）。

### 風險
- J02 的 K=5 fitness 比 J01 嚴格很多，產出率可能極低（72h 內第一顆都沒）。
  緩解：若 72h 無產出，LAMBDA_STD 從 1.0 降到 0.5（fallback 已寫入
  j02/config/thresholds.py 的欄位，一行改動）。

## 延後項目

- J02 A5 DSR post-hoc 濾器（`j02` v0.2.0）
- `arena_gates.py` 完全接管 arena23/45（`zangetsu` v0.7.1）
- arena23 V9 分支刪除（依賴上一項）
- 3-way holdout split 深度整合到 orchestrator data_cache（`zangetsu` v0.8.0）
- A5 live paper-trade shadow service（engine 層，v0.8.0）
