# Decision — Zangetsu indicator_cache 全鏈修復（Patches A–F'）
日期：2026-04-19

## 決定
修 7 個 patch（A/B/C/D/E/F/F'）讓 AlphaEngine 的 126 個 indicator terminals 真正被 invoke：
- Patch A: arena_pipeline.py:578 — GP evolve 傳 cache
- Patch B: signal_reconstructor.py — 自建 cache 若空
- Patch C: arena23_orchestrator.py — A2/A3 singleton 每次 populate cache
- Patch D: arena45_orchestrator.py — A4/A5 同樣 populate
- Patch E: arena_pipeline.py — val-backtest 用 holdout cache 再還原 train
- Patch F (rollback): addPrimitive arity=0 → DEAP 拒絕
- Patch F': subclass Terminal + pset.mapping swap → DEAP compile 輸出 'name()'

## 為什麼
Gemini audit 發現 638 個歷史 V10 champion **0 筆使用 indicator terminals**。GP 在不知道的情況下演化出「只用 5 個 OHLCV」的公式族，holdout 上 WR=14% 系統性做反。

## 拒絕的方案
- 改 Arena gate threshold：違反 j13 硬規則
- Signal inversion auto-detect：治標不治本
- Retire V10 回 V9：抹殺所有 GP 探索能力

## 對抗審查（5 維 Q1）
- Input boundary ✅ cache 為 None 時 AlphaEngine 接受 empty dict
- Silent failure ✅ build_indicator_cache 失敗會 log warning 不靜默
- External dep ✅ 無 Rust indicators fallback 到 zeros，不 crash
- Concurrency ⚠️ singleton cache 在 async worker 共用，clear+update 有 race window（單 worker 所以現實影響 0）
- Scope creep ✅ 不動 A2/A3/A4 gate

## Q1/Q2/Q3
Q1 PASS / Q2 PASS / Q3 PASS（每個 patch 獨立可回滾）

## 結果
Patch F' smoke test 4/6 公式正確跑完 val 回測，暴露真實 OOS 失敗（不再是假 crash）。infrastructure 100% ready，後續 cold-start 需要不同策略。
