# 07 — CANARY Observation Evidence (Sparse-Candidate Dry-Run)

> **Order**: TEAM ORDER 0-9S-CANARY (Sparse-Candidate Dry-Run CANARY Activation)
> **PR position**: fifth commit on top of `0d7f67d` baseline, after PR-A
> (`a8a8ba9`), PR-B (`3219b805`), PR-C (`fe3075f`), PR-D (`0d7f67d`).
> **Scope**: this PR ships the observer module + readiness checker.
> The continuous-observation window itself is governed by a separate
> future order `0-9S-CANARY-OBSERVE` and is **not** authorized here.

---

## 1. Status declaration — ACTIVATED_NOT_COMPLETE

依 TEAM ORDER 0-9S-CANARY §0 + §50 + §757 (ACTIVATED_NOT_COMPLETE rule):

> "If the required observation window cannot be completed in this
> execution, report status as `ACTIVATED_NOT_COMPLETE`, not `COMPLETE`."

This PR's terminal status is **`ACTIVATED_NOT_COMPLETE`**, decomposed as:

| Sub-state | Value | Meaning |
| --- | --- | --- |
| Observer module merged | YES | `zangetsu/services/sparse_canary_observer.py` (~600 LOC) is in the tree at the merge SHA. |
| Readiness checker merged | YES | `zangetsu/tools/sparse_canary_readiness_check.py` (~300 LOC) is in the tree. |
| CR1–CR15 readiness verdict | PASS (with documented CR6 OVERRIDE) | Static gate cleared at PR time. |
| Observation window started | NO | A continuous multi-day cadence cannot run inside a single CI execution. |
| Rounds_observed | 0 | Window has not opened. |
| Composite_score | N/A | No samples yet. |
| Final verdict (S1–S14, F1–F9) | N/A | Pending future order. |

CANARY observer 已**啟動可調用**（module + tool merged，tests 116/116
PASS），但**多日連續觀測視窗無法在單次 CI execution 內完成**。所以本 PR 的
status 嚴格標為 `ACTIVATED_NOT_COMPLETE`。實際 observation evidence
（rounds_observed, profiles_observed, composite_score, 等）將由後續顯式
order `0-9S-CANARY-OBSERVE` 填寫於本檔的 §3 / §4 / §5 / §6。

任何 caller、watchdog、bot、或人類 reviewer 在本 PR window 內看到 `[FUTURE_ORDER]`
與 `[TBD]` placeholder 應視為「尚未填寫」，**不得**據此判定 CANARY PASS / FAIL。
不可改寫此檔的 §1 status declaration 為 `COMPLETE` 直至 future order 落地。

---

## 2. Static evidence at PR time (already collected)

下表是 PR merge 當下即可確定的靜態資料；不依賴後續觀測視窗。

| Item | Value | Source / Verification |
| --- | --- | --- |
| Activation timestamp (UTC, ISO 8601) | `<UTC ISO will be merge-commit timestamp>` (placeholder until merge) | Will be filled with the merge commit's `committer.date` after merge to `main`. |
| Git SHA at activation | `<merge SHA, placeholder>` | Filled by the merge commit; recorded in `evidence-aborted.md` if PR is closed without merge. |
| Branch protection state | `enforce_admins=true / required_signatures=true / required_linear_history=true / allow_force_pushes=false / allow_deletions=false` | Verified through PR-A through PR-D (a8a8ba9, 3219b805, fe3075f, 0d7f67d). No relaxation of branch protection in this PR. |
| CR1–CR15 readiness verdict | PASS (with documented CR6 OVERRIDE) | Output of `python -m zangetsu.tools.sparse_canary_readiness_check`; CR6 OVERRIDE rationale recorded in `0-9s-canary/01_canary_activation_plan.md`. |
| Observer module SHA / file | `zangetsu/services/sparse_canary_observer.py` (~600 LOC) | New file in this PR. Leaf module — never imported by `arena_pipeline`, `arena23_orchestrator`, `arena45_orchestrator`, or any `live/` module. |
| Readiness tool SHA / file | `zangetsu/tools/sparse_canary_readiness_check.py` (~300 LOC) | New offline tool. Pure read-only; no DB writes; no production state mutation. |
| Test count (this PR) | 116 / 116 PASS (observer 71 + readiness 45) | `pytest zangetsu/tests/test_sparse_canary_observer.py zangetsu/tests/test_sparse_canary_readiness.py -v` |
| Adjacent test count | 409 / 0 regression | All sister suites in `zangetsu/tests/` re-run; no regressions across allocator / consumer / arena / audit / pass-rate / rejection-taxonomy / passport / generation-profile suites. |
| Composite weights default | `0.4 / 0.4 / 0.2` (a2 / a3 / deploy_density) | `DEFAULT_COMPOSITE_W_A2 = 0.4`, `DEFAULT_COMPOSITE_W_A3 = 0.4`, `DEFAULT_COMPOSITE_W_DEPLOY = 0.2` in `sparse_canary_observer.py`. Sums to 1.0. Matches 0-9R § 5 design defaults. |
| Mode constant | `MODE_DRY_RUN_CANARY` (hard-coded) | No runtime-switchable APPLY mode exists. |
| Apply path | NONE | No `apply_*` symbol; observer is pure-read. |

### 2.1 Forbidden runtime files unchanged (per order §5)

下列 runtime files 為 order §5 列入「禁止修改」清單；本 PR 全部維持 zero-diff：

| File | Status |
| --- | --- |
| `zangetsu/services/arena_pipeline.py` | UNCHANGED (zero-diff) |
| `zangetsu/services/arena23_orchestrator.py` | UNCHANGED |
| `zangetsu/services/arena45_orchestrator.py` | UNCHANGED |
| `zangetsu/services/arena_gates.py` | UNCHANGED |
| `zangetsu/services/feedback_budget_allocator.py` | UNCHANGED |
| `zangetsu/services/feedback_budget_consumer.py` | UNCHANGED |
| `zangetsu/services/feedback_decision_record.py` | UNCHANGED |
| `zangetsu/services/generation_profile_metrics.py` | UNCHANGED |
| `zangetsu/services/generation_profile_identity.py` | UNCHANGED |
| `zangetsu/services/arena_pass_rate_telemetry.py` | UNCHANGED |
| `zangetsu/services/arena_rejection_taxonomy.py` | UNCHANGED |
| `zangetsu/config/settings.py` | UNCHANGED |
| `zangetsu/engine/components/*.py` | UNCHANGED |
| `zangetsu/live/*.py` | UNCHANGED |
| `zangetsu/tools/profile_attribution_audit.py` | UNCHANGED |
| `scripts/governance/diff_snapshots.py` | UNCHANGED |

詳細的 invariance audit + per-test mapping → see `08_behavior_invariance_audit.md`.

---

## 3. Observation window — to be filled by future order

> Operator: leave every `[FUTURE_ORDER]` placeholder as-is until
> `0-9S-CANARY-OBSERVE` issues. **Do not** populate ahead of the
> explicit authorization sentence.

| Field | Value (placeholder) |
| --- | --- |
| Window start (UTC, ISO 8601) | `[FUTURE_ORDER]` |
| Window end (UTC, ISO 8601) | `[FUTURE_ORDER]` |
| Window complete (boolean) | `[FUTURE_ORDER]` |
| Rounds observed | `[FUTURE_ORDER]` |
| Profiles observed | `[FUTURE_ORDER]` |
| Continuous observer cadence | `[FUTURE_ORDER]` (proposed: once per A1 round close) |
| Storage path for observation records | `[FUTURE_ORDER]` (proposed: `docs/governance/canary-evidence/YYYYMMDD-canary-N/`) |
| Observation record format | JSON-Lines (one `SparseCanaryObservation.to_event()` per line) |
| Cadence-trigger source | `[FUTURE_ORDER]` (e.g. cron / arena-orchestrator-hook / external scheduler) |

`storage path` 的 proposed default 採 `docs/governance/canary-evidence/`
是為了與 0-9S-READY `05_evidence_template.md` § 3 filing convention
一致；future order 可指定其他 location，但**不得**寫入 CODE_FROZEN runtime
file 也不得寫入任何 production DB（observer 是 pure leaf）。

---

## 4. Observation metrics — to be filled by future order

下表的 threshold 全部 hard-coded 在 `sparse_canary_observer.py` 的 module-level
constants；future order 不得偷改 threshold（修改 threshold 需獨立 signed PR
+ docs/decisions/YYYYMMDD-*.md，per CLAUDE.md §17.7）。

```
SIGNAL_TOO_SPARSE rate:    [TBD]   (threshold S1: -20% relative vs baseline)
A2 pass_rate:              [TBD]   (threshold S2: +3pp vs baseline)
A3 pass_rate:              [TBD]   (threshold S3: <= -2pp tolerance)
OOS_FAIL rate:             [TBD]   (threshold S4: <= +3pp tolerance)
UNKNOWN_REJECT rate:       [TBD]   (threshold S6: < 0.05)
deployable_count:          [TBD]   (threshold S5: >= baseline)
deployable_density:        [TBD]   (passes_a3 / deployable, [0,1])
composite_score:           [TBD]   (0.4*A2 + 0.4*A3 + 0.2*deploy_density)
composite_delta:           [TBD]   (S14: >= 1σ for PASS)
profile_diversity_score:   [TBD]   (S8: > 0)
profile_collapse_detected: [TBD]   (S7 / F5: must be False)
consumer_plan_stability:   [TBD]   (PLAN_STABILITY_MIN = 0.70)
```

每個 `[TBD]` 由 `serialize_observation(obs)` 自動填寫；future order 在
`0-9S-CANARY-OBSERVE` 啟動 cadence 後，會將每輪 observer output 寫入
`observations.jsonl`，本檔的 §4 摘要由最終 aggregation step 產生。

---

## 5. Success criteria S1–S14 — to be evaluated by future order

| Criterion | Threshold (hard-coded constant) | Expected verdict |
| --- | --- | --- |
| S1 | SIGNAL_TOO_SPARSE rate ≥ 20% relative reduction vs baseline | `INSUFFICIENT_HISTORY` until ≥ 20 rounds; then `PASS / FAIL` |
| S2 | A2 pass_rate ≥ baseline + 3pp | `INSUFFICIENT_HISTORY` until ≥ 20 rounds |
| S3 | A3 pass_rate within −2pp of baseline | `INSUFFICIENT_HISTORY` until ≥ 20 rounds |
| S4 | OOS_FAIL rate within +3pp of baseline | `INSUFFICIENT_HISTORY` until ≥ 20 rounds |
| S5 | deployable_count ≥ baseline | `INSUFFICIENT_HISTORY` until ≥ 14 days of `zangetsu_status` VIEW samples |
| S6 | UNKNOWN_REJECT rate < 0.05 | Can `PASS / FAIL` from round 1 (pure rate cap) |
| S7 | profile_collapse_detected == False | Can `PASS / FAIL` from round 1 |
| S8 | profile_diversity_score > 0 | Can `PASS / FAIL` from round 1 |
| S9 | consumer_plan_stability ≥ 0.70 (PLAN_STABILITY_MIN) | `INSUFFICIENT_HISTORY` until ≥ 7 plans |
| S10 | dry-run invariant: `applied=false` for every plan | Can `PASS / FAIL` from round 1; FAIL = immediate F8 trigger |
| S11 | governance violation count == 0 over the window | Can `PASS / FAIL` from round 1 |
| S12 | composite_score ≥ baseline composite (re-evaluated daily) | `INSUFFICIENT_HISTORY` until ≥ 14 days of paired baseline+treatment composite |
| S13 | sign-stability of treatment delta ≥ 5 consecutive rounds | `INSUFFICIENT_HISTORY` until ≥ 5 actionable rounds |
| S14 | composite_delta ≥ 1σ vs baseline composite distribution | `INSUFFICIENT_HISTORY` until ≥ 20 paired rounds (need σ estimate) |

> Note: S2 / S3 / S4 / S5 / S12 / S14 will likely report
> `INSUFFICIENT_HISTORY` for the first 20+ rounds. This is **expected**
> and **not** a failure mode. The watchdog cadence in
> `0-9S-CANARY-OBSERVE` should explicitly surface
> `INSUFFICIENT_HISTORY` as INFO (not WARN/BLOCKING/FATAL).

---

## 6. Failure criteria F1–F9 — to be checked by future order

| Criterion | Trigger condition | Action on trigger |
| --- | --- | --- |
| F1 | A3 pass_rate drops > 2pp below baseline for 3 consecutive rounds | `rollback_required = True` → automatic rollback; `0-9R-IMPL-REWORK` order issued |
| F2 | OOS_FAIL rate exceeds baseline + 3pp for 3 consecutive rounds | `rollback_required = True` |
| F3 | deployable_count drops below baseline for ≥ 12h (CLAUDE.md §17.4 alignment) | `rollback_required = True` |
| F4 | UNKNOWN_REJECT rate ≥ 0.05 at any single sample | `rollback_required = True`; immediate halt |
| F5 | profile_collapse_detected == True (diversity → 1 active profile) | `rollback_required = True`; immediate halt |
| F6 | consumer_plan_stability falls below `PLAN_STABILITY_MIN = 0.70` for any 7-plan window | `rollback_required = True` |
| F7 | exploration_floor breached (any profile weight < 0.05) | `rollback_required = True`; this should be impossible if allocator knobs are within bounds, so trigger = upstream regression |
| F8 | dry-run invariant violated (any plan with `applied=true`) | `rollback_required = True`; immediate halt; **incident severity = FATAL** |
| F9 | governance violation detected (G1–G13 from 0-9R-IMPL-DRY) | `rollback_required = True`; immediate halt |

任一 F# triggered → observer 在下一輪 emit event 時於 `failure_flags`
field 標註觸發的 F#，consumer-side watchdog 根據此 field 自動觸發 rollback
sequence（per `0-9s-ready/03_rollback_plan.md`）。本 PR 不啟動 rollback
sequence；只**保證 observer 能正確識別並標註**。

---

## 7. Evidence-record schema

Observer 產生的每筆觀測紀錄由 `SparseCanaryObservation.to_event()` 序列化為
flat JSON。`required_observation_fields()` 回傳 35 個 mandatory field name。
任何 field 缺失或 None 將在 `__post_init__` 時 `ValueError`，即「壞訊號不會
靜默落地」。

35 個 mandatory field 列表（來源：`required_observation_fields()`）：

| # | Field | Type | Note |
| --- | --- | --- | --- |
| 1 | `event_type` | str | hard-coded `"sparse_canary_observation"` |
| 2 | `schema_version` | int | initial = 1 |
| 3 | `mode` | str | hard-coded `"DRY_RUN_CANARY"` |
| 4 | `applied` | bool | hard-coded `false` (§17 invariant) |
| 5 | `observation_id` | str (uuid v4) | unique per round |
| 6 | `observed_at_utc` | str (ISO 8601 Z) | round close UTC time |
| 7 | `round_id` | str | A1 round identifier |
| 8 | `cohort_split_method` | str | `passport_tag` / `worker_id_parity` |
| 9 | `treatment_cohort_size_pct` | int | 5–50 inclusive |
| 10 | `baseline_cohort_size_pct` | int | 100 − treatment |
| 11 | `signal_too_sparse_rate_treatment` | float | [0,1] |
| 12 | `signal_too_sparse_rate_baseline` | float | [0,1] |
| 13 | `a2_pass_rate_treatment` | float | [0,1] |
| 14 | `a2_pass_rate_baseline` | float | [0,1] |
| 15 | `a3_pass_rate_treatment` | float | [0,1] |
| 16 | `a3_pass_rate_baseline` | float | [0,1] |
| 17 | `oos_fail_rate_treatment` | float | [0,1] |
| 18 | `oos_fail_rate_baseline` | float | [0,1] |
| 19 | `unknown_reject_rate` | float | [0,1] |
| 20 | `deployable_count_treatment` | int | live VIEW |
| 21 | `deployable_count_baseline` | int | live VIEW |
| 22 | `deployable_density_treatment` | float | [0,1] |
| 23 | `deployable_density_baseline` | float | [0,1] |
| 24 | `composite_score_treatment` | float | weighted |
| 25 | `composite_score_baseline` | float | weighted |
| 26 | `composite_delta` | float | treatment − baseline |
| 27 | `composite_delta_sigma` | float | normalized |
| 28 | `profile_diversity_score` | float | [0,N] |
| 29 | `profile_collapse_detected` | bool | F5 flag |
| 30 | `consumer_plan_stability` | float | [0,1] |
| 31 | `governance_violation_count` | int | G1–G13 |
| 32 | `failure_flags` | list[str] | subset of {F1..F9} |
| 33 | `rounds_observed_so_far` | int | running counter |
| 34 | `insufficient_history_criteria` | list[str] | subset of {S1..S14} |
| 35 | `verdict` | str | `IN_PROGRESS / PASS / FAIL / ROLLBACK` |

例：one-liner JSON shape (illustrative only; values placeholder)：

```json
{"event_type":"sparse_canary_observation","schema_version":1,"mode":"DRY_RUN_CANARY","applied":false,"observation_id":"00000000-0000-0000-0000-000000000000","observed_at_utc":"2026-04-26T00:00:00Z","round_id":"r-2026-04-26-0000","cohort_split_method":"passport_tag","treatment_cohort_size_pct":10,"baseline_cohort_size_pct":90,"signal_too_sparse_rate_treatment":0.0,"signal_too_sparse_rate_baseline":0.0,"a2_pass_rate_treatment":0.0,"a2_pass_rate_baseline":0.0,"a3_pass_rate_treatment":0.0,"a3_pass_rate_baseline":0.0,"oos_fail_rate_treatment":0.0,"oos_fail_rate_baseline":0.0,"unknown_reject_rate":0.0,"deployable_count_treatment":0,"deployable_count_baseline":0,"deployable_density_treatment":0.0,"deployable_density_baseline":0.0,"composite_score_treatment":0.0,"composite_score_baseline":0.0,"composite_delta":0.0,"composite_delta_sigma":0.0,"profile_diversity_score":0.0,"profile_collapse_detected":false,"consumer_plan_stability":0.0,"governance_violation_count":0,"failure_flags":[],"rounds_observed_so_far":0,"insufficient_history_criteria":["S1","S2","S3","S4","S5","S9","S12","S13","S14"],"verdict":"IN_PROGRESS"}
```

`applied=false` 在 `to_event()` 中是 **post-construction reset**，即使 caller
傳 `applied=true` 也會被 reset（per `test_observation_invariants_resilient_to_caller_kwargs`
與 `test_observation_invariants_resilient_to_post_construction_mutation`）。
這是 §17 dry-run invariant 的 last-mile 保險。

---

## 8. Filing convention

| Item | Convention |
| --- | --- |
| Per-record format | One `SparseCanaryObservation.to_event()` JSON per line (JSONL) |
| Per-window directory | `docs/governance/canary-evidence/YYYYMMDD-canary-N/` |
| Per-record file | `observations.jsonl` (append-only within the window) |
| Hash chain | Each record carries `observation_id`; window-level Merkle root computed at window close (proposed) |
| Retention | **Non-deletable** per CLAUDE.md §17 audit-trail rules; corrections via new directory + decision record |
| Index update | Each new window appends one row to `docs/governance/canary-evidence/INDEX.md` |
| Aborted window | Rename `observations.jsonl` → `observations-aborted.jsonl` + add `abort-reason.md`; counter still increments |
| Backup | Mirrored to Alaya `~/decisions/canary-evidence/` via `~/.claude/hooks/sync-memory-to-alaya.sh` |

注意：observer 本身**不寫**任何 production DB；所有 observation records 落地
至 governance docs 區，由人 + version-bump-gate 雙重 review。observer 只
emit Python objects；序列化 + 落地由 caller-side 負責，這保證 leaf-only
不變。

---

## 9. Cross-reference

| Topic | Pointer |
| --- | --- |
| Continuation order | `0-9S-CANARY-OBSERVE` (NOT AUTHORIZED in this PR) |
| Static activation plan | `0-9s-canary/01_canary_activation_plan.md` |
| Behavior invariance audit | `0-9s-canary/08_behavior_invariance_audit.md` (sister doc) |
| Operator runbook | `0-9s-ready/06_operator_checklist.md` |
| Evidence template | `0-9s-ready/05_evidence_template.md` |
| Success / failure criteria origin | `0-9s-ready/02_canary_success_failure_criteria.md` |
| Rollback plan | `0-9s-ready/03_rollback_plan.md` |
| Alerting / monitoring | `0-9s-ready/04_alerting_and_monitoring_plan.md` |
| Governance approval matrix | `0-9s-ready/07_governance_approval_matrix.md` |
| Final 0-9S-READY report | `0-9s-ready/08_0-9s_ready_final_report.md` |
| Predecessor PR-A (passport persistence) | SHA `a8a8ba9` |
| Predecessor PR-B (audit) | SHA `3219b805` |
| Predecessor PR-C (dry-run consumer) | SHA `fe3075f` |
| Predecessor PR-D (readiness gate docs) | SHA `0d7f67d` |

### 9.1 Final-action conditional graph

After `0-9S-CANARY-OBSERVE` completes the window, the next order is one
of the following — **mutually exclusive**, decided by the §4 / §5 / §6
verdict:

- **All S# PASS + no F# triggered** → `0-9T-PREP` (production-readiness
  preparation). This is the only path that enables CANARY → APPLY
  transition.
- **Any F# triggered** → automatic rollback per `0-9s-ready/03_rollback_plan.md`,
  followed by `0-9R-IMPL-REWORK` order.
- **Mostly INSUFFICIENT_HISTORY** → continue observation under a new
  `0-9S-CANARY-OBSERVE` extension order; do **not** auto-promote to
  `0-9T-PREP`. Time is the final arbiter (CLAUDE.md §17.4).

任何「以 partial PASS 為由跳過剩餘 INSUFFICIENT_HISTORY 直接進 `0-9T-PREP`」
的提案，**reject by default**；需 j13 顯式書面授權 + docs/decisions/
紀錄。

---

## 10. Operator runbook tie-in

`0-9s-ready/06_operator_checklist.md` defines the per-phase invocation
procedure. 對應到 observer field：

| Phase (operator checklist) | Observer field updated |
| --- | --- |
| Phase 0 — Baseline metric capture | `signal_too_sparse_rate_baseline`, `a2_pass_rate_baseline`, `a3_pass_rate_baseline`, `oos_fail_rate_baseline`, `deployable_count_baseline`, `deployable_density_baseline`, `composite_score_baseline` |
| Phase 1 — Pre-CANARY rollback drills | none (drills are scripted; observer records the **post-drill** sanity round in field `failure_flags == []` to confirm no residual anomaly) |
| Phase 2 — Activation (cohort split goes live) | `cohort_split_method`, `treatment_cohort_size_pct`, `baseline_cohort_size_pct`, `observation_id`, `observed_at_utc`, `round_id`, `verdict = IN_PROGRESS` |
| Phase 3 — Continuous observation (per round) | `signal_too_sparse_rate_treatment`, `a2_pass_rate_treatment`, `a3_pass_rate_treatment`, `oos_fail_rate_treatment`, `unknown_reject_rate`, `deployable_count_treatment`, `deployable_density_treatment`, `composite_score_treatment`, `composite_delta`, `composite_delta_sigma`, `profile_diversity_score`, `profile_collapse_detected`, `consumer_plan_stability`, `governance_violation_count`, `rounds_observed_so_far`, `insufficient_history_criteria`, `failure_flags` |
| Phase 4 — Window close | `verdict` flips from `IN_PROGRESS` to one of `PASS / FAIL / ROLLBACK` |
| Phase 5 — Rollback (if any F# triggered) | observer is **not** restarted post-rollback in the same window; a fresh window (canary-(N+1)) opens after `0-9R-IMPL-REWORK` lands |

operator 在 Phase 3 期間每輪 close 時呼叫 `serialize_observation(obs)` →
append 到 `observations.jsonl`；不允許用 `>` overwrite，必須 `>>` append。
operator checklist § 11 對應 stale-service check (CLAUDE.md §17.6) 同樣
適用於 observer cadence host：observer 是純 library，但 invocation host
（cron / orchestrator hook）的 ActiveEnterTimestamp 必須 ≥ source mtime。

---

## 11. Adversarial review (Q1 five-dimension log)

> Per CLAUDE.md §3, every PR must document each Q1 dimension. Recorded
> outcomes for **this evidence document** (not for the observer module
> code, which is audited in `08_behavior_invariance_audit.md`):

| Dim | Outcome |
| --- | --- |
| 1. Input boundary | PASS — every numeric field in §4 / §5 has a bounded threshold; observer's `__post_init__` rejects None / NaN / out-of-[0,1]. |
| 2. Silent failure propagation | PASS — `applied=false` reset is enforced at three layers (constructor, `to_event()`, `serialize_observation()`); §10 confirms operator phase mapping covers all field updates. |
| 3. External dependency failure | PASS — observer is leaf; no DB / network / arena import. If `zangetsu_status` VIEW is unreachable at Phase 0 (baseline capture), operator MUST abort and re-attempt — observer cannot fabricate a baseline. |
| 4. Concurrency / race | PASS — observer is stateless per record; `observation_id` (uuid v4) gives a global ordering key; `rounds_observed_so_far` is monotone-increasing. No shared mutable state. |
| 5. Scope creep | PASS — this PR adds **only** observer + readiness + tests + two test allow-list extensions. No runtime SHA changes (see `08_behavior_invariance_audit.md` §3). No CANARY → APPLY transition. No new lineage. No new persistence. |

---

## 12. Author / sign-off

- Author: Claude (Lead, per CLAUDE.md §1)
- Reviewer requirement (§5 collaboration): Gemini adversarial review
  before merge; conflicts escalate to j13.
- Final j13 authorization sentence for `0-9S-CANARY-OBSERVE`: NOT
  PRESENT in this PR (intentionally — gating the future order).
- AKASHA witness slot for **this evidence doc**: not applicable
  (this is documentation, not a version bump). The witness applies at
  the activation evidence package under `docs/governance/canary-evidence/`,
  not here.

---

## 13. Closing reminder

`ACTIVATED_NOT_COMPLETE` 不是缺陷，是紀律。observer 已可調用、tests 全綠、
runtime 全未動，但**沒有觀測過任何輪次**。任何 reviewer / bot / 後續
session 看到本檔不可改寫 §1 status declaration，不可填寫 §3 / §4 / §5 /
§6 placeholders，直至 `0-9S-CANARY-OBSERVE` 顯式 issued 並完成 window。
