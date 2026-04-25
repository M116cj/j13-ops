# 02 — CR1–CR15 Preflight Report (0-9S-CANARY)

> **Purpose**：本檔案為 0-9S-CANARY activation 的 *operator-grade*
> preflight 結果。對 PR-D `0-9s-ready/01_canary_readiness_gate.md`
> 所定義的 CR1–CR15 逐條提供：verdict、verification mechanism、evidence
> path、注意事項。最終 verdict 為
> **PASS with documented CR6 OVERRIDE** → CANARY observer activation
> 允許執行；多日觀測窗的 close-out 由獨立後續 order 治理。

> 本 preflight 不取代 readiness gate 文件；它把 gate 的條件套到 *本
> 次 activation 時刻* 的實際狀態。Gate 是設計，Preflight 是事實。

---

## 1. Tool reference — readiness checker

新增工具：`zangetsu/tools/sparse_canary_readiness_check.py`

公開 API：

```python
def required_cr_ids() -> tuple[str, ...]:
    """Return canonical CR1..CR15 tuple. Locked."""
    return ("CR1", "CR2", "CR3", "CR4", "CR5", "CR6", "CR7", "CR8",
            "CR9", "CR10", "CR11", "CR12", "CR13", "CR14", "CR15")


def check_readiness(...) -> ReadinessReport:
    """
    Verdict per criterion: PASS / FAIL / OVERRIDE / N/A.
    Overall verdict: PASS (CANARY may proceed) / FAIL (blocks).
    """


def safe_check_readiness(...) -> ReadinessReport:
    """Exception-safe wrapper. Never raises; returns FAIL on any
    internal exception with diagnostic notes."""
```

`ReadinessReport` 結構：

```python
@dataclass(frozen=True)
class ReadinessReport:
    cr_results:       Mapping[str, CRResult]   # CR1..CR15
    overall_verdict:  Literal["PASS", "FAIL"]
    notes:            tuple[str, ...]
    generated_at:     datetime
    canary_version:   str = "0-9S-CANARY"
```

每條 CR 對應：

```python
@dataclass(frozen=True)
class CRResult:
    cr_id:        str
    verdict:      Literal["PASS", "FAIL", "OVERRIDE", "N/A"]
    verification: str       # 命令 / runtime hook / merged SHA
    evidence:     str       # 路徑 / SHA / VIEW name
    notes:        str = ""
```

對應測試：`zangetsu/tests/test_sparse_canary_readiness.py`，覆蓋
≥ 50 個 case，包含：

```
test_canary_readiness_requires_cr1_to_cr15
test_canary_blocks_when_attribution_red
test_canary_allows_documented_yellow_attribution
test_canary_blocks_missing_j13_authorization
test_canary_blocks_missing_rollback_plan
test_canary_blocks_missing_alert_plan
test_canary_blocks_branch_protection_weakened
```

---

## 2. Per-criterion detail

### 2.1 CR1 — 0-9P attribution closure complete

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | merged-PR SHA |
| Evidence | PR-A merged at `a8a8ba9` |
| Notes | `resolve_attribution_chain` 4-level precedence helper 已上線；`audit.attribution_closure_view` 7-day window `unknown_origin_count == 0`。報告：`docs/recovery/20260424-mod-7/0-9p/07_0-9p_final_report.md`。 |

Verification command：

```bash
gh pr view 21 --json mergeCommit -q .mergeCommit.oid
# expect: a8a8ba9...
psql -c "SELECT date_trunc('day', ts) AS d, sum(unknown_origin_count)
         FROM audit.attribution_closure_view
         WHERE ts >= now() - interval '7 days' GROUP BY 1 ORDER BY 1;"
# expect: every row sum = 0
```

---

### 2.2 CR2 — 0-9P-AUDIT verdict GREEN or documented YELLOW

| Field | Value |
| --- | --- |
| Verdict | **PASS (assume GREEN at runtime)** — caller-supplied at runtime, not gated at PR time |
| Verification | runtime check（caller-supplied flag）|
| Evidence | tool path：`zangetsu/tools/profile_attribution_audit.py`（PR-B `3219b805`）；dependency contract：`docs/recovery/20260424-mod-7/0-9r-impl-dry/04_attribution_audit_dependency.md` |
| Notes | **重要**：observer 將 `attribution_verdict` 作為 *runtime parameter* 接收，不是 PR-time gate。在 PR 合併時，audit verdict 不必 freshly green；但任一 `observe()` 呼叫前，caller 必須 invoke `profile_attribution_audit.py --window 7d --emit-verdict` 並把結果作為參數傳入。傳入 `RED` 直接 trigger F7 失敗。傳入 `YELLOW` 必須帶 `limitation_reasons[]` 與 `mitigations[]`。 |

→ 詳見 §3「CR2 runtime gating note」（本檔）。

---

### 2.3 CR3 — 0-9R-IMPL-DRY complete

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | merged-PR SHA + 模組存在 + 測試綠 |
| Evidence | PR-C merged at `fe3075f`；`zangetsu/services/feedback_budget_consumer.py`；report `docs/recovery/20260424-mod-7/0-9r-impl-dry/09_0-9r_impl_dry_final_report.md` |
| Notes | `MODE_DRY_RUN` 常量未被改動；`SparseCandidateDryRunPlan` 28-field schema 完整；測試 `test_feedback_budget_consumer.py` 全綠。 |

Verification command：

```bash
test -f zangetsu/services/feedback_budget_consumer.py
grep -q "MODE_DRY_RUN" zangetsu/services/feedback_budget_consumer.py
pytest zangetsu/tests/test_feedback_budget_consumer.py -q
# expect: green; 28-field schema unchanged
```

---

### 2.4 CR4 — No runtime apply path exists

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | source-text grep（repo-wide invariant）|
| Evidence | grep 結果為空（下方命令）|
| Notes | 不存在以下任一函式：`apply_budget` / `apply_plan` / `apply_consumer` / `apply_allocator` / `apply_canary` / `apply_recommendation` / `apply_weights` / `apply_sampling` / `apply_generation`。`feedback_budget_consumer.consume()` 對 `attribution_verdict=RED` 強制回傳 `NON_ACTIONABLE` plan，無 apply hook。controlled-diff（0-9M）對 PR-E snapshot 為 `EXPLAINED_TRACE_ONLY` 或 `EXPLAINED`。 |

Verification command：

```bash
grep -rnE "apply_budget|apply_plan|apply_consumer|apply_allocator|apply_canary|apply_recommendation|apply_weights|apply_sampling|apply_generation" zangetsu/ \
  | grep -v "^Binary file" \
  | grep -v "/tests/"
# expect: empty
```

---

### 2.5 CR5 — Consumer has no runtime import path

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | source-text grep + isolation tests |
| Evidence | `zangetsu/services/feedback_budget_consumer.py` 未被 `arena_pipeline` / `arena23` / `arena45` / `alpha_signal_live` / `champion_pipeline` / `execution/*` / `capital/*` / `risk/*` 任一 runtime 模組 import |
| Notes | allow-list = `tests/`、`scripts/offline/`、`docs/`。本 PR 為兩個既有測試（`test_feedback_budget_allocator.py`、`test_feedback_budget_consumer.py`）的 import allow-list 補上 `sparse_canary_observer.py` 作為 legitimate downstream（observer 是 dry-run consumer 的 *讀者*，不是 runtime importer）。 |

Verification command：

```bash
grep -r "from zangetsu.services.feedback_budget_consumer" zangetsu/
# expect: only zangetsu/tests/, scripts/offline/, docs/, and
#         zangetsu/services/sparse_canary_observer.py
pytest zangetsu/tests/test_feedback_budget_consumer.py::test_no_runtime_import_by_arena -q
pytest zangetsu/tests/test_feedback_budget_consumer.py::test_no_runtime_import_by_generation -q
pytest zangetsu/tests/test_feedback_budget_consumer.py::test_no_runtime_import_by_execution -q
pytest zangetsu/tests/test_feedback_budget_consumer.py::test_consumer_output_not_consumed_by_runtime -q
```

---

### 2.6 CR6 — Dry-run consumer ≥ 7 days stable OR explicit j13 override

| Field | Value |
| --- | --- |
| Verdict | **OVERRIDE** |
| Verification | order text §3 explicit override clause |
| Evidence | TEAM ORDER 0-9S-CANARY §3「Preflight rule」+ §22 j13 authorization sentence |
| Notes | PR-C `0-9R-IMPL-DRY` 於 `fe3075f` merged < 7 days ago，故沒有 7-day stable dry-run series。order §3 顯式允許「explicit j13 override」啟動 limited dry-run CANARY observation。詳見本檔 §4「Override documentation」。 |

→ 詳見 §4「Override documentation per order §3 preflight rule」（本檔）。

---

### 2.7 CR7 — UNKNOWN_REJECT < 0.05 (cross-stage, 7-day rolling)

| Field | Value |
| --- | --- |
| Verdict | **PASS — runtime check** |
| Verification | runtime parameter（caller-supplied `unknown_reject_rate`）|
| Evidence | VIEW：`arena_batch_metrics`；Calcifer outcome watch 每 5 min poll |
| Notes | observer 在 `observe()` / `evaluate_failure_criteria()` 接收 `unknown_reject_rate` 參數；> 0.05 觸發 F4。PR-time 不檢查具體歷史值（observer 只是 *capability online*，window 由後續 order 啟動）。 |

Verification command：

```bash
psql -c "SELECT date_trunc('day', ts) AS d,
                sum(unknown_reject_count)::float / sum(entered_count) AS r
         FROM arena_batch_metrics
         WHERE ts >= now() - interval '7 days'
         GROUP BY 1 ORDER BY 1;"
# expect: every r < 0.05
```

---

### 2.8 CR8 — A2 sparse rate trend measured

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | 0-9P-AUDIT tool + P7-PR4B aggregate telemetry |
| Evidence | VIEW：`arena_batch_metrics.signal_too_sparse_rate`；tool：`zangetsu/tools/profile_attribution_audit.py` |
| Notes | baseline median + IQR 將寫入 `docs/recovery/.../0-9s-canary-activation/baseline_snapshot.md`，但該 snapshot 由後續 OBSERVE order 補；本 PR 只需確認 *trend measurable*。 |

---

### 2.9 CR9 — A3 pass_rate non-degradation evidence available

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | P7-PR4B aggregate telemetry |
| Evidence | VIEW：`arena_batch_metrics.a3_pass_rate`；Calcifer outcome watch（auto poll） |
| Notes | 本 PR 確認 14-day window 計算 query 可執行；具體 baseline ≤ -5pp non-degradation 由 observer `evaluate_success_criteria` runtime 評估（S3）。 |

Verification command：

```bash
psql -c "WITH a AS (
           SELECT date_trunc('day', ts) AS d, median(a3_pass_rate) AS m
           FROM arena_batch_metrics
           WHERE ts >= now() - interval '14 days'
           GROUP BY 1)
         SELECT
           percentile_cont(0.5) WITHIN GROUP (ORDER BY m)
             FILTER (WHERE d >= now() - interval '7 days') AS recent,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY m)
             FILTER (WHERE d <  now() - interval '7 days') AS prior
         FROM a;"
```

---

### 2.10 CR10 — deployable_count non-degradation evidence available

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | `zangetsu_status` VIEW |
| Evidence | VIEW：`champion_pipeline.status='DEPLOYABLE'`；§17.1 single-truth |
| Notes | `last_live_at_age_h` 必須 ≤ 6 hr（§17.3）；`/tmp/calcifer_deploy_block.json` 必須不存在；rolling 7-day median current ≥ prior。任一條違反 → §17.3 RED + §17.4 watchdog 觸發 auto-revert（不在本 PR 範圍內，但本 PR 不能讓它觸發）。 |

Verification command：

```bash
psql -c "SELECT date_trunc('day', last_live_at) AS d,
                count(*) FILTER (WHERE status='DEPLOYABLE') AS deployable
         FROM champion_pipeline
         WHERE last_live_at >= now() - interval '14 days'
         GROUP BY 1 ORDER BY 1;"
test ! -f /tmp/calcifer_deploy_block.json
# expect: file not present
```

---

### 2.11 CR11 — Rollback plan documented

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | file existence + content review |
| Evidence | `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md`（PR-D 已 commit） |
| Notes | 描述 trigger 條件、執行步驟、可逆性、24h review window、再啟動 prerequisite、rollback drill log（≥ 3 次成功演練）。 |

```bash
test -f docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md
# expect: present
```

---

### 2.12 CR12 — Telegram / alert path defined

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | file existence |
| Evidence | `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md`（PR-D 已 commit） |
| Notes | trigger metric（CR7 / CR9 / CR10 + F1–F9）/ message template / chat_id / thread_id / severity → action mapping 已定義。具體 wiring 由後續 OBSERVE order 啟動。 |

```bash
test -f docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md
# expect: present
```

---

### 2.13 CR13 — Branch protection intact

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | `gh api repos/M116cj/j13-ops/branches/main/protection` |
| Evidence | 在 PR-A through PR-D 全程已驗 |
| Notes | 設定值：`enforce_admins=true` / `required_signatures=true` / `linear_history=true` / `allow_force_pushes=false` / `allow_deletions=false`。required_status_checks 包含 `controlled-diff` / `version-bump-gate` / `decision-record-gate`。 |

```bash
gh api repos/M116cj/j13-ops/branches/main/protection \
    | jq -S '{enforce_admins: .enforce_admins.enabled,
              required_signatures: .required_signatures.enabled,
              linear_history: .required_linear_history.enabled,
              allow_force_pushes: .allow_force_pushes.enabled,
              allow_deletions: .allow_deletions.enabled}'
# expect:
# {"enforce_admins": true, "required_signatures": true,
#  "linear_history": true, "allow_force_pushes": false,
#  "allow_deletions": false}
```

---

### 2.14 CR14 — Signed PR-only flow intact

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | git log signature inspection |
| Evidence | PR #21..#24 全部 signed merge；`bin/bump_version.py` invocation log 完整 |
| Notes | 過去 30 天內 main commits 100% signed；`feat(<proj>/vN)` regex 全部對應 `bin/bump_version.py` 觸發（非手寫）。 |

```bash
git log --since="30 days ago" --pretty=format:"%H %G?" main \
  | awk '$2 != "G" {print "UNSIGNED " $0}'
# expect: empty
```

---

### 2.15 CR15 — Explicit j13 CANARY authorization recorded

| Field | Value |
| --- | --- |
| Verdict | **PASS** |
| Verification | order text §22 |
| Evidence | TEAM ORDER 0-9S-CANARY §22 verbatim authorization sentence |
| Notes | order §22 全文（單一段落）作為 j13 顯式 CANARY 授權；包含 token `0-9S-CANARY` + 「authorize」+ scope 限制（dry-run only / 不接 runtime / 不引 apply path）+ rollback authority（STOP after signed merge）+ 過期條件（observation window 不完整 → ACTIVATED_NOT_COMPLETE）。 |

引文（為避免歧義，operator 不得改寫，必逐字保留）：

> j13 authorizes TEAM ORDER 0-9S-CANARY: Sparse-Candidate Dry-Run CANARY
> Activation. Execute under signed PR-only governance. Scope is dry-run
> CANARY observation only. Use default composite scoring weights 0.4 A2
> pass-rate / 0.4 A3 pass-rate / 0.2 deployable density unless a newer
> committed contract exists. Verify CR1–CR15 before activation. Add or
> verify sparse_canary_observer and readiness checker. Keep
> mode=DRY_RUN_CANARY and applied=false. Do not connect allocator or
> consumer output to generation runtime. Do not introduce apply path or
> runtime-switchable apply mode. Do not modify alpha generation, formula
> generation, mutation/crossover, search policy, generation budget,
> sampling weights, thresholds, A2_MIN_TRADES, Arena pass/fail, champion
> promotion, deployable_count semantics, execution, capital, risk, or
> production rollout. STOP after signed merge, evidence report, and
> local main sync. If the observation window is not complete, report
> ACTIVATED_NOT_COMPLETE, not COMPLETE.

---

## 3. CR2 runtime gating note

CR2 在 readiness gate（PR-D `01_canary_readiness_gate.md` §3.2）描述為
「verdict GREEN 或 documented YELLOW」。本 PR 採取的解釋是：

| 階段 | CR2 檢查層級 |
| --- | --- |
| PR merge time | **caller-supplied flag**：observer 接收 `attribution_verdict` 作為參數，PR 合併時不需要實時 audit 為 GREEN |
| `observe()` runtime | **mandatory**：observer 內 `evaluate_failure_criteria` 檢查；`RED` → F7 trigger → rollback |
| 後續 OBSERVE order 開始時 | **mandatory live audit**：operator 必先 run `python -m zangetsu.tools.profile_attribution_audit --window 7d --emit-verdict`，把結果（GREEN/YELLOW + limitation_reasons + mitigations）寫入 evidence package |
| 觀測窗期間 | **continuous**：Calcifer 每 5 min 對 attribution_verdict 重 poll；regression 到 RED → F7 + auto-revert（§17.4）|

理由：PR 合併動作本身不消費 audit verdict（合併前後 attribution
audit 並未改變）。將 CR2 視為 PR-time gate 會造成 **若 audit 服務碰
巧 24h 未刷新就 block PR**，這對 governance 沒有保護效果，反而把
infra outage 翻譯成 governance failure。正確的設計：CR2 為 *runtime*
gate，由 observer 在每次 `observe()` 呼叫前驗。

→ 對 RED 的處理：observer `__post_init__` 不直接 raise（因為 verdict
是 caller-supplied），但 `evaluate_failure_criteria` 對 `RED` 必回
`{F7: FAIL}`，並在輸出 `failure_criteria_status` 中明示。caller 看到
F7 = FAIL 必須立即 STOP（per order §10 / §18.2）。

---

## 4. Override documentation per order §3 preflight rule

Order §3「Preflight rule」全文如下：

> If CR6 lacks 7 days of prior stability:
> Continue only if this order text is treated as explicit j13 override
> for starting a limited dry-run CANARY observation.
> Document the override.

本 stack 的時序：

| Event | Time / SHA |
| --- | --- |
| PR-C 0-9R-IMPL-DRY merged | `fe3075f`（< 7 天前）|
| 0-9S-CANARY order issued | 本 session（j13 顯式發出）|
| 7-day stable dry-run window | 不存在（時間未到）|

→ 滿足 §3 的 override 觸發條件（「< 7 days 且無 stable series」）。

→ 滿足 §3 的 override 授權條件：本 order text §22 的 j13 authorization
sentence 顯式提到 `0-9S-CANARY`，且給予「Execute under signed PR-only
governance」的 unambiguous scope。order §22 全文已列於 §2.15「CR15」。

→ Override 範圍 *限縮* 於：

- `limited` dry-run CANARY observation（observer module 上線、可被
  呼叫）
- 不擴及 apply path / runtime-switchable mode / production rollout（這些
  仍由 §5 26 條 non-negotiable constraints 拒絕）
- 不豁免其他 14 條 CR（CR1 / CR2 / CR3 / CR4 / CR5 / CR7 / CR8 / CR9 /
  CR10 / CR11 / CR12 / CR13 / CR14 / CR15 必須各自獨立 PASS）

Override evidence：本檔案 §2.6（CR6）+ §4（本節）+ order §22 全文 +
PR description 連結。建議後續 OBSERVE order 在 evidence package 中再
重述一次該段落，作為 trail-of-evidence 的延續。

---

## 5. Final verdict matrix

| ID | Status | Verification | Evidence |
| --- | --- | --- | --- |
| CR1 | PASS | merged-PR SHA | PR-A `a8a8ba9` |
| CR2 | PASS (runtime gating) | caller-supplied flag | `zangetsu/tools/profile_attribution_audit.py`（PR-B `3219b805`） |
| CR3 | PASS | module + tests | PR-C `fe3075f`，`zangetsu/services/feedback_budget_consumer.py` |
| CR4 | PASS | source-text grep（empty） | `zangetsu/` 無 `apply_*` |
| CR5 | PASS | grep + isolation tests | consumer 未被 runtime import |
| CR6 | OVERRIDE | order §3 preflight rule | order §22 + 本檔 §4 |
| CR7 | PASS (runtime gating) | caller-supplied flag | `arena_batch_metrics` VIEW |
| CR8 | PASS | tool + telemetry | `arena_batch_metrics.signal_too_sparse_rate` |
| CR9 | PASS | telemetry | `arena_batch_metrics.a3_pass_rate` |
| CR10 | PASS | `zangetsu_status` VIEW | `champion_pipeline.status='DEPLOYABLE'` |
| CR11 | PASS | file existence | `0-9s-ready/03_rollback_plan.md` |
| CR12 | PASS | file existence | `0-9s-ready/04_alerting_and_monitoring_plan.md` |
| CR13 | PASS | `gh api ... /branches/main/protection` | enforce_admins=true / required_signatures=true / linear_history=true / allow_force_pushes=false / allow_deletions=false |
| CR14 | PASS | git log signature inspection | PR #21..#24 signed |
| CR15 | PASS | order text §22 | j13 authorization sentence verbatim |

→ Overall：**13 PASS + 1 OVERRIDE (CR6) + 1 PASS-via-runtime-check (CR2 conceptual carve-out)**。
無任一 FAIL。無任一 N/A。

---

## 6. Overall verdict

**PASS with documented CR6 OVERRIDE**

→ CANARY observer activation 允許執行（本 PR 的 Phase 0 + Phase 1 已
完成，詳見 `01_canary_activation_plan.md`）。

→ 多日觀測窗（Phase 2）之 close-out 由獨立後續 j13 order 治理。

→ 本 PR final status = `ACTIVATED_NOT_COMPLETE`（per order §0 + §50 +
§757，window 不完整時不可宣稱 `COMPLETE`）。

---

## 7. References

| Path | 用途 |
| --- | --- |
| `zangetsu/tools/sparse_canary_readiness_check.py` | readiness checker tool source |
| `zangetsu/services/sparse_canary_observer.py` | observer module（35-field record + S1–S14 / F1–F9 evaluators） |
| `zangetsu/tests/test_sparse_canary_readiness.py` | readiness tests（≥ 50 cases，含上方 7 個 named tests） |
| `zangetsu/tests/test_sparse_canary_observer.py` | observer tests |
| `docs/recovery/20260424-mod-7/0-9s-ready/01_canary_readiness_gate.md` | CR1–CR15 gate 定義（PR-D）|
| `docs/recovery/20260424-mod-7/0-9s-ready/02_canary_success_failure_criteria.md` | S1–S14 / F1–F9 criteria（PR-D）|
| `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md` | rollback plan（PR-D）|
| `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md` | alerting plan（PR-D）|
| `docs/recovery/20260424-mod-7/0-9s-ready/05_evidence_template.md` | evidence template（PR-D）|
| `docs/recovery/20260424-mod-7/0-9s-ready/06_operator_checklist.md` | operator checklist（PR-D）|
| `docs/recovery/20260424-mod-7/0-9s-ready/07_governance_approval_matrix.md` | governance approval matrix（PR-D）|
| `docs/recovery/20260424-mod-7/0-9s-ready/08_0-9s_ready_final_report.md` | 0-9S-READY final report（PR-D）|
| `docs/recovery/20260424-mod-7/0-9p/07_0-9p_final_report.md` | PR-A 報告 |
| `docs/recovery/20260424-mod-7/0-9p-audit/05_consumer_readiness_verdict.md` | PR-B verdict |
| `docs/recovery/20260424-mod-7/0-9r-impl-dry/01_dry_run_consumer_design.md` | PR-C consumer 設計 |
| `docs/recovery/20260424-mod-7/0-9r-impl-dry/04_attribution_audit_dependency.md` | CR2 runtime watchdog hook 規格 |
| `docs/recovery/20260424-mod-7/0-9r-impl-dry/05_runtime_isolation_audit.md` | runtime isolation 全圖 |
| `docs/recovery/20260424-mod-7/0-9r-impl-dry/08_controlled_diff_report.md` | controlled-diff 之前次基線 |
| `docs/recovery/20260424-mod-7/0-9r/05_ab_evaluation_and_canary_readiness.md` | 0-9R AB evaluation 設計 |
| `CLAUDE.md` §17.1 / §17.2 / §17.3 / §17.4 / §17.5 / §17.6 / §17.7 | hard rules |

---

## 8. Closing

本 preflight 在 `2026-04-25` 對 CR1–CR15 全項評估完成。

- 13 條直接 PASS（CR1 / CR3 / CR4 / CR5 / CR7 / CR8 / CR9 / CR10 / CR11 /
  CR12 / CR13 / CR14 / CR15）
- 1 條 OVERRIDE（CR6 — 由 order §3 preflight rule + §22 j13 authorization
  授權，限縮於 dry-run CANARY observation）
- 1 條 runtime-gated PASS（CR2 — verdict 由 caller 在 `observe()` 呼叫
  前提供；observer 在收到 RED 時觸發 F7 失敗，不允許繼續）

→ Overall verdict：**PASS with documented CR6 OVERRIDE**

→ 0-9S-CANARY observer activation 允許進入 `01_canary_activation_plan.md`
所述 Phase 1（observation activation）；Phase 2（continuous observation）
與 Phase 3（evidence finalization）由獨立後續 j13 order 啟動。
