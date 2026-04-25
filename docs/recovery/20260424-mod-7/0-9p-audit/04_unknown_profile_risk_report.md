# 04 — UNKNOWN_PROFILE Risk Report

## 1. Why UNKNOWN_PROFILE matters

Allocator-side, 0-9O-B's `compute_proposed_weights` already caps
UNKNOWN_PROFILE at `EXPLORATION_FLOOR (=0.05)` so it cannot dominate.
Audit-side, a high `unknown_profile_rate` is a **signal**: the upstream
producer is silently losing identity, which means any sparse-candidate
intervention based on profile statistics will misattribute.

## 2. Sources of UNKNOWN_PROFILE

| Source | Mitigation |
| --- | --- |
| Passport never written (pre-0-9P data) | Time → expire old passports |
| `_gen_profile_identity` resolution failed at A1 | Log + investigate |
| `passport.arena1` corruption / wrong shape | Schema validation upstream |
| Replay against fixture missing identity | Fixture upgrade |
| Orchestrator boot before workers had identity ready | Order-of-startup fix (out-of-scope for 0-9P-AUDIT) |
| `STRATEGY_ID` mismatch between A1 and A2/A3 | Cross-strategy isolation order |

## 3. Threshold

GREEN max: `unknown_profile_rate < 0.05`. Above that, optimizer-grade
decisions become unreliable.

## 4. Audit query

```python
result = audit(events)
risk_metrics = {
    "unknown_profile_rate": result.unknown_profile_rate,
    "unknown_profile_count": result.unknown_profile_count,
    "fingerprint_unavailable_rate": result.fingerprint_unavailable_rate,
}
```

## 5. Decision tree

```
unknown_profile_rate < 0.05 ─→ GREEN. Continue.
0.05 ≤ rate ≤ 0.20          ─→ YELLOW. Document cause.
                               Reasons must include:
                                 - data window covers pre-0-9P period?
                                 - any logged identity-resolution failures?
                                 - fingerprint_unavailable_rate also climbing?
                               If documented → may proceed to PR-C with
                               that limitation noted in PR-C's evidence
                               package.
rate > 0.20                  ─→ RED. STOP. PR-C is blocked.
```

## 6. RED-mode handling

Do **not** start PR-C / 0-9R-IMPL-DRY when verdict is RED.
Investigate root cause:

1. Confirm passport literal really persists `generation_profile_id`
   in current main (`grep "0-9P attribution closure"` should hit).
2. Run `replay_validate` on the current passport corpus — if the
   fixture says `passport_arena1` rate is high but production audit
   says `unknown` is high, the gap is at log-emission time
   (`arena_pass_rate_telemetry` reader did not pick it up).
3. Check `arena_rejection_taxonomy` for unknown-reject drift —
   high `UNKNOWN_REJECT` rate often correlates with attribution
   blind spots.

## 7. Re-audit after fix

Re-run `audit` after each suspected fix; require ≥ 3 consecutive
windows of GREEN before clearing PR-C blockage.
