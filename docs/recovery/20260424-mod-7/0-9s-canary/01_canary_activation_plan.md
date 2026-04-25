# 01 — CANARY Activation Plan (0-9S-CANARY)

> **Stack position / 在哪一層**：本檔案隸屬 PR-E `0-9S-CANARY` —
> 緊接 `0-9S-READY (PR-D, 0d7f67d)` 之後的第一個 *runtime-touching*
> 交付。它不是 design 文件、不是 readiness gate；它定義 **本次 PR
> 真正啟動了什麼，以及刻意沒啟動什麼**。所有「activate」一詞在本檔
> 裡都指 **observer module 上線可被呼叫**，而非 apply path 或 runtime
> 接管。違反此語意 = 違反 §5。

---

## 1. Mission statement（順從 §1.1 原文）

引自 TEAM ORDER 0-9S-CANARY §1.1（verbatim quote）：

> Activate a dry-run CANARY that continuously evaluates sparse-candidate
> optimization recommendations against live or near-live Arena telemetry
> **without applying those recommendations**. The CANARY should produce
> evidence about whether SIGNAL_TOO_SPARSE is decreasing, A2 pass_rate
> improves, A3 pass_rate remains stable, OOS_FAIL remains controlled,
> deployable_count is maintained or improved, UNKNOWN_REJECT remains
> below 0.05, profile allocation remains diversified, dry-run consumer
> output remains stable.

中文重述（以利 j13 review，**不取代上方原文**）：

啟動一個 *dry-run* CANARY，連續觀測 sparse-candidate 建議在 live /
near-live Arena 遙測下「**如果套用會發生什麼**」，但 **不真的套用**。
CANARY 只記錄、只計算、只輸出 evidence。它對 generation runtime、
Arena pass/fail、champion promotion、execution / capital / risk 完全
被動。

> 任何將本檔案理解為「先 partial apply、再 evidence」的解讀都是錯的。
> 三層 invariant（§3 / §4 / §6.1 of order）已在 module 層硬性鎖死：
> `mode == "DRY_RUN_CANARY"` / `applied == False` / `canary_version ==
> "0-9S-CANARY"`，違反三者中任一，`SparseCandidateObservation.__post_init__`
> 直接 raise，因此即使有人寫錯 caller 也無法繞開。

---

## 2. Scope boundary — 不可碰的明確列表（cite §5 of order）

下表列出 §5「Global non-negotiable constraints」的全部 26 項。本 PR
*所有* 變更必須位於此表 **左邊「Allowed」欄**，碰到右邊任一項即 STOP。

| # | Forbidden surface（§5 編號） | 對應 module / file path |
| --- | --- | --- |
| §5.1 | alpha generation behavior | `zangetsu/services/alpha_generator*.py` |
| §5.2 | formula generation behavior | `zangetsu/services/formula_*.py` |
| §5.3 | mutation / crossover behavior | `zangetsu/services/mutation_engine.py`, `crossover_engine.py` |
| §5.4 | search policy behavior | `zangetsu/services/search_policy.py` |
| §5.5 | real generation budget | `config/generation_budget*.yaml` |
| §5.6 | sampling weights | `config/sampling_weights*.yaml`, `zangetsu/services/sampling_*.py` |
| §5.7 | thresholds | `config/thresholds.yaml` |
| §5.8 | `A2_MIN_TRADES` | `zangetsu/services/arena_a2.py`（值固定 25）|
| §5.9 | A3 thresholds | `zangetsu/services/arena_a3.py` |
| §5.10 | Arena pass/fail branch conditions | `zangetsu/services/arena_pipeline.py` |
| §5.11 | rejection semantics | `zangetsu/services/rejection_taxonomy.py` |
| §5.12 | champion promotion | `zangetsu/services/champion_pipeline.py` |
| §5.13 | `deployable_count` semantics | `champion_pipeline.status='DEPLOYABLE'` VIEW |
| §5.14 | execution logic | `zangetsu/services/execution/*.py` |
| §5.15 | capital allocation | `zangetsu/services/capital/*.py` |
| §5.16 | risk controls | `zangetsu/services/risk/*.py` |
| §5.17 | production rollout | n/a — 本 order 禁止觸發 |
| §5.18 | branch protection | governance, `gh api ... /branches/main/protection` |
| §5.19 | signed PR-only flow | §17.5 `bin/bump_version.py` |
| §5.20 | controlled-diff | `.github/workflows/controlled-diff.yml` |
| §5.21 | full per-alpha lineage | n/a — 不引入 |
| §5.22 | formula explainability | n/a — 不要求 |
| §5.23 | apply path | 無 `apply_*` 函式（CR4 grep 為空）|
| §5.24 | runtime-switchable DRY_RUN/APPLY flag | 無 mode switch 變數 |
| §5.25 | consumer output → generation runtime | CR5 import isolation |
| §5.26 | CANARY 修改 live strategy 行為 | 三層 invariant lock |

> 上述全部 26 項 = 本 PR **forbidden surface**。
> 本 PR 的 commit 範圍只允許 4 處：
> - `zangetsu/services/sparse_canary_observer.py`（新增）
> - `zangetsu/tools/sparse_canary_readiness_check.py`（新增）
> - `zangetsu/tests/test_sparse_canary_observer.py` + `test_sparse_canary_readiness.py`（新增）
> - `zangetsu/tests/test_feedback_budget_allocator.py` + `test_feedback_budget_consumer.py`（既有測試的 allow-list 擴充，承認 `sparse_canary_observer.py` 為 legitimate downstream）
> - `docs/recovery/20260424-mod-7/0-9s-canary/*.md`（本目錄全部 docs）

---

## 3. Activation phases

| Phase | 名稱 | 範圍 | 本 PR 是否完成 | 觸發條件 |
| --- | --- | --- | --- | --- |
| Phase 0 | Preflight | CR1–CR15 verification + observer module + readiness checker + tests | ✅ 本 PR 完成 | order §3 / §15.5–15.10 |
| Phase 1 | Observation activation | branch + signed commit + Gate-A/B + admin merge + main sync | ✅ 本 PR 完成 | order §15.11–15.22 |
| Phase 2 | Continuous observation | multi-day observation window；定期呼叫 `observe()`；evidence 累積；S1–S14 / F1–F9 持續評估 | ❌ 本 PR 不完成 | **必須有獨立 j13 order**（建議命名 `TEAM ORDER 0-9S-CANARY-OBSERVE`）|
| Phase 3 | Evidence finalization | composite score 終局評估；S1–S14 / F1–F9 verdict close-out；recommendation report；下一階段 governance order（0-9T-PREP / production prep）建議 | ❌ 本 PR 不完成 | **必須有獨立 j13 order** |

### Phase 0 – Preflight（本 PR）

- 跑 `sparse_canary_readiness_check.check_readiness(...)` 對 CR1–CR15 全
  項評估。
- 結果（詳見 `02_cr1_cr15_preflight_report.md`）：
  - 13 PASS, 1 OVERRIDE (CR6), 1 PASS-via-runtime-check (CR2)
  - Overall verdict = **PASS with documented CR6 OVERRIDE**
- 任一 CR FAIL → STOP（per order §18 的 28 條 STOP 條件）。

### Phase 1 – Observation activation（本 PR）

- branch：`phase-7/0-9s-canary-dry-run-activation`
- 新增 module：`zangetsu/services/sparse_canary_observer.py`（~600 LOC）
  - `SparseCanaryObservation` dataclass，35 fields，
    `required_observation_fields()` lock。
  - `observe()` / `safe_observe()` / `serialize_observation()`。
  - `compute_composite_score(a2, a3, deploy, w_a2=0.4, w_a3=0.4, w_deploy=0.2)`。
  - `compute_deployable_density()` / `compute_profile_diversity()` /
    `detect_profile_collapse()` / `compute_consumer_plan_stability()`。
  - `evaluate_success_criteria(...)` → `{S1..S14: PASS|FAIL|INSUFFICIENT_HISTORY}`。
  - `evaluate_failure_criteria(...)` → `{F1..F9: PASS|FAIL}`。
  - `CanaryBaseline` dataclass for delta-style criteria。
- 新增 tool：`zangetsu/tools/sparse_canary_readiness_check.py`
  - `check_readiness(...)` → `ReadinessReport`，覆蓋 CR1–CR15。
  - `safe_check_readiness(...)`（exception-safe wrapper）。
  - `required_cr_ids()` → `("CR1", ..., "CR15")`。
  - Verdict labels：`PASS / FAIL / OVERRIDE / N/A`。
- 測試：116/116 PASS（observer 50+ + readiness 50+，總 116）。
- 相鄰套件回歸：409 PASS / 0 regression
  （P7-PR4B 54 + 0-9O-B 62 + 0-9P 40 + 0-9P-AUDIT 56 + 0-9R-IMPL-DRY 81
   + 0-9S-CANARY observer + readiness 116 = 409）。
- Gate-A / Gate-B / branch protection / signed PR-only flow 全部維持。

### Phase 2 – Continuous observation（FUTURE separate order required）

- **本 PR 不執行 multi-day window**，因為一次 CI 執行不可能跨足天級
  observation。order §0 / §50 / §757 已明示：window 不完整 → 狀態必為
  `ACTIVATED_NOT_COMPLETE`，**不可** 偽造 `COMPLETE`。
- 啟動條件：j13 顯式發出 `TEAM ORDER 0-9S-CANARY-OBSERVE`（建議名稱），
  指定觀測窗（如 14 天）、cohort、終止 trigger。
- 期間 operator 依 `0-9s-ready/06_operator_checklist.md` runbook 對
  `observe()` 進行週期呼叫（建議 hourly），每次寫入
  `feedback_decision_record_dry_run` 與 `sparse_canary_observation`
  存檔；同時 Calcifer 對 CR7 / CR9 / CR10 持續 5-min poll。

### Phase 3 – Evidence finalization（FUTURE separate order）

- composite score 終局評估（依 §4 weights）。
- S1–S14 / F1–F9 close-out verdict（依 `evaluate_success_criteria` /
  `evaluate_failure_criteria` 終局輸出）。
- Recommendation report：建議下一階段 order
  - 若 PASS → `TEAM ORDER 0-9T-PREP`（為 production prep 鋪路；仍非
    rollout）。
  - 若 FAIL（任一 F1–F9 trigger）→ §17.4 auto-revert + 失敗報告 + j13
    決策。
  - 若 INSUFFICIENT_HISTORY → 觀測窗延長或縮減 cohort。

---

## 4. Composite scoring weights（per order §4）

預設 weights 由 order §4 寫死（直到有更新的 committed contract）：

```python
DEFAULT_COMPOSITE_W_A2     = 0.4
DEFAULT_COMPOSITE_W_A3     = 0.4
DEFAULT_COMPOSITE_W_DEPLOY = 0.2
```

對應 module：

```python
def compute_composite_score(a2: float, a3: float, deploy: float,
                            w_a2: float = 0.4,
                            w_a3: float = 0.4,
                            w_deploy: float = 0.2) -> float:
    """Composite per order §4. Defaults locked to (0.4, 0.4, 0.2)."""
    return w_a2 * a2 + w_a3 * a3 + w_deploy * deploy
```

Override path（per order §4 rule 4）：

- 在 `docs/governance/composite-weights/YYYYMMDD-canary-N.md` 提交
  *committed contract*；該 contract 必須附 j13 簽署 + 通過
  `decision-record-gate`（§17.7）。
- override 後仍呼叫同一函式，但顯式傳入新權重；**不可** 在 module 層
  改 default。
- 若 weights 出現 ambiguity（兩個 contract 相互矛盾、或新舊版時間戳
  混亂），按 order §4 rule 5 — **STOP before activation, request j13
  confirmation**。

> 本 PR 在 ambiguity-free 情況下執行；無 newer committed contract 存在，
> 故使用 (0.4, 0.4, 0.2) 不變。

---

## 5. Status determination — 為何本 PR 是 `ACTIVATED_NOT_COMPLETE`

Order §0 要求最終 status 為下列四者之一：

```
COMPLETE / ACTIVATED_NOT_COMPLETE / STOPPED / BLOCKED
```

且 §50 + §757 顯式規定：

> If the required observation window cannot be completed in this
> execution, report status as `ACTIVATED_NOT_COMPLETE`, not `COMPLETE`.

| 條件 | 是否符合 `COMPLETE` |
| --- | --- |
| PR merged 且 signed | ✅ |
| CR1–CR15 PASS（含 documented OVERRIDE） | ✅ |
| Observer module 上線 | ✅ |
| Readiness checker 上線 | ✅ |
| 三層 invariant lock 正確 | ✅ |
| Runtime isolation 通過 | ✅ |
| Tests 全綠 | ✅ |
| Controlled-diff 0 forbidden | ✅ |
| Gate-A / Gate-B / branch protection 不變 | ✅ |
| **multi-day observation window 完成** | ❌ — 不可能在一次 CI 完成 |
| **S1–S14 / F1–F9 全部 close-out 為 PASS / FAIL** | ❌ — 缺 history |

→ 結論：**`ACTIVATED_NOT_COMPLETE`**。

這不是失敗、不是 BLOCKED、也不是 STOPPED。這是 order 設計上預期的
中間狀態：本 PR 把 *可被觀測的能力* 上線，但 *觀測 itself* 由獨立後續
order 啟動。

---

## 6. What "activate" means in this PR

| 是 | 不是 |
| --- | --- |
| Observer module 已 import-able、可被呼叫 | runtime 自動呼叫它 |
| `observe()` 在 caller 給定參數時可正確輸出 35-field record | runtime pipeline 已 wired 進 observer |
| Readiness preflight 對 CR1–CR15 全項 PASS（含 OVERRIDE） | 觀測窗已開始累積 evidence |
| 三層 invariant 在 module level 已硬性 lock | apply path 已被引入（並未） |
| Tests 116/116 + 相鄰 409 全綠 | S1–S14 已 close-out（不足 history） |
| Branch protection / signed PR-only / Gate-A / Gate-B 全綠 | 已生產上線 |

---

## 7. What "activate" does NOT mean

明確不包含：

1. **不觸碰 generation runtime**：`alpha_generator*`、`formula_*`、
   `mutation_engine`、`crossover_engine`、`search_policy`、
   `sampling_*` 全部零變更。
2. **不 apply weights**：`compute_composite_score()` 只回傳數字，沒有
   `apply_*` 函式存在（CR4 grep 為空，已驗證）。
3. **不切 APPLY mode**：沒有 `MODE_APPLY` flag，沒有 runtime-switchable
   apply mode。`mode` 只能是固定字串 `"DRY_RUN_CANARY"`，否則 dataclass
   `__post_init__` 直接 raise。
4. **不變更 deployable_count semantics**：`champion_pipeline.status='DEPLOYABLE'`
   VIEW 計算邏輯零變更（§17.1 single-truth）。
5. **不變更 Arena pass/fail**：`arena_pipeline.py` / `arena_a2.py` /
   `arena_a3.py` / `rejection_taxonomy.py` 全部零變更。
6. **不啟動 production rollout**：本 PR 對 production runtime SHA 0
   commits、0 lines。
7. **不引入 per-alpha lineage / formula explainability requirement**：
   §5.21 / §5.22 明確排除。

---

## 8. Reference docs

本 stack 內：

| Doc | Path |
| --- | --- |
| CR1–CR15 readiness gate（PR-D） | `docs/recovery/20260424-mod-7/0-9s-ready/01_canary_readiness_gate.md` |
| S1–S14 / F1–F9 criteria（PR-D） | `docs/recovery/20260424-mod-7/0-9s-ready/02_canary_success_failure_criteria.md` |
| Rollback plan（PR-D） | `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md` |
| Alerting / monitoring plan（PR-D） | `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md` |
| Evidence template（PR-D） | `docs/recovery/20260424-mod-7/0-9s-ready/05_evidence_template.md` |
| Operator checklist（PR-D） | `docs/recovery/20260424-mod-7/0-9s-ready/06_operator_checklist.md` |
| Governance approval matrix（PR-D） | `docs/recovery/20260424-mod-7/0-9s-ready/07_governance_approval_matrix.md` |
| 0-9S-READY final report（PR-D） | `docs/recovery/20260424-mod-7/0-9s-ready/08_0-9s_ready_final_report.md` |
| **本 PR preflight 報告** | `docs/recovery/20260424-mod-7/0-9s-canary/02_cr1_cr15_preflight_report.md` |

跨 stack：

| Doc | Path | PR / SHA |
| --- | --- | --- |
| Passport identity design | `docs/recovery/20260424-mod-7/0-9p/01_passport_identity_design.md` | PR-A `a8a8ba9` |
| Attribution precedence contract | `docs/recovery/20260424-mod-7/0-9p/03_attribution_precedence_contract.md` | PR-A `a8a8ba9` |
| Profile attribution audit dependency | `docs/recovery/20260424-mod-7/0-9r-impl-dry/04_attribution_audit_dependency.md` | PR-B `3219b805` |
| Consumer readiness verdict | `docs/recovery/20260424-mod-7/0-9p-audit/05_consumer_readiness_verdict.md` | PR-B `3219b805` |
| Dry-run consumer design | `docs/recovery/20260424-mod-7/0-9r-impl-dry/01_dry_run_consumer_design.md` | PR-C `fe3075f` |
| Smoothing & step-limit contract | `docs/recovery/20260424-mod-7/0-9r-impl-dry/03_smoothing_and_step_limit_contract.md` | PR-C `fe3075f` |
| Runtime isolation audit | `docs/recovery/20260424-mod-7/0-9r-impl-dry/05_runtime_isolation_audit.md` | PR-C `fe3075f` |
| Controlled-diff report | `docs/recovery/20260424-mod-7/0-9r-impl-dry/08_controlled_diff_report.md` | PR-C `fe3075f` |
| AB evaluation & CANARY readiness | `docs/recovery/20260424-mod-7/0-9r/05_ab_evaluation_and_canary_readiness.md` | 0-9R |

CLAUDE.md hard rules 引用：

- §17.1 single-truth VIEW（`zangetsu_status.deployable_count`）
- §17.2 mandatory AKASHA witness（CANARY activation 對應 AKASHA witness slot）
- §17.3 Calcifer outcome watch（5-min poll CR7 / CR9 / CR10）
- §17.4 auto-regression revert（12h 不動自動回滾，本 stack 全程必須維持
  `last_live_at_age_h <= 6` per §17.3）
- §17.5 bot-only version bump（`bin/bump_version.py`）
- §17.6 stale-service check（observer module mtime ≤ 任何 long-running
  consumer process start time）
- §17.7 decision-record CI gate（每個 `feat(zangetsu/...)` 必有
  `docs/decisions/YYYYMMDD-*.md`）

---

## 9. Closing

本 PR 標誌 ZANGETSU 從 *pure dry-run design* 過渡到 *dry-run CANARY
observation capability online*。

它 **沒有** 啟動觀測窗、**沒有** 開始累積 evidence、**沒有** 啟動 S1–S14
close-out。這些都明確留給後續 j13 order。

它 **有** 把可被呼叫、可被驗證、三層 invariant 已硬鎖、CR1–CR15 已 PASS
的 observer 上線。

任何試圖在本 stack 之上 implicit-flip 為 apply / production / 任何
runtime-switchable APPLY mode 的修改 → 必須 STOP（§18.4 / §18.5 /
§18.7 / §18.8 / §18.20）。
