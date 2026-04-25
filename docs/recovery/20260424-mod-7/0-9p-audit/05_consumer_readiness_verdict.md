# 05 — Consumer Readiness Verdict (How to Use)

## 1. Purpose

Defines how the verdict from `audit()` is consumed by:

1. PR-C / 0-9R-IMPL-DRY — gates whether the consumer module may
   actionably interpret allocator output.
2. PR-D / 0-9S-READY — gates CANARY readiness criterion CR2.
3. Future operators — informs incident triage.

## 2. Verdict semantics

| Verdict | Meaning | PR-C action |
| --- | --- | --- |
| GREEN | Attribution clean enough for sparse intervention design | PR-C may proceed; consumer's actionability gates assume passport identity is reliable |
| YELLOW | Some attribution gap; documented limitation acceptable | PR-C may proceed only if the YELLOW reason is documented in PR-C's evidence package and is non-blocking (e.g. data window includes pre-0-9P passports) |
| RED | Attribution unreliable | PR-C **blocked**. Investigate + fix + re-audit before unblocking. |

## 3. Verdict expiry

A GREEN / YELLOW verdict expires when:

- New audit window shows a different verdict.
- 7 days have elapsed without a re-audit.
- Significant pipeline change (passport schema / orchestrator boot
  sequence / taxonomy update) introduces ambiguity.

PR-C consumer must treat verdict as a per-day input, not a one-time
permission slip.

## 4. Verdict → safety_constraints

The consumer module's `sparse_candidate_dry_run_plan` stores the
verdict in its `attribution_verdict` field and includes it in
`safety_constraints` if the verdict is YELLOW (so downstream readers
know the plan was generated under documented limitation).

```
plan.attribution_verdict = "GREEN" | "YELLOW" | "RED" | "UNAVAILABLE"
plan.safety_constraints  may include "ATTRIBUTION_VERDICT_YELLOW_DOCUMENTED"
```

## 5. CANARY tie-in

PR-D / 0-9S-READY enforces:

```
CR2: 0-9P-AUDIT verdict GREEN or documented YELLOW
```

CR2 is checked at **CANARY activation** time, not just at PR-C merge
time. A regression to RED after merge requires CANARY pause until
re-audit clears.

## 6. Operator runbook

```
1. Run audit on the most recent log window (≥ 7 days).
2. Confirm verdict.
3. If GREEN:
     proceed to PR-C / continue PR-D readiness checks
4. If YELLOW:
     document offending rate + cause in evidence package
     compare with previous window — improving / stable / degrading?
     stable or improving → may proceed; degrading → stop, re-investigate
5. If RED:
     STOP all sparse-candidate optimization work
     investigate per §04 §6 root-cause checklist
     re-run audit after each suspected fix
     require 3 consecutive GREEN windows before unblocking
```
