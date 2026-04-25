# 0-9S-READY — CANARY Readiness Gate Final Report

## 1. Status

**COMPLETE — pending Gate-A / Gate-B / signed merge on Alaya side.**

Local execution complete (branch ready, evidence package produced, zero
runtime / test / tool changes). Alaya-side gates run in CI / on PR open.

PR-D 是 **0-9P/R-STACK-v2 stack 中第四也是最後一個 PR** — 接於 PR-A
（0-9P passport persistence，merged at `a8a8ba9786e83e20e501fc5ffa76ce1601cef59f`）、
PR-B（0-9P-AUDIT attribution audit tool，merged at
`3219b805f8c1739ef06be32080dd1b09826bc81d`）、
PR-C（0-9R-IMPL-DRY dry-run consumer，merged at
`fe3075ffe979913fc849c06972f69a32cb597b0b`）之後。

PR-D 只交付 **documentation**：8 evidence docs + 1 stack-level final
report（`00_stack_final_report.md` in
`docs/recovery/20260424-mod-7/0-9p-r-stack/`）。No runtime files,
no tests, no tools touched. CANARY apply path **不**由本 PR 啟動；
PR-D 只是定義「未來任一 0-9S-CANARY activation order **必須先通過**」
的 readiness gate。

## 2. Baseline

- origin/main SHA at start: `fe3075ffe979913fc849c06972f69a32cb597b0b`
  （PR-C / 0-9R-IMPL-DRY merge SHA — direct prior in stack）
- prior stack SHAs:
  - PR-A / 0-9P: `a8a8ba9786e83e20e501fc5ffa76ce1601cef59f`
  - PR-B / 0-9P-AUDIT: `3219b805f8c1739ef06be32080dd1b09826bc81d`
  - PR-C / 0-9R-IMPL-DRY: `fe3075ffe979913fc849c06972f69a32cb597b0b`
- branch: `phase-7/0-9s-ready-canary-readiness-gate`
- PR URL: TBD — filled in after `gh pr create`
- merge SHA: TBD — filled in after merge
- signature verification: ED25519 SSH
  `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`
  （same key as PR-A / PR-B / PR-C across the stack）

## 3. Mission

定義 + documentate 出 **CANARY readiness gate** 給 sparse-candidate
generation profile intervention 迴路。Mission 範疇刻意縮小：產出
criteria、runbook、alert plan、evidence template、operator checklist、
governance approval matrix、success/failure criteria — 任何 **未來**
TEAM ORDER 0-9S-CANARY 都必須先通過本 gate。

Mission **does NOT activate CANARY**. Mission 不:

- 啟動 CANARY、不 hot-swap runtime weights、不修改 production weights。
- 修改 `feedback_budget_consumer.py` 或任何 runtime / Arena / champion
  pipeline / execution / capital / risk / broker module。
- 變更 `deployable_count` semantics、Arena pass/fail、`A2_MIN_TRADES`、
  ATR / TRAIL / FIXED grids、A3 segment thresholds 任一條目。
- 主動觸發 Calcifer alert hot-swap、寫入 AKASHA witness、發 Telegram
  廣播。
- 弱化 branch protection、required_signatures、required_status_checks。

PR-D 是 stack 凍結期的最後一塊：runtime apply path 仍為零、consumer
仍無 import path、0-9R-IMPL 之 treatment 仍未啟動。本 gate 只是
0-9S-CANARY 啟動的最低門檻，不是充分條件。

## 4. What changed

| File | Type | Notes |
| --- | --- | --- |
| `docs/recovery/20260424-mod-7/0-9s-ready/01_canary_readiness_gate.md` | new doc | CR1–CR15 readiness criteria, gate evaluation rule, CR satisfaction matrix |
| `docs/recovery/20260424-mod-7/0-9s-ready/02_canary_success_failure_criteria.md` | new doc | S1–S14 success / F1–F9 failure criteria definitions |
| `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md` | new doc | Operator runbook, hot-swap procedure, multi-rollback policy, anti-claims |
| `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md` | new doc | Alert path, severity matrix, Telegram template, Calcifer integration |
| `docs/recovery/20260424-mod-7/0-9s-ready/05_evidence_template.md` | new doc | Evidence package skeleton for the future 0-9S-CANARY activation order (12-section template) |
| `docs/recovery/20260424-mod-7/0-9s-ready/06_operator_checklist.md` | new doc | Step-by-step operator checklist (6 phases + hard STOP triggers) |
| `docs/recovery/20260424-mod-7/0-9s-ready/07_governance_approval_matrix.md` | new doc | Phase-gate model + 7-actor approval matrix + j13 authorization sentence template + §17 inheritance |
| `docs/recovery/20260424-mod-7/0-9s-ready/08_0-9s_ready_final_report.md` | this file | PR-D phase final report |
| `docs/recovery/20260424-mod-7/0-9p-r-stack/00_stack_final_report.md` | new doc | 4-PR stack final report (cross-PR summary) |

**Zero runtime files modified.** No `arena_pipeline.py`,
`arena23_orchestrator.py`, `arena45_orchestrator.py`, `arena_gates.py`,
`feedback_budget_allocator.py`, `feedback_budget_consumer.py`,
`feedback_decision_record.py`, `generation_profile_identity.py`,
`generation_profile_metrics.py`, `profile_attribution_audit.py`,
`zangetsu/config/`, `zangetsu/engine/`, `zangetsu/live/`, or
`zangetsu/tools/` change.

**Zero test files modified.** No allow-list extension, no new test, no
existing test edited. PR-C 結算的 293 PASS / 0 regression 計數逐字
carry forward。

**Zero CI / GitHub Actions / governance config modified.** No
`.github/workflows/*.yml`, no `bin/bump_version.py`, no branch
protection update, no `required_status_checks` change.

## 5. Readiness gate summary (CR1–CR15)

Cite: `01_canary_readiness_gate.md`（full text）。

CR1–CR15 為 **all-pass gate**：任一 criterion FAIL → 0-9S CANARY
activation order **不得發出**。CR2 可為 YELLOW with documented
limitations + actionable mitigations；**僅** CR2 享 YELLOW override，
其餘 14 條全 PASS-only。

| # | Criterion (1-line) | At PR-D delivery |
| --- | --- | --- |
| CR1 | 0-9P attribution closure complete (passport persistence delivered) | Met (PR #21 / `a8a8ba9`) |
| CR2 | 0-9P-AUDIT verdict GREEN, or documented YELLOW with mitigations | Pending evidence — audit refresh < 24h pre-activation |
| CR3 | 0-9R-IMPL-DRY complete (consumer module delivered, dry-run only) | Met (PR #23 / `fe3075f`, 81 tests green) |
| CR4 | No runtime apply path exists | Met (controlled-diff EXPLAINED; grep empty) |
| CR5 | Consumer has no runtime import path | Met (PR-C runtime isolation suite green) |
| CR6 | Dry-run consumer ≥ 7 days stable OR explicit j13 override | Pending evidence — wait for dry-run job accumulation |
| CR7 | UNKNOWN_REJECT < 0.05 (cross-stage, 7-day rolling) | Pending evidence — Calcifer 5-min poll |
| CR8 | A2 sparse rate trend measured (baseline established) | Pending evidence — `baseline_snapshot.md` to be produced |
| CR9 | A3 pass_rate non-degradation evidence available | Pending evidence — 14-day window calculation |
| CR10 | `deployable_count` non-degradation evidence available | Pending evidence — §17.1 VIEW continuous monitor |
| CR11 | Rollback plan documented | Met (`03_rollback_plan.md` ships in this stack) |
| CR12 | Telegram / alert path defined | Met (`04_alerting_and_monitoring_plan.md` ships in this stack) |
| CR13 | Branch protection intact | Met (baseline diff = 0) |
| CR14 | Signed PR-only flow intact | Met (last 30 days 100% signed) |
| CR15 | Explicit future j13 CANARY authorization recorded | Pending j13 — flips only on TEAM ORDER 0-9S-CANARY |

Evaluation cadence: full CR1–CR15 check before drafting any 0-9S
activation order；Calcifer outcome watchdog auto-polls CR7 / CR9 /
CR10 every 5 min；governance review of CR2 / CR11 / CR12 / CR13 /
CR14 weekly。

## 6. Success / failure criteria summary (S1–S14 + F1–F9)

Cite: `02_canary_success_failure_criteria.md`。

CANARY 啟動後須在 evidence package 內逐條對 S1–S14 列出 PASS / FAIL；
任一 F1–F9 觸發即 mandatory rollback（不可由 j13 override 維持
treatment）。

S1–S14 success 標的（節錄）：

- S1 — A2 `signal_too_sparse_rate` 下降 ≥ 20%（vs baseline 7-day
  median）。
- S2 — A2 `pass_rate` 上升 ≥ 5 pp absolute。
- S3 — A3 `pass_rate` 不下降 ≥ 5 pp absolute（non-degradation）。
- S4 — `deployable_count` 7-day rolling median 不下降。
- S5 — `unknown_reject_rate` 持續 < 0.05。
- S6 — bottleneck label drift 收斂（`SIGNAL_TOO_SPARSE_DOMINANT` 失去
  dominance）。
- S7 — actionable profile diversity ≥ 3。
- S8 — composite score（`0.4*A2_pass + 0.4*deployable_yield +
  0.2*OOS_passrate`）treatment ≥ baseline。
- S9 — attribution verdict 全期間維持 GREEN。
- S10 — cohort split 無 contamination（j01/j02 cohort tag 純度
  100%）。
- S11 — observed bottleneck 與預測 bottleneck 一致（diagnostic
  stability）。
- S12 — exploration floor 全期間 ≥ 0.05。
- S13 — 7-day evaluation window 完成。
- S14 — j13 24h review pass。

F1–F9 失敗標的（與 `03_rollback_plan.md` §2.1 一一對應）：

- F1 — A2 pass_rate 上升但 A3 collapse（≥ 5 pp absolute drop）。
- F2 — A2 pass_rate 上升但 deployable_count 7-day rolling median
  下降 ≥ 1。
- F3 — OOS_FAIL 上升 ≥ 5 pp absolute。
- F4 — UNKNOWN_REJECT 增加（≥ baseline + 2 pp）。
- F5 — trade-count inflation（mean_trades_per_passed_a2 上升 ≥ 100%
  且 pnl_per_trade 下降 ≥ 20%）。
- F6 — profile collapse（actionable profile 數 < baseline 50%）。
- F7 — exploration floor 違反（任何 profile < 0.05）。
- F8 — 結果由單一 regime / 單一 time slice 主導。
- F9 — composite score regression（treatment composite < baseline − 1σ）。

S/F 觀察視窗：CANARY 啟動後 7-day rolling，每日由 Calcifer aggregate
入 `champion_pipeline` / `arena_batch_metrics` VIEW。

## 7. Rollback plan summary

Cite: `03_rollback_plan.md`。

Rollback principle (不可協商)：**Every CANARY apply MUST be reversible
within 30 minutes.**

關鍵約束：

- No irreversible state mutation；no destructive DB write；no schema
  migration；no threshold change；no champion promotion semantic
  change；hot-swap only。
- 觸發條件：F1–F9 任一、operator-initiated j13 STOP（`/stop
  0-9S-CANARY`）、Calcifer outcome watchdog RED（CLAUDE.md §17.3）、
  attribution verdict regression 至 RED。
- 啟動前必備 artifacts A1–A8：baseline weights snapshot、簽名 git
  tag、snapshot script output、`/tmp/canary_state.json`、paired
  baseline systemd unit、`scripts/canary/rollback.sh`（dry-run tested
  ≥ 3 次）、AKASHA witness baseline POST、Calcifer watchlist。
- Hot-swap 7 步驟：j13 STOP → Calcifer RED → rollback.sh atomic
  rename → DEPLOYABLE 計數驗證 → AKASHA witness（獨立 service）→
  Telegram alert → 24h observation window。
- Multi-rollback policy：30 day 內第 2 次自動 `HALT_INDEFINITE`，
  require 0-9R-IMPL-REWORK；第 3 次 governance halt + 0-9P/R-STACK-v3
  baseline reset。
- Anti-claims：candidate pool poisoning、cross-strategy contamination、
  downstream consumer cache、AKASHA chunk 殘留、witness chain history
  皆無法由 rollback 還原。

## 8. Alerting and monitoring summary

Cite: `04_alerting_and_monitoring_plan.md`。

關鍵內容：

- **Channels**：Telegram @Alaya13jbot, chat `-1003601437444`, thread
  `362`；Calcifer `/tmp/calcifer_deploy_block.json`（presence = block）；
  AKASHA witness POST chain（CLAUDE.md §17.2 / §17.3 / §17.4）。
- **Watched metrics**：CR7 / CR9 / CR10 + F1–F9，每 metric → severity
  → action mapping。具體 metric 表如 A2 `signal_too_sparse_rate`、
  A3 `pass_rate`、`deployable_count`、`unknown_reject_rate`、
  `mean_trades_per_passed_a2`、`actionable_profile_count`、
  attribution `verdict`、composite score。
- **Severity ladder**：INFO / WARN / ERROR / FATAL；FATAL 立即
  hot-swap。Operator paging：FATAL severity 必須在 90 秒內觸達 j13；
  ERROR 5 分鐘內；WARN 30 分鐘內；INFO 不 page。
- **Calcifer integration**：每 5 min poll `arena_batch_metrics` +
  `champion_pipeline_fresh` VIEW；違反 threshold → 寫入
  `/tmp/calcifer_deploy_block.json`。
- **Telegram template** 對齊 CLAUDE.md §6 publish flow（ASCII code
  block, 3 msgs under 4096 chars each, no Mermaid）。
- **AKASHA witness chain**：CANARY pre-snapshot witness → 持續
  outcome witness（每 5 min）→ rollback witness（觸發時）。chain
  不可中斷，斷鏈即視為 §17.4 auto-revert trigger。

## 9. Evidence template summary

Cite: `05_evidence_template.md`。

提供 12-section copy-paste template，是 0-9S-CANARY activation order
evidence package 的 skeleton：

```
docs/recovery/.../0-9s-canary-activation/
├── evidence_package.md       # CR1–CR15 逐項勾選 + 證據連結
├── baseline_snapshot.md      # CR8 / CR9 / CR10 數值
├── j13_authorization.md      # CR15 授權紀錄（含 SHA / ts）
├── rollback_drill_log.md     # rollback 端到端演練紀錄（CR11 補強）
└── canary_pre_witness.json   # AKASHA witness POST 結果
```

`evidence_package.md` 的 12 section 為：(1) Header & SHA chain，
(2) CR1–CR15 evaluation, (3) S1–S14 expected pass conditions,
(4) F1–F9 hard-fail triggers + auto-rollback hooks,
(5) Baseline snapshot reference, (6) Rollback drill log reference,
(7) AKASHA witness pre-snapshot, (8) j13 authorization sentence
verbatim, (9) Calcifer watchlist confirmation, (10) Telegram alert
test result, (11) Operator on-call schedule, (12) controlled-diff
classification + Gate-A / Gate-B status。

任何 CR Pending evidence 不得 inline override；必須引用實際 query
結果。

## 10. Operator checklist summary

Cite: `06_operator_checklist.md`。

提供 6-phase checklist + hard STOP triggers：

| Phase | Description | Owner |
| --- | --- | --- |
| Phase 1 | Pre-flight (24h before activation) | Operator + Calcifer |
| Phase 2 | Pre-activation (T-2h to T-0) | Operator + Lead (Claude) |
| Phase 3 | Activation moment (T-0) | Operator + Lead + j13 (notified) |
| Phase 4 | During CANARY (T+0 to T+7d) | Operator + Calcifer (auto) |
| Phase 5 | Decision moment (T+7d) | j13 (explicit) + Lead + Adversary (Gemini) |
| Phase 6 | Post-CANARY observation (T+7d to T+14d) | Operator + Governance |

Hard STOP triggers (immediate hot-swap)：
- 任何 F1–F9 trigger fired。
- Calcifer outcome watchdog RED 持續 ≥ 2 cycle（10 min）。
- Attribution verdict regression 至 RED。
- AKASHA witness chain 中斷 > 15 min。
- Operator manual `/stop 0-9S-CANARY` Telegram 指令。
- j13 親自 STOP 指令（任何 channel）。

每步驟附 verification command + expected outcome + responsible owner。

## 11. Governance approval matrix summary

Cite: `07_governance_approval_matrix.md`。

採 **phase-gate model** 對應上節 6 phases，每 phase gate 由不同
combination of approver 簽收。**7-actor matrix**：

| Actor | Role | Authority |
| --- | --- | --- |
| j13 | Owner | CR15 explicit authorize / STOP / 24h verdict |
| Lead (Claude) | Architect | CR1/CR3/CR4/CR5/CR11/CR13 attest |
| Adversary (Gemini) | Reviewer | F1–F9 reasoning audit, alternative-hypothesis check |
| Operator | Executor | A1–A8 prep, Phase 1–4 step execution |
| Calcifer | Watchdog | CR7 / CR9 / CR10 polling, RED file write |
| AKASHA Witness | Independent verifier | CR15 / pre-snapshot / outcome chain |
| Governance Bot | Pre-receive enforcer | branch protection, signed-commit, version-bump-gate |

**j13 authorization sentence template**（必須 verbatim 引用於
activation order，否則 CR15 FAIL）：

> "I, j13, explicitly authorize TEAM ORDER 0-9S-CANARY activation on
> commit SHA `<sha>` for treatment cohort `<cohort>` with maximum
> duration `<hh>h`, rollback authority delegated to
> [Operator | Calcifer | j13 only]. This authorization expires at
> `<UTC ts>` and applies only to the specified SHA. Any drift from
> the named SHA invalidates this authorization."

授權必須以下述任一形式記錄（三選一）：(a) Telegram thread 362 message
SHA + timestamp；(b) signed commit footer `cr15_authorized_by=j13
sha=<authorization_message_sha>`；(c) AKASHA witness POST `kind:
canary_activation_authorization`。授權若 > 72h 未啟動 → 過期，須
重新授權。

**§17 inheritance**：本 governance matrix 完全 inherit CLAUDE.md §17
project constitution 的 hard rules — §17.1 single-truth VIEW (`zangetsu_status`
`deployable_count`)、§17.2 mandatory witness、§17.3 Calcifer outcome
watch、§17.4 auto-regression revert、§17.5 bot-only version bump、
§17.6 stale-service check、§17.7 decision record CI gate、§17.8
scratch-to-tests integration。任一違反即視為 governance FAIL，
0-9S-CANARY 立刻終止。

## 12. Behavior invariance

| Item | Status |
| --- | --- |
| No alpha generation change | yes — PR-D ships docs only |
| No formula generation change | yes |
| No mutation / crossover change | yes |
| No search policy change | yes |
| No real generation budget change | yes |
| No sampling weight change | yes |
| No threshold change (incl. `A2_MIN_TRADES`, ATR/TRAIL/FIXED grids, A3 segments) | yes |
| `A2_MIN_TRADES` pinned at 25 | yes (沿用 PR-A/B/C 既有 source-text 測試) |
| No Arena pass/fail change | yes |
| No champion promotion change | yes |
| No `deployable_count` semantic change | yes — §17.1 VIEW unchanged |
| No execution / capital / risk change | yes |
| No broker module change | yes |
| No new runtime importer of any allocator / consumer / audit symbol | yes |
| No `apply` / `commit` / `execute` / `deploy` symbol introduced | yes |
| No `feedback_budget_consumer.py` runtime wiring | yes |
| No `SparseCandidateDryRunPlan` consumed at runtime | yes |
| No `DryRunBudgetAllocation` consumed at runtime | yes |
| No `AttributionAuditResult` consumed at runtime | yes |
| No CI / GitHub Actions config edit | yes |
| No branch protection edit | yes |
| No `required_status_checks` edit | yes |
| No formula lineage / parent-child ancestry telemetry introduced | yes |
| CANARY started | NO |
| Production rollout started | NO |

PR-D 為 docs-only PR，本表逐項保持與 PR-C 相同 PASS 狀態（continuity
inheritance from `09_0-9r_impl_dry_final_report.md` §9）。

## 13. Test results

```
$ python3 -m pytest zangetsu/tests/  # PR-D adds ZERO new tests
```

PR-D adds **zero** new tests；existing 293 PASS / 0 regression count
preserved verbatim from PR-C（P7-PR4B 54 + 0-9O-B 62 + 0-9P 40 +
0-9P-AUDIT 56 + 0-9R-IMPL-DRY 81 = 293）。

8 pre-existing local-Mac failures in `arena_pipeline.py` chdir suite
（`/home/j13/j13-ops` 路徑只 resolve 在 Alaya）；驗證 pre-existing on
main during P7-PR4B / 0-9O-B / 0-9P / 0-9P-AUDIT / 0-9R-IMPL-DRY 執行
期間，**unrelated** to PR-D。

Expected on Alaya CI: 全部既有 tests = full PASS（與 PR-C merge 時相
同數字）。PR-D 不引入任何 test delta。

## 14. Controlled-diff

Expected classification: **EXPLAINED** (NOT EXPLAINED_TRACE_ONLY —
no runtime SHA changed, no `--authorize-trace-only` flag needed; PR-D
ships docs only).

```
Zero diff:                    ~43 fields  (incl. all 6 CODE_FROZEN runtime SHAs)
Explained diff:               1 field    — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:    0 fields
Forbidden diff:               0 fields
```

CODE_FROZEN runtime SHAs all zero-diff:

- `config.zangetsu_settings_sha` — zero-diff
- `config.arena_pipeline_sha` — zero-diff
- `config.arena23_orchestrator_sha` — zero-diff
- `config.arena45_orchestrator_sha` — zero-diff
- `config.arena_gates_sha` — zero-diff
- `config.alpha_signal_live_sha` — zero-diff
- `config.feedback_decision_record_sha` — zero-diff
- `config.calcifer_supervisor_sha` — zero-diff
- `config.zangetsu_outcome_sha` — zero-diff

PR-D 的 diff 範圍完全在 `docs/recovery/20260424-mod-7/0-9s-ready/` 與
`docs/recovery/20260424-mod-7/0-9p-r-stack/`；`zangetsu/`、`bin/`、
`.github/workflows/`、`scripts/` 全部 zero-diff。

Detailed report: 由 controlled-diff job 在 CI 自動生成於 PR opens 時，
無需 PR-D 內手動 placeholder。

## 15. Gate-A / Gate-B / Branch protection

- **Gate-A**：expected **PASS**（snapshot-diff classified as
  EXPLAINED → exit code 0；no runtime SHA changed → no
  governance-relevant delta；docs-only PR）。
- **Gate-B**：expected **PASS**（PR open with required artifacts；
  pull-request trigger restored by 0-9I；signed commits via
  `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`；CR1–CR15 +
  S1–S14 + F1–F9 + rollback + alerting + evidence template + operator
  checklist + governance matrix + stack final report 全部齊備）。
- **Branch protection on `main`**：expected **INTACT** —
  `enforce_admins=true`, `required_signatures=true`,
  `linear_history=true`, `allow_force_pushes=false`,
  `allow_deletions=false`。PR-D does not modify governance
  configuration. 全 stack 4 PR 走完 baseline diff = 0。

## 16. Forbidden changes audit

- CANARY: **NOT** started — PR-D 僅交付 readiness gate documentation；
  activation 須 future TEAM ORDER 0-9S-CANARY + j13 顯式授權（CR15）。
- Production rollout: **NOT** started — runtime apply path 仍為零。
- No `apply` / `commit` / `execute` / `deploy` symbol introduced — 全
  domain 範圍無 source-text grep 命中（沿用 PR-C 既有 reverse
  source-text 測試輸出）。
- No new runtime importer of any allocator / consumer / audit symbol —
  PR-D 不修改 `zangetsu/services/*.py` 或任何 runtime 模組。
- No `A2_MIN_TRADES` / ATR / TRAIL / FIXED / A3-segment / Arena
  pass-fail / champion-promotion / `deployable_count` semantic edit —
  threshold 全部 unchanged（沿用 PR-A/B/C 既有 invariance 測試）。
- No new `DEPLOYABLE` literal anywhere — `champion_pipeline_fresh.status
  ='DEPLOYABLE'` 仍由 `arena45_orchestrator.maybe_promote_to_deployable`
  authoritative。
- No formula lineage / parent-child ancestry telemetry introduced。
- No production wiring of `SparseCandidateDryRunPlan` output — 仍如
  PR-C ship inert：consumer importable but never invoked at runtime。
- No allow-list extension — PR-D 不修改任何 test 的 `allow_paths`。
- No `bin/bump_version.py` invocation — PR-D 不發 `feat(zangetsu/vN)`
  commit；PR title 為 `docs(0-9s-ready): ...` 性質。

PR-D 唯一可 plausibly affect 的 runtime surface 是 future 0-9S-CANARY
activation order 引用本檔的 CR1–CR15 / S1–S14 / F1–F9 / rollback
contract — 而 activation order 是另一個 PR、需另一輪 j13 授權。
本 PR shipped **inert**：documentation importable, fully
cross-referenced, 但 runtime side never 觸及。

## 17. Remaining risks

- **Design-only cannot prove runtime safety.** PR-D 全程 documentation；
  CR1–CR15 / S1–S14 / F1–F9 在紙上嚴謹，但實際 production 行為唯有
  CANARY 啟動後才能驗證。任何「looks bulletproof on paper」的 gate
  仍可能在 live data 下露出 sample-distribution mismatch、batch-size
  ergodicity violation 或 cohort tagging race condition。
- **Verdict expiry.** CR2 要求 0-9P-AUDIT verdict GREEN，且 audit run
  須在 activation 前 24h 內刷新；若 activation 與 audit 之間 ≥ 24h，
  必須重跑 audit。documented but enforcement 仍依賴 operator 紀律 +
  Calcifer schedule，未由 GitHub Actions 強制。
- **Multi-rollback policy not yet stress-tested.** §7 規範 30 day 內
  第 2 次自動 `HALT_INDEFINITE`、第 3 次 governance halt；但
  watchdog 端的具體實作（counter persistence、window rolling、auto
  branch lockout）尚未在 0-9R-IMPL-APPLY 之前 wiring。在第 1 次
  CANARY 之前無法演練第 2 / 第 3 次 rollback 路徑。
- **Smoothing-knob clamping under production conditions.** 0-9R-IMPL-DRY
  consumer clamp `ema_alpha ≤ 0.20`、`max_step_abs ≤ 0.10`、
  `floor ≥ 0.05`、`diversity_cap_min ≥ 2`；clamping 行為在 unit test
  下行為良好，但 production caller 一旦 mis-config（例如傳遞超出範圍
  的值）只會 silently clamp、不 raise — 必須仰賴 plan 上的
  `*_used` 欄位由 operator 手動 cross-check。本 PR 已將 cross-check
  納入 operator checklist（doc 06）但未提供自動 alert。
- **Cohort poisoning.** §8 anti-claims 列明 candidate pool poisoning
  不可由 rollback 還原；CANARY 啟動後 7 day baseline calibration 為
  唯一 mitigation。若 baseline calibration 期間又啟動下一輪 CANARY，
  poisoning effect 將累積，目前並無自動偵測。
- **Cross-strategy contamination.** j01 / j02 cohort 若意外混血，
  rollback 不會 un-mix。Cohort tagging 仍仰賴 caller-supplied
  `cohort_id`；若 caller bug → baseline 與 treatment 數據污染、F8
  trigger 也可能 false-negative。
- **AKASHA witness independence.** §17.2 規定 witness 由獨立 service
  寫；現行 AKASHA service 與 deployment automation 共享 100.123.49.102
  Tailscale endpoint，若 Alaya 整機故障，witness chain 與 deployment
  watchdog 同時失能 — 屬於 single-point-of-failure，待 0-9S-CANARY
  之外的 governance order 處理。
- **Calcifer model drift.** Calcifer 為 Gemma4 E4B，在 5-min poll
  cycle 內負責解讀 metric，但 LLM 判讀本身 nondeterministic；對齊
  CLAUDE.md §17.3 已要求 RED 寫文件，但 GREEN/YELLOW 邊界仍可能 LLM
  drift。0-9S-CANARY activation 期間建議搭配硬 SQL threshold 雙重
  check（已寫入 doc 04），但實作仍為 future order。
- **Composite scoring weights are design proposals, not committed
  thresholds.** S6 / S8 / F9 引用 `composite_score = 0.4*A2_pass +
  0.4*deployable_yield + 0.2*OOS_passrate` 為現行 design proposal；
  final tuning 需 j13 acknowledgement before 0-9S-CANARY；CR15
  authorization sentence 必須 verbatim 引用授權的 weight tuple。

## 18. Recommended next action

**TEAM ORDER 0-9S-CANARY — Sparse-Candidate Dry-Run CANARY Activation**
— **only if j13 explicitly authorizes**.

PR-A（passport persistence）+ PR-B（attribution audit）+
PR-C（dry-run consumer）+ PR-D（CANARY readiness gate）merged 後，
sparse-candidate 干預迴路的 read+plan+gate 三側皆已 inert ready。
0-9S-CANARY 的 activation order 必須 carry：

1. 完整 CR1–CR15 evidence package（依 doc 05 template）。
2. Baseline snapshot（依 doc 02 / CR8 / CR9 / CR10 quantitative
   numbers）。
3. j13 顯式授權 sentence（依 doc 07 verbatim template，三 channel
   任一）。
4. Rollback drill log ≥ 3 次成功（dry-run mode），對齊 doc 03 §3 A6。
5. AKASHA witness baseline POST 結果（doc 03 §3 A7）。
6. Calcifer watchlist 確認文件（doc 03 §3 A8）。
7. controlled-diff EXPLAINED or EXPLAINED_TRACE_ONLY（如有
   `arena45_orchestrator.py` 動 swap-file logic 時）。
8. `bin/bump_version.py` invocation log（CLAUDE.md §17.5）。

j13 authorization sentence template（cite
`07_governance_approval_matrix.md`）：

> "I, j13, explicitly authorize TEAM ORDER 0-9S-CANARY activation on
> commit SHA `<sha>` for treatment cohort `<cohort>` with maximum
> duration `<hh>h`, rollback authority delegated to
> [Operator | Calcifer | j13 only]. This authorization expires at
> `<UTC ts>` and applies only to the specified SHA. Any drift from
> the named SHA invalidates this authorization."

只有當 0-9S-CANARY activation order 出現、CR1–CR15 全 PASS、j13
authorization sentence verbatim 引用、AKASHA witness chain 完整、
controlled-diff 通過 + signed merge，才能 flip CR15 從 Pending j13
至 Met。在此之前，runtime apply path 仍為零、consumer 仍 inert，
本 stack 全程「one level short of any production change」紀律不變。

— end of report —
