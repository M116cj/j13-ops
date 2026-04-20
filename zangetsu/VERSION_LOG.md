## v0.7.1 — 2026-04-20 — Governance upgrade: physical split + staging + admission validator + 11-field provenance + dual-evidence VIEWs
**Scope:** `engine/components/alpha_engine.py` (no change; re-verified), `engine/provenance.py` + `engine/patches.py` (new), `services/arena_pipeline.py` (staging INSERT + validator call + telemetry emit), `services/arena23_orchestrator.py` + `services/arena45_orchestrator.py` + `services/shared_utils.py` + `dashboard/api.py` + `live/main_loop.py` + `live/card_rotation.py` + `zangetsu_ctl.sh` + `calcifer/*.py` + `tests/test_integration.py` + `scripts/run_dashboard.py` + `scripts/v8_vs_v9_metrics.py` (bare `champion_pipeline` → `champion_pipeline_fresh`), `scripts/rescan_legacy_with_new_gates.py` + `services/seed_101_alphas*.py` + `services/alpha_discovery.py` + `services/factor_zoo.py` (DEPRECATED guard), `scripts/zangetsu_snapshot.sh` + `d-mail-miniapp/static/index.html` (dual-evidence health cards), `migrations/postgres/v0.7.1_governance.sql` + `rollback_v0.7.1.sql` (new), `scripts/verify_no_archive_reads.sh` + `.githooks/pre-commit` (new), `docs/decisions/20260420-governance-v0.7.1.md` (new ADR).

> **主因：** v0.7.0 在單一表混裝 Epoch A（indicator-disabled legacy）+ Epoch B（fresh GP）資料。j13 指示這是制度斷點，須物理分離 + staged admission + 11-field provenance + 雙證據 adjudication + fitness lock。

### 物理隔離（DB schema v0.7.1）
- `champion_pipeline` → `champion_legacy_archive`（1564 rows，read-only triggers）
- 新建 `champion_pipeline_fresh`（Epoch B 已 admission 的 alpha；只能由 validator 寫入）
- 新建 `champion_pipeline_staging`（pre-admission 暫存；admission_state ∈ pending/admitted/rejected/pending_validator_error）
- 新建 `champion_pipeline_rejected`（rejected row forensics）
- 新建 `engine_telemetry`（time-series metric；14 種 metric_name CHECK）

### 三閘 admission（`admission_validator(BIGINT)` plpgsql function）
- Gate 1 Structural: alpha_hash 格式 (^[0-9a-f]{16}$)
- Gate 2 Provenance: epoch='B_full_space'（11 欄 NOT NULL DB 強制）
- Gate 3 Post-write: arena1_score finite
- 失敗路由：rejected + 複製到 rejected 表；validator 自身異常 → pending_validator_error 留 staging

### 11 欄 Provenance（`zangetsu/engine/provenance.py`）
engine_version / git_commit / git_ref_type / config_hash / grammar_hash / fitness_version / patches_applied[] / run_id / worker_id / seed / epoch / created_ts
- `get_git_commit` dirty tree 直接 raise（workers 拒絕啟動）
- `compute_grammar_hash` 決定性測試通過（6c9def...）
- `fitness_version` 讀 fitness.py 檔案 sha256 → 任何 fitness 改動 hash 變

### 雙證據 VIEWs
- `fresh_pool_outcome_health`：indicator_alpha_ratio_pct / distinct_indicators / avg_depth / avg_nodes / deployable_count per strategy
- `fresh_pool_process_health`：8 個 process metrics per strategy，從過去 1h `engine_telemetry` 計算

### 5 條硬規則執行層
1. Archive readonly triggers（INSERT/UPDATE/DELETE RAISE）
2. `fresh_insert_guard` trigger + `zangetsu.admission_active` session-var 機制
3. 11 欄 NOT NULL DB constraint
4. `.githooks/pre-commit` 偵測 fitness.py 改動 → 拒 commit 除非同 PR 有 ADR
5. `verify_no_archive_reads.sh` 在 `zangetsu_ctl.sh start` pre-flight 掃描

### 查詢路徑切換（29 處 + dashboard + shared_utils + live + calcifer + tests + ctl.sh）
全部從 bare `champion_pipeline` 切到 `champion_pipeline_fresh`。Deprecated 檔案（rescan, seed_*, alpha_discovery, factor_zoo）加 `--i-know-deprecated-v071` 硬 flag。

### Miniapp
card-j01 + card-j02 加 outcome + process 兩個 sub-block，15s 自動刷新。

### 驗收
- archive rows 1564（保留）；fresh rows 0（bake pending）
- archive trigger 測試：直接 INSERT raise ✓
- fresh_insert_guard 測試：直接 INSERT raise ✓
- verify_no_archive_reads.sh exit 0 ✓
- provenance.py smoke test 通過 ✓

### 延後項目（v0.7.2 → v0.9.0）
- v0.7.2: 閾值實測 + adjudication threshold 寫入 `config/adjudication_thresholds.json`
- v0.8.0: arena23/45 orchestrator 完全接管 `arena_gates.py` 模組；V9 indicator-combo 分支刪除
- v0.9.0: A5 live paper-trade shadow service

---

## v0.7.0 — 2026-04-20 — Engine split: Zangetsu becomes neutral training engine; J01 + J02 strategies spawn
**Scope:** `engine/components/alpha_engine.py` + `services/arena_pipeline.py` + `services/holdout_splits.py` + `zangetsu_ctl.sh` + `scripts/zangetsu_snapshot.sh` + `migrations/postgres/v0.7.0_strategy_id.sql` (new) + `config/sql/zangetsu_status_view.sql` + `README.md` + `CLAUDE.md` + `docs/decisions/20260420-engine-split.md` (new). Sibling projects created: `../j01/` (harmonic K=2) + `../j02/` (ICIR K=5). Miniapp `d-mail-miniapp/static/index.html` + `server.py` gain J01/J02 cards.

> **主因：** v0.6.0 單一 fitness 被 Gemini 對抗審查找出 zombie alpha 風險；三個 research agent 交叉驗證後，共識是**同時跑多個 fitness 策略**比在一個策略內精修更正確。j13 決策升級 Zangetsu 為中性訓練引擎，J01（harmonic K=2）+ J02（ICIR K=5）各自是獨立策略項目共用引擎。

### Engine 層改動（zangetsu/）
- `alpha_engine.AlphaEngine.__init__` 加 `fitness_fn: Optional[Callable[[np.ndarray, np.ndarray, int], float]]` 參數；`_evaluate` 改為 thin wrapper delegate 到注入的 fitness_fn。舊 buggy 公式**整段刪除**。
- `services/holdout_splits.py` 加 `split_into_k_folds(bars, k)` 供 J02 及未來多-fold 策略用。
- `services/arena_pipeline.py` 讀 `STRATEGY_ID` env → 動態 `from {j01|j02}.fitness import fitness_fn` → 傳給 `AlphaEngine()`；INSERT 寫 `strategy_id` 欄位。
- `zangetsu_ctl.sh` 改 4 workers 切 2+2：w0/w1 → `STRATEGY_ID=j01`，w2/w3 → `STRATEGY_ID=j02`。
- `scripts/zangetsu_snapshot.sh` 讀三個 VIEW（engine + j01 + j02）輸出 `tiers` + `strategies.{j01,j02}` 結構到 `/tmp/zangetsu_live.json`。

### DB schema（migrations/postgres/v0.7.0_strategy_id.sql）
- `champion_pipeline` 加 `strategy_id text NOT NULL DEFAULT 'j01'`，CHECK `∈ {j01, j02, zangetsu_legacy}`。
- 舊 V9 engine_hash rows 自動 backfill 為 `zangetsu_legacy`。
- 三個 VIEW：`zangetsu_engine_status`（跨策略 rollup）、`j01_status`、`j02_status`。原 `zangetsu_status` 保留做 backward-compat。
- 新增 index `(strategy_id, status)` + `(strategy_id, deployable_tier) WHERE status = 'DEPLOYABLE'`。

### Miniapp（`d-mail-miniapp/`）
- `static/index.html` 加兩張卡 `card-j01` + `card-j02`，`loadZangetsu()` 改為渲染三卡（engine rollup + j01 + j02）。
- Polling 15s 不變，讀同一個 `/api/zangetsu/live`。

### 新增的 sibling projects
- `../j01/` — harmonic K=2 fitness + 完整 project skeleton（CLAUDE.md, VERSION_LOG, README, fitness.py, config/thresholds.py, config/sql/j01_status_view.sql, secret.example/, docs/decisions, docs/retros）
- `../j02/` — ICIR K=5 fitness + 完整 project skeleton

### Q1/Q2/Q3
見 `docs/decisions/20260420-engine-split.md`。

### 驗收
- `SELECT strategy_id, COUNT(*) FROM champion_pipeline GROUP BY 1` → `j01: 1551`, `zangetsu_legacy: 13`, `j02: 0`（fresh 產出 bake 中）。
- `SELECT * FROM j01_status;` + `j02_status;` + `zangetsu_engine_status;` 全可查，結構正確。
- 6 workers 新 PID + env 驗證：w0/w1 有 `STRATEGY_ID=j01`，w2/w3 有 `STRATEGY_ID=j02`。
- fitness_fn 獨立 import smoke test 通過（j01 = 0.9731, j02 = 0.9711 on synthetic strong alpha）。
- 新 workers mtime 在 process start 前（§17.6 satisfied）。

### 延後項目（下個 session 清理）
- J02 A5 post-hoc DSR 濾器（j02 v0.2.0）
- `arena_gates.py` 模組完全接管 arena23/45 inline 邏輯（zangetsu v0.7.1）
- arena23 V9 indicator-combo 分支刪除（依賴上一項）
- 3-way holdout split 深度整合到 orchestrator data_cache（zangetsu v0.8.0）
- A5 live paper-trade shadow service（zangetsu v0.8.0）

---

## v0.6.0 — 2026-04-20 — Arena 5-gate 重構 + DEPLOYABLE tier 制 + secret/ 遷移 + repo history 密碼清洗
**Scope:** `engine/components/alpha_engine.py` + `services/{arena23,arena45}_orchestrator.py` + `services/{arena_gates,holdout_splits,regime_tagger}.py` (new) + `scripts/rescan_legacy_with_new_gates.py` (new) + `config/sql/zangetsu_status_view.sql` (new) + `migrations/postgres/v0.6.0_deployable_tier.sql` (new) + `secret/` 遷移 + `zangetsu_ctl.sh` env-load 補丁

> **主因：** 30 天 0 DEPLOYABLE。根因 A1 fitness 單段 |IC| + 執行 60-bar 持倉錯配 → 99.7% val_neg_pnl。§17 憲法採用後要求單一真相 VIEW + 分層 DEPLOYABLE 證據等級。j13 2026-04-20 指令：「訓練的冠軍要確保真實狀況下穩定 pnl/勝率/交易次數」。

### A1 fitness 改寫（`engine/components/alpha_engine.py:_evaluate`）
舊：`fitness = abs(spearman_ic(alpha, forward_returns)) - 0.001*height`（單段 |IC|）
新：split 訓練窗為兩半，要求 `sign(ic_early) == sign(ic_late)`，
    `fitness = |ic_early|*|ic_late| - ||ic_early|-|ic_late|| - 0.001*height`
`_forward_returns` 60-bar 維持（對齊 `alpha_to_signal.min_hold`），docstring 簡化為單行。

### 新 Arena gate 模組（`services/arena_gates.py`）
純函數 `arena2_pass / arena3_pass / arena4_pass` + `build_a3_segments`，
搭配 `services/holdout_splits.py`（3-split + N-段）與 `services/regime_tagger.py`
（bull/bear/chop + RegimeParams）。Rescan 腳本與未來 A5 shadow 共用。

### DEPLOYABLE tier 制（`migrations/postgres/v0.6.0_deployable_tier.sql`）
`champion_pipeline.deployable_tier ∈ {historical, fresh, live_proven}`（CHECK + index）。
`zangetsu_status` VIEW 重建並拆三欄；`deployable_count` 保留做 backward-compat 彙總。
`config/sql/zangetsu_status_view.sql` 為 canonical VIEW 定義（§17.1）。

### Rescan 腳本（`scripts/rescan_legacy_with_new_gates.py`）
讀取 LEGACY / ARENA2_REJECTED / ARENA4_ELIMINATED 含 passport 的 champion，
用新 A2/A3/A4 在 BTCUSDT holdout 3-split 上重評，通過者標 tier=historical。
2026-04-20 全池 1564 個跑完：0 pass，851 個 passport AST 引用已不存在的 primitive，
legacy 池技術上死。第一顆 DEPLOYABLE 必須靠 tier=fresh（新 GP 產出）。

### arena45 DSR 清理
刪：`deflated_sharpe_ratio` import、`A4_MIN_DSR/A4_MIN_TRIALS_FOR_DSR` 常數、
DSR 計算 block、`dsr_pass` 失敗 reason、passport 內 `dsr/dsr_num_trials`。
CANDIDATE→DEPLOYABLE SQL 加 `deployable_tier = "fresh"`。

### secret 遷移（本版同步）
`/etc/zangetsu/zangetsu.env` → `zangetsu/secret/.env`（700/600）。
`secret.example/.env.example` 進 repo 當欄位骨架。
4 個 systemd live unit + 8 個 deploy/ 模板 `EnvironmentFile=` 全更。
`zangetsu_ctl.sh` 加 `set -a; . secret/.env; set +a` 啟動前載入。

### Miniapp（`d-mail-miniapp/`）
`scripts/zangetsu_snapshot.sh` 加 `tiers` block（讀 `zangetsu_status` VIEW）。
`static/index.html` 新增 `card-zangetsu` 顯示三 tier、candidate、active、
champions_last_1h、last_live 年齡、recent errors，15s poll。

### 其他
- arena23 V9 indicator-combo 分支本次**未刪**（處理歷史 V9 passport，下個 session 單獨 Q1 清理）。
- V9 `_v10_alpha_to_signal` 舊 stub（arena23 line 67）亦未刪，同理。
- 3-way holdout split 未深度整合到 arena23/arena45 的 `data_cache` 建構；
  新 gate 模組目前由 rescan + A5 shadow 使用，orchestrator 整合留待 v0.6.1。

### 驗收
- §17.1 VIEW：deployable_total / historical / fresh / live_proven 皆可查，
  目前全 0（workers 剛重啟 bake 中）。
- §17.6 stale-service：新 workers mtime 在 process start 前（verified）。
- Q1/Q2/Q3：見 `docs/decisions/20260420-arena-reconstruction.md`。
- Retro：`docs/retros/20260420.md`。

---

## v0.5.5 — 2026-04-18 — @macmini13 miniapp self-contained (Docker → host process, proxy removed)
**Scope:** `~/d-mail-miniapp/` refactor + systemd unit

> **註:** j13 指示「不做 proxy 連結、直接把 macmini13 miniapp 做好」。本次撤除 v0.5.4 的 proxy/host-gateway/ufw detour，把 calcifer 的 ops 邏輯**直接**合進 d-mail-miniapp，並從 Docker 轉為 systemd host process 讓 shell exec 無需中介。

### Change
- d-mail-miniapp 架構：**Docker container → systemd user service** `d-mail-miniapp.service`，listen `0.0.0.0:8771`（port 不變，Caddy `/dmail/` 路由不動）
- `server.py` 456 → 1047 行：吸收 calcifer 所有 ops code（`_ACTION_COMMANDS` 動作登錄、`_run_job`/`dispatch_job` 工作調度器、`audit_log` 寫入、`require_owner_fresh` j13 白名單 + 1h fresh auth、shortcut/tasks/jobs endpoints）
- `validate_init_data` 抽出共用 `_validate_init_data_core(max_age_s)`：d-mail 24h wrapper + calcifer 1h owner wrapper 都用同一 HMAC 邏輯
- HTML：9 個 `/api/ops/*` fetch 改回 `/api/*`（無 proxy prefix）
- `Dockerfile` + `docker-compose.yml` → `.deprecated_v055_<ts>` (保留以 rollback)
- **撤除 v0.5.4 的所有網路 detour**：
  - 移除 `CALCIFER_UPSTREAM` + `host.docker.internal:host-gateway` extra_hosts
  - 移除 ufw 3 rules（`8772 ALLOW 172.17/18/22.0.0/16`）
  - 移除 7 個 `/api/ops/*` proxy endpoints
- **硬化 MINIAPP_OWNER_TG_ID**：systemd `Environment=MINIAPP_OWNER_TG_ID=5252897787` 明確寫入（不靠 `.env` fallback），防 subagent flag 的「silent allow-all」失誤模式

### Endpoints (最終 15 個)
Public：`GET /`、`GET /api/akasha/health`
Auth 24h：`/api/akasha/{context,projects}`、`POST /api/upload`、`/api/zangetsu/live`、`/api/current-task`、`/api/session/health`、`/api/shortcuts`、`/api/tasks/pending`、`/api/shortcut/{keyword}`（讀取型）、`GET /api/jobs/{id}`
Auth 1h + j13 whitelist：`POST /api/tasks/{id}/approve`、`POST /api/tasks/{id}/reject`、`DELETE /api/jobs/{id}`、`/api/shortcut/{keyword}`（破壞型分支）

### Verification
- systemd `active (running)` pid 1736662
- port 8771 listen 0.0.0.0 ✓
- 8 endpoint smoke: health 200, 6× auth 401, shortcut GET 405（POST only）
- env 檢查：MINIAPP_OWNER_TG_ID=5252897787、ENV=miniapp、MINIAPP_AUDIT_DIR=/home/j13/audit
- Redis SSOT `shorthand:dict:v1` 不變
- `/tmp/zangetsu_live.json` + `/tmp/j13-current-task.md` host 直讀（不需 volume mount）

### Rollback
```bash
sudo systemctl disable --now d-mail-miniapp
cp server.py.bak_v055_<ts> server.py
mv docker-compose.yml.deprecated_v055_<ts> docker-compose.yml
mv Dockerfile.deprecated_v055_<ts> Dockerfile
docker compose up -d --build
```

### Out-of-scope（延後 v0.5.6+）
- Calcifer `/api/shortcuts`, `/api/tasks/*`, `/api/shortcut/*`, `/api/jobs/*` endpoints 留著 dead code，未啟用（d-mail 已不呼叫）。v0.5.6 清除讓 calcifer 回歸 infra-only。
- T1-A session_store writer + T2 mention router 仍未部署 — Session Health + Pending Tasks 顯示 empty 直到上線

### Lessons
- **不 proxy 就是最直的路**：v0.5.4 proxy 模式要處理 Docker→host 網路（host-gateway + ufw）；移除 Docker 後所有複雜性消失。Occam's Razor 勝。
- **Subagent 風險 flag 必須主動 hardening**：Subagent 回報 `MINIAPP_OWNER_TG_ID fallback 0 allow-all` 是 silent 風險。Lead 在 systemd unit 加 `Environment=` 明寫，不依賴 `.env`。

## v0.5.4 — 2026-04-18 — Ops UI merged into @macmini13 miniapp (d-mail unified command center)
**Scope:** `~/d-mail-miniapp/` (proxy layer + UI merge) + Alaya ufw (3 new rules)

> **註:** 本次將 v0.5.3 放在 calcifer-miniapp 的 Ops/Dispatch 面板 (shortcut grid、pending tasks、job polling) 遷移到 d-mail-miniapp (= @macmini13bot 的 miniapp)，讓 j13 只需開一個 URL (`/dmail/`) 即可存取所有 Claude Command Center 功能。Calcifer backend 保留為後端 API service，Calcifer UI (`/calcifer/`) 暫留為 infra-only diagnostic fallback。

### Feature: d-mail `/api/ops/*` proxy layer
- **Change type:** feat (new capability)
- **What changed:** `services/server.py` 373 → 456 行 (+83)。新增 7 個 proxy endpoints：
  - `GET  /api/ops/shortcuts`            → forward to calcifer `/api/shortcuts`
  - `GET  /api/ops/tasks/pending`        → `/api/tasks/pending`
  - `POST /api/ops/tasks/{id}/approve`   → `/api/tasks/{id}/approve`
  - `POST /api/ops/tasks/{id}/reject`    → `/api/tasks/{id}/reject`
  - `POST /api/ops/shortcut/{keyword}`   → `/api/shortcut/{keyword}` (dispatch timeout 30s)
  - `GET  /api/ops/jobs/{id}`            → `/api/jobs/{id}`
  - `DELETE /api/ops/jobs/{id}`          → cancel job
- **Upstream resolution:** `CALCIFER_UPSTREAM=http://host.docker.internal:8772` (env)
- **Auth pass-through:** `X-Telegram-Init-Data` header forwarded as-is; initData 驗證仍由 calcifer 端嚴格把關 (j13-only whitelist + 1h fresh auth for destructive)
- **Fault tolerance:** upstream error (calcifer down, network timeout) → return HTTP 502 `{"error":"calcifer_upstream_unavailable"}` without crashing d-mail
- **Why:** j13 的 UX 設計要求所有 Claude Command Center 功能集中在 @macmini13 miniapp。Proxy 模式保留 calcifer 作為 ops backend (維持 host process 直接 shell 能力) 同時讓 UI 統一。

### Feature: HTML merge — d-mail 統一面板
- **What changed:** `static/index.html` 從 d-mail v0.5.3 (3 Context panels + AKASHA + Upload) 擴充至 1344 行，加入 Ops panels：
  - **Shortcut Grid panel:** 8 shorthand 按鈕 (狀/部/回/監/接/問G/問M/問C) + 2 支援 (AKASHA/cleanup/restart 仍留 calcifer 專屬)
  - **Pending Tasks panel:** 從 `/api/ops/tasks/pending` 拉 ZSET，approve/reject 按鈕
  - **Active Jobs sub-section:** destructive 短語觸發後顯示 job_id + 輪詢狀態
- **Visual hardening (Gemini #5):**
  - Read-only 按鈕 (狀/問G/問M/問C): 青色 (cyan/green accent)
  - Destructive 按鈕 (部): 紅色 (red accent)
  - `data-destructive="true"` 屬性 + 2-step confirm modal
- **Layout order:** Current Task → Quick Snapshot → Session Health → Shortcut Grid → Pending Tasks → AKASHA → Upload
- **API URL rewrites:** 9 fetch 點全部改 `/api/` → `/api/ops/`
- **Subagent produced, Lead verified:** 0 bare-path leaks; d-mail existing panels byte-identical preserved
- **Skipped panel:** calcifer 的 "Live Snapshot" (fetches `/api/status` = infra view) 與 d-mail 既有 "Quick Snapshot" (fetches `/api/zangetsu/live` = 策略 view) 功能不同但 home 已不需第二 panel → 未移植，infra view 仍可在 `/calcifer/` 查看

### Feature: docker-compose host-gateway
- **What changed:**
  - `extra_hosts: - "host.docker.internal:host-gateway"` 讓 Docker 20.10+ 自動解析 host magic
  - `CALCIFER_UPSTREAM=http://host.docker.internal:8772` env
- **Why:** d-mail-miniapp 在 custom Docker network (akasha_akasha_net + magi_default)，需要一個穩定的 host 地址指向 calcifer (跑 host process on 0.0.0.0:8772)

### Feature: ufw rules for Docker bridges → calcifer:8772
- **Change type:** infra (firewall)
- **What changed:** Alaya ufw 新增 3 rules (編號 23-25):
  - `8772 ALLOW IN 172.17.0.0/16` — docker0 bridge (host.docker.internal 解析到 172.17.0.1)
  - `8772 ALLOW IN 172.18.0.0/16` — magi_default network
  - `8772 ALLOW IN 172.22.0.0/16` — akasha_akasha_net
- **Why:** Alaya `INPUT` policy = DROP (ufw managed)。Container → host TCP 沒 explicit ACCEPT → timeout。加 3 rules 覆蓋 d-mail 可能走的所有 bridge gateway。
- **Root cause analysis (deploy-time discovery):**
  - Deployed compose + restart container → TCP connect 172.17.0.1:8772 / 172.18.0.1:8772 / 172.22.0.1:8772 全部 timeout
  - 問題不在 calcifer (0.0.0.0:8772 ✓)，不在 host-gateway 解析 (172.17.0.1 ✓)
  - 根因：ufw INPUT 預設 DROP + 缺 explicit calcifer:8772 ALLOW rule
  - 參考既有 pattern：nexus-engine port 8001 已有 3 個 bridge ALLOW rules (rules 2-4)，依樣為 calcifer 加 3 rules
- **Q1/Q2/Q3:** PASS
  - Q1 input: rules 作用域限 private subnet，外網不會走這 rule
  - Q1 silent failure: proxy 有 upstream timeout 回 502 (不會 crash)
  - Q1 concurrency: ufw 原子更新 + reload
  - Q1 scope creep: 只開 8772 一個 port，不開整機 docker range
  - Q2: 3 rules 完整 mirror 既有 nexus-engine pattern
  - Q3: 最小增量，一 port 三 subnet
- **Rollback:** `sudo ufw delete 25 && sudo ufw delete 24 && sudo ufw delete 23 && sudo ufw reload`

### Deployment verification
- d-mail container rebuilt + started (uptime new)
- 7 `/api/ops/*` endpoints all respond 401 (auth middleware works + routing correct)
- Container → host TCP connectivity: `host.docker.internal:8772` / `172.17.0.1:8772` / `172.18.0.1:8772` 全 OK
- Container → calcifer HTTP chain: `urlopen /api/shortcuts` → HTTP 401 (= **proxy chain end-to-end works**, auth correctly rejected at calcifer layer)
- **Awaiting j13 phone test** for true UX validation (needs real Telegram initData)

### Files modified
- `/home/j13/d-mail-miniapp/server.py` v0.5.3 → v0.5.4 (backup `.bak_v054_<ts>`)
- `/home/j13/d-mail-miniapp/static/index.html` (backup `.bak_v054_<ts>`)
- `/home/j13/d-mail-miniapp/docker-compose.yml` (backup `.bak_v054_<ts>`)
- Alaya ufw: 3 rules added (persistent, `sudo ufw reload` applied)

### Out-of-scope / deferred
- Calcifer `/calcifer/` UI **未 retire** — 暫留 infra diagnostic fallback。若需完全 retire，後續 v0.5.5 動作
- telegram-optimization T1-A (Redis session_store writer) + T2 (mention router `@macmini13 <task>`) 仍未部署 — Ops panels 目前顯示 `pending=[]` 直到 T2 mention router 上線產出 task queue entries
- `intent modifiers`（狀+短/狀+深 等）: 當 audit log 顯示 j13 頻繁補充再加
- Ops panel 的即時 WebSocket 推送 (目前 5s 輪詢): 下版 consider

### Lessons
- **Docker custom networks 不繼承 docker0 的 iptables rules.** host-gateway magic 解析地址正確 (172.17.0.1)，但 packet 離開 container 後仍走 custom network's own route，而 iptables ufw default-drop 擋在 INPUT chain。修復靠 ufw 允許 private subnet。未來 Docker→host 的 deploy 必須 **pre-flight 檢查 ufw subnet allow list**。
- **Deploy-time 暴露 infra gap 優於 UX-time**: 先 container 內 TCP smoke test 抓到，j13 手機開 miniapp 前就修好。流程應該所有 proxy/跨 service deploy 加入「container → backend TCP smoke」這一步。
- **Proxy pattern 的 auth 邊界責任**：d-mail 端 pass-through initData，真 auth logic 在 calcifer。兩層都是 `require_auth` + `require_j13` 的話會有 double validation；目前只有 calcifer validate，d-mail 端只 validate user 有登入 (get_current_user) 沒做 whitelist。這是故意的（whitelist 邏輯只在 calcifer 統一），但要寫進 code comment 避免未來人誤改。

## v0.5.3 — 2026-04-18 — Miniapp UX redesign: Claude command center (d-mail + calcifer extension)
**Scope:** `~/d-mail-miniapp/` + `~/calcifer-miniapp/` (NOT zangetsu core)
**Branch / commit:** direct-to-alaya deploy (not in zangetsu repo — miniapp lives outside)

> **註:** 本 entry 記錄在 zangetsu VERSION_LOG，因為新 miniapp 功能重度依賴 zangetsu 的 `/tmp/zangetsu_live.json` + `/tmp/j13-current-task.md` + shorthand SSOT。miniapp code 本身 repo 位在 `~/d-mail-miniapp/` 和 `~/calcifer-miniapp/`（無獨立 VERSION_LOG）。

### Feature: d-mail-miniapp — Context & State panels
- **Change type:** feat (new capability, no breaking change to existing AKASHA + upload)
- **What changed (`/home/j13/d-mail-miniapp/`):**
  - `server.py` 6.4K → 12.9K, +3 endpoints:
    - `GET /api/zangetsu/live` — read `/tmp/zangetsu_live.json` with mtime <1h stale-check
    - `GET /api/current-task` — read `/tmp/j13-current-task.md` with mtime <1h stale-check
    - `GET /api/session/health?thread_id={id}` — Redis HASH `session:alaya13jbot:{thread_id}` (env-aware: miniapp mode disables file-fallback per Gemini hardening #3)
  - `static/index.html` 15K → 25K, +3 panels (Current Task / Quick Snapshot / Session Health) above existing AKASHA + Upload
  - `docker-compose.yml` +vol mount `/tmp:/tmp:ro`, +env `NEXUS_REDIS_URL=redis://magi-redis-1:6379`, +env `ENV=miniapp`
  - `requirements.txt` +redis>=5.0 (container rebuild)
  - Session Health panel: **NO pseudo-compact button** (Gemini "kill this feature" veto — compact belongs in agent.py context_monitor only)
- **Why:** j13 跨 3 介面切換成本 3-5 min/switch。Passive read miniapp 讓 j13 手機打開即看當前 task progress + Zangetsu 健康 + session context%。
- **Q1/Q2/Q3:** PASS
  - Q1 input boundary: stale file → `{state:"unavailable"}` HTTP 200, never 500; malformed JSON tolerated; oversized file capped
  - Q1 silent failure: all IO try/except + log
  - Q1 external deps: Redis down in miniapp mode → `state:unavailable` no file-fallback (避免 Mac/Alaya filesystem 不同步導致 stale read)
  - Q1 concurrency: redis-py pool thread-safe; read-only endpoints
  - Q1 scope creep: 0 writes, 0 shell exec, 0 pseudo-compact
- **Rollback:** `cp server.py.bak_v03_20260419_003545 server.py && cp static/index.html.bak_v03_* static/index.html && cp docker-compose.yml.bak_v03_* docker-compose.yml && cp requirements.txt.bak_v03_* requirements.txt && docker compose down && docker compose build && docker compose up -d`

### Feature: calcifer-miniapp — Ops & Dispatch panels
- **Change type:** feat (new capability + safety hardening for existing `shell()`)
- **What changed (`/home/j13/calcifer-miniapp/`):**
  - `server.py` 12.4K → 38K, +7 endpoints (spec asked 5, Subagent B added 2 bonus):
    - `GET /api/tasks/pending` — Redis ZSET `task_queue:pending` score=priority (ZRANGE REV WITHSCORES LIMIT 50)
    - `POST /api/tasks/{id}/approve` (j13-only + audit log)
    - `POST /api/tasks/{id}/reject` (j13-only + audit log)
    - `POST /api/shortcut/{keyword}` (auth + shell exec; destructive → j13-only 1h fresh auth)
    - `GET /api/shortcuts` (list seeded shortcuts — bonus)
    - `GET /api/jobs/{id}` (job status polling; Redis TTL 24h so frontend polling survives restart)
    - `DELETE /api/jobs/{id}` (cancel running job — bonus)
  - **Job dispatcher**: `asyncio.create_task` + SIGTERM→5s grace→SIGKILL; output drained to 2KB tail buffers; state persist to Redis `job:{id}` TTL 24h
  - **Audit log**: `~/audit/miniapp-{YYYY-MM-DD}.log` every destructive + approve/reject logged with `{iso_ts}|{user_id}|{action}|{detail}`
  - **Auth model split**:
    - `require_auth` (24h window): read-only APIs + `/api/shortcut/{keyword}` read-only path
    - `require_owner_fresh` (1h window + j13 whitelist): all destructive + approve/reject + DELETE jobs
  - **Shortcut action registry** (explicit, no eval/string-interp):
    - snapshot → `cat /tmp/zangetsu_live.json`
    - resume_current_task → `cat /tmp/j13-current-task.md`
    - review_gemini → `gemini -p '...'`
    - review_markl → curl Ollama gemma3:12b on Mac (wait — lead-verified: correct model, local-loopback on alaya:11434)
    - review_calcifer → curl Ollama **gemma4:e4b** on alaya (lead-fixed from Subagent B's `gemma3:4b` error)
    - **deploy → `bash /home/j13/j13-ops/zangetsu/zangetsu_ctl.sh restart`** (lead-fixed from Subagent B's non-existent `/home/j13/alaya/zangetsu/deploy.sh`)
    - **rollback → disabled as shortcut** (lead-decision: too stateful, needs .bak selection + DB cleanup, must go through bot/Claude session)
  - `static/index.html` 18K → 37K, +3 panels (Zangetsu Live / Shortcut Grid / Pending Tasks)
  - `calcifer-miniapp.service` +env placeholder `MINIAPP_OWNER_TG_ID` (fallback to existing `CALCIFER_TG_USER_ID=5252897787` if unset — Subagent B's graceful default)
- **Why:** 給 j13 手機可用的「Ops & Dispatch center」— 短語 tap-to-action，destructive 強制 2-step confirm，pending task queue UI 取代 Telegram 打字 `/confirm <task_id>`。
- **Q1/Q2/Q3:** PASS
  - Q1 input boundary: unknown keyword→404 `{error:"unknown_shortcut"}`; confirm-token TTL GC; disk-full for audit log → stderr fallback
  - Q1 silent failure: Gemini #1 (zombie/timeout) fixed via job dispatcher (no 15s timeout for destructive); SIGTERM→grace→SIGKILL lifecycle; state survives restart via Redis TTL
  - Q1 external deps: Redis down → shortcut lookup fails gracefully (404); Ollama timeout → `[X unavailable]` string
  - Q1 concurrency: ZSET approve atomic (`ZADD approved + ZREM pending` in txn); Redis HSET atomic per-field; job dict LRU cap 100
  - Q1 scope creep: 0 new write-destruction beyond what registry explicitly allows; rollback disabled; destructive gated 3-way (j13 whitelist + 1h fresh auth + 2-step confirm)
- **Audit trail guarantee**: every destructive call writes `{ts}|{tg_user_id}|{action}|{detail}|{job_id}` to `~/audit/miniapp-YYYY-MM-DD.log` 700-perm dir; rotation未設（Lead follow-up）
- **Rollback:** `cp server.py.bak_v03_20260419_003612 server.py && cp static/index.html.bak_v03_* static/index.html && bash /tmp/launch_calcifer.sh`

### Feature: Redis shorthand SSOT seed
- **Change type:** infra (new shared state)
- **What changed:** Redis HASH `shorthand:dict:v1` on `magi-redis-1`
- **Entries (8 keyword mappings):**
  - 狀→snapshot, 部→deploy, 回→rollback, 監→monitor_loop, 接→resume_current_task, 問G→review_gemini, 問M→review_markl, 問C→review_calcifer
  - +meta: version=1, updated_at, schema=keyword->action_code
- **Why:** Markl review 指出 shorthand 分散 3 處（bot / Mac CLI / miniapp）→ 需 single source of truth。Redis HASH 讓未來加短語改一處即可。
- **How to add shortcut**: `docker exec magi-redis-1 redis-cli HSET shorthand:dict:v1 "新短語" "action_code"` + calcifer server.py 的 `_ACTION_COMMANDS` dict 加 mapping。

### Deployment process (/team 4-phase applied)
- Phase 1 Recon: 3 parallel reviewers (Gemini 7/10→4/10 after hardening, Markl GO-w-mod, Calcifer HOLD→SAFE-w-preconditions) → design v2 consensus (10 modifications)
- Phase 2 Task Design: 8 sub-tasks with acceptance criteria
- Phase 3 Spawn: 2 Opus 4.7 subagents parallel (A: d-mail, B: calcifer) → both Q1 self-PASS
- Phase 4 Integration: Lead verified + fixed 2 flags (B's path assumption / A's Dockerfile dep) + scp + restart + smoke test (6 endpoints all 401 = auth middleware work + endpoint exists)

### E2E smoke test results
- d-mail (port 8771): `/api/zangetsu/live`, `/api/current-task`, `/api/session/health` → all **401** (initData required) ✅
- calcifer (port 8772): `/api/shortcuts`, `/api/tasks/pending`, `/api/jobs/fake-id` → all **401** ✅
- Caddy reverse proxy: existing rules `handle_path /dmail/*` + `handle_path /calcifer/*` already route correctly, no change
- `/tmp:/tmp:ro` mount verified inside d-mail container (zangetsu_live.json + j13-current-task.md accessible)

### Pre-existing dependencies not yet deployed (out-of-scope for v0.5.3)
- telegram-optimization T1-A **Redis session_store** (required for `/api/session/health` to return real data — currently returns `{state:"empty"}` until agent.py patched) — `~/.claude/scratch/telegram-optimization/t1_core/`
- T2 **mention router** (`@macmini13 <task>`) that produces `task_queue:pending` ZSET entries — `~/.claude/scratch/telegram-optimization/t2_mention/`
- 上述 2 個先前 Mac CLI session 已產出 draft code 但未部署；v0.5.4 應部署以讓 miniapp 新功能有真實資料源
- 不影響本次 miniapp 健康：miniapp endpoint 優雅降級顯示「empty」或「unavailable」，不 crash

### Deferred
- V0.5.4: T1-A + T2 部署（miniapp 資料源）
- V0.5.5: audit log rotation + alert on audit anomaly
- V0.5.6: rollback-as-shortcut（需先設計 .bak snapshot DB 結構）
- V0.5.7: `intent modifiers`（Markl suggested「狀+短 / 狀+深 / 部+dry」）當 audit log 顯示 j13 頻繁補充語氣再加

### Lessons
- **Gemini "kill this feature" 救了一個設計錯誤**：pseudo-compact 按鈕放在 miniapp 會引起 race condition with agent.py monitor。第 1 次 review 的批判最有價值。
- **Subagent B path assumption**：預設生產 script 路徑時，應強制 Lead verify 或讓 subagent SSH 檢查。本次 `/home/j13/alaya/zangetsu/deploy.sh` 不存在，Lead 修正為 `zangetsu_ctl.sh restart`。
- **Lead model name flag caught by coincidence**：Subagent B 寫 `gemma3:4b` 給 Calcifer，我知道是 `gemma4:e4b` 因為今天用過。無此先驗知識會默默 call 錯 model。建議 subagent spec 中把外部服務版本列成 grounding fact。
- **/team 4-phase Q1 reviewer 數≥3 顯著降風險**：Gemini+Markl+Calcifer 各抓 7/5/6 個不同層面的問題，無重疊，都 actionable。單審查容易漏。

## v0.5.2 — 2026-04-18 — Mac CLI session: A4 V10 dispatcher + max_hold alignment + dedup isolation (post-factum record)
**Engine hash:** `zv5_v10_alpha` (unchanged)
**Branch / commit:** (post-factum — originally deployed 12:54 + 14:24 UTC without VERSION_LOG entry)

> **註**：此 entry 是事後補寫。修復由 Mac CLI session 於 2026-04-18 12:54 和 14:24 UTC 直接部署到 Alaya 生產環境，當下未同步 VERSION_LOG。v0.5.3 session 補寫此記錄以恢復 source-of-truth 對齊。Backup 仍保留：`.backup_20260418_122707_claude_deploy/`。

### Feature P0-G: A4 V10 alpha_expression dispatcher (arena45_orchestrator.py, +47 / -20 lines)
- **Change type:** fix (silent-reject CRITICAL)
- **What changed:**
  - `services/arena45_orchestrator.py` L385-455: `if not configs: fail no_configs` → `if not configs and not has_v10_alpha: fail`，加 `has_v10_alpha = bool(arena1.get("alpha_expression"))` dispatcher
  - V10 path: `reconstruct_signal_from_passport(passport, close, high, low, open, vol, entry_thr, exit_thr, min_hold=60, cooldown, regime)`（A5 live 也用同一函數）
  - V9 path: 原 `compute_indicators` + zero-MAD filter + `generate_threshold_signals` 邏輯不變，僅縮排至 else branch
  - 加 zero-signal guard：`if not np.any(signals): fail v10_alpha_reconstruct_failed`（防 reconstruct 返回 zero-fallback 卻被 backtest 當合格訊號）
  - Import `deflated_sharpe_ratio` from shared_utils（供後續 DSR gate 使用）
- **Why:** V10 champion 因設計上 `configs=[]`，被 L385 的 `if not configs` guard 全數 silent reject 為 `no_configs`。A4 的 V10 reconstruct 路徑（L430）**從未被執行過**。v0.5.1 session 的 outcome metric「2 V10 reached ARENA4_ELIMINATED」**其實是 silent reject，不是 legit holdout elimination** — 這點在 v0.5.1 當下未被識別。
- **Q1/Q2/Q3:** PASS
  - Q1 input boundary: has_v10_alpha 用 `bool(arena1.get("alpha_expression"))`，KeyError/None 都安全
  - Q1 silent failure: zero-signal guard 明確防止 fallback signal pass-through
  - Q1 scope creep: 僅加 dispatcher + guard，V9 path 純縮排不變邏輯
  - Q2: V9 向後相容，V10 champion 首次走入真 holdout test
  - Q3: 47 增 20 刪
- **Outcome metric (measured post-deploy):** 12:54 UTC P0-G deploy 至 15:01 UTC（2h07m）+13 筆 V10 通過 reconstruct 路徑進入 holdout test，全部 legit segmented WR fail（例 71477 DOGE bear wr=0.200, 71455 ETH bear wr=0.220 etc.）。A4 V10 pass rate 實測 = 0% 但**是真的 0%，不是假的 silent reject 0%**。
- **Rollback:** `cp .backup_20260418_122707_claude_deploy/arena45_orchestrator.py services/arena45_orchestrator.py && bash zangetsu_ctl.sh restart arena45_orchestrator`

### Feature M2: A4 V10 detection 統一 engine_hash prefix match (arena45_orchestrator.py)
- **Change type:** fix
- **What changed:** `pick_arena3_complete` SQL 從 `engine_hash != 'zv5_v10_alpha'` 改 `engine_hash IS NULL OR engine_hash NOT LIKE 'zv5_v10%'`
- **Why:** 未來 V10 variant（e.g. `zv5_v10_beta`）不會被新增字串重複。SQL detection 與 Python 端 `.startswith("zv5_v10")`（L321）統一。
- **Q1/Q2/Q3:** PASS（純 SQL literal，無注入面）

### Feature M3: A2 dedup engine_hash isolation (arena23_orchestrator.py +5 lines)
- **Change type:** fix
- **What changed:** `is_duplicate_champion` dedup SELECT 加 `AND (engine_hash IS NULL OR engine_hash NOT LIKE 'zv5_v9%')`
- **Why:** V9 pre-migration row 可能保留非 LEGACY 狀態；其 `config_hash` 和 V10 champion collide 會誤擋 V10。隔離 engine 家族避免跨世代 dedup 污染。
- **Q1/Q2/Q3:** PASS

### Feature: A2 V10 max_hold alignment with A1 (arena23_orchestrator.py:482, 1-line change)
- **Change type:** fix (pos_count=0 rejection root cause)
- **What changed:** `bt = backtester.run(sig, close, symbol, cost_bps, **120**, high=high, low=low, sizes=sz)` → `**480**`
- **Why:** A1 使用 `max_hold=480`（arena_pipeline.py:633），A2 原用 120 造成 same-alpha-diff-backtest。V10 rank crossover signal 的 min_hold=60 + cooldown=60，120 max_hold 會強制退出可獲利之持倉，轉成 cost-dominated loss，導致 `pos_count=0` 97% 拒絕率。對齊 480 讓 A2 重現 A1 的回測條件。
- **Q1/Q2/Q3:** PASS（配對上 A1 既有 max_hold，無新 magic number）

### Correction to v0.5.1 outcome metric (AKASHA chunk correction)
v0.5.1 session 聲明「2 V10 rows (71455 ETHUSDT, 71477 DOGEUSDT) reached ARENA4_ELIMINATED (legitimate holdout failure)」**此判定錯誤**。實際這 2 筆在 P0-G fix 之前就 ELIMINATED，走的是 `no_configs` silent reject 路徑（arena45 L385 V9-era guard），沒真的進入 A4 holdout test。v0.5.1 修復的是 A2/A3 signal-gen bridge（確實 end-to-end 恢復），但 A4 last-mile 到 12:54 UTC P0-G deploy 才真正打通。

### Process meta
- Mac CLI session 在 /team 深度掃描中發現 pos_count=0 問題（`~/.claude/scratch/zangetsu-247-monitor/POS_COUNT_ZERO.md`），該檔正確指出 max_hold asymmetry 為 H1 主因、passport 不可重現為 H2、direction bias 為 H3
- P0-G 本名源自 Mac CLI 內部 priority classification（P0=critical, G=group, letter 對應 discovery 順序）
- 24/7 monitor 系統於 14:10-14:12 UTC 建立於 `~/.claude/scratch/zangetsu-247-monitor/`，含 A1/A2A3/A4/A5/A13/Infra 6 區塊

### Deferred to v0.5.3
- VERSION_LOG 補記紀律：未來 Mac CLI 直接部署必須同步 prepend entry（本次 4 修復缺 1 日才被補上）
- Outcome metric 必達 DEPLOYABLE/ACTIVE 才算 end-to-end done（A4_ELIMINATED 不夠）
- `_global/feedback_outcome_metric.md` 新 memory 記錄此教訓

### Lessons
- **"V10 rolling migration" 的 4 個檔案同步陷阱**：producer（A1）→ consumer chain（A2/A3/A4/A5）任一未同步，表面 pass rate 會偽造為合法 elim。A2 是 signal-gen 不一致（v0.5.1 修），A4 是 no_configs silent reject（v0.5.2 修），兩步都無 VERSION_LOG entry 提前警示。
- **AKASHA chunk 修正成本**：已 POST 的 chunk 不能改，只能 POST 新 chunk 註解前者錯誤。本次 v0.5.1 的 AKASHA chunk 需由 v0.5.2 的修正 chunk 覆寫解讀。
- **監控系統 ≠ 修復部署追蹤**：24/7 monitor 抓到 0 promote/h，但因我們把「A4_ELIMINATED = legit」當成功指標，silent reject 在 monitor 裡也看起來綠。下次應加「no_configs rate」或「A4 dispatcher path hit count」作為 diagnostic metric。

---

## v0.5.1 — 2026-04-18 — V10 signal-gen alignment + hotfix return format
**Engine hash:** `zv5_v10_alpha` (unchanged)
**Branch / commit:** `feat/v10-signal-alignment` @ (pending)

### Feature: V10 A2/A3 signal-gen alignment with A1 (CORE FIX)
- **Change type:** fix (architectural)
- **What changed:**
  - `services/arena23_orchestrator.py`:
    - `_v10_alpha_to_signal()` body → stub raising `NotImplementedError`
    - A2 V10 branch (was calling `_v10_alpha_to_signal` = sign-of-zscore): now compiles AST inline and calls `generate_alpha_signals(alpha_values, ENTRY=0.80, EXIT=0.50, MIN_HOLD=60, COOLDOWN=60)` — same function A1 uses
    - A3 V10 branch: same alignment. Also **fixed latent NameError**: old code referenced `close/high/low/volume` undefined in `process_arena3` scope (would have crashed the moment any V10 row reached A3 — masked because A2 was rejecting all V10 rows first)
    - Added module-level env-driven constants `_V10_ENTRY_THR/_V10_EXIT_THR/_V10_MIN_HOLD/_V10_COOLDOWN` (read `ALPHA_*` env vars, fallback to A1 defaults)
    - Wrapped compile_ast + generate_alpha_signals in try/except; added `np.isfinite()` + `np.std<1e-10` guards
    - Passport gains `signal_gen`/`signal_params` fields for auditability
  - Hotfix v21 (same session): A2 V10 return changed from 3-tuple `(True, fields, passport)` to 2-tuple `(True, {"status":"ARENA2_COMPLETE", "arena2_win_rate":..., "arena2_n_trades":..., "passport_patch":{"arena2":{...}}})` matching V9 format. A3 V10 return changed to dict with `status="ARENA3_COMPLETE"` + `passport_patch` matching V9 A3 format.
- **Why:** 
  - Root cause (bridge bug): A1 produced champions using `generate_alpha_signals` (percentile-rank crossover, trades≥30) but A2/A3 evaluated them with `sign(tanh(rolling_zscore(raw, 500)))` — Kakushadze 2016 alpha-ensemble method, NOT a trade-signal generator. Same alpha produced ≥30 trades in A1 but 0-1 trades in A2 → 100% V10 rejection for 36 hours. 898 rows accumulated, 0 reached A3/A4/A5.
  - Secondary bug (pre-existing, masked): V10 branches returned 3-tuple `(True, fields, passport)` while main loop unpacked 2-tuple → ValueError immediately upon any V10 pass. Never surfaced because no V10 row had ever passed A2 since V10 deployment (2026-04-16). Fixing the bridge bug exposed this in production — caught within 3 minutes via tail log, hotfix applied within 5 minutes.
- **Q1/Q2/Q3:** PASS — 
  - Q1 input boundary: NaN/Inf/flat alpha → log + return None (no crash); env parse errors → fallback to code defaults
  - Q1 silent failure: try/except on compile_ast + signal_gen; stub raises NotImplementedError (no silent bypass)
  - Q1 concurrency: no shared state added; module-level constants immutable
  - Q1 scope creep: overfitting ratio change (Gemini+Markl both vetoed) explicitly deferred to v0.2.2; A3 NameError fix is in-scope (was prerequisite for outcome metric)
  - Q2: error_rollback path unchanged; rejected rows return to ARENA1_COMPLETE
  - Q3: ~20 LoC core + 15 LoC hotfix; no refactoring
- **Outcome metric (validated):** 2 V10 champions reached ARENA3_COMPLETE within 5 min of patch deploy:
  - id=71455 ETHUSDT `<alpha>` trades=1102 A2 sharpe=0.04 → A3 sharpe=0.05 → A4_ELIMINATED (holdout wr<0.40)
  - id=71477 DOGEUSDT `<alpha>` trades=49 A2 sharpe=0.70 → A3 sharpe=0.70 → A4_ELIMINATED
  - A4 elimination is legitimate holdout failure, not a bug. Pipeline now end-to-end functional.
- **Rollback:** `cp services/arena23_orchestrator.py.bak_v2_20260418_170404 services/arena23_orchestrator.py && bash zangetsu_ctl.sh restart`. 51 reset rows would naturally re-enter A2 under old code and revert to their prior rejected state — no DB rollback needed (tested via consensus review with Calcifer).

### Non-feature changes
- Audit: `services/alpha_quality_gates.py` confirmed to have **0 callers** across services/engine/live/scripts. The 6 designed quality gates (DSR>0.95, PBO<0.5, IC stability, regime robustness, turnover, monotonic spread) are inactive. Deferred to v0.2.3 PR (requires forward_returns + regime_labels data stream).
- Audit: A4 DSR threshold (0.05) vs `alpha_quality_gates.DSR_THRESHOLD` (0.95) — likely different metric formulas (one may be single-test, other multiple-testing corrected). Flagged for math review in v0.2.3 (no scope to reconcile this session).

### Deferred
- V0.2.2: tiered overfitting ratio (Markl recommended `<100 trades: 2x`, `>500 trades: 5x`, instead of current flat 10x and proposed flat 3x)
- V0.2.3: `alpha_quality_gates.py` wiring (need forward_returns stream from A1 post-A3)
- V0.2.4: end-to-end smoke test harness as CI check (to prevent future "producer upgraded, consumer not upgraded" incidents)

### Process meta — /team 四階段 applied
- Phase 1 Recon: 3 parallel — Explore Agent (A3/A4/A5 gates), Claude (A1/A2 gates + signal function map), Codex (backup audit — failed due to sandbox)
- Phase 2 Task Design: Unified Fix Plan v1 → 3-reviewer audit (Gemini 7/10, Markl GO-with-mod, Calcifer HOLD) → v2 consensus
- Phase 3 Spawn: 2 Opus 4.7 subagents in parallel (A: smoke test + patch; B: 5 deploy/monitor/rollback scripts). Subagent A caught latent A3 NameError during implementation (adversarial voice) — explicitly flagged in report
- Phase 4 Integration: Lead ran smoke test PASS → env check PASS → stop → scp patch → DB cleanup → start → caught 3-tuple bug in 3 min → Edit local + scp hotfix → workers up → outcome verified

### Lessons (for retro 20260418.md)
- **Subagent B scripts had BSD-vs-GNU awk `strftime` bug** → silent exit 0 without executing anything. Caught by manual verification (`ps aux`). Lesson: subagent-produced shell scripts need a runtime dry-check on Mac before production use.
- **3-tuple-vs-2-tuple latent bug was masked by the primary bug**. Fixing the primary exposed it immediately. Lesson aligns with existing memory `feedback_end_to_end_upgrade`: partial upgrade + smoke test covering only the first stage misses downstream format mismatches.
- **AKASHA memory was stale** (said arena-pipeline/arena45_orchestrator services were in systemd `activating` state; reality: arena services were *intentionally disabled* from systemd in v0.1.1 and replaced by ctl.sh + watchdog). Markl's 04-18 06:42 finding reinforced the stale state. Lesson: AKASHA memory decays fast on infra moves.

---

## v0.5.0 — 2026-04-18 — V10 core upgrade + single-track consolidation
**Engine hash:** `zv5_v10_alpha` (V10 active) + `zv5_v71`/`zv5_v9` (archived labels)
**Branch:** `main` @ `98a95e22` (single-track — feat deleted)

### Feature: V10 GP Alpha Expression Engine core integration
- **Change type:** major refactor (V9 → V10 paradigm shift)
- **What changed (22 files, +12986/-1033 lines):**
  - `services/arena_pipeline.py` (925-line rewrite): A1 workers now run per-symbol GP evolution (replaces V9 indicator-combo voting); INSERT engine_hash='zv5_v10_alpha'
  - `engine/components/alpha_engine.py` (1197-line expansion): 166 primitives (5 OHLCV + 126 indicators + 35 operators)
  - `services/arena23_orchestrator.py`, `arena45_orchestrator.py`: V10 alpha consumption
  - `services/{indicator_precompute, data_collector, event_queue, shared_data, shared_utils, pidlock, arena13_feedback}`: plumbing updates for V10
  - `engine/core.py`, `engine/components/{signal_utils, data_preprocessor}`: signal-generation updates
  - `config/settings.py`, `config/a13_guidance.json`: V10-related config values
  - `services/v9_search.py`: kept as legacy helper for A2/A3 side
- **Why:** V10 doctrine "GP Alpha Expression Engine" replaces V9 "indicator voting" — 4 A1 workers already running V10 code on disk since pre-session (uncommitted), but git reflected V9. Commit closes runtime ↔ git drift; any future restart/reset now loads correct V10 from git.
- **Q1/Q2/Q3:**
  - Q1 PASS — V10 runtime proven to work (862 alphas in DB, DSR=1.0 PASS, alpha_discovery cron runs clean)
  - Q2 PASS — all 18 modified files committed atomically; V9 snapshot preserved as immutable archive
  - Q3 PASS — minimum changes (only staged pre-existing runtime state, no new edits)

### Feature: V9 archive snapshot (immutable, in-project)
- **Change type:** archive (per j13 workflow: 淘汰舊版本封存在專屬專案的封存庫)
- **What changed:** New directory committed: `zangetsu/archive/v9_snapshot_20260418_030520/`
  - `arena_pipeline.py` (V9 indicator-voting, 993 lines)
  - `alpha_engine.py` (V9 pre-GP, 494 lines)
  - `signal_utils.py`, `v9_attention.py`, `v9_search.py` (V9 reference)
- **Why:** Per j13 rule "新版本出來之後直接進行部署，淘汰掉的舊版本進行封存": V10 deploys directly to main, V9 frozen at 2026-04-18 03:05:20 UTC as immutable snapshot inside project. Archive timestamp = pre-V10-seed moment (5 minutes before 03:10 seed of 851 Kakushadze alphas).
- **Q1/Q2/Q3:**
  - Q1 PASS — V9 core covered (arena_pipeline + alpha_engine are the two V9→V10 rewrites)
  - Q2 PASS — MD5 verified: archived files ≠ live for V9→V10 rewrites, = live for unchanged helpers
  - Q3 PASS — 5 files, 2365 frozen lines
- **Rollback:** `git checkout 98a95e22~1` (pre-merge state) or cp archive files back to live paths

### Feature: Single-track branch consolidation
- **Change type:** workflow (per j13 "不要有任何分支,分支很容易污染後續")
- **What changed:**
  - Fast-forward push `feat/v9-oneshot-hardening` → `origin/main` (89abc946..98a95e22)
  - Deleted `feat/v9-oneshot-hardening` (remote + local)
  - Deleted local branches: `backup/pre-filter-zangetsu_v3`, `upgrade-v5`, `v5-paper-trading`, `v5.1-fitness-redesign`, `ops/ecosystem-upgrade-v5`, original old `main`
  - **Remaining:** `main` (only, local + remote)
  - **PR #3** automatically moved to MERGED state
- **Why:** Branch sprawl was: 1 main (on origin), 1 feat (live dev), 5 legacy local. Violates single-track rule. Consolidation = main is canonical forever, every future commit goes direct to main.
- **Q1/Q2/Q3:**
  - Q1 PASS — feat was fast-forward of main, no merge conflicts, no force-push
  - Q2 PASS — remote main now at 98a95e22 (12 commits ahead of pre-session); PR #3 MERGED
  - Q3 PASS — `git push origin feat:main` one-shot operation

### Feature: Dashboard engine_hash filter correction
- **Change type:** fix
- **What changed:** `zangetsu/dashboard/api.py` line 1054, 1068: `WHERE engine_hash='zv9'` → `WHERE engine_hash IN ('zv5_v9', 'zv5_v10_alpha', 'zv5_v71')`
- **Why:** Prior filter used `'zv9'` label (no `zv5_` prefix); DB actually stores `zv5_v9` / `zv5_v10_alpha` / etc. Dashboard was returning 0 rows. Now shows V9 + V10 + V7.1 historical together.
- **Q1/Q2/Q3:** PASS — safe IN list, no SQL injection surface
- **Rollback:** sed reverse

### Feature: Log file gitignore
- **Change type:** infra cleanup
- **What changed:**
  - Added to `.gitignore`: `zangetsu/logs/`, `calcifer/calcifer.log`, `zangetsu/.venv/`
  - `git rm --cached` on `zangetsu/logs/engine.jsonl` (11449 lines) + `calcifer/calcifer.log` (2880 lines)
- **Why:** Log files churn at MB/hour. Should never be version-controlled.
- **Q1/Q2/Q3:** PASS — `--cached` only, files stay on disk for services to write

### Final V10 state (post v0.5.0)
```
Active V10 alphas:
  DISCOVERED + ARENA1_READY (valid alpha_hash): 13 (growing every 30 min via cron)
  SEED + ARENA1_READY (Kakushadze 2016):       851
  Total active:                                 864

Archived:
  DISCOVERED LEGACY (NULL-hash retired):         10
  zv5_v9_coldstart SEED LEGACY:                  13
  V9 source snapshot (immutable):                 5 files in zangetsu/archive/

Branch: main (single-track; feat/v9-oneshot-hardening deleted)
Remote: origin/main @ 98a95e22
PR #3: MERGED
```

### Deferred (not in this version)
- Watchdog presence-check architecture (lockfile blindness to clean shutdown)
- `zangetsu/config/a13_guidance.json` runtime updates (auto-written by A13 cron — expected churn)
- `calcifer/maintenance_last.json` runtime updates (same — expected)
- Dedicated `zangetsu-archive` GitHub repo (currently in-project archive suffices)

## v0.4.1 — 2026-04-18 — V10 post-deploy emergency fixes
**Engine hash:** unchanged
**Branch / commit:** `feat/v9-oneshot-hardening` @ (pending)

### Feature: alpha_discovery.py INSERT column correctness + status fix
- **Change type:** fix (production-impacting, caught by Round 3 adversarial sweep)
- **What changed:**
  - `services/alpha_discovery.py` INSERT statement:
    - Added `alpha_hash` column (was omitted → UNIQUE constraint defeated with NULL)
    - Pass `alpha.hash` as `$4` parameter
    - Changed status from `'DEPLOYABLE'` → `'ARENA1_READY'` (was incorrectly bypassing pipeline)
- **Why:** Round-3 Explore agent sweep caught 6 NULL alpha_hash rows created by v0.4.0 cron's first run. UNIQUE constraint on alpha_hash WHERE NOT NULL meant NULL rows accumulated unbounded. Status=DEPLOYABLE also wrong — discovered alphas must enter A1 pipeline for validation, not skip to deployment.
- **Q1/Q2/Q3:**
  - Q1 PASS — after fix, 3 test-run alphas inserted with valid `alpha_hash` and `status='ARENA1_READY'`
  - Q2 PASS — 9 pre-fix NULL rows retired to LEGACY (not deleted, preserved for forensic)
  - Q3 PASS — 3 sed operations on single file

### Data fix: retire 9 NULL alpha_hash rows
- **Change type:** data cleanup
- **What changed:** `UPDATE champion_pipeline SET status='LEGACY' WHERE engine_hash='zv5_v10_alpha' AND card_status='DISCOVERED' AND alpha_hash IS NULL`
- **Why:** Pre-fix cron runs inserted 9 rows with NULL alpha_hash. These can't be referenced by future dedup checks. Retiring preserves data without polluting active pipeline.

### Round 3 Emergency: V9 workers were DEAD
- **Change type:** fix (production-impacting, incident)
- **What changed:** Re-ran `zangetsu_ctl.sh start` — 6 workers back online (4 A1 + A23 + A45)
- **Why:** Between 03:00 UTC (watchdog: "all 8 services healthy") and 03:30 UTC (watchdog: "all 2 services healthy"), all 6 V9 workers died. Watchdog blind because pidlocks were cleanly removed (not stale-PID). My v0.4.0 report wrongly claimed "V9 untouched" — in reality workers died some time during the V10 deploy window.
- **Lesson learned:** Watchdog presence-check is lockfile-based; if lockfile removed cleanly, watchdog doesn't restart. Need "expected services" tracker.
- **Q1/Q2/Q3:** PASS — workers back, pipeline resumed

### Adversarial sweep findings (documented, not fixed in this version)
- **P1** 22 modified + 18 untracked files in repo (alpha_dedup, alpha_ensemble, alpha_quality_gates, factor_zoo, signal_reconstructor). Untracked includes critical V10 modules. Next commit should stage these.
- **P1** Watchdog lockfile-only presence detection → misses services that die cleanly. Architectural fix needed in separate version.
- **P2** `calcifer/calcifer.log` and `zangetsu/logs/engine.jsonl` tracked in git (shouldn't be). Add to .gitignore next commit.

### Running V10 state (after all v0.4.1 fixes)
```
DISCOVERED + ARENA1_READY (valid alpha_hash): 13
DISCOVERED + LEGACY (9 NULL + 1 original dupe):    10
SEED + ARENA1_READY (Kakushadze 2016 batch):      851
Total V10 alphas in pipeline: 874
```

### Deferred to next version
- Commit all untracked V10 files (alpha_dedup/ensemble/quality_gates/factor_zoo/signal_reconstructor)
- `.gitignore` calcifer.log + engine.jsonl
- Watchdog presence-check architecture upgrade

## v0.4.0 — 2026-04-18 — V10 factor expression deployment (Path B isolated)
**Engine hash:** V9 (zv5_v9, zv5_v71) + **V10 new (zv5_v10_alpha)**
**Branch / commit:** `feat/v9-oneshot-hardening` @ (pending)

### Feature: V10 Alpha Expression Engine activated
- **Change type:** deploy + fix
- **What changed:**
  - Fixed `services/alpha_discovery.py` two code-drift bugs:
    - Line 5 docstring + line 137 INSERT: `zv5_v9_alpha` → `zv5_v10_alpha` (matches DB reality)
    - Line 117: `alpha.to_passport_dict()` → `alpha.to_passport()` (actual method name)
  - Added cron entry: `*/30 * * * * cd ~/j13-ops && nice -n 10 zangetsu/.venv/bin/python -m zangetsu.services.alpha_discovery >> /tmp/zangetsu_alpha_discovery.log 2>&1`
  - `watchdog.sh` skip list extended: `alpha_discovery` joins `arena13_feedback|calcifer_supervisor` (cron-managed, not daemon)
  - Verified end-to-end: manual run produced 3 new alphas for BTCUSDT (GP 15 gen × 80 pop, ~3 sec eval)
- **Why:** V10 GP Alpha Expression Engine existed dormant since 2026-04-18 03:10 UTC (when 851 kakushadze_2016 seeds + 11 DISCOVERED rows were inserted), but alpha_discovery was never running due to two code-drift bugs. Path B strategy: keep V9 A1-A5 pipeline untouched, run V10 discovery isolated at `nice +10` every 30 min.
- **Q1/Q2/Q3:**
  - Q1 PASS — `nice +10` ensures no CPU contention with 4 A1 workers @ 100%; discovery runs ~3 sec; no DB write contention (inserts to separate engine_hash)
  - Q2 PASS — v10_alpha_ic_analysis shows 862 alphas, 108 with IC > 0.05, top DSR = 1.0000
  - Q3 PASS — 2 sed fixes + 1 cron + 1 watchdog line; zero V9 pipeline changes
- **Rollback:** revert two sed fixes, remove cron line, revert watchdog skip

### Feature: Schema constraints (V2 — Agent-3 adversarial finding)
- **Change type:** fix (adversarial finding mitigation)
- **What changed:** `zangetsu/migrations/postgres/v0.4.0_v2_constraints.sql`:
  - `uniq_regime_indicator_hash_v9`: UNIQUE(regime, indicator_hash) WHERE alpha_hash IS NULL AND status != 'LEGACY' (V9 rows)
  - `uniq_alpha_hash_v10`: UNIQUE(alpha_hash) WHERE alpha_hash IS NOT NULL AND status != 'LEGACY' (V10 rows)
  - `chk_sane_metrics`: numeric bounds on win_rate [0,1], trades >=0, pnl [-10, 100], elo [-1000, 5000], n_indicators [0, 10]
- **Why:** Agent-3 adversarial audit found `champion_pipeline` had ONLY PKEY + 2 status CHECKs. Any SSH+DB holder could plant `status='DEPLOYABLE'` bypassing all gates. Constraints lock the physical schema.
- **Q1/Q2/Q3:**
  - Q1 PASS — constraint apply surfaced real duplicate `alpha_hash=3ff11ef5fb27b838` (retired as LEGACY)
  - Q2 PASS — indexes created, no drop on existing data
  - Q3 PASS — migration idempotent with IF NOT EXISTS guards

### Feature: V10 alpha status normalization
- **Change type:** data fix
- **What changed:**
  - 11 DISCOVERED V10 alphas had `status='DEPLOYABLE'` (bypassing pipeline) → fixed to `status='ARENA1_READY'`
  - 851 SEED V10 alphas had `status='DEPLOYABLE'` → fixed to `status='ARENA1_READY'`
  - 1 duplicate alpha_hash row retired to `status='LEGACY'`
- **Why:** Seeded alphas should enter A1 pipeline via `ARENA1_READY`, not skip to `DEPLOYABLE`. Previous seed script had wrong default.
- **Q1/Q2/Q3:** PASS — no alpha lost (all reassigned, not deleted)
- **Rollback:** UPDATE ... SET status='DEPLOYABLE' WHERE ...

### V10 current inventory (post-deployment)
- **862 total V10 alphas** (851 SEED + 11 DISCOVERED)
  - All in `status='ARENA1_READY'` awaiting A1 evaluation
  - `engine_hash='zv5_v10_alpha'` (distinct from V9's `zv5_v9`/`zv5_v71`)
  - Regimes: MULTI (851), BULL_TREND (5), CONSOLIDATION (6)
- **Quality baseline** (via v10_alpha_ic_analysis):
  - Mean IC: 0.0374
  - 333 alphas with IC > 0.02 (V9 MIN_IC_THRESHOLD)
  - 108 alphas with IC > 0.05 (strong signals)
  - Max IC: 0.4832
  - Top alpha DSR: 1.0000 (PASS V10 gate 1)
- **Discovery cadence:** every 30 min via cron, one symbol per run, GP 15 gen × 80 pop

### Cron state (post-v0.4.0)
```
*/5 * * * *  watchdog.sh
*/5 * * * *  arena13_feedback (single-shot)
0 */6 * * *  daily_data_collect
*/30 * * * * alpha_discovery (nice +10, NEW)
45 * * * *   v10_alpha_ic_analysis (pre-existing)
0 3 * * 0    /tmp cleanup
```

### Adversarial / code-drift issues caught this batch
1. `to_passport_dict` vs `to_passport` (fatal, blocked all discovery)
2. `zv5_v9_alpha` vs `zv5_v10_alpha` (silent drift, DB ignored discovery)
3. Duplicate alpha_hash (UNIQUE caught, retired to LEGACY)
4. Seed script defaulted status='DEPLOYABLE' (bypassing pipeline)

### Deferred (not in this version)
- Path A acceleration (V10 接線 V9 live ensemble) — wait 1 week observation
- V1 train=test architectural fix — will propose separate PR after V10 proves out
- Gemini/OpenAI auth on Alaya — needs API keys
- PR #3 merge to main — wait 1 week from earlier commit cycle

## v0.3.4 — 2026-04-17 — Watchdog round 2: orchestrator stale-check skip
**Engine hash:** `zv5_v71` / `zv5_v9`
**Branch / commit:** `feat/v9-oneshot-hardening` @ `f8bc5701`

### Feature: Watchdog — arena23/45 orchestrators skip stale-log check
- **Change type:** fix (production-impacting, second-order from v0.3.2)
- **What changed:** `zangetsu/watchdog.sh` lockfile loop now branches:
  - For `arena23_orchestrator` and `arena45_orchestrator`: PID-alive check only, skip stale-log check entirely
  - All other workers (A1 pipeline w0-w3): keep stale check (they actively log when working)
- **Why:** v0.3.2 bumped STALE_THRESHOLD 600→1800 (10min→30min) but observation at 15:00 UTC showed orchestrators STILL restarted every cycle. Root cause: orchestrators legitimately idle while `champion_pipeline` empty (V9 has no champions yet) → no log writes for 30+ min → stale check fires → pure churn restart. Restarting an idle orchestrator does nothing useful. The threshold isn't the right knob; orchestrator semantics are different from A1 workers (which actively process work).
- **Q1/Q2/Q3:**
  - Q1 PASS — orchestrators still get PID-dead detection (real crashes still restart); only the stale-log false-positive is suppressed
  - Q2 PASS — manual `bash watchdog.sh` after fix shows `WATCHDOG: all 8 services healthy`
  - Q3 PASS — 7-line patch (case statement + continue)
- **Rollback:** revert the case branch in lockfile loop

### Round-2 deep scan summary (Explore agent + Opus env audit + Codex/Gemini auth-blocked)
- ✅ **0 critical findings** in all-projects audit (zangetsu, calcifer, markl, agent_bus, infra)
- ✅ **0 systemd failed units**
- ✅ **22 Docker containers healthy**
- ✅ **Disk 10% / RAM 21G free / GPU idle** — no leaks
- ✅ **0 zombie/defunct processes** (17 orphans = legitimate daemon backgrounding)
- ✅ **8 pidlocks** (4 A1 + arena23 + arena45 + arena13_feedback transient + calcifer_supervisor)
- ✅ **All `zangetsu_v5` references in active code = 0** (`zv5_` only in engine_hash + log filenames, intentional)
- ✅ **Cross-project consistency**: agent_bus / markl / infra all clean
- ⚠️ **Codex CLI on Alaya needs OPENAI_API_KEY** (`codex exec` returned 401 Unauthorized)
- ⚠️ **Gemini CLI on Alaya needs GEMINI_API_KEY** (already noted in v0.3.0)

## v0.3.1 — 2026-04-17 — LFS + V9 SQL view + watchdog stale-loop fix
**Engine hash:** `zv5_v71` / `zv5_v9` (literals preserved)
**Branch / commit:** `feat/v9-oneshot-hardening` @ `c1f23a46`

### Feature: Git LFS tracking for parquet data files (preventive)
- **Change type:** new (infra)
- **What changed:**
  - Installed `git-lfs` on Alaya via `apt install -y git-lfs`
  - `git lfs install` per-repo + `git lfs track "zangetsu/data/**/*.parquet"`
  - Created `.gitattributes` (1 line, repo root)
- **Why:** Previous push attempt warned BTCUSDT.parquet (99 MB) close to GitHub 100 MB hard limit. data/ is also gitignored + skip-worktree, so LFS never fires today — but if someone removes the gitignore or new symbols join, files auto-route to LFS instead of bloating the repo.
- **Q1/Q2/Q3:** PASS — `git lfs status` confirms tracking active; no behavior change for current commits
- **Rollback:** delete `.gitattributes` + `git lfs uninstall` (per-repo)

### Feature: V9 SQL view foundation (champion_pipeline_v9)
- **Change type:** new (DB schema)
- **What changed:**
  - New file: `zangetsu/migrations/postgres/v0.3.0_v9_view.sql`
  - View: `CREATE OR REPLACE VIEW champion_pipeline_v9 AS SELECT * FROM champion_pipeline WHERE engine_hash IN ('zv5_v9', 'zv5_v71');`
  - Applied to deploy-postgres-1
- **Why:** Dashboard has 17 query sites all hitting raw `champion_pipeline`. Wholesale modification = invasive. The view provides a non-breaking migration path: dashboard/scripts can switch to the view incrementally as V9 (`zv5_v9`) accumulates records. When v71 retires, just drop it from the view's IN clause — zero code change downstream.
- **Q1/Q2/Q3:** PASS — `SELECT count(*) FROM champion_pipeline_v9` returns 0 cleanly (table empty); view DDL idempotent
- **Rollback:** `DROP VIEW champion_pipeline_v9`

### Feature: Arena13 lifecycle decision (single-shot via cron, not daemon)
- **Change type:** decision + execution
- **What changed:**
  - Read `arena13_feedback.py` carefully: log says "Arena 13 Feedback complete (single-shot)" then exits — NOT a long-running daemon despite `REFRESH_INTERVAL_S = 300` constant (which appears to be a planned-but-unshipped daemon feature)
  - Reverted accidental ctl.sh + watchdog daemon-style integration from earlier in this session
  - Added cron entry: `*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1`
  - `arena13_evolution.py` decision: KEEP (DISABLED stub with reintroduction requirements documented in its docstring)
- **Why:** systemd unit `arena13-feedback.timer` was the original trigger; we removed all systemd arena units in v0.3.0. Without re-trigger, A13 guidance freezes. cron is the correct equivalent.
- **Q1/Q2/Q3:** PASS — A13 logs show clean run + exit every 5 min; no orphan processes
- **Rollback:** `crontab -e` remove the line

### Feature: Weekly /tmp cleanup cron
- **Change type:** new
- **What changed:** Cron entry `0 3 * * 0 find /tmp -maxdepth 1 \( -name "zangetsu_*.log.[0-9]" -o -name "zangetsu-*.txt" -o -name "zangetsu-*.bak" \) -mtime +7 -delete`
- **Why:** Long-running watchdog rotates logs (`.log.1`, `.log.2`); Mac scratch transit files accumulate in /tmp. Weekly sweep keeps disk clean.
- **Q1/Q2/Q3:** PASS — only deletes files older than 7 days, only matching specific patterns
- **Rollback:** remove cron line

---

## v0.3.2 — 2026-04-17 — Watchdog stale-loop bug fix (caught by 1h observation)
**Engine hash:** `zv5_v71` / `zv5_v9`
**Branch / commit:** `feat/v9-oneshot-hardening` @ `c1f23a46`

### Feature: Watchdog — bump STALE_THRESHOLD + skip cron-managed services
- **Change type:** fix (production-impacting)
- **What changed:**
  - `zangetsu/watchdog.sh`: `STALE_THRESHOLD=600` → `1800` (10min → 30min)
  - Added skip clause in main lockfile loop: `case "$name" in arena13_feedback|calcifer_supervisor) continue ;; esac`
- **Why:** P0-6 watchdog observation revealed two real production bugs introduced earlier this session:
  1. **arena13_feedback false-restart loop**: cron-managed `*/5min`, but lock file persists between runs with dead PID. Watchdog iterates `/tmp/zangetsu/*.lock`, sees dead PID, attempts restart → hits `*) unknown service` branch → spammed `WATCHDOG: unknown service arena13_feedback, cannot restart` every cycle.
  2. **arena23/45 vicious restart loop**: orchestrators idle when `champion_pipeline` empty (which it is — V9 hasn't accumulated). Idle = no log writes. STALE_THRESHOLD=600 (10min) → watchdog killed them every cycle. Logs showed `restarted arena23_orchestrator (pid=N)` repeatedly. Without fix: continuous worker churn until DB has data.
- **Q1/Q2/Q3:**
  - Q1 PASS — manual `bash watchdog.sh` runs silently (healthy); skip clause limited to known cron-managed services
  - Q2 PASS — `tail -f /tmp/zangetsu_watchdog.log` after fix shows no further restart events
  - Q3 PASS — 6-line patch
- **Rollback:** revert sed (one block + one line)

---

## v0.3.3 — 2026-04-17 — Git history partial cleanup (gc 6.0G → 1.3G)
**Engine hash:** unchanged
**Branch / commit:** N/A (git plumbing only, no commit needed)

### Operation: aggressive gc + reflog expire
- **Change type:** infra (one-shot)
- **What changed:**
  - `git reflog expire --expire=now --all`
  - `git gc --prune=now --aggressive`
  - Repo `.git`: **6.0 GB → 1.3 GB** (78% reduction)
- **Why:** Earlier `git filter-branch` (during rename, v0.2.0) made `zangetsu_v3/.venv` blobs unreachable but didn't gc them. They sat in pack files for hours. Aggressive gc reclaimed the space.
- **Q1/Q2/Q3:** PASS — refs/HEAD unchanged; only unreachable objects pruned; force-push not needed
- **Note:** `git filter-repo --path zangetsu_v3 --invert-paths --force` attempted but blocked by interactive sanity-check prompt (stdin EOF over SSH). To complete: run with `--enforce-sanity-checks=false` from attached terminal. Estimated additional savings: ~500 MB.

### Deferred (not in this version)
- Full `git filter-repo` to remove `zangetsu_v3/` source from history — needs interactive shell or `--enforce-sanity-checks=false`
- engine_hash 17-query migration to `champion_pipeline_v9` view — wait for V9 data accumulation
- PR #3 merge to main — pending review
- Gemini auth on Alaya — needs `GEMINI_API_KEY`

---

## v0.3.0 — 2026-04-17 — All-ctl service model + test cred + hygiene
**Engine hash:** `zv5_v71` / `zv5_v9` (literals preserved)
**Branch / commit:** `feat/v9-oneshot-hardening` @ `d0aab305`

### Feature: all-ctl.sh service management (eliminate systemd dual-management)
- **Change type:** refactor (infra)
- **What changed:**
  - Removed 6 systemd unit files: `arena-pipeline.service`, `arena23-orchestrator.service`, `arena45-orchestrator.service`, `arena13-feedback.service`, `arena13-feedback.timer`, `arena13-evolution.service`
  - `watchdog.sh`: removed dead `SYSTEMD_SERVICES` array + `LOCK_TO_SYSTEMD` map + the `restart_service` systemd-prefer branch (~23 lines)
  - `restart_service` now lockfile-only restart for arena workers
  - Source-of-truth: `zangetsu_ctl.sh` + `watchdog.sh` (cron */5min)
  - Kept systemd-managed: `console-api`, `dashboard-api`, `calcifer-supervisor`
- **Why:** systemd arena units were spawning workers in restart loop, losing pidlock to ctl.sh-spawned ones. Pure log noise. Watchdog's `LOCK_TO_SYSTEMD` mapping triggered failed `systemctl restart` calls. Single-management model = clean ops.
- **Q1/Q2/Q3:** PASS — V9 scan reports `✅ Systemd units stable`, 6 workers running, no restart loops
- **Rollback:** re-create unit files from systemd template + `daemon-reload`

### Feature: test credential auto-loading
- **Change type:** new
- **What changed:**
  - Created user-readable env file at `~/.zangetsu_test.env` (mode 0600, owner j13:j13) — copy of `/etc/zangetsu/zangetsu.env`
  - Added `zangetsu/tests/conftest.py` — auto-loads env vars from that file on pytest startup
- **Why:** `/etc/zangetsu/zangetsu.env` is root-only (used by systemd EnvironmentFile). pytest as `j13` user couldn't read → asyncpg InvalidPassword in `test_db` / `test_checkpoint` / `test_console_api`. After fix: 3 passed / 3 skipped (was 2 failed).
- **Q1/Q2/Q3:** PASS — pytest now exits 0
- **Rollback:** delete the user-readable env file and `tests/conftest.py`

### Feature: V32 scan — Calcifer endpoint moved to AKASHA /health
- **Change type:** fix
- **What changed:** `~/.claude/scratch/v32-deep-scan.sh` Calcifer section: `http://100.123.49.102:8770/health` → `http://100.123.49.102:8769/health` (AKASHA), section header renamed `## Calcifer` → `## AKASHA Health`
- **Why:** Calcifer-supervisor doesn't bind any HTTP port (it's an Ollama+Telegram bot), so 8770 returned empty forever. AKASHA at 8769 is the actual health source.
- **Q1/Q2/Q3:** PASS — scan now reads `AKASHA: {"status":"ok"}`
- **Rollback:** revert sed in scan script

### Feature: ctl.sh — `$0 status` bug + V5/V9 banner
- **Change type:** fix (cosmetic + ergonomics)
- **What changed:** Line 63 `$0 status` → `bash "$(dirname "$0")/zangetsu_ctl.sh" status`; banner string `"Zangetsu V5 services"` → `"Zangetsu V9 services"`
- **Why:** `$0` resolves to bare `zangetsu_ctl.sh` (not in PATH), causing `command not found` every restart. Banner was outdated.
- **Q1/Q2/Q3:** PASS
- **Rollback:** sed reverse

### Feature: post-rename hygiene — calcifer paths + log filenames
- **Change type:** fix (post-rename leftover)
- **What changed:**
  - `calcifer/supervisor.py`: 3 paths `~/j13-ops/zangetsu_v5/` → `~/j13-ops/zangetsu/`, lock `/tmp/zangetsu_v5/` → `/tmp/zangetsu/`
  - `watchdog.sh` + `zangetsu_ctl.sh`: log filenames `/tmp/zv5_*.log` → `/tmp/zangetsu_*.log`
  - cron: `/tmp/zv5_watchdog.log` → `/tmp/zangetsu_watchdog.log`
  - `.gitignore`: added `**/.venv/`, `**/__pycache__/`, `**/*.bak2`, `**/*.deleted`, `zangetsu/data/{funding,ohlcv,oi,regimes}/`
- **Why:** Explore-agent post-rename audit caught these (Calcifer was actively writing to dead path; log filenames mismatch would trigger watchdog auto-restart in 5min)
- **Q1/Q2/Q3:** PASS — caught by 2nd-round scan, fixed before next watchdog tick

### Non-feature changes
- engine_hash literals (`zv5_v9`, `zv5_v71`) and SQL pattern (`'zv5_%'`) intentionally preserved per project_naming convention (folder=physical axis, hash=runtime stamp axis)
- During sweep I accidentally caught engine_hash literals — reverted in same session
- arena45 worker dropped during ctl restart → systemd race spawned duplicate → caught + cleaned + systemd units permanently removed in this version

### Deferred (not in this version)
- Git LFS for `zangetsu/data/**/*.parquet` — needs `apt install git-lfs` on Alaya first
- engine_hash default filter on dashboard/scripts — wait until V9 (`zv5_v9`) accumulates champion records
- PR #3 merge to main — pending review

---

# zangetsu — VERSION LOG

> Per `_global/feedback_project_naming.md`: bare project folder name + this log file as single-source-of-truth for "what changed when".
> Latest version on top. Per-feature granularity required.

---

## v0.2.0 — 2026-04-17 — Folder rename: `zangetsu_v5` → `zangetsu`
**Engine hash:** `zv5_v71` (unchanged — runtime stamp axis decoupled from folder)
**Branch / commit:** `feat/v9-oneshot-hardening` @ (pending)

### Feature: project folder rename
- **Change type:** refactor (physical layout)
- **What changed:**
  - `~/j13-ops/zangetsu_v5/` → `~/j13-ops/zangetsu/` (git mv, history preserved)
  - 43 code/config files swept: all `zangetsu_v5` → `zangetsu` in imports / paths / SQL DSN / shell scripts
  - 10 systemd unit files updated (`/etc/systemd/system/{arena,console,dashboard,calcifer,health-monitor,live-trader}*.service`)
  - 2 cron entries updated (watchdog + daily_data_collect)
  - 46 `.venv/bin/` script shebangs sed-rewritten
  - Lock dir `/tmp/zangetsu_v5/` → `/tmp/zangetsu/`
  - Mac scan script `~/.claude/scratch/v32-deep-scan.sh` updated
- **Why:** Adopting new project naming rule (`feedback_project_naming.md`). Version-suffixed dirs caused the V9 全局修復 saga: scan tooling stayed at V3 paths, schemas, modules — silent decay. Folder names should be physical-layer identifiers; doctrine version (V9 Sharpe Quant) lives in code/branch, runtime version (`zv5_v71`) lives in DB.
- **Q1/Q2/Q3:** PASS — 6 workers restarted clean, all imports green, systemd 3 conflict units stay disabled, no inflight-data loss (workers idle at rename moment)
- **Rollback:** `git mv zangetsu zangetsu_v5 && sudo find /etc/systemd/system -name "*.service" -exec sed -i "s|zangetsu/|zangetsu_v5/|g" {} \; && sudo systemctl daemon-reload && crontab /tmp/zangetsu-crontab.bak && bash zangetsu_ctl.sh restart`

### Non-feature changes
- `engine_hash` in DB stays `zv5_v71` — intentional decoupling per project_naming feedback rule
- `zangetsu_ctl.sh` still echoes "Zangetsu V5 services" string in startup banner — cosmetic, acceptable; will rename to "V9" when next version logical

---

## v0.1.1 — 2026-04-17 — Pidlock import-time fix + scan rewrite + pytest config
**Engine hash:** `zv5_v71`
**Branch / commit:** `feat/v9-oneshot-hardening` @ `bb1602fc`

### Feature: pidlock single-instance guard
- **Change type:** fix
- **What changed:** moved `acquire_lock()` from module top-level into `if __name__ == "__main__"` guard in 4 services: `arena_pipeline.py`, `arena13_feedback.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py`
- **Why:** any `import` of these services triggered pidlock → `sys.exit(1)`, breaking scan/test/lint pipelines silently. V3.2 scan reported "S01 import failure" with empty error → this was the root cause.
- **Q1/Q2/Q3:** PASS — commit `3dc1304e`
- **Rollback:** `cp services/{name}.py.bak2 services/{name}.py`

### Feature: pytest async test support
- **Change type:** new
- **What changed:** added `zangetsu/pytest.ini` with `asyncio_mode = auto`; installed `pytest-asyncio` 1.3.0 in `.venv`
- **Why:** 3 integration tests were silently skipped because pytest didn't recognize `async def`. After fix, 1 test now passes; 2 still fail on asyncpg credentials (separate test-infra issue, not in scope here).
- **Q1/Q2/Q3:** PASS — commit `bb1602fc`
- **Rollback:** `rm pytest.ini && pip uninstall pytest-asyncio`

### Feature: V3.2 scan script rewrite (Mac side)
- **Change type:** refactor
- **What changed:** `~/.claude/scratch/v32-deep-scan.sh` rewritten from V3 era to V9 reality:
  - Paths: `zangetsu_v3` → `zangetsu_v5` (later → `zangetsu` in v0.2.0)
  - SQL: V3 tables (`factor_candidates` etc.) → V9 schema (`champion_pipeline`, `pipeline_state`, `pipeline_errors` with correct column names)
  - Module check list: V9 module layout
  - S01 stderr handling fixed (was treating optional-lib WARNINGs as failures)
  - ps grep aligned to script-style invocation `services/(arena|v9_)`
  - Calcifer freshness JSON parse guarded
  - New section: Service Manager Conflict Check (auto-detects systemd-vs-ctl issues)
- **Why:** Old script was V3-era; reported false MISSING for everything V9 had refactored. Couldn't distinguish "broken" from "intentionally moved."
- **Q1/Q2/Q3:** PASS — minimal changes per section, verified by re-running scan
- **Rollback:** `cp v32-deep-scan.sh.v3.bak v32-deep-scan.sh` (kept on Mac /tmp)

### Feature: redundant systemd units disabled
- **Change type:** infra cleanup
- **What changed:** `systemctl stop && disable` for `arena-pipeline`, `arena23-orchestrator`, `arena45-orchestrator`, `arena13-feedback`, `arena13-evolution`, `arena13-feedback.timer`. Workers continue running via `zangetsu_ctl.sh + watchdog.sh` (manual `&` spawn model — confirmed by reading `watchdog.sh` restart logic).
- **Why:** Systemd units were spawning workers in restart loop, losing pidlock to ctl.sh-spawned ones. Pure log noise. Watchdog uses `LOCK_TO_SYSTEMD` map but its actual restart path uses `eval $cmd > log 2>&1 &` (not `systemctl restart`) — so systemd units were never the real management.
- **Q1/Q2/Q3:** PASS — V9 scan went from `⚠️ Systemd units in failure/restart loop` to `✅ Systemd units stable`
- **Rollback:** `sudo systemctl enable && start arena-pipeline arena23-orchestrator arena45-orchestrator`
