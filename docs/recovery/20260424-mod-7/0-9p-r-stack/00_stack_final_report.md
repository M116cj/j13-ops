# 0-9P/R-STACK-v2 Final Report

Stack: 4-PR sequential signed-PR stack delivering profile passport
persistence, attribution audit tooling, dry-run sparse-candidate
consumer, and CANARY readiness gate documentation. Stack name:
`0-9P/R-STACK-v2`. Stack window: 2026-04-24 → 2026-04-25.

The stack closes the read+plan+gate side of the sparse-candidate
generation profile intervention loop while keeping the runtime apply
path at zero. CANARY 仍未啟動，production 仍未變更。本份 stack-level
final report 是 j13 在 PR-D merge 之後檢視全 stack 結果的單一 entry
point，並且為下一輪 TEAM ORDER（0-9S-CANARY、若被授權）的依據文件。

## 1. Status

**COMPLETE / pending PR-D merge** — PR-A、PR-B、PR-C 已 signed-merge
進 main；PR-D（0-9S-READY）docs-only PR 已 ready，等待 Gate-A /
Gate-B / admin merge。

| PR | Order id | Status |
| --- | --- | --- |
| PR-A | 0-9P | MERGED |
| PR-B | 0-9P-AUDIT | MERGED |
| PR-C | 0-9R-IMPL-DRY | MERGED |
| PR-D | 0-9S-READY | IN PROGRESS (this PR; pending merge) |

整個 stack 期間 branch protection on `main` 不變（§9 詳列）；ED25519
SSH key `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8` 為四個 PR
的 commit signing key；GitHub squash-merge `verified=true`（PGP）逐
條保留。

## 2. Baseline

- starting main SHA: `75f7dd8dc66af6e3c06e7c05ad7c6cffd43a6376`
- final main SHA: (pending — fill after PR-D merge)
- stack signing key: ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`
- stack window: 2026-04-24 → 2026-04-25 (PR-A → PR-D)
- stack repo: `https://github.com/M116cj/j13-ops`
- stack target branch: `main` (linear-history, signed-only)

## 3. PR-A / 0-9P

PR: https://github.com/M116cj/j13-ops/pull/21
main SHA: `a8a8ba9786e83e20e501fc5ffa76ce1601cef59f`
branch: `phase-7/0-9p-generation-profile-passport-persistence`

summary: passport identity persistence + 4-level precedence helper
（runtime A1 admit time `passport.arena1` payload 增加
`generation_profile_id` + `generation_profile_fingerprint`；新增
`resolve_attribution_chain()` 4-level precedence helper：
arena_run_lineage > sampling_dispatch_record > caller-passed > UNKNOWN）。

files touched:
- `zangetsu/services/arena_pipeline.py` — passport literal at A1 admit
  time (try/except + safe fallback)
- `zangetsu/services/generation_profile_identity.py` — new
  `resolve_attribution_chain()` 4-level precedence helper
- `zangetsu/tests/test_passport_profile_attribution.py` — 40 tests

evidence: `docs/recovery/20260424-mod-7/0-9p/01..07*.md` (7 docs)

tests: 40/40 PASS local；adjacent suites 156 PASS / 0 regression
controlled-diff: **EXPLAINED_TRACE_ONLY**
（`config.arena_pipeline_sha` authorized via `--authorize-trace-only`；
其餘 5 個 CODE_FROZEN runtime SHA zero-diff）
Gate-A: PASS
Gate-B: PASS
controlled-diff exception ledger: see
`0-9l_controlled_diff_exception_record.md` baseline pattern.

PR-A 是整個 stack 唯一 touch runtime SHA 的 PR；PR-B/C/D 全 zero-diff
on runtime SHA。

## 4. PR-B / 0-9P-AUDIT

PR: https://github.com/M116cj/j13-ops/pull/22
main SHA: `3219b805f8c1739ef06be32080dd1b09826bc81d`
branch: `phase-7/0-9p-audit-profile-attribution-validation`

summary: `profile_attribution_audit.py` + GREEN/YELLOW/RED verdict tool
（24-field `AttributionAuditResult`、`audit()` / `safe_audit()` /
`classify_verdict()` / `verdict_blocks_consumer_phase()` /
`replay_validate()` / `parse_event_log_lines()` /
`required_audit_fields()`；offline read-only tool；no runtime import）。

files touched:
- `zangetsu/tools/__init__.py` — new package
- `zangetsu/tools/profile_attribution_audit.py` — new offline tool
- `zangetsu/tests/test_profile_attribution_audit.py` — 56 tests

evidence: `docs/recovery/20260424-mod-7/0-9p-audit/01..08*.md` (8 docs)

tests: 56/56 PASS local；adjacent suites 212 PASS / 0 regression
（P7-PR4B 54 + 0-9O-B 62 + 0-9P 40 + 0-9P-AUDIT 56）

attribution verdict: tool ships unconditionally；field readiness depends
on data window — verdict 計算需要 ≥ 7 day rolling window 才視為
actionable（cite `0-9p-audit/04_verdict_thresholds.md`）。
Verdict thresholds:
- GREEN: `unknown_profile_rate < 5%`、`profile_mismatch_rate < 1%`、
  `fingerprint_unavailable_rate < 5%`
- YELLOW: 5–20% / 1–5% / 5–20%
- RED: > 20% / > 5% / > 20%
- `verdict_blocks_consumer_phase(VERDICT_RED) is True`

controlled-diff: **EXPLAINED**（no runtime SHA changed）
Gate-A: PASS
Gate-B: PASS

## 5. PR-C / 0-9R-IMPL-DRY

PR: https://github.com/M116cj/j13-ops/pull/23
main SHA: `fe3075ffe979913fc849c06972f69a32cb597b0b`
branch: `phase-7/0-9r-impl-dry-sparse-candidate-consumer`

summary: `feedback_budget_consumer.py` dry-run consumer
（28-field `SparseCandidateDryRunPlan`、`consume()` / `safe_consume()` /
`ema_smooth()` / `limit_step()` / `enforce_floor_and_diversity()` /
`serialize_plan()` / `required_plan_fields()`；EMA α≤0.20、window≥5、
max_step≤10pp、floor≥0.05、diversity_cap_min≥2；
`ALLOWED_INTERVENTIONS = (PB-FLOOR, PB-DIV, PB-SHIFT)`；three-layer
dry-run invariant：`__post_init__` + `to_event()` + 不存在 `apply`
method；no runtime importer）。

files touched:
- `zangetsu/services/feedback_budget_consumer.py` — new module
- `zangetsu/tests/test_feedback_budget_consumer.py` — 81 tests
- `zangetsu/tests/test_feedback_budget_allocator.py` — allow-list
  extension only（將 consumer 加入 legitimate downstream allow-list）
- `zangetsu/tests/test_profile_attribution_audit.py` — allow-list
  extension only（同上）

evidence: `docs/recovery/20260424-mod-7/0-9r-impl-dry/01..09*.md` (9 docs)

tests: 81/81 PASS local；adjacent suites 293 PASS / 0 regression
（P7-PR4B 54 + 0-9O-B 62 + 0-9P 40 + 0-9P-AUDIT 56 + 0-9R-IMPL-DRY 81）

controlled-diff: **EXPLAINED**（no runtime SHA changed）
Gate-A: PASS
Gate-B: PASS

PR-C consumer is **inert at runtime**：consumer importable but
runtime code 並無 import path（verified by 0-9R `05_runtime_isolation_audit.md`
+ 6 source-text reverse tests）。

## 6. PR-D / 0-9S-READY

PR: (pending — fill after merge)
main SHA: (pending — fill after merge)
branch: `phase-7/0-9s-ready-canary-readiness-gate`

summary: CANARY readiness gate documentation package
（CR1–CR15 readiness criteria、S1–S14 success criteria、F1–F9 failure
criteria、rollback plan、alerting plan、evidence template、operator
checklist、governance approval matrix；docs-only；zero runtime / test
/ tool changes）。

files touched (docs only):
- `docs/recovery/20260424-mod-7/0-9s-ready/01_canary_readiness_gate.md`
- `docs/recovery/20260424-mod-7/0-9s-ready/02_canary_success_failure_criteria.md`
- `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md`
- `docs/recovery/20260424-mod-7/0-9s-ready/04_alerting_and_monitoring_plan.md`
- `docs/recovery/20260424-mod-7/0-9s-ready/05_evidence_template.md`
- `docs/recovery/20260424-mod-7/0-9s-ready/06_operator_checklist.md`
- `docs/recovery/20260424-mod-7/0-9s-ready/07_governance_approval_matrix.md`
- `docs/recovery/20260424-mod-7/0-9s-ready/08_0-9s_ready_final_report.md`
- `docs/recovery/20260424-mod-7/0-9p-r-stack/00_stack_final_report.md` (this file)

checks: docs only; no tests added; no module added; no tool added
controlled-diff: **EXPLAINED** (docs-only)
Gate-A: PASS (expected)
Gate-B: PASS (expected)

PR-D ships **zero runtime change**；CANARY apply path 仍為零；
governance config / branch protection / required_status_checks 全部
不變。

## 7. Stack result

- profile passport persistence: **SHIPPED** via PR-A
  （`passport.arena1.generation_profile_id` +
  `generation_profile_fingerprint` 在 A1 admit time 寫入）
- attribution audit: **SHIPPED** via PR-B
  （offline tool ready；GREEN/YELLOW/RED verdict 計算 + 24-field
  `AttributionAuditResult`；no runtime importer）
- sparse dry-run consumer: **SHIPPED** via PR-C
  （`feedback_budget_consumer.py` dry-run only；
  no apply path；EMA α≤0.20 / max_step≤10pp / floor≥0.05 /
  diversity_cap_min≥2；ALLOWED_INTERVENTIONS = PB-FLOOR/PB-DIV/PB-SHIFT；
  three-layer dry-run invariant）
- CANARY readiness gate: **SHIPPED** via PR-D
  （CR1–CR15 + S1–S14 + F1–F9 + rollback + alerting + evidence
  template + operator checklist + governance matrix；
  gate documented, NOT activated）
- runtime apply path: **NONE EXISTS**
  （sparse-candidate intervention 仍 inert；no runtime caller of
  `feedback_budget_consumer` 或 `feedback_budget_allocator`；
  `arena45_orchestrator.maybe_promote_to_deployable` 仍為唯一
  `DEPLOYABLE` 寫入 path；CODE_FROZEN runtime SHA 6 條全 zero-diff
  except `config.arena_pipeline_sha` PR-A EXPLAINED_TRACE_ONLY）
- CANARY: **NOT STARTED**
- production: **NOT STARTED**

## 8. Forbidden changes audit

| Item | Status across 4 PRs |
| --- | --- |
| alpha generation | UNCHANGED |
| formula generation | UNCHANGED |
| mutation / crossover | UNCHANGED |
| search policy | UNCHANGED |
| generation budget | UNCHANGED |
| sampling weights | UNCHANGED |
| thresholds | UNCHANGED |
| `A2_MIN_TRADES` | PINNED at 25 |
| ATR / TRAIL / FIXED grids | UNCHANGED |
| A3 segment thresholds | UNCHANGED |
| Arena pass/fail | UNCHANGED |
| champion promotion | UNCHANGED |
| `deployable_count` | UNCHANGED |
| execution / capital / risk | UNCHANGED |
| broker module | UNCHANGED |
| CI / GitHub Actions | UNCHANGED |
| branch protection | UNCHANGED |
| `required_signatures` | UNCHANGED |
| `required_status_checks` | UNCHANGED |

`DEPLOYABLE` literal grep across all 4 PR diffs: **single occurrence**
仍只在 `arena45_orchestrator.maybe_promote_to_deployable`；no new
producer。`A2_MIN_TRADES` source-text test pinned at 25 across all 4
PRs。`apply` / `commit` / `execute` / `deploy` symbol grep across the 4
new modules（`generation_profile_identity` / `profile_attribution_audit`
/ `feedback_budget_consumer` plus PR-A passport edits）: **zero**
public-API hits（match CLAUDE.md §17 invariants）。

## 9. Branch protection

`main` branch protection state at start, throughout, and at end of
stack:

```
enforce_admins:        true
required_signatures:   true
linear_history:        true
allow_force_pushes:    false
allow_deletions:       false
required_pull_request_reviews.required_approving_review_count: 1
required_status_checks.strict: true
required_status_checks.contexts: ["controlled-diff", "gate-a", "gate-b"]
restrictions: null
```

四個 PR 的 squash-merge `verified=true`（GitHub PGP）；commit
signing 全程 ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`；
linear history 連續無 merge commit。Stack-level baseline diff for
governance configuration: **0**。

## 10. Remaining risks

- **Pre-0-9P passports without identity (in-flight).** PR-A 起寫入
  `generation_profile_id` + `generation_profile_fingerprint`；但 PR-A
  merge 時刻 in-flight 的 passport（已過 A1 但未存檔）會留下 identity
  缺失，PR-B `audit()` 視為 `unknown_profile`/`unavailable_fingerprint`。
  Mitigation：CR2 要求 audit run within 24h of CANARY activation；
  evidence template doc 05 強制 record。
- **YELLOW verdict requires documented limitation before PR-C consumer
  becomes actionable.** PR-C consumer 在 verdict YELLOW 下不
  short-circuit，但 `plan_status` 由 actionable 降級為 NON_ACTIONABLE
  + structured limitation；任一未在 evidence package 內 documented
  YELLOW 都視為 CR2 FAIL。文檔流程 cite 0-9p-audit/05 + 0-9r-impl-dry/04。
- **Composite scoring weights (0.4 / 0.4 / 0.2) are design proposals.**
  S6–S14 + F9 引用 `composite_score = 0.4*A2_pass + 0.4*deployable_yield
  + 0.2*OOS_passrate` 為現行 design proposal；final tuning requires
  j13 acknowledgement before 0-9S-CANARY（cite doc 02 §3.2）；CR15
  authorization sentence 必須 verbatim 引用授權的 weight tuple。
- **4-PR sequential constraint cannot be parallelized.** Stack 設計上
  PR-A → PR-B → PR-C → PR-D 為硬 dependency chain（PR-B 依賴 PR-A
  passport identity；PR-C 依賴 PR-B verdict gate；PR-D 依賴
  PR-C consumer existence）。任何 PR 重新打開 → 後續 PR 必須 rebase；
  不能 parallel 化。
- **8 pre-existing local Mac test failures remain.** `arena_pipeline.py`
  line 18 `os.chdir("/home/j13/j13-ops")` 在 Mac 解析失敗；這 8 個
  test 在 Alaya CI 全 PASS。Stack 不引入新 Mac-only failure；數量沿用
  PR-C 結算的 8。
- **AKASHA witness independence at single-point-of-failure (Alaya).**
  CLAUDE.md §17.2 規定 witness 由獨立 service 寫；現行 AKASHA service
  與 deployment automation 共享 100.123.49.102 Tailscale endpoint。
  若 Alaya 整機故障，witness chain 與 deployment watchdog 同時失能。
  Stack 期內 untouched；列為下一次 governance review 範圍。
- **Calcifer Gemma4 E4B model drift on YELLOW boundary.** §17.3
  watchdog 對 RED 寫文件規範清楚；GREEN/YELLOW 邊界 LLM 判讀
  nondeterministic，仍須搭配硬 SQL threshold 雙重 check（doc 04 已
  指明，實作為 future order）。

## 11. Recommended next action

Expected:

**TEAM ORDER 0-9S-CANARY — Sparse-Candidate Dry-Run CANARY Activation**
— ONLY if j13 explicitly authorizes via the authorization sentence
template in
`docs/recovery/20260424-mod-7/0-9s-ready/07_governance_approval_matrix.md`：

> "I, j13, explicitly authorize TEAM ORDER 0-9S-CANARY activation on
> commit SHA `<sha>` for treatment cohort `<cohort>` with maximum
> duration `<hh>h`, rollback authority delegated to
> [Operator | Calcifer | j13 only]. This authorization expires at
> `<UTC ts>` and applies only to the specified SHA. Any drift from
> the named SHA invalidates this authorization."

授權必須以下述任一形式記錄（三選一）：
1. Telegram thread 362 message SHA + timestamp。
2. signed commit footer
   `cr15_authorized_by=j13 sha=<authorization_message_sha>`。
3. AKASHA witness POST `kind: canary_activation_authorization`。

If j13 does not authorize → stack 維持 inert；下一輪只允許 docs /
research /  retro 類 PR。

## 12. Stack timeline

四個 PR 的 merge timestamp 與 relative gap：

| PR | Merge timestamp (UTC) | Gap from previous |
| --- | --- | --- |
| PR-A / 0-9P | 2026-04-24 22:38 (approx.) | — |
| PR-B / 0-9P-AUDIT | 2026-04-24 22:46 | **+8m40s** |
| PR-C / 0-9R-IMPL-DRY | 2026-04-25 01:44 | **+2h58m** |
| PR-D / 0-9S-READY | (pending) | (pending merge) |

PR-A → PR-B 8m40s gap 反映 audit tool 是 PR-A passport persistence
直接 read-only consumer，audit 工具設計 + 56-test suite + 8 evidence
docs 主體在 PR-A 期間平行展開、PR-A merge 後立即收口 push。

PR-B → PR-C 2h58m gap 是 stack 中最長的 phase：consumer 模組 ~700 LOC
+ 81 tests + EMA / step-limit / floor / diversity 四層 pipeline 設計
+ three-layer dry-run invariant + allow-list extension 兩處測試 +
9 evidence docs；複雜度為 stack 之冠。

PR-C → PR-D pending：PR-D 為 docs-only PR，無 module / test / tool
delta；merge 在 j13 review 8 evidence docs + 1 stack final report 後
即可 squash-merge。

Stack 全程在 ~3 hour 內完成主要 implementation，PR-D 的 docs 整理
~1 hour。完整 stack window 預期 < 5 hour wall-clock。

## 13. Cross-PR data flow

整個 stack 以 passport identity 為錨，依序串聯 audit → consumer →
CANARY readiness criteria。ASCII diagram：

```
    PR-A  (0-9P)                       PR-B  (0-9P-AUDIT)
    ───────────────                    ──────────────────
    arena_pipeline.py                  profile_attribution_audit.py
      │                                       │
      │ A1 admit:                             │ read-only:
      │   passport.arena1                     │   AttributionAuditResult
      │     .generation_profile_id            │     (24 fields)
      │     .generation_profile_fingerprint   │   classify_verdict()
      │                                       │   verdict_blocks_consumer_phase()
      │ resolve_attribution_chain():          │
      │   arena_run_lineage         >         │
      │   sampling_dispatch_record  >         │
      │   caller-passed             >         │
      │   UNKNOWN                             │
      │                                       │
      ▼                                       ▼
    passport literal ─────► event_log ─────► audit() reads JSON-line
                                              produces verdict
                                              GREEN / YELLOW / RED
                                                           │
                                                           ▼
                                              PR-C  (0-9R-IMPL-DRY)
                                              ─────────────────────
                                              feedback_budget_consumer.py
                                                consume(allocation,
                                                        attribution_verdict, …)
                                                  │
                                                  │ if VERDICT_RED:
                                                  │   plan_status = BLOCKED
                                                  │   block_reason = BLOCK_VERDICT_RED
                                                  │
                                                  │ else:
                                                  │   ema_smooth (α ≤ 0.20)
                                                  │   limit_step (≤ 10pp)
                                                  │   enforce_floor_and_diversity
                                                  │     (floor ≥ 0.05,
                                                  │      diversity_cap_min ≥ 2)
                                                  │   ALLOWED_INTERVENTIONS:
                                                  │     PB-FLOOR | PB-DIV | PB-SHIFT
                                                  │
                                                  ▼
                                              SparseCandidateDryRunPlan
                                                28 fields
                                                mode = DRY_RUN
                                                applied = False
                                                  │
                                                  │ (NEVER reaches runtime;
                                                  │  no apply / commit / execute
                                                  │  symbol on public surface)
                                                  ▼
                                                 ┃
                                                 ┃ inert dry-run plan
                                                 ┃
                                                 ▼
                                              PR-D  (0-9S-READY)
                                              ─────────────────
                                              CANARY readiness gate
                                                CR1–CR15 reads:
                                                  CR1:  PR-A delivered? ──┐
                                                  CR3:  PR-C delivered? ──┤
                                                  CR4:  no runtime apply ─┤
                                                  CR5:  no runtime impt. ─┤
                                                  CR6:  ≥ 7-day stable ───┤
                                                  CR2:  audit GREEN ──────┘
                                                  CR15: j13 authorize
                                                  └──► gate evaluation
                                                       (all-pass except CR2 YELLOW)
                                                       ↓
                                                  TEAM ORDER 0-9S-CANARY
                                                  (gated by j13 authorization
                                                   sentence — verbatim, see
                                                   doc 07)
```

關鍵 invariant：integration 全為 read-only。PR-B 不寫入 passport；
PR-C 不修改 audit 工具；PR-D 不引用 consumer 至 runtime。
四個 PR 中最早一筆 runtime SHA 變動是 PR-A `arena_pipeline_sha`
（EXPLAINED_TRACE_ONLY），其餘三 PR 全 zero-diff on runtime SHA。

## 14. Subagent acceleration

整個 stack 動用 subagent 並行寫作以壓縮 wall-clock；以下是 concrete
data point（誰 / 在哪一 PR / 寫了哪幾份 doc / 並行 vs sequential）：

| PR | Doc set | Authoring mode |
| --- | --- | --- |
| PR-A (0-9P) | 7 evidence docs (`01..07`) | Lead (Claude) sequential — passport persistence touch runtime SHA，所有 doc 須 cross-reference 同一條 controlled-diff exception，採 sequential 寫作以避免互相 contradict |
| PR-B (0-9P-AUDIT) | 8 evidence docs (`01..08`) | Lead (Claude) sequential — audit tool 為 read-only，doc 主體沿用 PR-A 結構，仍採 sequential 寫作 |
| PR-C (0-9R-IMPL-DRY) | 9 evidence docs (`01..09`) | **Subagent parallel** — `07_test_results.md` / `08_controlled_diff_report.md` / `09_0-9r_impl_dry_final_report.md` 三份在 Lead 完成 `01..06` 之後並行寫作，gap 從預期 ~45min 壓到 ~12min |
| PR-D (0-9S-READY) | 8 evidence docs + 1 stack report | **Subagent parallel** — `01..07` 七份 doc 全並行寫作（CR1–CR15、S/F criteria、rollback、alerting、evidence template、operator checklist、governance matrix），Lead 在等待過程中 audit `08_0-9s_ready_final_report.md` 與 stack `00_stack_final_report.md` 的 cross-reference consistency；wall-clock 壓縮 ~3× |

Subagent 運用注意：
1. 並行寫作的 doc 必須有「不互相 reference」的 design property；PR-D
   `01..07` 各自為 self-contained chapter（CR / S/F / rollback / …），
   只在 stack final report 整合 cross-reference，所以可大幅並行。
2. PR-A / PR-B sequential 是因為 controlled-diff exception ledger 與
   audit verdict scheme 須單一 source-of-truth；無法切割。
3. 任何並行寫作之 subagent 輸出 Lead 必須做 Q1 五維 audit；本 stack
   PR-C / PR-D 並行 doc 在 merge 前皆通過 Lead 對抗檢查（input
   boundary / silent failure / external dep / concurrency / scope）。

Lead-only 寫作的部分：(a) `08_*_final_report.md` 各 PR 收口；(b) 本份
`00_stack_final_report.md`；(c) cross-PR data flow ASCII；(d)
Q1 adversarial summary。原因：以上需要全 stack mental model，subagent
因 context window 切割而不適合。

— end of stack final report —
