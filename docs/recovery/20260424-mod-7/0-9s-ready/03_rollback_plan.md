# 03 — Rollback Plan (CANARY Operator Runbook)

## 0. 範圍與位置

本檔是 TEAM ORDER **0-9S-READY** (PR-D of stack `0-9P/R-STACK-v2`) 的
operator runbook：定義未來 0-9S-CANARY activation **必須** honor 的
rollback 路徑。

> **0-9S-READY 不執行 CANARY**。本檔不啟動任何 production runtime mutation；
> 它定義 CANARY 啟動的前置 rollback contract — 任何未滿足本檔條件的
> CANARY 都會被 0-9R guardrail watchdog 拒絕啟動。

它把 0-9R `05_ab_evaluation_and_canary_readiness.md` §8 "Rollback procedure"
的 sketch（hot-swap baseline ↔ treatment、Telegram alert、AKASHA witness、
24-hour review）operationalize 成可執行 runbook，並與 CLAUDE.md §17 跨專案
hard rules（§17.1 SINGLE TRUTH / §17.2 MANDATORY WITNESS / §17.3 CALCIFER
OUTCOME WATCH / §17.4 AUTO-REGRESSION REVERT / §17.6 STALE-SERVICE CHECK）
對齊。

---

## 1. Rollback principle（不可協商）

> **Every CANARY apply MUST be reversible within 30 minutes.**

這是 invariant，不是 SLA goal。所有 implementation order 都必須遵守：

- **No irreversible state mutation** — CANARY 不得寫入會被 downstream
  cache / index / dashboard 永久消化的 schema-shape data。
- **No destructive DB write** — CANARY 不得 DELETE / UPDATE 既有
  champion_pipeline / generation_profile_metrics rows；只能 INSERT 新
  rows，由 status / cohort tag 區分 baseline vs treatment。
- **No schema migration** — CANARY 期間 forbidden：ALTER TABLE、新增
  PRIMARY KEY、改 VIEW definition、改 trigger function。
- **No threshold change** — 對齊 0-9R `04_anti_overfit_guardrails.md` G11
  / S7：A2_MIN_TRADES、ATR/TRAIL/FIXED gates、Arena pass conditions
  全部 unchanged。
- **No champion promotion semantic change** — 對齊 0-9R S9 / G13。
- **Hot-swap only** — runtime consumer 必須能在不重啟 service 的情況下
  從 treatment weights 切回 baseline weights（reload swap file）。

任何 implementation order 若違反上述任一條，0-9R red-team 直接 STOP。

---

## 2. 觸發 rollback 的條件

Rollback 由 **任一** 以下事件觸發。Rollback 不可由 j13 override 維持
treatment（對齊 0-9R §7 末段）。

### 2.1 F1–F9 failure criteria（對齊 0-9R `05_ab_evaluation_and_canary_readiness.md` §7）

| # | Trigger |
| --- | --- |
| F1 | A2 pass_rate improve **但** A3 pass_rate collapse（A3 down ≥ 5 pp absolute） |
| F2 | A2 pass_rate improve 但 deployable_count down（7-day rolling median 下降 ≥ 1） |
| F3 | OOS_FAIL increase ≥ 5 pp absolute |
| F4 | UNKNOWN_REJECT 增加（≥ baseline + 2 pp） |
| F5 | trade-count inflation（mean_trades_per_passed_a2 上升 ≥ 100% 且 pnl_per_trade 下降 ≥ 20%） |
| F6 | profile collapse（actionable profile 數 < baseline 的 50%） |
| F7 | exploration floor 違反（任何 profile < 0.05） |
| F8 | 結果由單一 regime / 單一 time slice 主導（其他 regime 全 degrade） |
| F9 | composite score regression（treatment composite < baseline composite − 1σ） |

> F9 對應 0-9R S12 的反向；任何 F1–F9 觸發都 mandatory rollback。

### 2.2 Operator-initiated j13 STOP

- j13 在 Telegram 對 alert bot 發 `/stop 0-9S-CANARY` → 立刻進入 §4 hot-swap。
- 不需理由、不需 evidence；j13 STOP 是 final。

### 2.3 Calcifer outcome watchdog RED

對齊 CLAUDE.md §17.3：

- `deployable_count==0 AND last_live_at_age_h>6` → Calcifer 寫
  `/tmp/calcifer_deploy_block.json`，狀態 RED。
- 本檔 §4 hot-swap 必須 **先讀** `/tmp/calcifer_deploy_block.json`；
  presence = RED = block。

### 2.4 Attribution verdict regression to RED

對齊 0-9R-IMPL-DRY `04_attribution_audit_dependency.md` §4：

- 0-9P-AUDIT 在 CANARY 期間每日 audit 一次（>= 7 day window）。
- 之前 GREEN 但新一輪 audit 回 RED → consumer **立刻** stop emitting
  actionable plans → 觸發 rollback。
- CR2 在 CANARY activation 時間驗一次；regression 時不需要 j13 確認，
  watchdog 自動 rollback。

---

## 3. CANARY 啟動前 **必須存在** 的 rollback artifacts

如果 CANARY 啟動前缺失任一 artifact，CANARY 不允許啟動（GitHub Actions
Gate-A / Gate-B 拒絕 merge）。

| # | Artifact | 路徑 / location | 驗證方式 |
| --- | --- | --- | --- |
| A1 | Baseline `proposed_profile_weights_dry_run` snapshot | `docs/governance/snapshots/canary-pre-{run_id}-profile-weights-baseline.json`（per profile_id） | `jq '.profile_weights | length > 0'` |
| A2 | Pre-CANARY git tag at merge commit | `git tag canary-pre-{run_id}` 簽名 tag | `git tag -v canary-pre-{run_id}` 必須 GPG verify pass |
| A3 | Pre-CANARY snapshot via existing script | `scripts/governance/capture_snapshot.sh canary-pre-{run_id}` 寫到 `docs/governance/snapshots/` | snapshot file SHA256 寫入 AKASHA witness |
| A4 | `/tmp/canary_state.json` baseline + treatment markers | `/tmp/canary_state.json` (key: `baseline_weights_path`, `treatment_weights_path`, `cohort_split`) | `jq '.baseline_weights_path and .treatment_weights_path'` |
| A5 | Paired baseline-only systemd unit | 若 CANARY 引入 `0-9s-canary.service`，必須同時存在 `0-9s-baseline.service` | `systemctl list-unit-files | grep 0-9s-baseline` |
| A6 | `scripts/canary/rollback.sh` (future, dry-run tested) | `scripts/canary/rollback.sh` | dry-run 模式至少 3 次成功（對齊 0-9R CR5） |
| A7 | AKASHA witness baseline POST | `POST /witness {kind: "canary_pre_snapshot", run_id, baseline_sha, ts}` | AKASHA `GET /witness/{run_id}` 必須回非空 |
| A8 | Calcifer outcome watchdog 已對 sparse metrics 加 alert | Calcifer config（對齊 0-9R CR6） | `/tmp/calcifer_watchlist.json` contains keys: `a2_sparse_rate`, `a3_pass_rate`, `attribution_verdict`, `deployable_count` |

A1–A8 任一缺失 → CANARY 不可啟動，直接 STOP。

> **Hard rule（CLAUDE.md §17.6 STALE-SERVICE CHECK）**：在 CANARY 宣告
> 啟動前，runtime consumer process start time 必須 ≥ swap file mtime；
> 否則視為 STALE。`~/.claude/hooks/pre-done-stale-check.sh` exit !=0 →
> not-done。

---

## 4. Hot-swap procedure

```
1. j13 issues STOP via Telegram bot
   → @Alaya13jbot receives /stop 0-9S-CANARY
   → bot writes /tmp/canary_stop_request.json
   → notifies operator channel (thread 362)

2. Calcifer writes /tmp/calcifer_deploy_block.json (RED)
   → JSON: {"reason": "F<n> | OPERATOR_STOP | ATTRIBUTION_RED",
            "trigger_ts": "...", "run_id": "..."}
   → presence of file = block on any new feat(0-9s/vN) commit
   → 對齊 CLAUDE.md §17.3

3. Operator runs scripts/canary/rollback.sh (future implementation)
   - reads previous_profile_weights from
     docs/governance/snapshots/canary-pre-{run_id}-profile-weights-baseline.json
   - writes them to runtime consumer's swap file:
       /var/lib/0-9s/runtime_consumer/profile_weights.json.swap
   - atomic rename to /var/lib/0-9s/runtime_consumer/profile_weights.json
   - the runtime consumer hot-loads (inotify on the file; no service restart)
   - rollback.sh exit code 0 = swap successful;
     non-zero = halt and escalate (FATAL, see 04_alerting_and_monitoring_plan.md §3)

4. Operator verifies (must pass before declaring rollback done):
       psql -h <alaya> -c "
         SELECT count(*) FROM champion_pipeline_fresh
         WHERE status='DEPLOYABLE'
       "
   - count must be ≥ baseline floor recorded in A1 snapshot
   - 對齊 CLAUDE.md §17.1 SINGLE TRUTH

5. AKASHA witness service POSTs rollback record
       POST /witness {
         "kind": "canary_rollback",
         "run_id": "...",
         "trigger": "F<n> | OPERATOR_STOP | ATTRIBUTION_RED | CALCIFER_RED",
         "rollback_sha": "<commit sha of rollback merge>",
         "before_deployable_count": <int>,
         "after_deployable_count": <int>,
         "ts": "..."
       }
   - 必須由 AKASHA 獨立 service 寫，不可由 rollback.sh 自寫
   - 對齊 CLAUDE.md §17.2 MANDATORY WITNESS

6. Telegram alert sent
   - thread 362：「0-9S-CANARY rollback executed」
   - includes: trigger, run_id, before/after deployable_count,
     evidence file paths, AKASHA witness id
   - format 詳見 04_alerting_and_monitoring_plan.md §6

7. 24-hour observation window
   - branch protection 對 0-9s-* branch 啟動 lockout（read-only）
   - 任何 re-activation 都 blocked，直到 §6 review window 結束
```

完成 7 步驟才算 rollback 完成；任一步驟失敗 → escalate FATAL，停止
所有後續 step，j13 manual review。

---

## 5. Rollback 之後的驗證

Hot-swap 結束不等於 clean rollback。必須觀察以下指標確認無 lingering effect：

| 指標 | 預期行為 | 驗證命令 / 來源 | 觀察視窗 |
| --- | --- | --- | --- |
| `generation_profile_metrics.confidence` | **不**從 CONFIDENCE_A1_A2_A3_AVAILABLE regress | `SELECT confidence, count(*) FROM generation_profile_metrics WHERE created_at > now() - interval '24h' GROUP BY 1` | 24 h |
| A2 `signal_too_sparse_rate` | 回到 baseline trajectory 24–48h | `arena_batch_metrics` aggregate | 48 h |
| `deployable_count`（rolling 7d median） | 7 day 內 ≥ baseline | `champion_pipeline.status='DEPLOYABLE'` VIEW | 7 d |
| `unknown_reject_rate` | < 0.05（對齊 G4） | aggregate query | 24 h |
| `oos_fail_rate` | 不 spike ≥ baseline + 5 pp | A3 telemetry | 24 h |
| Calcifer outcome watchdog | `/tmp/calcifer_deploy_block.json` 已被 clear（rollback 完成後 Calcifer 寫 GREEN 或刪除 file） | `ls /tmp/calcifer_deploy_block.json` 應 ENOENT | rollback +30 min |

任一指標未在預期視窗內回正 → 升級為 FATAL，啟動 §6 review window
之外的額外調查（governance halt，對齊 04_alerting_and_monitoring_plan.md §4）。

---

## 6. 24-hour review window

j13 必須在 re-attempt CANARY 前讀 incident report。

- **檔案位置**：`docs/governance/incidents/YYYYMMDD-rollback.md`
- **誰寫**：Calcifer 自動 draft，j13 補 root-cause；對齊 CLAUDE.md §17.7
  decision record CI gate（`/team` session 必須有 retro，rollback 算
  /team-grade event）。

Incident report 必須回答：

1. 哪一個 CR / G / F 觸發 rollback？
2. 什麼 evidence file（snapshot / log / verdict）支持該觸發？
3. Root-cause 假設（單一 / 多重）。
4. 這 root-cause 屬於 0-9R `04_anti_overfit_guardrails.md` §2 G1–G13 的
   哪一條？是否揭露 guardrail gap？
5. 修復需要：
   - 純 documentation update（0-9R-IMPL-DRY-AMEND）？
   - 或需重做 0-9R-IMPL-REWORK？
6. 下一輪 CANARY 啟動最早時間（不得早於 incident report merge + 7 day）。

j13 的 review verdict 三選一：

- `RESUME_AFTER_FIX` — root-cause 已釐清且修復可在 7 day 內完成
- `RESUME_AFTER_REWORK` — 需要 0-9R-IMPL-REWORK 全套重來
- `HALT_INDEFINITE` — 暫時不再嘗試 0-9R-IMPL，j13 另開 order

---

## 7. Multi-rollback policy

| 條件 | 必要動作 |
| --- | --- |
| 30 day 內第 1 次 rollback | §6 24-hour review window，正常 resume |
| 30 day 內第 2 次 rollback | 自動 `HALT_INDEFINITE`，require 獨立 `0-9R-IMPL-REWORK` order；j13 不可短路 |
| 30 day 內第 3 次 rollback（極端情況） | governance halt，branch protection 全 lockout 0-9s-* / 0-9r-impl-* branches；j13 必須開新的 `0-9P/R-STACK-v3` 重設 baseline |

> 30 day window 由 incident report timestamp 計算（merge 到 main 的時間）。
> 對齊 CLAUDE.md §17.4 AUTO-REGRESSION REVERT 的精神：
> 時間是最終裁判，多次 rollback 代表結構性問題而非偶發 noise。

---

## 8. Rollback **無法** recover 的東西

明確 anti-claims，避免「rollback 之後就一切 OK」的誤解。

- **Candidate pool poisoning** — treatment shape 的 candidate 已經
  寫入 champion_pipeline / candidate_passport，rollback 不會刪掉它們；
  需要 7 day baseline calibration 才能重建乾淨的 sample distribution。
  對齊 0-9R `04_anti_overfit_guardrails.md` §10 counter-inconsistency
  drift。
- **Cross-strategy contamination**（j01 / j02 cohort）— 如果 cohort
  切分意外把 j02 sample 混進 j01 treatment（或反向），rollback 不會
  un-mix；需要按 cohort tag 標記受污染 batch、從 evaluation set 排除。
- **Downstream consumer state** — 外部 dashboard / Grafana / 第三方
  monitoring（如 calcifer-mini-app cache）可能 cache 了 treatment
  metrics；rollback 不會 invalidate 這些 cache，需要分別清。
- **AKASHA chunk 殘留** — CANARY 期間 AKASHA upsert 的 chunk
  （TTL 內）會繼續被 retrieval 命中；rollback 後需要 explicit
  POST `/compact` 清掉 cohort=treatment 的 chunks。
- **Witness chain history** — 對齊 §17.2，witness record 是
  append-only ledger；rollback 不刪 witness，只新增「rollback witness」。
  歷史 audit 必須能看到 forward + rollback 兩個 record 才是 complete chain。

---

## 9. 與未來 0-9R-IMPL-APPLY 的連接

每個 implementation order **觸碰真實 budget** 的（即從 dry-run 升級到
runtime consumer 寫 swap file 的）必須：

1. **Embed runnable rollback.sh** — 在 PR diff 中提供具體 path
   `scripts/canary/rollback.sh`，禁止「rollback 在另一個 PR 補上」。
2. **Dry-run tested** — rollback.sh 必須在 dry-run mode 下測試 ≥ 3 次
   成功 swap baseline ↔ treatment（對齊 0-9R CR5），輸出 log 寫到
   `docs/governance/dry-runs/canary-rollback-{ts}.log` 並由 PR
   reference。
3. **CI Gate-A check** — GitHub Actions Gate-A 檢查：
   - PR title prefix `feat(0-9s/...)` 或 `feat(0-9r-impl-apply/...)` →
     必須包含 `scripts/canary/rollback.sh` modification 或新增。
   - 必須 reference 至少 1 個 dry-run log 路徑。
   - 對齊 CLAUDE.md §17.5：只有 `bin/bump_version.py` 可發
     `feat(<proj>/vN)` commit。
4. **AKASHA witness pre-flight** — merge 前 POST
   `/witness {kind: "canary_pre_apply_check", rollback_script_sha,
   dry_run_log_sha}`；missing → CI block。

> **0-9R-IMPL-APPLY 是 future order**。本檔不啟動它；只規範它必須符合
> 哪些 rollback contract 才能被 0-9R red-team 放行。

---

## 10. Cross-reference

- 0-9R `05_ab_evaluation_and_canary_readiness.md` §7 (F1–F8) §8
  (Rollback procedure) §9 (CR1–CR9)
- 0-9R `04_anti_overfit_guardrails.md` §2 G1–G13 §11 watchdog
- 0-9R-IMPL-DRY `04_attribution_audit_dependency.md` §4 verdict regression
- 0-9P-AUDIT verdict consumer flow（GREEN / YELLOW / RED）
- CLAUDE.md §17.1 SINGLE TRUTH（VIEW deployable_count）
- CLAUDE.md §17.2 MANDATORY WITNESS（AKASHA independent service）
- CLAUDE.md §17.3 CALCIFER OUTCOME WATCH
- CLAUDE.md §17.4 AUTO-REGRESSION REVERT
- CLAUDE.md §17.5 VERSION BUMP IS BOT ACTION
- CLAUDE.md §17.6 STALE-SERVICE CHECK
- CLAUDE.md §17.7 DECISION RECORD CI GATE
- 04_alerting_and_monitoring_plan.md（PR-D 第 4 章，alert 觸發 ↔ 本檔
  rollback hot-swap 是 1:1 對應）
