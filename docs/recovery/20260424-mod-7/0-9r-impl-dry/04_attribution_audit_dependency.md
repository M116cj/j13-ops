# 04 — Attribution Audit Dependency

## 1. Why this dependency exists

PR-B / 0-9P-AUDIT classifies attribution coverage as
GREEN / YELLOW / RED. The consumer **must** consult that verdict
before treating any allocation as actionable, otherwise the dry-run
plan would be built on misattributed profile statistics.

## 2. Verdict consumption

```
plan = consume(
    allocation,
    run_id="...",
    attribution_verdict="GREEN" | "YELLOW" | "RED" | "UNAVAILABLE",
)
```

| Verdict | Plan status |
| --- | --- |
| `RED` | `NON_ACTIONABLE`, `block_reasons += ["ATTRIBUTION_VERDICT_RED"]` |
| `YELLOW` | proceed if other gates clear; `safety_constraints += ["ATTRIBUTION_VERDICT_YELLOW_DOCUMENTED"]` |
| `GREEN` | proceed if other gates clear |
| `UNAVAILABLE` | proceed (treated as "not RED"); other gates still apply |

`attribution_verdict` is normalized to uppercase before comparison
(`"red"` ≡ `"RED"`).

## 3. Operator runbook (ties to PR-B `05_consumer_readiness_verdict.md`)

```
1. Run audit() on most recent log window (>= 7 days).
2. Read result.verdict.
3. If RED:
     do NOT call consume(); fix attribution gap first.
4. If YELLOW:
     document offending rate + cause in evidence package;
     call consume(attribution_verdict="YELLOW") to flag the
     plan with the safety_constraint marker.
5. If GREEN:
     call consume(attribution_verdict="GREEN").
6. Inspect plan.plan_status:
     ACTIONABLE_DRY_RUN → record plan, no apply
     NON_ACTIONABLE     → record plan, no apply
     BLOCKED            → governance-grade failure; investigate
                          block_reasons before retrying
```

## 4. Failure mode: verdict regression

If `audit()` was previously GREEN but a new window returns RED, the
consumer must immediately stop emitting actionable plans. The
operator runbook handles this: each consume() call passes a fresh
verdict; there is no cached/persistent permission slip.

## 5. Failure mode: audit unavailable

When `attribution_verdict=VERDICT_UNAVAILABLE` (default), the
consumer treats it as "not RED" and lets the other gates rule. This
is intentional — early bring-up of the consumer can run before the
audit pipeline is wired without falsely blocking. Once the audit
pipeline is in place, callers MUST pass `GREEN` / `YELLOW` / `RED`
explicitly.

## 6. CR2 in 0-9S-READY

PR-D's CANARY readiness criterion `CR2` enforces:

```
CR2: 0-9P-AUDIT verdict GREEN or documented YELLOW
```

CR2 is checked at **CANARY activation** time, not just at consumer
emission time. A regression to RED after CANARY start triggers
CANARY pause until re-audit clears. This is design-only here;
0-9S-READY will document the runtime watchdog.

## 7. Integration test surface

The consumer's verdict gate is verified by:

- `test_consumer_blocks_red_attribution_verdict`
- `test_consumer_allows_green_attribution_verdict`
- `test_consumer_allows_documented_yellow_attribution_verdict`
- `test_consumer_unavailable_verdict_does_not_block`
- `test_consume_attribution_verdict_string_normalization`
- `test_plan_attribution_verdict_yellow_adds_safety_constraint`
- `test_plan_attribution_verdict_red_does_not_add_yellow_constraint`

Audit-side:

- PR-B's `test_red_classification_blocks_consumer_phase`
- PR-B's `test_attribution_audit_red_classification`
