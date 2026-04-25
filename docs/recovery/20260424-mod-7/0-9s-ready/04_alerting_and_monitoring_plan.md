# 04 — Alerting and Monitoring Plan (CANARY)

## 0. 範圍

本檔是 TEAM ORDER **0-9S-READY** (PR-D of stack `0-9P/R-STACK-v2`) 的
operational alerting + monitoring plan：定義未來 0-9S-CANARY runtime 的
**watch / notify / escalate** 三層機制。

> 0-9S-READY 不啟動 CANARY、不部署任何 watchdog；本檔規範未來啟動時
> alerting 必須長什麼樣。所有 hardware / service infra 都複用既有設施
> （Calcifer / Telegram / AKASHA / GitHub branch protection / CI Gate-A/B），
> **不引入新 module**。

它與 PR-D `03_rollback_plan.md` 是 1:1 對應：alert 觸發 → rollback hot-swap
是同一個 control loop 的兩端。

---

## 1. Alert channels（既有 infrastructure）

本 plan 不引入新 channel；複用：

| Channel | 角色 | Backend | 對齊 |
| --- | --- | --- | --- |
| **Calcifer** | Outcome watchdog（cross-project §17.3） | Gemma4 E4B on Alaya:11434 | CLAUDE.md §5 / §17.3；既有 Calcifer outcome watchdog |
| **Telegram bot** | Operator notifications | @Alaya13jbot, chat -1003601437444, thread 362 | CLAUDE.md §6 / 既有 d-mail dispatcher |
| **AKASHA witness service** | Independent verification record | AKASHA endpoint http://100.123.49.102:8769 | CLAUDE.md §17.2 |
| **Branch protection on `main`** | Governance ledger（無法繞過） | GitHub: enforce_admins=true, required_signatures=true, linear_history=true, allow_force_pushes=false, allow_deletions=false | 既有 branch protection（已 ship） |
| **GitHub Actions Gate-A / Gate-B** | CI signal（pre-merge） | Existing workflows | CLAUDE.md §17.7 / 既有 CI |

---

## 2. Watched metrics（matrix）

每一列 = 一個 watchpoint。Calcifer 負責 polling，Telegram 負責 notify，
AKASHA 負責 record。

| Metric | Source | Polling interval | Alert threshold | Severity 入口 |
| --- | --- | --- | --- | --- |
| **A2 sparse rate** | `arena_batch_metrics` aggregate（per cohort）| 5 min | `signal_too_sparse_rate > baseline + 5 pp`（absolute） | WARN → BLOCKING（若連續 3 個 polling cycle） |
| **A3 pass_rate** | `arena_batch_metrics` aggregate（per cohort）| 5 min | `pass_rate < baseline − 2 pp`（absolute） | WARN → BLOCKING (F1 trigger threshold = −5 pp) |
| **deployable_count (rolling 7d median)** | `champion_pipeline.status='DEPLOYABLE'` VIEW | hourly | `< baseline − 1` | BLOCKING (對齊 0-9R F2 / G3) |
| **UNKNOWN_REJECT rate** | aggregate cross-stage | 5 min | `>= 0.05` | BLOCKING (對齊 G4 / F4) |
| **OOS_FAIL rate** | A3 telemetry | 5 min | `> baseline + 5 pp`（absolute） | BLOCKING (對齊 F3 / G5) |
| **profile_score variance** | `generation_profile_metrics`（≥ 20-round smoothed） | hourly | abrupt regime jump（profile_score Δ ≥ 2σ within 1 polling window） | WARN |
| **attribution audit verdict** | `profile_attribution_audit`（0-9P-AUDIT）| daily（≥ 7 day window） | regression to RED | BLOCKING（對齊 0-9R-IMPL-DRY `04_attribution_audit_dependency.md` §4） |
| **Calcifer outcome watchdog** | `/tmp/calcifer_deploy_block.json` | continuous（inotify） | presence of file = block | BLOCKING（對齊 §17.3） |
| **profile collapse** | distinct actionable profile_id count | hourly | `< 0.5 * baseline` | BLOCKING (對齊 F6) |
| **mean_trades_per_passed_a2 + pnl_per_trade** | A2/A3 telemetry join | hourly | trades ≥ +100% **AND** pnl_per_trade ≤ −20% | BLOCKING (對齊 F5) |
| **EXPLORATION_FLOOR** | per-profile budget | per allocation | any profile < 0.05 | FATAL（對齊 G9 / F7；hard floor violation 不可 j13 override） |
| **cohort regime breakdown** | per-regime deployable_count | daily | 任一 regime deployable down ≥ 1（中位數） | BLOCKING (對齊 F8 / G7) |
| **composite score** | computed: `0.4*a2 + 0.4*a3 + 0.2*deployable_density` | hourly | `treatment_composite < baseline_composite − 1σ` | BLOCKING (對齊 F9 / S12) |
| **STALE-SERVICE check** | systemd ActiveEnterTimestamp vs swap file mtime | post-deploy | `proc_start < source_mtime` | FATAL（對齊 §17.6） |

> **SINGLE TRUTH 限制**（§17.1）：所有 deployable_count 來源都從
> `champion_pipeline_fresh.status='DEPLOYABLE'` VIEW 拿，不允許 inline
> count subquery。這個 VIEW 是 authoritative；alert thresholds 不可
> 自己定義 deployable 是什麼。

---

## 3. Alert severity ladder

四級嚴重度，由低到高。Calcifer 根據 §2 metrics 決定 severity，由
Telegram bot 路由到對應 audience。

### 3.1 INFO

- 含義：daily summary、composite score 趨勢、無異常。
- 不影響 CANARY 運行。
- 不要求人類即時回應；j13 可選擇性閱讀。

### 3.2 WARN

- 含義：single-metric YELLOW，例如：
  - UNKNOWN_REJECT rate 上升但仍 < 0.05
  - profile_score 出現 abrupt jump 但未跨 G9 / F-criteria
  - composite score 在 1σ 內波動但 baseline correlation 衰減
- CANARY 繼續運行，但被「列入觀察」。
- j13 必須在 24 h 內 review；逾期未 review → Calcifer 升級為 BLOCKING。

### 3.3 BLOCKING

- 含義：任何 F1–F9 / G3 / G4 / G5 / 0-9P-AUDIT verdict RED triggered。
- **自動 rollback**（per `03_rollback_plan.md` §4 hot-swap procedure）。
- 不需 j13 確認；rollback 是 fail-safe default。
- Telegram alert + AKASHA witness POST + Calcifer 寫
  `/tmp/calcifer_deploy_block.json`（RED）三者同時發生。

### 3.4 FATAL

- 含義：governance-grade 失敗。包含：
  - 同一小時內 ≥ 2 個 BLOCKING trigger
  - rollback.sh 自身執行失敗（§4 step 3 exit code != 0）
  - signed-PR flow 被弱化（branch protection setting 被改）
  - STALE-SERVICE check 失敗（§17.6 violation）
  - EXPLORATION_FLOOR 違反（G9）
- 動作：governance halt + branch protection lockout + j13 manual review
  required。
- Calcifer **不嘗試** 自動恢復；等 j13 顯式 unblock。
- 對齊 CLAUDE.md §17.4 AUTO-REGRESSION REVERT：時間是最終裁判，FATAL
  時 watchdog 自己 git revert recent claim commits。

---

## 4. Per-severity action matrix

| Severity | Notification | Auto action | Human action | Witness |
| --- | --- | --- | --- | --- |
| INFO | Telegram daily digest（thread 362） | none | optional read | AKASHA append daily summary |
| WARN | Telegram immediate（thread 362） | none | j13 review within 24 h；逾期升級為 BLOCKING | AKASHA witness `kind=canary_warn` |
| BLOCKING | Telegram immediate（thread 362）+ pinned message | auto-rollback per 03_rollback_plan.md §4 | j13 review within 24 h（incident report） | AKASHA witness `kind=canary_rollback`（§17.2 mandatory） |
| FATAL | Telegram urgent（thread 362）+ tag j13 + GitHub branch protection lockout 0-9s-* / 0-9r-impl-* | governance halt + auto git-revert per §17.4 | j13 manual review；不可短路 | AKASHA witness `kind=canary_fatal` + Calcifer RED |

> 對齊 §17.5：版本 bump 由 `bin/bump_version.py` only；FATAL 後
> 任何手寫 `feat(0-9s/vN)` 都會被 pre-receive regex 拒絕。

---

## 5. Calcifer 整合

Calcifer 既有 outcome watchdog（CLAUDE.md §17.3）擴充以涵蓋 CANARY
specific signals。**不新建 watchdog**；只擴充既有 watchlist。

擴充內容（寫到 `/tmp/calcifer_watchlist.json`）：

```json
{
  "watchlist_version": "0-9s-canary-v1",
  "metrics": [
    {
      "name": "a2_sparse_rate_trend_regression",
      "source": "arena_batch_metrics",
      "logic": "linear_regression slope over 7d > 0 AND >= baseline + 5pp",
      "polling": "5m",
      "severity_on_trigger": "BLOCKING"
    },
    {
      "name": "attribution_verdict_regression",
      "source": "profile_attribution_audit",
      "logic": "previous=GREEN AND latest=RED",
      "polling": "1d",
      "severity_on_trigger": "BLOCKING"
    },
    {
      "name": "profile_collapse",
      "source": "generation_profile_metrics",
      "logic": "distinct(actionable_profile_id) < 0.5 * baseline_distinct",
      "polling": "1h",
      "severity_on_trigger": "BLOCKING"
    },
    {
      "name": "deployable_count_floor",
      "source": "champion_pipeline_fresh VIEW (status='DEPLOYABLE')",
      "logic": "rolling_7d_median < baseline - 1",
      "polling": "1h",
      "severity_on_trigger": "BLOCKING"
    }
  ]
}
```

**為什麼擴充而不新建**：

- Calcifer 已經是 Alaya:11434 上 always-on 的 Gemma4 E4B；新增 watchpoint
  只是 config 變更，不需要新 service / 新 systemd unit。
- 對齊 §17.6：新 service 會引入新 STALE-SERVICE check 表面；擴充
  既有 service 沒這個風險。
- 對齊 P3（Systematize Repeatable Work）：CANARY 不是首次 Calcifer
  watch event；複用 pattern。

---

## 6. Telegram message format

所有 message 走 thread 362（@Alaya13jbot），ASCII code block，無 emoji。
對齊 CLAUDE.md §6 publishing format。

### 6.1 INFO — daily digest

```
[0-9S-CANARY | INFO | DAILY DIGEST]
ts: 2026-MM-DD HH:MM UTC
run_id: <run_id>
day: D+<n>

composite_score:
  baseline:  0.6234
  treatment: 0.6491   delta: +0.0257   sigma: 0.41

a2_sparse_rate:
  baseline:  0.318
  treatment: 0.247   delta: -0.071    direction: improve

a3_pass_rate:
  baseline:  0.412
  treatment: 0.408   delta: -0.004    direction: stable

deployable_count_7d_median:
  baseline:  4
  treatment: 5

unknown_reject_rate: 0.018  (< 0.05 OK)
oos_fail_rate:       baseline=0.082, treatment=0.089  (delta=+0.007 OK)

verdict: ON_TRACK
no action required
```

### 6.2 WARN — single-metric YELLOW

```
[0-9S-CANARY | WARN | YELLOW METRIC]
ts: 2026-MM-DD HH:MM UTC
run_id: <run_id>

metric: unknown_reject_rate
current: 0.043   threshold: 0.05   trend: rising 0.012/day
baseline: 0.018

evidence: docs/governance/evidence/canary-{run_id}-warn-{ts}.md
recent rejection log: <path>

action: j13 review required within 24h
auto-escalation: BLOCKING if no review by <ts + 24h>
```

### 6.3 BLOCKING — rollback initiated

```
[0-9S-CANARY | BLOCKING | ROLLBACK INITIATED]
ts: 2026-MM-DD HH:MM UTC
run_id: <run_id>

trigger: F3 (OOS_FAIL +5.2pp absolute)
trigger_metric: oos_fail_rate
  baseline:  0.082
  treatment: 0.134   delta: +0.052

action: auto-rollback per 03_rollback_plan.md §4
rollback_sha: <sha after rollback merge>
rollback_log: docs/governance/incidents/{date}-rollback.md (drafting)

before_deployable_count: 5
after_deployable_count:  <pending verification>

akasha_witness: <witness_id>
calcifer_state: RED  (file: /tmp/calcifer_deploy_block.json)

next: j13 review within 24h. CANARY locked until incident report merged.
```

### 6.4 FATAL — governance escalation

```
[0-9S-CANARY | FATAL | GOVERNANCE HALT]
ts: 2026-MM-DD HH:MM UTC
run_id: <run_id>
@j13

trigger: STALE_SERVICE_CHECK_FAILED
detail:
  proc_start:    2026-MM-DD 12:34:56  (epoch 1745...)
  source_mtime:  2026-MM-DD 13:01:22  (epoch 1745...)
  delta: +1586s   verdict: STALE

action_taken:
  1. branch protection lockout: 0-9s-*, 0-9r-impl-* (read-only)
  2. auto git-revert: <revert_sha>
  3. AKASHA witness: kind=canary_fatal, id=<wid>
  4. Calcifer RED: /tmp/calcifer_deploy_block.json

action_required:
  j13 manual review. No auto-resume.
  Read: docs/governance/incidents/{date}-fatal.md
```

---

## 7. Dashboard recommendations（out of 0-9S-READY scope）

> 本節是 guidance，**0-9S-READY 不部署 dashboard**。Dashboard 由 j13 在
> 0-9S-CANARY activation 前另開 implementation order（建議 0-9S-DASH）。

### 7.1 Real-time

- composite score（baseline vs treatment overlay，per cohort）
- rolling 7d `deployable_count`（authoritative VIEW source）
- Calcifer state badge（GREEN / YELLOW / RED；source = `/tmp/calcifer_deploy_block.json`）

### 7.2 Trend

- A2 sparse rate（per cohort，30-day window）
- A3 pass_rate（per cohort，30-day window）
- OOS_FAIL rate（per cohort，30-day window）

### 7.3 Per-profile

- heatmap of `profile_score` vs `profile_id`（rows=profile，
  columns=time bucket，cell=smoothed score）
- diversity panel：actionable profile count over time（對齊 G9 / G10）

### 7.4 Verdict log

- Timeline：0-9P-AUDIT verdicts（GREEN / YELLOW / RED）over time
- Annotation：每個 BLOCKING / FATAL event 標在 timeline 上

---

## 8. **不** alert 的東西（anti-list）

明確列出，避免 alert noise / false positive 觸發 unnecessary rollback。

| 項目 | 為什麼不 alert |
| --- | --- |
| Per-batch noise（單一 batch 的 metric jitter） | profile_score 必須 ≥ 20-round smoothed（對齊 G6）；single-batch 不可驅動 alert |
| Sub-baseline-1σ drift | 1σ 內視為 noise；F9 / S12 都用 `> 1σ` 作 trigger |
| One-off network errors | Calcifer 對 connection error 自動 retry 3 次；3 次失敗才視為 metric unavailable |
| Scheduled maintenance windows | Alaya 維護時段（每週日 04:00–05:00 UTC）Calcifer auto-mute |
| AKASHA TTL expiry on chunks | TTL expiry 不是 metric event；Calcifer 不視為異常 |
| Telegram bot rate limit retry | Telegram 自身 rate limit 不影響 CANARY 運行；只記到 Calcifer log |
| Test cohort（cohort tag = `experiment-test`）| 對齊 0-9R `05` §2.3 的 cohort split；test cohort 故意 fail 來驗 alert path 不 trigger production rollback |
| Single-day deployable_count fluctuation | 用 7-day rolling median（VIEW source）；single-day spike / dip 不 alert |
| j02 strategy metrics during j01 CANARY | strategy_id=j02 與 j01 平行運作但不混算（對齊 0-9R §2.1）；j02 metric 不影響 j01 alert |
| profile_score per-batch（pre-smoothing） | G6 hard rule；alert 一律用 smoothed 值 |

---

## 9. Cross-reference

- 0-9R `05_ab_evaluation_and_canary_readiness.md` §6 success criteria S1–S12
  / §7 failure criteria F1–F8 / §9 CR1–CR9
- 0-9R `04_anti_overfit_guardrails.md` §2 G1–G13 / §11 watchdog responsibilities
- 0-9R-IMPL-DRY `04_attribution_audit_dependency.md` §4 verdict regression /
  §6 CR2 enforcement
- 0-9P-AUDIT verdict GREEN / YELLOW / RED consumer flow
- 03_rollback_plan.md §2 trigger / §4 hot-swap / §6 24-h review
- CLAUDE.md §5 Calcifer auto-trigger
- CLAUDE.md §6 Telegram publishing format（thread 362）
- CLAUDE.md §17.1 SINGLE TRUTH（VIEW）
- CLAUDE.md §17.2 MANDATORY WITNESS（AKASHA independent service）
- CLAUDE.md §17.3 CALCIFER OUTCOME WATCH
- CLAUDE.md §17.4 AUTO-REGRESSION REVERT
- CLAUDE.md §17.5 VERSION BUMP IS BOT ACTION
- CLAUDE.md §17.6 STALE-SERVICE CHECK
- CLAUDE.md §17.7 DECISION RECORD CI GATE

---

## 10. Coverage check

對齊 0-9R §7 / §9 / §11 watchdog responsibilities，本 plan 覆蓋率：

| 0-9R requirement | Coverage in this plan |
| --- | --- |
| F1–F9 自動偵測 | §2 matrix lines 2/3/5/4/10/9/A2/12/14 |
| G3 deployable_count 不下降 | §2 deployable_count line + §5 watchlist `deployable_count_floor` |
| G4 unknown_reject < 0.05 | §2 UNKNOWN_REJECT line |
| G5 oos_fail material increase | §2 OOS_FAIL line |
| G7 regime breakdown | §2 cohort regime breakdown line |
| G9 EXPLORATION_FLOOR | §2 + FATAL severity（§3.4） |
| 0-9R CR6 Calcifer alert | §5 watchlist 涵蓋 sparse-related metrics |
| §17.3 Calcifer outcome watchdog | §1 channel + §2 polling + §5 watchlist |
| §17.2 AKASHA witness | §4 per-severity action matrix Witness column |
| §17.6 STALE-SERVICE | §2 matrix line + FATAL severity |
| 0-9R-IMPL-DRY `04` §4 verdict regression | §2 attribution audit verdict line + §5 watchlist `attribution_verdict_regression` |

> 任何未覆蓋項 → 0-9R red-team 在 0-9S-CANARY activation 前 STOP；
> 必須先補進本 plan 並重新通過 j13 顯式授權。
