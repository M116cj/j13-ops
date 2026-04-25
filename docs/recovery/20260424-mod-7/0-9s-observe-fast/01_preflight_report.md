# 01 — Preflight Report

## 1. Tool

`zangetsu/tools/sparse_canary_readiness_check.check_readiness()`

## 2. Inputs supplied

```python
audit_verdict="GREEN"
consumer_days_stable=3
consumer_override=True             # documented per order §3
unknown_reject_rate=0.02
a2_sparse_trend_measured=True
a3_pass_rate_measured=True
deployable_evidence_measured=True
branch_protection={
    "enforce_admins": True,
    "required_signatures": True,
    "linear_history": True,
    "allow_force_pushes": False,
    "allow_deletions": False,
}
signed_pr_only=True
j13_authorization_present=True     # order §9 sentence
```

## 3. Per-criterion verdict (live tool output)

| CR | Verdict | Note |
| --- | --- | --- |
| CR1 | PASS | passport.arena1 persists generation_profile_id |
| CR2 | PASS | attribution verdict GREEN |
| CR3 | PASS | feedback_budget_consumer.py present |
| CR4 | PASS | no apply_* function in services/ |
| CR5 | PASS | consumer not imported by runtime |
| CR6 | OVERRIDE | j13 order text treated as explicit override per §3 preflight rule |
| CR7 | PASS | unknown_reject_rate=0.0200 < 0.05 |
| CR8 | PASS | A2 sparse rate trend measured |
| CR9 | PASS | A3 pass_rate evidence available |
| CR10 | PASS | deployable_count evidence available |
| CR11 | PASS | rollback plan: 03_rollback_plan.md |
| CR12 | PASS | alerting plan: 04_alerting_and_monitoring_plan.md |
| CR13 | PASS | branch protection intact |
| CR14 | PASS | signed PR-only flow intact |
| CR15 | PASS | j13 authorization sentence present per §22 |

## 4. Overall verdict

```
overall_verdict: PASS
overall_blocks_canary: False
notes: []
```

## 5. Conclusion

Preflight clears CANARY observation activation per order §3. CR6 OVERRIDE
documented. No blocking failure detected. Observation may proceed.

## 6. Repro

```
python3 -c "
from zangetsu.tools.sparse_canary_readiness_check import check_readiness
r = check_readiness(
    audit_verdict='GREEN',
    consumer_days_stable=3,
    consumer_override=True,
    unknown_reject_rate=0.02,
    a2_sparse_trend_measured=True,
    a3_pass_rate_measured=True,
    deployable_evidence_measured=True,
    branch_protection={
        'enforce_admins': True, 'required_signatures': True,
        'linear_history': True, 'allow_force_pushes': False,
        'allow_deletions': False,
    },
    signed_pr_only=True,
    j13_authorization_present=True,
)
print('overall_verdict:', r.overall_verdict)
print('blocks_canary:', r.overall_blocks_canary)
for cr in r.cr_results:
    print(f'{cr.cr_id}: {cr.verdict}  -- {cr.note}')
"
```
