# Decision — §17 CONSTITUTION 8 條硬規範
日期：2026-04-19

## 決定
將 CLAUDE.md 擴 §17 為跨專案憲法 8 條：
1. SINGLE TRUTH（<proj>_status VIEW）
2. MANDATORY WITNESS（AKASHA 獨立簽名）
3. CALCIFER OUTCOME WATCH（DEPLOYABLE flat>6h → deploy block）
4. AUTO-REGRESSION REVERT（12h 不動自動回滾）
5. VERSION BUMP 機器化（bin/bump_version.py only）
6. STALE-SERVICE CHECK（PROC_START > SOURCE_MTIME）
7. DECISION RECORD CI GATE
8. SCRATCH → TESTS INTEGRATION

## 為什麼
Zangetsu 30 天 post-mortem 顯示：
- 宣告「完成」重複 4 次但 DEPLOYABLE=0 持續 30 天
- Silent-reject 每層都有（7 個 patch 今日才抓完）
- decision record 整個月只 1 份、retro 0 份
- 2026-04-18 v0.5.1 Claude 宣告 A4 legit 4h 後被 post-factum 打臉

## 拒絕的方案
- 只加 hook（pre-commit 可 --no-verify 繞過）
- 純文件規則（30 天前已寫 feedback_outcome_metric.md 照樣違反）
- CI-only（GitHub 設定可臨時關）

## 對抗審查
- Disk > 90% / Calcifer down → §17.3 還能 enforce？→ Claude 退路讀快取，需獨立實作
- git revert 失敗（merge conflict）→ §17.4 需 fallback Telegram 通知而不自動循環

## Q1/Q2/Q3
Q1 PASS（5 維逐一分析在 scratch/team-regs-update/）
Q2 PASS（每條條款獨立可 rollout + rollback）
Q3 PASS（§17.1 先上 1h 實作，其他 D2-D7 漸進）

## 結果
文本 100% ready，實作工具（VIEW / bump_version.py / pre-receive hook）D1–D7 排程待 j13 綠燈。
