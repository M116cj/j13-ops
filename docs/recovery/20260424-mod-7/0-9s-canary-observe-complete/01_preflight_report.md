# 01 — Preflight Report

## 1. Tool

`zangetsu/tools/sparse_canary_readiness_check.check_readiness()`

## 2. Inputs supplied

```python
audit_verdict="GREEN"
consumer_days_stable=4
consumer_override=True             # documented per order §2 / preflight rule
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
j13_authorization_present=True     # order §19 sentence
```

## 3. Per-criterion verdict

| CR | Verdict | Note |
| --- | --- | --- |
| CR1 | PASS | passport.arena1 persists generation_profile_id (PR-A 0-9P) |
| CR2 | PASS | attribution verdict GREEN |
| CR3 | PASS | feedback_budget_consumer.py present (PR-C 0-9R-IMPL-DRY) |
| CR4 | PASS | no apply_* runtime symbol |
| CR5 | PASS | consumer not imported by runtime |
| CR6 | OVERRIDE | order §2 / preflight rule explicit override (PR-C merged < 7 days) |
| CR7 | PASS | unknown_reject_rate=0.02 < 0.05 |
| CR8 | PASS | A2 sparse trend measurable via 0-9P-AUDIT |
| CR9 | PASS | A3 pass_rate measurable via P7-PR4B aggregate telemetry |
| CR10 | PASS | deployable_count measurable via champion_pipeline VIEW |
| CR11 | PASS | rollback plan committed (0-9s-ready/03) |
| CR12 | PASS | alerting plan committed (0-9s-ready/04) |
| CR13 | PASS | branch protection intact through PR-A through 0-9S-OBSERVE-FAST |
| CR14 | PASS | signed PR-only flow intact |
| CR15 | PASS | order §19 j13 authorization sentence present |

## 4. Overall verdict

```
overall_verdict: PASS
overall_blocks_canary: False
notes: []
```

## 5. Conclusion

Preflight clears CANARY observation continuation per order §3 / §17.
CR6 OVERRIDE documented. No blocking failure. Replay/backfill phase
may proceed.

## 6. Repro

```bash
python3 -c "
from zangetsu.tools.sparse_canary_readiness_check import check_readiness
r = check_readiness(
    audit_verdict='GREEN', consumer_days_stable=4, consumer_override=True,
    unknown_reject_rate=0.02, a2_sparse_trend_measured=True,
    a3_pass_rate_measured=True, deployable_evidence_measured=True,
    branch_protection={'enforce_admins':True,'required_signatures':True,
                        'linear_history':True,'allow_force_pushes':False,
                        'allow_deletions':False},
    signed_pr_only=True, j13_authorization_present=True,
)
print('overall:', r.overall_verdict, 'blocks:', r.overall_blocks_canary)
for c in r.cr_results: print(f'{c.cr_id}: {c.verdict}')
"
```
