# Zangetsu Governance v0.7.1 — 2026-04-20

## 背景

v0.7.0 engine split 把 Zangetsu 拆成中性引擎 + J01/J02 策略項目，但保留
單一 `champion_pipeline` 表混裝 Epoch A（indicator-disabled GP 殘骸）與
Epoch B（fresh GP）資料。j13 檢視後指出：**這是制度斷點，不是 patch 級
bug**。legacy pool 是 biased sample，不得作為 search space 基準；
fresh pool 若未被雙證據證明 recovery，也不得作為正式 baseline。

v0.7.1 把這個診斷翻譯成四層隔離 + 三閘 + 雙證據 + 鎖定五條硬規則，
直接寫入 DB + code + git hook 層。

## 四層隔離

| 層 | 實作 |
|---|---|
| 物理 | `champion_pipeline` → `champion_legacy_archive`（1564 rows，read-only）；新建 `champion_pipeline_fresh` / `champion_pipeline_staging` / `champion_pipeline_rejected` |
| 權限 | Postgres trigger：archive INSERT/UPDATE/DELETE raise；fresh INSERT 必須透過 `admission_validator()` 設置 `zangetsu.admission_active` session var，否則 raise |
| 查詢 | `verify_no_archive_reads.sh` 在 `zangetsu_ctl.sh start` pre-flight 掃描所有 `*.py/.sh/.sql`；任何 bare `FROM/INTO/UPDATE/JOIN champion_pipeline` 皆 abort |
| 決策 | Epoch A 只能透過 `_archive` 後綴 VIEW 讀取，不得進入任何 ranking / promotion / deployment 路徑 |

## 三閘 admission

```
GP → champion_pipeline_staging (admission_state='pending')
     ├─ Gate 1 Structural：alpha_hash 格式 (16 hex char)
     ├─ Gate 2 Provenance：epoch='B_full_space'（11 欄 NOT NULL DB-level）
     └─ Gate 3 Post-write：arena1_score finite（無 NaN/Inf）
     ↓ (all pass)
     champion_pipeline_fresh (只能由 admission_validator 寫入)
```

失敗分類：
- `rejected:gate1_invalid_alpha_hash_format`
- `rejected:gate2_epoch_not_B`
- `rejected:gate3_score_not_finite`
- `pending_validator_error`（validator 本身異常，不寫 fresh，留 staging 供 forensics）

Rejected row 同步複製到 `champion_pipeline_rejected` 表留檔。

## 11 欄 Provenance（DB-enforced NOT NULL）

| 欄位 | 意義 |
|---|---|
| `engine_version` | `zangetsu_v0.7.1` 字面 |
| `git_commit` | `git rev-parse HEAD`；dirty tree 直接 raise `DirtyTreeError` |
| `git_ref_type` | `branch:<name>` 或 `detached`（額外欄位，非 11 之一） |
| `config_hash` | `Settings` dataclass 所有欄位 sha256 16-char |
| `grammar_hash` | sorted(operators) + sorted(indicator_terminals) sha256 16-char |
| `fitness_version` | `{j01|j02}.fitness@sha256:{16hex}` |
| `patches_applied` | `PATCHES_APPLIED` list from `zangetsu/engine/patches.py` |
| `run_id` | uuid4，每個 worker startup 唯一 |
| `worker_id` | `A1_WORKER_ID` env |
| `seed` | `A1_WORKER_SEED` env 或 fallback worker_id |
| `epoch` | `B_full_space`（CHECK constraint） |
| `created_ts` | `NOW()` |

## 雙證據 recovery adjudication

### Outcome evidence（`fresh_pool_outcome_health` VIEW）
- indicator_alpha_ratio_pct
- distinct_indicators
- usage_entropy（miniapp 層計算）
- avg_depth
- avg_nodes
- deployable_count

### Process evidence（`fresh_pool_process_health` VIEW，讀過去 1h `engine_telemetry`）
- compile_exception_count
- evaluate_exception_count
- indicator_terminal_exception_count
- cache_hit_rate
- nan_inf_count
- zero_variance_count
- admitted_rate
- rejected_rate

**任一側不達標 → 不可調 fitness，必須先定位 process 缺口並修復**。

閾值**刻意不寫死** — 由 24-72h 觀察窗後實測分位數決定，寫入
`docs/decisions/20260421-adjudication-thresholds.md`（v0.7.2 交付）。

## 五條硬規則與執行層機制

1. **Epoch A row 永不進 ranking/promotion/deployment** — archive 三觸發器 +
   `verify_no_archive_reads.sh` pre-flight + VIEW 權限分離
2. **未過三閘 alpha 永不進 fresh** — `fresh_insert_guard` trigger + session-var
   機制 + `admission_validator` SECURITY DEFINER 獨佔路徑
3. **Provenance 任一 NULL → DB constraint 擋** — 11 欄 `NOT NULL`
4. **Recovery 未證明前絕不調 fitness** — `.githooks/pre-commit` 偵測
   `j01/fitness.py` / `j02/fitness.py` 改動 → 拒絕 commit 除非同 PR 含
   `docs/decisions/YYYYMMDD-*-(fitness|recovery|epoch-b)-*.md`
5. **Downstream readers 未切 fresh 前不重啟 live pool** — `zangetsu_ctl.sh start`
   首步 call `verify_no_archive_reads.sh`；任何 bare 引用 abort

## Q1 Adversarial 5 維

1. **Input boundary** — validator 對 NULL / 空 staging_id / 已處理 row
   均 early return；alpha_hash 格式檢查；NaN/Inf 檢查。全 PASS。
2. **Silent failure propagation** — validator `EXCEPTION WHEN OTHERS`
   包裹，任何未預期錯誤歸類 `pending_validator_error` 留 staging，
   永不進 fresh。PASS。
3. **External dependency failure** — DB 斷線 / 觸發器 missing 會讓
   arena_pipeline.py INSERT 失敗 + asyncpg raise；worker 重試或退出。PASS。
4. **Concurrency & race** — `FOR UPDATE` 鎖 staging row；`session_variable`
   transaction-local 不會外洩；每 alpha 唯一 staging_id。PASS。
5. **Scope creep** — 本次只動：DB migration、provenance 模組、
   arena_pipeline staging 路徑、orchestrators 改 fresh、snapshot/miniapp
   health cards、deprecation guards。未碰：fitness 函數、GP operators、
   backtester、alpha_engine 的 GP 演化邏輯。PASS。

## Q2 Structural / Q3 Efficiency

- Q2 Structural — Staging→Fresh 是單向單路；failure 分類清楚有 forensics
  表；provenance 11 欄 DB-enforced NOT NULL；no silent propagation。
- Q3 Efficiency — 每筆 alpha 多一次 DB function call（admission_validator），
  < 5ms 額外成本；telemetry flush 5min 一次 batch，無熱路徑開銷。

## 執行順序

1. Freeze（6 workers stop + locks 清理）
2. pg_dump 備份（2.2 MB gz）
3. migration v0.7.1_governance.sql（rename + 3 tables + telemetry + validator
   + triggers + 6 VIEWs）
4. provenance.py + patches.py
5. arena_pipeline.py refactor（staging + validator + telemetry）
6. orchestrators + shared_utils + dashboard/api 切 fresh（sed）
7. Orphan scripts deprecated（rescan, seed_*, alpha_discovery, factor_zoo）
8. verify_no_archive_reads.sh + .githooks/pre-commit
9. ADR + VERSION_LOG（this file）
10. Gemini 自對抗審查
11. Commit + push
12. Restart workers + 驗證第一筆 staging→fresh 流動
13. Calcifer cron 15min poll

## 觀察窗後決策程序（v0.7.2）

**Recovery 達標**（雙證據同時綠 ≥ 24h）：
- 寫 `docs/decisions/20260421-epoch-b-recovery-proven.md`
- 記錄實測閾值到 `config/adjudication_thresholds.json`
- 允許解除 fitness lock（`git hook` 讀取該 ADR 存在）
- 開始評估是否調 fitness

**Recovery 未達標**（任一側異常 ≥ 24h）：
- 寫 `docs/decisions/20260421-gap-diagnosis-{metric}.md`
- 針對該缺口 diagnose + fix（**不**碰 fitness）
- 再等一輪 24-72h
- 直到雙證據全綠

## Consequences

### 正面
- 制度性防 zombie data：legacy 永遠無法污染 live ranking
- 每筆 alpha 帶 11 欄 provenance，任何時候可完整 audit
- Admission staging 防意外，rejected 有 forensics
- 過程證據與結果證據雙重確認 recovery，不再「看 DEPLOYABLE 數字就信」
- Fitness 被鎖，避免誤調

### 負面 / 待辦
- arena23 V9 indicator-combo branch 未刪（處理 legacy passport）— v0.8.0 配合 orchestrator 重構
- 深度 arena_gates 模組接管 orchestrator inline 邏輯 — v0.8.0
- A5 live paper-trade shadow service — v0.9.0
- 閾值實測 + adjudication threshold 鎖入 — v0.7.2

### 風險
- J02 K=5 ICIR fitness 太嚴 72h 內 0 fresh alpha → 自動保持 fitness-locked，
  不會自我放寬；需 j13 審閱 process evidence + 決定 relax 或修 process gap
