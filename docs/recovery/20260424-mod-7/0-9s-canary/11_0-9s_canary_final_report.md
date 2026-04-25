# 0-9S-CANARY — Sparse-Candidate Dry-Run CANARY Activation Final Report

## 1. Status

**ACTIVATED_NOT_COMPLETE** — per TEAM ORDER 0-9S-CANARY §0 + §50 + §757。

Observer module 已交付且 import-able / invocable；CR1–CR15 readiness
preflight 全 PASS（含 documented CR6 OVERRIDE）；三層 dry-run-CANARY
invariant 在 module 層硬鎖；runtime isolation 七條 source-text scan 全
通過；behavior invariance 十二條全 UNCHANGED；tests 116 / 116 PASS、
adjacent suites 409 / 0 regression；controlled-diff 預期 EXPLAINED；
branch protection / signed-PR-only flow / Gate-A / Gate-B 全部 INTACT。

但是：

> Multi-day continuous observation window 不可能在一次 CI execution
> 內完成。

per order §757，當 observation window 不完整時，本 PR 的正確 status 是
`ACTIVATED_NOT_COMPLETE` 而非 `COMPLETE` — 偽造 `COMPLETE` 即違反 §50
與 CLAUDE.md §17.6 stale-service check 精神。Phase 2 / Phase 3
（continuous observation + evidence finalization）需要由獨立後續 j13
order 啟動（建議命名 `TEAM ORDER 0-9S-CANARY-OBSERVE`），詳見 §19。

## 2. Baseline

- **origin/main SHA at start**: `0d7f67d7a6a1c5d44d38f5259faf6f0d11db427a`
  （PR-D `0-9S-READY` merged）
- **branch**: `phase-7/0-9s-canary-dry-run-activation`
- **PR URL**: pending（待 `gh pr create` 後填入）
- **Merge SHA**: pending（待 squash merge 後填入）
- **Signature**: ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`
  （與 0-9P / 0-9P-AUDIT / 0-9O-B / 0-9R-IMPL-DRY / 0-9S-READY 同一把
  私鑰）。GitHub-side `verified=true` 由 GitHub squash merge 階段以
  GitHub 自身 PGP key 重新簽署 merge commit 完成。

## 3. Mission

引自 TEAM ORDER 0-9S-CANARY §1.1（verbatim quote）：

> Activate a dry-run CANARY that continuously evaluates sparse-candidate
> optimization recommendations against live or near-live Arena telemetry
> **without applying those recommendations**. The CANARY should produce
> evidence about whether SIGNAL_TOO_SPARSE is decreasing, A2 pass_rate
> improves, A3 pass_rate remains stable, OOS_FAIL remains controlled,
> deployable_count is maintained or improved, UNKNOWN_REJECT remains
> below 0.05, profile allocation remains diversified, dry-run consumer
> output remains stable.

引自 §2（verbatim quote）：

> The activation MUST NOT modify alpha generation, formula generation,
> mutation, crossover, search policy, generation budget, sampling
> weights, thresholds, A2_MIN_TRADES, A3 thresholds, Arena pass/fail
> branch conditions, rejection semantics, champion promotion,
> deployable_count semantics, execution logic, capital allocation, risk
> controls, production rollout, branch protection, signed PR-only flow,
> controlled-diff, full per-alpha lineage, formula explainability, apply
> path, runtime-switchable DRY_RUN/APPLY flag, consumer output → generation
> runtime path, or live strategy behavior.

中文重述（不取代上方原文）：啟動 dry-run CANARY，僅觀測「假設套用會
發生什麼」，不真的套用。CANARY 對 generation runtime / Arena pass-fail
／champion promotion / execution / capital / risk 完全被動。

## 4. CR1–CR15 preflight

| CR | Status | Notes |
| --- | --- | --- |
| CR1 | PASS | passport persistence (PR-A `a8a8ba9`) |
| CR2 | PASS (runtime-gated) | observer 在 runtime 接收 `attribution_verdict` 並依 GREEN / documented YELLOW 放行；PR-time 預設 caller 提供 GREEN |
| CR3 | PASS | `feedback_budget_consumer.py` 存在 (PR-C `fe3075f`) |
| CR4 | PASS | source-text grep 對 `apply_budget` / `apply_plan` / `apply_consumer` / `apply_allocator` / `apply_canary` / `apply_recommendation` / `apply_weights` / `apply_sampling` / `apply_generation` 九個 symbol 全為空 |
| CR5 | PASS | consumer 不被 Arena / generation / execution runtime import |
| CR6 | OVERRIDE | order §3 explicit override（PR-C `fe3075f` merged < 7 days ago，default veto override per §3 rule 3） |
| CR7 | PASS (runtime-supplied) | `unknown_reject_rate` gate 在 `observe()` 時讀 caller 提供的 metrics |
| CR8 | PASS | A2 sparse trend 由 0-9P-AUDIT replay-validate 通道測得 |
| CR9 | PASS | A3 pass_rate 由 P7-PR4B `arena_batch_metrics` 觀察 |
| CR10 | PASS | `deployable_count` 由 `champion_pipeline.status='DEPLOYABLE'` VIEW 測量（§17.1 single-truth） |
| CR11 | PASS | rollback plan committed at `0-9s-ready/03_rollback_plan.md` |
| CR12 | PASS | alerting plan committed at `0-9s-ready/04_alerting_and_monitoring_plan.md` |
| CR13 | PASS | branch protection（5 個 sub-flag）intact |
| CR14 | PASS | signed PR-only flow 維持（§17.5 `bin/bump_version.py` 路徑） |
| CR15 | PASS | order §22 j13 explicit authorization sentence 載於本 PR commit message |

**Overall verdict**: PASS with documented CR6 OVERRIDE。詳細：
`02_cr1_cr15_preflight_report.md`。

## 5. What changed

| File | Type | Notes |
| --- | --- | --- |
| `zangetsu/services/sparse_canary_observer.py` | **new module** (~600 LOC) | `SparseCanaryObservation` dataclass + observer + helpers + S1–S14 / F1–F9 evaluators |
| `zangetsu/tools/sparse_canary_readiness_check.py` | **new offline tool** (~300 LOC) | `check_readiness(...)` / `safe_check_readiness(...)` / `required_cr_ids()` 覆蓋 CR1–CR15 |
| `zangetsu/tests/test_sparse_canary_observer.py` | new test file | 71 tests |
| `zangetsu/tests/test_sparse_canary_readiness.py` | new test file | 45 tests |
| `docs/recovery/20260424-mod-7/0-9s-canary/01..11*.md` | evidence docs | 11 markdown artifacts |
| `zangetsu/tests/test_feedback_budget_allocator.py` | allow-list extension | 1-line `set` 新增（將 `sparse_canary_observer.py` 列為 legitimate downstream） |
| `zangetsu/tests/test_feedback_budget_consumer.py` | allow-list extension | 1-line `set` 新增（同上，consumer plan 觀察輸入） |

**Zero CODE_FROZEN runtime files modified.** 0-9O-B `feedback_budget_
allocator.py` / 0-9R-IMPL-DRY `feedback_budget_consumer.py` / 0-9P
`generation_profile_identity.py` / 0-9P-AUDIT `profile_attribution_audit.py`
／全部 Arena / engine / live / config 路徑檔案皆 zero-diff。

## 6. CANARY observer

### 6.1 Public surface

```python
@dataclass
class SparseCanaryObservation:
    # 35 required fields locked by required_observation_fields()
    telemetry_version: str
    observation_id: str
    canary_version: str        # locked to "0-9S-CANARY"
    mode: str                  # locked to "DRY_RUN_CANARY"
    applied: bool              # locked to False
    event_type: str            # locked to "SPARSE_CANARY_OBSERVATION"
    observed_at: str
    window_start_at: str
    window_end_at: str
    rounds_observed: int
    profiles_observed: int
    signal_too_sparse_rate: float
    a2_pass_rate: float
    a3_pass_rate: float
    oos_fail_rate: float
    unknown_reject_rate: float
    deployable_count: int
    deployable_density: float
    profile_diversity: float
    profile_collapse_detected: bool
    consumer_plan_stability: float
    composite_score: float
    composite_delta: float
    composite_weights: dict
    attribution_verdict: str   # GREEN / YELLOW / RED
    rollback_available: bool
    exploration_floor_active: bool
    success_criteria: dict     # {S1..S14: PASS|FAIL|INSUFFICIENT_HISTORY}
    failure_criteria: dict     # {F1..F9: PASS|FAIL|NOT_EVALUATED_FAILURE_TRIGGERED}
    bottleneck: str
    top_reject_reasons: list
    expected_effect: str       # locked to "DRY_RUN_CANARY_NOT_APPLIED"
    safety_constraints: list   # incl. NOT_APPLIED_TO_RUNTIME, OBSERVER_ONLY
    reason: str
    source: str
```

### 6.2 三層 dry-run invariant

| Layer | Mechanism |
| --- | --- |
| 1. Construction | `__post_init__` 強制 reset `mode="DRY_RUN_CANARY"` / `applied=False` / `canary_version="0-9S-CANARY"`；caller 提供其他值會被 overwrite |
| 2. Serialization | `to_event()` 在輸出前 re-assert 同三項；任一不符 raise |
| 3. API | 公開 `dir()` walk 對 `apply` / `commit` / `execute` / `deploy` 四 keyword regex 全空，無 `apply_*` 函式存在 |

### 6.3 Evaluators / helpers

```python
observe(...) -> SparseCanaryObservation
safe_observe(...) -> SparseCanaryObservation | OBSERVATION_BLOCKED record
serialize_observation(obs) -> dict (JSON-ready)

compute_composite_score(a2: float, a3: float, deploy: float,
                        *, w_a2: float = 0.4,
                        w_a3: float = 0.4,
                        w_deploy: float = 0.2) -> float
compute_deployable_density(deployable: int, total: int) -> float
compute_profile_diversity(profile_weights: dict) -> float
detect_profile_collapse(profile_weights: dict,
                        *, diversity_cap_min: int = 2,
                        max_weight_threshold: float = 0.95) -> bool
compute_consumer_plan_stability(plan_ids: Sequence[str]) -> float

evaluate_success_criteria(treatment: SparseCanaryObservation,
                          baseline: CanaryBaseline,
                          *, weights: dict = DEFAULT_WEIGHTS) \
    -> dict   # {"S1": "PASS"|"FAIL"|"INSUFFICIENT_HISTORY", ..., "S14": ...}
evaluate_failure_criteria(treatment: SparseCanaryObservation,
                          baseline: CanaryBaseline,
                          *, weights: dict = DEFAULT_WEIGHTS) \
    -> dict   # {"F1": "PASS"|"FAIL"|"NOT_EVALUATED_FAILURE_TRIGGERED", ..., "F9": ...}
```

Default composite weights：`(0.4, 0.4, 0.2)` per order §4。Override 路徑
須通過 `docs/governance/composite-weights/YYYYMMDD-canary-N.md`
committed contract + j13 簽署 + decision-record-gate（§17.7），不允許
修改 module default。

詳細設計：`03_sparse_canary_observer_design.md`。

## 7. Observation window

| Field | Value |
| --- | --- |
| start | pending（governed by future order） |
| end | pending |
| complete | False |
| rounds_observed | 0（observer activated；continuous observation 須 future order 啟動） |
| profiles_observed | 0 |

Multi-day continuous observation window 不可能在一次 CI 執行完成；
本 PR 把 `observe()` 上線並可被呼叫，但實際週期呼叫（建議 hourly）+
evidence 累積須由 `TEAM ORDER 0-9S-CANARY-OBSERVE` 啟動（詳 §19）。

## 8. Metrics（placeholder values，待 future order 填入）

| Metric | Value |
| --- | --- |
| SIGNAL_TOO_SPARSE rate | pending |
| A2 pass_rate | pending |
| A3 pass_rate | pending |
| OOS_FAIL rate | pending |
| UNKNOWN_REJECT rate | pending |
| deployable_count | pending |
| deployable_density | pending |
| profile_diversity | pending |
| profile_collapse_detected | pending |
| consumer_plan_stability | pending |
| composite_score | pending（default weights 0.4 / 0.4 / 0.2） |
| composite_delta | pending |

## 9. Success criteria S1–S14

待 future order 評估。在 rounds < §4 規定 minimum history 期間，多數
criteria 將回報 `INSUFFICIENT_HISTORY` — 此為設計上預期的中間狀態，非
失敗。每條 criterion 的 evaluator 實作已由 9 條 dedicated tests 在
`test_sparse_canary_observer.py` 驗證（§12.3 對應 9 條 + extras
boundary）。詳細：`04_success_failure_criteria.md`。

## 10. Failure criteria F1–F9

待 future order 評估。每條 evaluator 實作已由 9 條 dedicated tests 驗
證（§12.4 對應 9 條 + extras）。F7 attribution-verdict regress to RED 與
F9 execution / capital / risk path touched 觸發時，其餘 F-criteria 改為
`NOT_EVALUATED_FAILURE_TRIGGERED` 短路（safety-first）。詳細：
`04_success_failure_criteria.md`。

## 11. Runtime isolation

確認所有以下事實（由 `05_runtime_isolation_audit.md` + 七條 source-
text scan 驗證）：

- observer **NOT** imported by any generation runtime module
- observer **NOT** imported by any Arena runtime module
- observer **NOT** imported by any execution / capital / risk module
- consumer **NOT** imported by generation runtime
- allocator output **NOT** consumed by generation runtime
- **No** apply path（`apply_*` 九 symbol 全空）
- **No** runtime-switchable apply mode（無 `MODE_APPLY` flag、無 mode
  switch 變數）
- `applied=false` invariant 在三層強制（construction + serialization +
  public dir walk）

## 12. Behavior invariance

下列十二項 **UNCHANGED**（由 `08_behavior_invariance_audit.md` + 十二條
source-text scan 驗證）：

- alpha generation
- formula generation
- mutation / crossover
- search policy
- generation budget
- sampling weights
- thresholds（ATR / TRAIL / FIXED grids 全部保留）
- `A2_MIN_TRADES`（pinned at 25）
- Arena pass / fail
- champion promotion
- `deployable_count` semantics（§17.1 single-truth VIEW
  `champion_pipeline.status='DEPLOYABLE'`）
- execution / capital / risk

## 13. Tests

```
$ python3 -m pytest zangetsu/tests/test_sparse_canary_observer.py zangetsu/tests/test_sparse_canary_readiness.py
======================== 116 passed, 1 warning in 0.45s =========================
```

- 0-9S-CANARY 新增：116 / 116 PASS（observer 71 + readiness 45）
- Adjacent (P7-PR4B 54 + 0-9O-B 62 + 0-9P 40 + 0-9P-AUDIT 56 +
  0-9R-IMPL-DRY 81 + 0-9S-CANARY 116)：**409 PASS / 0 regression**
- 8 pre-existing local-Mac fails 屬於 `arena_pipeline.py:18`
  `os.chdir('/home/j13/j13-ops')` Alaya path issue，與本 PR 無關，
  Alaya CI 將 PASS

詳細：`09_test_results.md`。

## 14. Controlled-diff

Expected classification: **EXPLAINED**（NOT EXPLAINED_TRACE_ONLY — no
runtime SHA changed）。

```
Zero diff:                   ~43 fields  (incl. all 6 CODE_FROZEN runtime SHAs)
Explained diff:              1 field   — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:   0 fields
Forbidden diff:              0 fields
```

無 `--authorize-trace-only` flag 需求。詳細：
`10_controlled_diff_report.md`。

## 15. Gate-A

Expected: **PASS**（snapshot-diff classified EXPLAINED → exit code 0；
無 runtime SHA 變動 → 無 governance-relevant delta）。CI run reference
pending。

## 16. Gate-B

Expected: **PASS**（PR open with required artifacts；pull-request
trigger restored by 0-9I）。CI run reference pending。

## 17. Branch protection

Expected unchanged on `main`：

- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

本 PR 不修改 governance configuration / branch protection rules / CI
workflow / signed-PR-only flow — INTACT。

## 18. Remaining risks

- **Observation window incomplete in this PR**：multi-day continuous
  observation window 不可能在一次 CI 執行完成。Phase 2 / Phase 3 必須由
  獨立 j13 order 啟動（建議 `TEAM ORDER 0-9S-CANARY-OBSERVE`）；本 PR
  狀態為 `ACTIVATED_NOT_COMPLETE` 即此風險的 explicit acknowledgement。
- **CR6 OVERRIDE 是 documented 而非 invariant PASS**：order §3 explicit
  override 因 PR-C `fe3075f` merged < 7 days ago；後續 stability check
  時可能需重新評估。
- **CR2 runtime-gated**：caller 在 `observe()` 呼叫時必須提供 GREEN 或
  documented YELLOW；提供 RED 時 F7 觸發、observation 拒絕。本 PR 不能
  保證 future caller 一定提供合規 verdict — 需 operator runbook
  保證（`0-9s-ready/06_operator_checklist.md`）。
- **8 個 pre-existing local-Mac test fails**：與本 PR 無關，但對
  Local Mac 開發者持續造成噪音。Alaya CI 路徑存在無此問題；建議獨立
  order 處理 `arena_pipeline.py:18` chdir 條件化。
- **Composite scoring weights (0.4 / 0.4 / 0.2) 為 CANARY default**：
  per order §4。production scoring weights 須額外 j13 sign-off + new
  committed contract（`docs/governance/composite-weights/`），不在本
  PR 範疇。
- **Profile collapse detection 使用 `diversity_cap_min=2` 與
  `max_weight_threshold=0.95`**：兩個閾值由 `04_success_failure_criteria.md`
  定義；live observation 期間可能需要 tuning。tuning 動作必須走獨立
  order（不可在本 PR 範疇內調整）。
- **observer 不替代 production gate**：observer 為 evidence-only 工具，
  其 PASS / FAIL 不直接觸發 production rollout 或 production block；
  決策權保留給 j13 + governance gate。

## 19. Recommended next action

本 PR status: **`ACTIVATED_NOT_COMPLETE`**。

### Primary recommendation

**TEAM ORDER 0-9S-CANARY-OBSERVE**（建議命名）— multi-day continuous
observation window，由 operator 依
`docs/recovery/20260424-mod-7/0-9s-ready/06_operator_checklist.md`
runbook 對 `observe()` 進行週期呼叫（建議 hourly），累積
`SparseCanaryObservation` records；定期執行
`evaluate_success_criteria(...)` / `evaluate_failure_criteria(...)`；
產出最終 verdict。Calcifer 對 CR7 / CR9 / CR10 持續 5-min poll（per
CLAUDE.md §17.3）。

期間若 §17.4 auto-regression revert 觸發（12h 不動 + version bump claim
存在），則自動 revert 並升至 j13。

### Alternative

**TEAM ORDER 0-9T-PREP**（production prep）— 若 j13 需先做 production
readiness gate 規劃。但 0-9T-PREP **premature without observation
evidence**（observer 上線但未累積；未證 Z 字 success criteria）；強烈
建議先跑 0-9S-CANARY-OBSERVE 累積至少 14 天 evidence 後再啟動 0-9T-PREP。

### NOT recommended

- 在本 stack 之上 implicit-flip 為 apply / production / runtime-
  switchable APPLY mode → 違反 order §18.4 / §18.5 / §18.7 / §18.8 /
  §18.20；任何 PR 嘗試此路徑必須 STOP。
- 直接套用 composite_score 至 production 排程 → 須先有 committed
  composite-weights contract + j13 簽署。
- 在 observation 累積完成前發出 `feat(zangetsu/vN.N)` version bump →
  違反 §17.5 `bin/bump_version.py` 對 `deployable_count` non-degradation
  的要求。
