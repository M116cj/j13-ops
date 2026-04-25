# 05 — 0-9S-CANARY Evidence Template

## 1. Purpose

PR-D / 0-9S-READY ships a documentation-only **gate**. This file IS the
evidence template every operator MUST complete and file **before** j13
issues a separate `0-9S-CANARY` activation order.

This template is the operator-facing artifact for:

- 0-9R `05_ab_evaluation_and_canary_readiness.md` § 9 (CR1–CR9, plus
  CR10–CR15 added by PR-D — see § 2 below)
- 0-9R-IMPL-DRY `04_attribution_audit_dependency.md` § 6 (CR2 runtime
  watchdog hook)
- 0-9P-AUDIT `profile_attribution_audit.py` GREEN/YELLOW/RED verdict
- CLAUDE.md §17.1 (single-truth VIEW), §17.2 (mandatory witness),
  §17.3 (Calcifer outcome watch), §17.5 (bot-only version bump),
  §17.6 (stale-service check), §17.7 (decision-record CI gate)

PR-D **does not start CANARY**. PR-D **defines the evidence shape** so
that any future CANARY activation is reproducible, auditable, and
non-negotiable.

The template below is a fill-in-the-blanks markdown block. Operator:

1. Create a new directory `docs/governance/canary-evidence/{{YYYYMMDD-canary-N}}/`
2. Copy the entire fenced block at § 14 into that directory as
   `evidence.md`
3. Replace every `{{...}}` placeholder with verified, sourced data
4. Cross-link to `06_operator_checklist.md` for the runbook commands
   that produce each piece of evidence
5. Commit the evidence directory with a signed PR

Empty `{{...}}` placeholders, "TBD", or hand-waved values are not
acceptable. CR satisfaction is checked by humans **and** by the
`version-bump-gate` GitHub Action (CLAUDE.md §17.5 / §17.7).

---

## 2. CR1–CR15 Index

0-9R `§ 9` originally listed CR1–CR9. PR-D extends with CR10–CR15 to
cover the post-0-9R-IMPL-DRY runtime surface (audit watchdog, snapshot
discipline, AKASHA witness wiring). The extended list is the canonical
reference for evidence § 2 below.

| CR# | Source                              | Statement                                                                                  |
| --- | ----------------------------------- | ------------------------------------------------------------------------------------------ |
| CR1 | 0-9R § 9                            | 0-9R-IMPL-DRY consumer 穩定運行 ≥ 7 days，無 G1–G13 violation                              |
| CR2 | 0-9R § 9 + 0-9R-IMPL-DRY § 6        | 0-9P-AUDIT 最近 ≥ 7 day window verdict GREEN，或書面 documented YELLOW                     |
| CR3 | 0-9R § 9                            | 每個 actionable profile 通過 § 03 multi-window 條件（≥ 5 連續 sign-stable）                 |
| CR4 | 0-9R § 9                            | runtime consumer 通過 isolation tests（與 0-9O-B allocator 同等級）                          |
| CR5 | 0-9R § 9                            | rollback path 端到端演練 ≥ 3 次成功（dry-run 切換 baseline ↔ treatment）                    |
| CR6 | 0-9R § 9                            | Calcifer outcome watchdog 已對 sparse-related metrics 加 alert                              |
| CR7 | 0-9R § 9                            | branch protection 未弱化；signed PR-only flow 正常                                           |
| CR8 | 0-9R § 9                            | controlled-diff 在 dry-run 期間維持 EXPLAINED 或 EXPLAINED_TRACE_ONLY                       |
| CR9 | 0-9R § 9                            | j13 顯式授權 0-9S CANARY                                                                    |
| CR10 | PR-D                                | composite scoring weights 已凍結並 sign-off（cohort design § 6 + smoothing knob § 7）       |
| CR11 | PR-D + CLAUDE.md §17.6              | stale-service check 對所有 long-running consumer / allocator / Calcifer service GREEN       |
| CR12 | PR-D + CLAUDE.md §17.2              | AKASHA witness service responding；pre-CANARY witness slot reserved                         |
| CR13 | PR-D                                | Telegram digest path（INFO / WARN / BLOCKING / FATAL）端到端 verified                       |
| CR14 | PR-D                                | git tag `0-9s-canary-{{N}}-pre` signed + pushed；branch protection snapshot 存檔            |
| CR15 | PR-D + CLAUDE.md §17.7              | docs/decisions/YYYYMMDD-canary-{{N}}.md + docs/retros/YYYYMMDD-canary-{{N}}.md 已建立並 PR  |

CR15 ensures the CI decision-record gate (§17.7) cannot be bypassed by
a CANARY activation that lacks a paired decision record.

---

## 3. Filing convention

| Item                  | Convention                                                                       |
| --------------------- | -------------------------------------------------------------------------------- |
| Directory             | `docs/governance/canary-evidence/{{YYYYMMDD}}-canary-{{N}}/`                     |
| Required files        | `evidence.md` (this template), `audit.json`, `consumer-stability.json`, `branch-protection.json`, `snapshot-pre-canary.tar.gz`, `rollback-drill-{1,2,3}.log`, `telegram-preflight.json`, `akasha-witness-receipt.json` |
| Naming                | ISO date + `canary-N` where `N` increments per cohort attempt (1, 2, 3, ...)     |
| Retention             | **Non-deletable.** Append-only; corrections via new directory + decision record. |
| Index                 | Link added to `docs/governance/canary-evidence/INDEX.md`                         |
| Permanent ledger      | Each entry becomes part of the governance ledger; cannot be rewritten            |

If a CANARY attempt is aborted before activation, the partial evidence
directory is **still kept** (rename `evidence.md` → `evidence-aborted.md`
and add `abort-reason.md`). Aborted attempts count toward the `N`
counter; the next attempt is `canary-(N+1)`.

---

## 4. Authorization chain

CANARY activation requires a verbatim j13 authorization sentence. The
operator does **not** paraphrase, translate, or reformat. The exact
text is captured in evidence § 1.

The sentence MUST contain:

- The literal token `0-9S-CANARY`
- Either `授權` or `authorize` / `authorization`
- A timestamp or session reference

Examples of acceptable sentences (operator pastes whichever j13 sent):

```
2026-04-25 22:30 UTC — j13: 授權 0-9S-CANARY 啟動，cohort treatment-v1，14 天視窗
```

```
authorization 0-9S-CANARY canary-1, treatment cohort, 14-day window — j13, 2026-04-25
```

If the sentence is ambiguous (no `0-9S-CANARY` token, no timestamp, or
appears in chitchat rather than an explicit order line), the operator
MUST request re-authorization. Do not infer.

---

## 5. Audit verdict requirement (CR2)

CR2 requires the operator pull a fresh attribution audit and embed the
result.

- Window: **most recent ≥ 7 days** ending **at or after** the
  activation timestamp − 24 hours
- Tool: `zangetsu/tools/profile_attribution_audit.py` (PR-B / 0-9P-AUDIT,
  PR #22, SHA `3219b805`)
- Verdict states: `GREEN`, `YELLOW`, `RED`
- **`RED` is a hard block** — operator MUST NOT proceed; CR2 fails;
  evidence package returns to draft until a fresh window is GREEN
- `YELLOW` requires a documented YELLOW justification in evidence § 3
  (offending rate + cause), per
  `0-9r-impl-dry/04_attribution_audit_dependency.md` § 3 step 4

The runtime watchdog hooked at CR2 means the verdict is **also** checked
during CANARY (not just at activation). If the verdict regresses to RED
mid-CANARY → CANARY pauses, baseline weights re-applied, incident filed.

---

## 6. Dry-run consumer stability (CR1)

The 0-9R-IMPL-DRY consumer (`zangetsu/services/feedback_budget_consumer.py`,
PR #23, SHA `fe3075f`) MUST have logged ≥ 7 calendar days of
`sparse_candidate_dry_run_plan` events with:

- `plan_applied = false` for every plan (dry-run invariant)
- ≥ 1 ACTIONABLE_DRY_RUN per day on average
- ≥ 5 consecutive sign-stable runs on the most recent actionable
  profile（§ 03 multi-window condition）
- No `BLOCKED` plan with `block_reasons` containing
  `ATTRIBUTION_VERDICT_RED` in the trailing 7 days
- No G1–G13 governance violation in the trailing 7 days

Evidence § 4 captures the raw counts. Source data: AKASHA `events`
table filtered by `event_type = 'sparse_candidate_dry_run_plan'` and
`run_id LIKE 'dry-%'`.

---

## 7. Outcome metric baselines (must be measured live)

Per CLAUDE.md §17.1, "deployable" is defined by the
`zangetsu_status` VIEW (`deployable_count` column). All baseline numbers
in evidence § 5 MUST come from a live VIEW query, **not** from a
remembered or estimated value.

Operator runs the queries in `06_operator_checklist.md` Phase 0; the
JSON output is attached to the evidence directory as
`baseline-metrics.json`. Evidence § 5 quotes the JSON.

Evidence § 5 covers a **14-day** window (vs the audit's 7-day) because
S1–S12 success criteria need a stable trend, not a single-week sample.

---

## 8. Cohort design freeze (CR10)

By the time evidence is filed, the cohort design must be frozen:

- Split method: passport tag (`passport.experiment.cohort`) preferred,
  worker_id fallback per 0-9R § 2.3
- STRATEGY_ID isolation: `j01` only (j02 runs but is **not** mixed into
  the comparison), per 0-9R § 2.1
- Treatment cohort size: explicit % (e.g. 10 / 25 / 50)
- Baseline cohort size: 100 − treatment%
- Expected duration: integer days, ≥ 14 (per PR2 in 0-9R § 10),
  ≤ 30 (off-cycle cap in 0-9R § 11)

If cohort size is "TBD" or "to be determined at activation", evidence
is incomplete. Operator must lock the design at evidence-write time.

---

## 9. Smoothing knob bounds (CR10)

PR-D enforces hard bounds on the smoothing knobs supplied to the
allocator at CANARY start. Evidence § 7 records the values; the
`version-bump-gate` rejects values outside these ranges.

| Knob              | Bound          | Reason                                                                |
| ----------------- | -------------- | --------------------------------------------------------------------- |
| `ema_alpha`       | ≤ 0.20         | over-aggressive smoothing nullifies the signal (0-9R § 7 F7 risk)     |
| `smoothing_window`| ≥ 5            | shorter windows produce noise-driven sign flips                       |
| `max_step_abs`    | ≤ 0.10         | per-round capped step prevents runaway weight movement                |
| `exploration_floor`| ≥ 0.05        | matches F7 hard floor — never allow a profile below 5%                |
| `diversity_cap_min`| ≥ 2           | at least two profiles must remain actionable to avoid F6 collapse     |

Values **outside** these ranges = evidence rejected.
Values **at** these ranges = allowed but flagged in evidence § 11
checklist with a brief justification line.

---

## 10. Composite scoring weights (CR10)

0-9R § 5 proposes `0.40 / 0.40 / 0.20` (a2 / a3 / deployable_density).
PR-D requires evidence § 8 explicitly declare the chosen weights and
sum to 1.0. Departure from the design defaults requires a one-line
justification cross-linked to a docs/decisions/ entry.

---

## 11. Rollback discipline (CR5, CR11, CR14)

Evidence § 9 demonstrates rollback is not theoretical:

- `baseline weight snapshot path`: must reference a file under
  `docs/governance/canary-evidence/{{YYYYMMDD-canary-N}}/baseline-weights.json`
- `pre-CANARY git tag`: signed annotated tag (`0-9s-canary-{{N}}-pre`)
- `pre-CANARY snapshot`: output of `scripts/governance/capture_snapshot.sh`
- `/tmp/canary_state.json` initialized: confirms runtime state file
  exists with `state = "PRE_ACTIVATION"`
- `rollback.sh path`: scripts/canary/rollback.sh resolves; `--dry-run`
  exit 0
- Rollback drills: ≥ 3 timestamped successful runs **before**
  activation (CR5 explicitly requires "≥ 3 次成功")

Stale-service check (CLAUDE.md §17.6) covers `feedback_budget_consumer`,
`feedback_budget_allocator`, and `calcifer-supervisor`. Each service's
`ActiveEnterTimestamp` ≥ source mtime, recorded in evidence § 11
checklist with a line-per-service.

---

## 12. Alert / witness path (CR6, CR12, CR13)

CANARY runs without manual polling. Evidence § 10 confirms:

- Calcifer outcome watchdog is alerting on
  `deployable_count` drop and `last_live_at_age_h` regression
  (CLAUDE.md §17.3 / §17.4)
- `/tmp/calcifer_deploy_block.json` is **absent** at the moment of
  evidence sign-off (presence = RED = STOP)
- AKASHA witness preflight POST returns 200 and a witness slot id
- Telegram bot @Alaya13jbot reachable via `getMe`
- INFO / WARN / BLOCKING / FATAL routes have each delivered at least
  one test message in the preflight phase (timestamps recorded)

The witness slot id reserved at preflight is the same id quoted in
evidence § 12 ("AKASHA witness id"). After activation, the witness
service writes the actual receipt; before activation, the slot proves
the path is wired.

---

## 13. Sign-off (CR15)

Evidence § 12 captures three signatures:

1. Operator name + the commit SHA where evidence was filed
2. j13 acknowledgement (verbatim quote with timestamp; cross-link to
   the same source as the authorization in § 1)
3. AKASHA witness id (the slot id reserved at preflight, later
   confirmed by the witness service after activation)

A missing signature line = `version-bump-gate` rejects the activation
PR.

---

## 14. Template (copy this block into `evidence.md`)

```markdown
# 0-9S-CANARY Evidence Package — {{YYYYMMDD-canary-N}}

> Operator: replace every {{...}} with verified data. Do not delete
> sections. If a section is N/A, write `N/A — reason: ...`. Empty
> placeholders fail CR15 and are rejected by version-bump-gate.

## 1. Activation request

- Order id: 0-9S-CANARY
- j13 authorization sentence (verbatim, including timestamp):
  ```
  {{paste exact j13 text}}
  ```
- Activation timestamp (UTC, ISO 8601): {{YYYY-MM-DDTHH:MM:SSZ}}
- Git tag at activation: {{0-9s-canary-N-pre}} ({{full SHA}})
- Branch protection snapshot:
  ```json
  {{output of `gh api repos/M116cj/j13-ops/branches/main/protection`}}
  ```

## 2. CR satisfaction (CR1–CR15)

| CR# | Status (PASS / FAIL / DOCUMENTED-YELLOW) | Evidence path                                            |
| --- | ---------------------------------------- | -------------------------------------------------------- |
| CR1 | {{PASS}}                                  | {{relative path inside this dir}}                        |
| CR2 | {{PASS or DOCUMENTED-YELLOW}}             | {{audit.json}}                                            |
| CR3 | {{PASS}}                                  | {{consumer-stability.json}}                               |
| CR4 | {{PASS}}                                  | {{tests/INTEGRATION-RESULTS.md}}                          |
| CR5 | {{PASS}}                                  | {{rollback-drill-1.log, rollback-drill-2.log, rollback-drill-3.log}} |
| CR6 | {{PASS}}                                  | {{calcifer-watchdog.json}}                                |
| CR7 | {{PASS}}                                  | {{branch-protection.json}}                                |
| CR8 | {{PASS}}                                  | {{controlled-diff-status.md}}                             |
| CR9 | {{PASS}}                                  | {{see § 1 — j13 authorization sentence}}                  |
| CR10 | {{PASS}}                                 | {{see § 6 / § 7 / § 8}}                                   |
| CR11 | {{PASS}}                                 | {{stale-service-check.json}}                              |
| CR12 | {{PASS}}                                 | {{akasha-witness-receipt.json}}                           |
| CR13 | {{PASS}}                                 | {{telegram-preflight.json}}                               |
| CR14 | {{PASS}}                                 | {{git-tag-verify.txt + branch-protection.json}}           |
| CR15 | {{PASS}}                                 | {{docs/decisions/YYYYMMDD-canary-N.md, docs/retros/...}}  |

## 3. Attribution audit (most recent window ≥ 7 days)

- Window start (UTC): {{YYYY-MM-DDTHH:MM:SSZ}}
- Window end (UTC):   {{YYYY-MM-DDTHH:MM:SSZ}}
- Total events: {{integer}}
- A1 / A2 / A3 split: {{A1 count}} / {{A2 count}} / {{A3 count}}
- passport_identity_rate: {{0.000 — 1.000}}
- orchestrator_fallback_rate: {{0.000 — 1.000}}
- unknown_profile_rate: {{0.000 — 1.000}}
- profile_mismatch_rate: {{0.000 — 1.000}}
- fingerprint_unavailable_rate: {{0.000 — 1.000}}
- Verdict: {{GREEN | YELLOW | RED}}
- If YELLOW — documented reasons (rate + cause): {{free text}}
- If RED — STOP. Do not proceed. File `evidence-aborted.md`.
- Audit JSON path: {{audit.json}}
- Tool SHA: 0-9P-AUDIT PR #22 / SHA 3219b805 (or newer; record actual)

## 4. Dry-run consumer stability (≥ 7 days)

- Number of `sparse_candidate_dry_run_plan` events: {{integer}}
- ACTIONABLE_DRY_RUN count: {{integer}}
- NON_ACTIONABLE count:    {{integer}}
- BLOCKED count:           {{integer}}
- Consecutive sign-stable runs (most recent actionable profile): {{integer; must be ≥ 5}}
- Latest plan_id: {{uuid or string}}
- Latest plan applied: False  (CR1 invariant — must be False)
- Source: AKASHA events query, run at {{UTC timestamp}}
- Consumer SHA: 0-9R-IMPL-DRY PR #23 / SHA fe3075f (or newer; record actual)

## 5. Outcome metric baselines (last 14 days, live VIEW)

> Source: `zangetsu_status` VIEW per CLAUDE.md §17.1. Re-query, do not
> cite a remembered number.

- A2 pass_rate baseline: {{0.000 — 1.000}}
- A3 pass_rate baseline: {{0.000 — 1.000}}
- A2 SIGNAL_TOO_SPARSE rate baseline: {{0.000 — 1.000}}
- A3 OOS_FAIL rate baseline: {{0.000 — 1.000}}
- deployable_count 7-day rolling median baseline: {{integer}}
- UNKNOWN_REJECT baseline: {{0.000 — 1.000; should be < 0.05 per S6}}
- Query timestamp (UTC): {{YYYY-MM-DDTHH:MM:SSZ}}
- Raw JSON: {{baseline-metrics.json}}

## 6. Cohort design (frozen)

- Cohort split method: {{passport tag | worker_id parity}}
- Passport tag value (if used): {{passport.experiment.cohort = "..."}}
- STRATEGY_ID isolation: j01 only (j02 not mixed)
- Treatment cohort size (% of total): {{integer 5–50}}
- Baseline cohort size (% of total):  {{100 − treatment%}}
- Expected duration (days): {{integer 14–30}}
- Cohort mapping artifact: {{cohort-mapping.json}}

## 7. Smoothing knob configuration

| Knob               | Value         | Bound          | Within bound? |
| ------------------ | ------------- | -------------- | ------------- |
| ema_alpha          | {{0.00–0.20}} | ≤ 0.20         | {{Y/N}}       |
| smoothing_window   | {{integer}}   | ≥ 5            | {{Y/N}}       |
| max_step_abs       | {{0.00–0.10}} | ≤ 0.10         | {{Y/N}}       |
| exploration_floor  | {{0.05–0.20}} | ≥ 0.05         | {{Y/N}}       |
| diversity_cap_min  | {{integer}}   | ≥ 2            | {{Y/N}}       |

Any "N" → evidence rejected.

## 8. Composite scoring weights

| Component             | Weight   |
| --------------------- | -------- |
| a2_pass_rate          | {{0.40}} |
| a3_pass_rate          | {{0.40}} |
| deployable_density    | {{0.20}} |
| **Total**             | **1.00** |

Departure from design defaults (0.40 / 0.40 / 0.20)?
{{No}} — or {{Yes — justification: ... + cross-link to docs/decisions/YYYYMMDD-...}}

## 9. Rollback artifacts

- baseline weight snapshot path: {{baseline-weights.json}}
- pre-CANARY git tag: 0-9s-canary-{{N}}-pre
- pre-CANARY git tag SHA: {{full SHA}}
- pre-CANARY snapshot path (output of scripts/governance/capture_snapshot.sh):
  {{snapshot-pre-canary.tar.gz}}
- `/tmp/canary_state.json` initialized: {{Y/N}} — current state value: PRE_ACTIVATION
- rollback.sh path: scripts/canary/rollback.sh
- rollback drill performed (≥ 3 times before activation):
  - drill 1: {{YYYY-MM-DD HH:MM UTC, log path}}
  - drill 2: {{YYYY-MM-DD HH:MM UTC, log path}}
  - drill 3: {{YYYY-MM-DD HH:MM UTC, log path}}

## 10. Alert / witness path

- Calcifer outcome watchdog active: {{Y}} — last heartbeat: {{UTC timestamp}}
- /tmp/calcifer_deploy_block.json absent (presence = RED = STOP): {{Y}}
- Telegram bot @Alaya13jbot reachable (`getMe` 200): {{Y}}
- AKASHA witness service responding: {{Y}} — preflight slot id: {{slot id}}
- INFO route verified: {{Y, message id, UTC timestamp}}
- WARN route verified: {{Y, message id, UTC timestamp}}
- BLOCKING route verified: {{Y, message id, UTC timestamp}}
- FATAL route verified: {{Y, message id, UTC timestamp}}

## 11. Pre-activation checklist

- [ ] CR1–CR15 all met (table § 2)
- [ ] j13 explicit authorization received (§ 1, verbatim)
- [ ] Branch protection intact: enforce_admins, required_signatures,
      required_linear_history all true; allow_force_pushes,
      allow_deletions both false (§ 1 snapshot)
- [ ] Audit verdict GREEN or documented YELLOW (§ 3)
- [ ] Consumer ≥ 7 days stable, ≥ 5 consecutive sign-stable runs (§ 4)
- [ ] Baseline metrics queried live, not remembered (§ 5)
- [ ] Cohort design frozen (§ 6)
- [ ] Smoothing knobs within bounds (§ 7)
- [ ] Composite weights sum to 1.0 (§ 8)
- [ ] Rollback drill ≥ 3 successful runs (§ 9)
- [ ] Calcifer watchdog active, no deploy_block (§ 10)
- [ ] AKASHA witness slot reserved (§ 10)
- [ ] Telegram all four routes verified (§ 10)
- [ ] Snapshot captured + path verified (§ 9)
- [ ] Git tag pushed and signed (`git tag -v` exit 0)
- [ ] Stale-service check GREEN for consumer + allocator + Calcifer
      (CLAUDE.md §17.6)
- [ ] docs/decisions/{{YYYYMMDD-canary-N}}.md committed (CR15 / §17.7)
- [ ] docs/retros/{{YYYYMMDD-canary-N}}.md committed if /team used (§17.7)

## 12. Sign-off

- Operator name: {{name}}
- Operator signature (PR # / commit SHA where evidence was filed):
  {{PR # or SHA}}
- j13 acknowledgement (verbatim, with timestamp):
  ```
  {{paste exact j13 ack text}}
  ```
- AKASHA witness slot id (reserved at preflight): {{slot id}}
- AKASHA witness receipt id (post-activation, written by witness service): {{receipt id or "PENDING — to be populated by witness service after activation"}}

## 13. Post-activation appendix (populated after T+0)

> Operator extends this section as the CANARY runs. Do not pre-populate.

- T+5min  digest: {{summary or path}}
- T+30min digest: {{}}
- T+1h    digest: {{}}
- T+24h   digest: {{}}
- T+72h   digest: {{}}
- T+7d    digest: {{}}
- T+14d   digest: {{}}
- Daily audit re-run results: {{path or table}}
- Composite score trajectory: {{path or chart reference}}
- Any STOP trigger fired? {{N or Y + rollback report path}}
```

---

## 15. Cross-references

| Source                                                                  | Relevance                                |
| ----------------------------------------------------------------------- | ---------------------------------------- |
| `0-9r/05_ab_evaluation_and_canary_readiness.md`                         | CR1–CR9 origin; S1–S12; F1–F8            |
| `0-9r-impl-dry/04_attribution_audit_dependency.md`                      | CR2 verdict-consumption rules            |
| `0-9p-audit/...` (PR #22 SHA `3219b805`)                                | `audit()` API; verdict semantics         |
| 0-9R-IMPL-DRY consumer (PR #23 SHA `fe3075f`)                           | `feedback_budget_consumer.py` API        |
| 0-9P (PR #21 SHA `a8a8ba9`)                                              | passport persistence; `resolve_attribution_chain` |
| 0-9O-B                                                                   | `feedback_budget_allocator.py`           |
| P7-PR4B                                                                  | A1/A2/A3 aggregate Arena telemetry       |
| CLAUDE.md §17.1                                                          | `<project>_status` VIEW = single truth   |
| CLAUDE.md §17.2                                                          | mandatory AKASHA witness                 |
| CLAUDE.md §17.3                                                          | Calcifer outcome watch                   |
| CLAUDE.md §17.4                                                          | auto-regression revert                   |
| CLAUDE.md §17.5                                                          | `bin/bump_version.py` enforcement        |
| CLAUDE.md §17.6                                                          | stale-service check                      |
| CLAUDE.md §17.7                                                          | decision-record CI gate                  |
| `06_operator_checklist.md` (this directory)                              | runbook commands per phase               |

---

## 16. Notes for future maintainers

- This template **adds** CR10–CR15 on top of 0-9R § 9. If 0-9R is
  later amended to expand its CR list, **align here**; do not
  duplicate or contradict.
- Knob bounds in § 9 are **defaults**; tightening is allowed via
  signed PR + decision record. Loosening requires j13 explicit order.
- The template itself is governance code. Edits to this file go
  through the same signed-PR + decision-record discipline as runtime
  code.
- 0-9S-READY ships **only** this template + `06_operator_checklist.md`.
  Activation is a **separate** order under a **separate** PR. PR-D
  must not contain any code that flips a feature flag or starts a
  CANARY job.
