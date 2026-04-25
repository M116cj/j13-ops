# 01 — CANARY Readiness Gate (CR1–CR15)

> **重要前提 / Reminder**：本檔案為 PR-D / 0-9S-READY 之 design 交付物，
> **0-9S-READY 不啟動 CANARY**。CR15 明確要求另一個獨立 j13 order
> （TEAM ORDER 0-9S-CANARY）才能 activate runtime apply path。
> 在該 order 出現之前：consumer 維持 dry-run only、runtime 無 import
> path、deployable_count semantics 不變、Arena pass/fail 不變、
> A2_MIN_TRADES / ATR / TRAIL / FIXED grids 不變。

---

## 1. 範圍與位置

PR-D 是 0-9P / R-STACK-v2 stack 中第四個（最後一個 design 階段）PR。
其唯一交付為 **operator-grade gate criteria**：將 0-9R 設計階段的
CR1–CR9 擴展為 CR1–CR15，使 0-9S-CANARY activation order 可逐條
勾選 evidence。

| PR | Order | Scope | Merged SHA |
| --- | --- | --- | --- |
| PR-A | 0-9P | passport persistence + `resolve_attribution_chain` 4-level precedence | `a8a8ba9` |
| PR-B | 0-9P-AUDIT | `zangetsu/tools/profile_attribution_audit.py` GREEN/YELLOW/RED verdict | `3219b805` |
| PR-C | 0-9R-IMPL-DRY | `zangetsu/services/feedback_budget_consumer.py` + `SparseCandidateDryRunPlan` 28-field schema | `fe3075f` |
| PR-D | 0-9S-READY | CR1–CR15 + S1–S14 + F1–F9 + alert path + rollback plan（**docs only**） | — |

PR-D **不修改任何 production code**，亦不弱化 branch protection、
不寫入 AKASHA witness、不發 Telegram 廣播。

---

## 2. Gate criteria — 一覽表

| # | Criterion | Source |
| --- | --- | --- |
| CR1 | 0-9P attribution closure complete | PR-A |
| CR2 | 0-9P-AUDIT verdict GREEN, or documented YELLOW with mitigations | PR-B |
| CR3 | 0-9R-IMPL-DRY complete | PR-C |
| CR4 | No runtime apply path exists | repo-wide invariant |
| CR5 | Consumer has no runtime import path | PR-C `runtime_isolation_audit` |
| CR6 | Dry-run consumer ≥ 7 days stable outputs OR explicit j13 override | PR-C operating window |
| CR7 | UNKNOWN_REJECT < 0.05 (cross-stage, 7-day rolling) | 0-9R 04 G4 |
| CR8 | A2 sparse rate trend measured (baseline established) | P7-PR4B telemetry |
| CR9 | A3 pass_rate non-degradation evidence available | 0-9R 04 G2 |
| CR10 | deployable_count non-degradation evidence available | CLAUDE.md §17.1 / §17.3 |
| CR11 | Rollback plan documented | this stack `03_rollback_plan.md` |
| CR12 | Telegram / alert path defined | this stack `04_alert_path.md` |
| CR13 | Branch protection intact | governance |
| CR14 | Signed PR-only flow intact | §17.2 / §17.5 |
| CR15 | Explicit future j13 CANARY authorization recorded | TEAM ORDER 0-9S-CANARY |

---

## 3. 逐條展開

### 3.1 CR1 — 0-9P attribution closure complete

- **Why it matters**：sparse-candidate intervention 必須依靠精確的
  `origin_profile / origin_run_id / origin_strategy_id` 才能正確歸因；
  attribution 缺口會把不同 profile 的指標互相混算，使 CANARY 結論失真。
- **How it's verified**：
  ```
  gh pr view 21 --json mergeCommit -q .mergeCommit.oid
  # expect: a8a8ba9...
  psql -c "SELECT date_trunc('day', ts) AS d, sum(unknown_origin_count)
           FROM audit.attribution_closure_view
           WHERE ts >= now() - interval '7 days' GROUP BY 1 ORDER BY 1;"
  # expect: every row sum = 0
  ```
- **What blocks it**：任一 7-day batch 出現 `unknown_origin_count > 0`、
  或 `resolve_attribution_chain` 4-level precedence helper 未上線。
- **Evidence path**：
  - PR-A merge：`a8a8ba9`
  - report：`docs/recovery/20260424-mod-7/0-9p/07_0-9p_final_report.md`
  - VIEW：`audit.attribution_closure_view`
- **Cross-ref**：0-9P `01_passport_identity_design.md`、
  `03_attribution_precedence_contract.md`。

### 3.2 CR2 — 0-9P-AUDIT verdict GREEN or documented YELLOW

- **Why it matters**：`feedback_budget_consumer.consume()` 對
  `attribution_verdict=RED` 強制回傳 `NON_ACTIONABLE` plan；CANARY 必
  須在 GREEN（或 documented YELLOW）窗內啟動，否則 dry-run plan 本身
  即被視為 misattributed 的 noise。
- **How it's verified**：
  ```
  python -m zangetsu.tools.profile_attribution_audit \
      --window 7d --emit-verdict
  # expect: verdict in {GREEN, YELLOW}; if YELLOW → limitation_reasons[] 必填
  ```
  Evidence package 引用最新一次 audit run 的 `verdict`、
  `limitation_reasons`、`mitigations`。
- **What blocks it**：verdict = RED；或 YELLOW 但缺 mitigations；或
  audit 過去 24h 未刷新（stale → 視同 UNAVAILABLE，不可作為 GREEN）。
- **Evidence path**：
  - tool：`zangetsu/tools/profile_attribution_audit.py`（PR #22, 3219b805）
  - dependency contract：`docs/recovery/20260424-mod-7/0-9r-impl-dry/04_attribution_audit_dependency.md`
- **Cross-ref**：0-9P-AUDIT `05_consumer_readiness_verdict.md`。

### 3.3 CR3 — 0-9R-IMPL-DRY complete

- **Why it matters**：CANARY 的 candidate “treatment” 行為由 PR-C 的
  consumer 模組產生；缺此模組或被改成 apply path → CANARY 失去 dry-run
  semantic baseline。
- **How it's verified**：
  ```
  test -f zangetsu/services/feedback_budget_consumer.py
  grep -q "MODE_DRY_RUN" zangetsu/services/feedback_budget_consumer.py
  pytest zangetsu/tests/test_feedback_budget_consumer.py -q
  # expect: all green; CONSUMER_VERSION exposed; SparseCandidateDryRunPlan
  # 28 fields per `01_dry_run_consumer_design.md`
  ```
- **What blocks it**：file 缺、tests 紅、`MODE_DRY_RUN` 被改、或 28-field
  schema 被縮減。
- **Evidence path**：
  - PR-C merge：`fe3075f`
  - report：`docs/recovery/20260424-mod-7/0-9r-impl-dry/09_0-9r_impl_dry_final_report.md`
  - module：`zangetsu/services/feedback_budget_consumer.py`
- **Cross-ref**：`01_dry_run_consumer_design.md`、`07_test_results.md`。

### 3.4 CR4 — No runtime apply path exists

- **Why it matters**：sparse intervention 一旦帶 apply path，CANARY 等
  同 production rollout；本 stack 全程禁止此狀態，必須以「runtime apply
  path == ∅」為前提發出 0-9S-CANARY。
- **How it's verified**：
  ```
  grep -rnE "apply_feedback_budget|apply_consumer_output|commit_plan" zangetsu/
  # expect: empty
  grep -rn "feedback_budget_consumer" zangetsu/services/ \
      | grep -v feedback_budget_consumer.py \
      | grep -v feedback_budget_allocator.py
  # expect: empty
  ```
  controlled-diff CI（0-9M）對 PR-D snapshot 必為 `EXPLAINED` 或
  `EXPLAINED_TRACE_ONLY`。
- **What blocks it**：runtime 中發現 apply hook（即使 disabled by flag），
  或 controlled-diff 出現 `UNEXPLAINED`。
- **Evidence path**：
  - audit doc：`docs/recovery/20260424-mod-7/0-9r-impl-dry/05_runtime_isolation_audit.md`
  - controlled-diff report：`docs/recovery/20260424-mod-7/0-9r-impl-dry/08_controlled_diff_report.md`
- **Cross-ref**：0-9R-IMPL-DRY `05_runtime_isolation_audit.md` §4「Apply-path absence」。

### 3.5 CR5 — Consumer has no runtime import path

- **Why it matters**：即使 apply 函式不存在，只要 runtime 模組 import
  consumer，未來不慎呼叫 `consume()` 即可能被誤接管 weights。
- **How it's verified**：
  ```
  grep -r "from zangetsu.services.feedback_budget_consumer" zangetsu/
  # expect: only zangetsu/tests/, scripts/offline/, docs/
  pytest zangetsu/tests/test_feedback_budget_consumer.py::test_no_runtime_import_by_arena -q
  pytest zangetsu/tests/test_feedback_budget_consumer.py::test_no_runtime_import_by_generation -q
  pytest zangetsu/tests/test_feedback_budget_consumer.py::test_no_runtime_import_by_execution -q
  pytest zangetsu/tests/test_feedback_budget_consumer.py::test_consumer_output_not_consumed_by_runtime -q
  ```
- **What blocks it**：generation runtime / Arena runtime / champion
  pipeline / execution / capital / risk 任一模組（含 transitively）出現
  consumer import。
- **Evidence path**：
  - tests 名單見 `05_runtime_isolation_audit.md` §2「Verified-by-test isolation」
  - allow-list：tests / offline / docs only。
- **Cross-ref**：0-9R-IMPL-DRY `05_runtime_isolation_audit.md` §1「Forbidden import direction」。

### 3.6 CR6 — Dry-run consumer ≥ 7 days stable OR j13 override

- **Why it matters**：CANARY 需基於穩定的 dry-run series 才能比較
  treatment/baseline；< 7 days 樣本量不足以區分 noise。
- **How it's verified**：
  ```
  psql -c "SELECT count(*), min(ts), max(ts)
           FROM feedback_decision_record_dry_run
           WHERE plan_status='ACTIONABLE_DRY_RUN'
             AND ts >= now() - interval '7 days';"
  # expect: count >= 7 distinct calendar days
  # expect: 0 unhandled exceptions in dry-run job log
  # expect: 0 G1–G13 violations (per 0-9R 04)
  ```
  Override 路徑：j13 顯式 Telegram 訊息或 commit footer
  `cr6_override=true`，evidence package 必須引用該訊息 SHA / ts。
- **What blocks it**：< 7 days 且無 override；或 EXPLORATION_FLOOR < 0.05
  / max-step 違反 / EMA reset → blocked，**不可** override。
- **Evidence path**：
  - `feedback_decision_record_dry_run` 表
  - dry-run job log（Calcifer monitored）
  - override letter（若用）：`docs/recovery/.../0-9s-canary-activation/j13_authorization.md`
- **Cross-ref**：0-9R-IMPL-DRY `03_smoothing_and_step_limit_contract.md`、
  0-9R 04 G1–G13。

### 3.7 CR7 — UNKNOWN_REJECT < 0.05 (cross-stage, 7-day rolling)

- **Why it matters**：UNKNOWN_REJECT 高 → A2/A3 metric 解釋力下降；
  CANARY success criteria（S1/S2/S3/S4）將被 noise 主導。consumer 內部
  亦對此設 veto（`UNKNOWN_REJECT_VETO`）。
- **How it's verified**：
  ```
  psql -c "SELECT date_trunc('day', ts) AS d,
                  sum(unknown_reject_count)::float / sum(entered_count) AS r
           FROM arena_batch_metrics
           WHERE ts >= now() - interval '7 days'
           GROUP BY 1 ORDER BY 1;"
  # expect: every r < 0.05
  ```
- **What blocks it**：任一單日 ≥ 0.05；7-day mean ≥ 0.05；taxonomy
  regression（0-9H/0-9I）尚未修復。
- **Evidence path**：
  - VIEW：`arena_batch_metrics`
  - Calcifer outcome watch：每 5 min poll，違反寫
    `/tmp/calcifer_deploy_block.json`
- **Cross-ref**：0-9R `05_ab_evaluation_and_canary_readiness.md` §6 S6、
  0-9R 04 G4、CLAUDE.md §17.3。

### 3.8 CR8 — A2 sparse rate trend measured

- **Why it matters**：S1（sparse rate decrease ≥ 20%）需要 baseline；
  缺 baseline → S1 無法判定 → CANARY 結論不可信。
- **How it's verified**：
  ```
  psql -c "SELECT date_trunc('day', ts) AS d,
                  median(signal_too_sparse_rate) AS m
           FROM arena_batch_metrics
           WHERE ts >= now() - interval '7 days'
           GROUP BY 1 ORDER BY 1;"
  # expect: 7 distinct days, each with >= 1 batch event
  ```
  baseline median + IQR 寫入 `baseline_snapshot.md`。
- **What blocks it**：< 7 distinct days、或 batch event missing、或
  P7-PR4B telemetry pipeline 異常。
- **Evidence path**：
  - VIEW：`arena_batch_metrics.signal_too_sparse_rate`
  - file：`docs/recovery/.../0-9s-canary-activation/baseline_snapshot.md`
- **Cross-ref**：P7-PR4B aggregate Arena pass-rate telemetry、
  0-9R `05_ab_evaluation_and_canary_readiness.md` §4「必要 metrics」。

### 3.9 CR9 — A3 pass_rate non-degradation evidence

- **Why it matters**：CANARY 重大失敗模式之一是 A2 通過率上升、A3 反
  而崩塌（F1）；無 baseline non-degradation 證據 → 無法區分 baseline
  本身已退化。
- **How it's verified**：
  ```
  psql -c "WITH a AS (
             SELECT date_trunc('day', ts) AS d,
                    median(a3_pass_rate) AS m
             FROM arena_batch_metrics
             WHERE ts >= now() - interval '14 days'
             GROUP BY 1)
           SELECT
             percentile_cont(0.5) WITHIN GROUP (ORDER BY m)
               FILTER (WHERE d >= now() - interval '7 days')   AS recent,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY m)
               FILTER (WHERE d <  now() - interval '7 days')   AS prior
           FROM a;"
  # expect: recent - prior >= -5 pp
  ```
- **What blocks it**：A3 過去 7 天較前 7 天下降 ≥ 5 pp absolute、或單日
  spike drop 未在 evidence 中標註 outlier。
- **Evidence path**：
  - VIEW：`arena_batch_metrics.a3_pass_rate`
  - Calcifer outcome watch（auto poll）。
- **Cross-ref**：0-9R 04 G2、0-9R `05_ab_evaluation_and_canary_readiness.md` F1。

### 3.10 CR10 — deployable_count non-degradation evidence

- **Why it matters**：`deployable_count` 為 §17.1 唯一「完成」定義；
  CANARY 啟動前 baseline 若已退化 → CANARY 後續任何 “improve” 評估都
  與 §17.4 auto-revert 冲突。
- **How it's verified**：
  ```
  psql -c "SELECT date_trunc('day', last_live_at) AS d, count(*) FILTER
           (WHERE status='DEPLOYABLE') AS deployable
           FROM champion_pipeline
           WHERE last_live_at >= now() - interval '14 days'
           GROUP BY 1 ORDER BY 1;"
  # rolling 7-day median: current >= prior
  # last_live_at_age_h <= 6 (per §17.3)
  ```
- **What blocks it**：rolling 7-day median 下降 ≥ 1、或 `last_live_at_age_h
  > 6` → 同步觸發 §17.3 RED + §17.4 watchdog。
- **Evidence path**：
  - VIEW：`zangetsu_status` / `champion_pipeline.status='DEPLOYABLE'`
  - Calcifer outcome watch（authoritative）
  - file：`/tmp/calcifer_deploy_block.json` 必須不存在
- **Cross-ref**：CLAUDE.md §17.1 / §17.3 / §17.4。

### 3.11 CR11 — Rollback plan documented

- **Why it matters**：CANARY 觸發 F1–F9 任一條 → 必須 hot-swap 回 baseline；
  rollback 文件缺、過時、或未端到端演練 → §17.4 auto-revert 與 j13 手動
  rollback 都無 SOP 可循。
- **How it's verified**：
  ```
  test -f docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md
  ```
  檔案需描述：trigger 條件、執行步驟、可逆性、24h review window、
  再啟動 prerequisite、rollback drill log（≥ 3 次成功演練）。
- **What blocks it**：文件缺、未通過 review、drill log < 3、或可逆性
  條件未列。
- **Evidence path**：
  - rollback plan：`docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md`
  - drill log：`docs/recovery/.../0-9s-canary-activation/rollback_drill_log.md`
- **Cross-ref**：0-9R `05_ab_evaluation_and_canary_readiness.md` §8、CR5（drill 演練）。

### 3.12 CR12 — Telegram / alert path defined

- **Why it matters**：CANARY 啟動後若 metric 退化，必須在分鐘級觸達
  j13；alert path 未定義 → §17.4 auto-revert 即便發生也無人感知。
- **How it's verified**：
  ```
  test -f docs/recovery/20260424-mod-7/0-9s-ready/04_alert_path.md
  ```
  檔案需涵蓋：trigger metric（CR7/CR9/CR10 + F1–F9）、message template、
  chat_id / thread_id、severity → action mapping。實際 wiring 在 0-9S
  activation order 中執行（PR-D 不打通）。
- **What blocks it**：alert 文件缺；severity table 缺 F-criterion；chat_id
  未對齊 §6 publish channel。
- **Evidence path**：
  - alert path：`docs/recovery/20260424-mod-7/0-9s-ready/04_alert_path.md`
- **Cross-ref**：CLAUDE.md §6（Telegram publish flow）、§17.3 Calcifer。

### 3.13 CR13 — Branch protection intact

- **Why it matters**：governance 層的最後防線；branch protection 弱化
  → unsigned commit / 手寫 version bump / skip CI 都成可能，CANARY 即
  失去 controlled-diff / version-bump-gate 的安全網。
- **How it's verified**：
  ```
  gh api repos/M116cj/j13-ops/branches/main/protection \
      | jq -S . > /tmp/main_protection.json
  diff -u docs/recovery/.../baseline/main_protection_baseline.json \
          /tmp/main_protection.json
  # expect: empty diff
  ```
  required_status_checks 名單必含：controlled-diff、version-bump-gate、
  decision-record-gate（§17.2 / §17.7）。
- **What blocks it**：diff 非空、required_status_checks 缺項、required
  approvals < baseline。
- **Evidence path**：
  - baseline：`docs/recovery/.../baseline/main_protection_baseline.json`
  - 即時 snapshot：`/tmp/main_protection.json`
- **Cross-ref**：CLAUDE.md §17.7 CI gate、§17.2 mandatory witness。

### 3.14 CR14 — Signed PR-only flow intact

- **Why it matters**：§17.5 規定 version bump 唯一路徑為
  `bin/bump_version.py`；違反即等同人類繞開 outcome metric 護欄。
- **How it's verified**：
  ```
  git log --since="30 days ago" --pretty=format:"%H %G?" main \
      | awk '$2 != "G" {print "UNSIGNED " $0}'
  # expect: empty
  git log --since="30 days ago" --pretty=format:"%s" main \
      | grep -E "^feat\([^)]+/v[0-9]" | wc -l
  # cross-check: each match has matching bin/bump_version.py invocation log
  ```
- **What blocks it**：偵測到未簽名 commit、手寫 `feat(<proj>/vN)`、或
  pre-receive regex 失效。
- **Evidence path**：
  - git log
  - `bin/bump_version.py` invocation log（CI artifact）
- **Cross-ref**：CLAUDE.md §17.2 / §17.5 / §17.7、`docs/decisions/20260419-*.md`。

### 3.15 CR15 — Explicit future j13 CANARY authorization recorded

- **Why it matters**：本檔案 / PR-D 並未取得 CANARY 授權；CR15 是 gate
  的 last lock —— 只有當 0-9S-CANARY activation order 出現、且 evidence
  package 引用 j13 顯式授權，才能視為 PASS。
- **How it's verified**：
  - 0-9S activation order 中存在 j13 認可訊息（Telegram thread 362 /
    signed commit footer / AKASHA witness 三選一），明確指定：生效
    SHA、treatment cohort、最大持續時間、rollback authority。
  - session 接手必驗 outcome metric，不繼承前人「done」（§17 +
    `feedback_session_discipline`）。
- **What blocks it**：未授權、過期授權（> 72 h 未啟動）、授權對應 SHA
  與當前 main HEAD 不一致。
- **Evidence path**：
  - `docs/recovery/.../0-9s-canary-activation/j13_authorization.md`
  - AKASHA witness（§17.2）
- **Cross-ref**：CLAUDE.md §4 Authority、§17.2 Mandatory witness、
  `feedback_session_discipline.md`。

---

## 4. CR satisfaction matrix（at PR-D 交付時）

| # | Criterion | Status | 備註 |
| --- | --- | --- | --- |
| CR1 | 0-9P attribution closure complete | Met | PR #21 / `a8a8ba9` merged |
| CR2 | 0-9P-AUDIT verdict GREEN or documented YELLOW | Pending evidence | audit run 須在 0-9S activation 前 24h 內刷新 |
| CR3 | 0-9R-IMPL-DRY complete | Met | PR #23 / `fe3075f` merged，tests 全綠 |
| CR4 | No runtime apply path exists | Met | controlled-diff `EXPLAINED`；grep 為空 |
| CR5 | Consumer has no runtime import path | Met | `05_runtime_isolation_audit.md` §2 tests 全綠 |
| CR6 | Dry-run consumer ≥ 7 days stable OR j13 override | Pending evidence | 待 dry-run job 累積 7 天綠燈 |
| CR7 | UNKNOWN_REJECT < 0.05 | Pending evidence | 7-day rolling 須 < 0.05；Calcifer poll |
| CR8 | A2 sparse rate trend measured | Pending evidence | baseline_snapshot.md 待產出 |
| CR9 | A3 pass_rate non-degradation evidence | Pending evidence | 14-day window 計算待補 |
| CR10 | deployable_count non-degradation evidence | Pending evidence | §17.1 VIEW 數據持續 monitor |
| CR11 | Rollback plan documented | Met（with this stack） | `03_rollback_plan.md` 同 stack 交付 |
| CR12 | Telegram / alert path defined | Met（with this stack） | `04_alert_path.md` 同 stack 交付 |
| CR13 | Branch protection intact | Met | baseline diff = 0 |
| CR14 | Signed PR-only flow intact | Met | 過去 30 天 100% signed |
| CR15 | Explicit future j13 CANARY authorization recorded | Pending j13 | 須 TEAM ORDER 0-9S-CANARY 才能 flip |

> **Status legend**：Met = 已通過 / Pending j13 = 等待 j13 授權 /
> Pending evidence = 等待時間或 baseline 累積 / N/A = 不適用。

---

## 5. Gate evaluation rule

CR1–CR15 為 **all-pass gate**：任何單一 criterion 為 FAIL → 0-9S
CANARY activation order **不可發出**。CR2 為 YELLOW 時，可在 evidence
package 中以 documented limitation + mitigations 通過，但：

- limitation 必須具體（例：「單一 regime 樣本不足，僅 bull / range」）。
- mitigations 必須 actionable（例：提早觸發 rollback、縮短 CANARY 視窗、
  強制每日 j13 review）。
- 任何其他 CR 不適用此 YELLOW override（只 CR2 享有）。

Evaluation cadence：

- 0-9S activation order 草稿前 → 跑一次完整 CR1–CR15 check。
- Calcifer outcome watchdog 每 5 min 對 CR7 / CR9 / CR10 自動 poll；
  違反即寫 `/tmp/calcifer_deploy_block.json` → 後續 commit / activation
  自動 RED。
- Governance（j13 + Lead）每週對 CR2 / CR11 / CR12 / CR13 / CR14 做
  人為 review。

未來 0-9S-CANARY activation order 的 evidence package 結構（建議）：

```
docs/recovery/.../0-9s-canary-activation/
├── evidence_package.md       # CR1–CR15 逐項勾選 + 證據連結
├── baseline_snapshot.md      # 對應 CR8 / CR9 / CR10 的數值
├── j13_authorization.md      # 對應 CR15 的授權紀錄（含 SHA / ts）
└── rollback_drill_log.md     # rollback 端到端演練紀錄（CR11 補強）
```

PR-D 至此交付完畢；CR15 仍 Pending j13。0-9S-CANARY 由 j13 顯式下單後
另行啟動，活化 runtime apply path 之前必先重跑此 gate。
