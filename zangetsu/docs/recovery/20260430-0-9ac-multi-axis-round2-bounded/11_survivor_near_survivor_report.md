# 11 — Survivor / Near-Survivor Report

**ORDER**: 0-9AC-CLOSE — Workstream E

## Definitions

- **Survivor**: status == PASSED.
- **Near-survivor**: status == REJECTED with net_bps in [−5.0, 0.0].
- NOT_EVALUATED candidates are NEVER survivors or near-survivors.
- ERROR candidates are NEVER survivors or near-survivors.

## Counts

| Axis | Survivors (PASSED) | Near-survivors (REJECTED, net in [-5, 0]) |
|---|---:|---:|
| H | 11 | 95 |
| C | 9 | 95 |
| D | 0 | 728 |
| **Total** | **20** | **918** |

## Note on D's Near-Survivor Count

728 of D's 896 rejections are `no_trades_generated` with net_bps = 0.0; these fall in the [-5, 0] band by definition. They represent ABSENCE of signal-driven trades, not edge-narrowly-missed setups. The near-survivor metric is preserved as a strict definition; future tournaments interpreting D's improvement should weight `mean_trade_count` from the band-crossing report rather than this raw count.

## Survivors Are Not Deployables

Per AC29: PASSED candidates here cleared the shadow A2 gate (trade_count ≥ 25 AND net positive). They do NOT increment zangetsu_status.deployable_count. The deployable_count VIEW remains 0, verified at run start AND after PR merge. Champion promotion semantics unchanged.

## NOT_EVALUATED Separation Verified

NOT_EVALUATED = 0 in run; rule enforced by survivor_bank.is_survivor / is_near_survivor regardless of run; tested in test_core_factory_survivor_bank.py.

## Outputs

- `shadow_outputs/near_survivor_report.csv` — 918 rows.
- Survivors filterable from shadow_batch_results.jsonl by status == PASSED (20 rows).

## Acceptance Mapping

- AC26 PASS survivor / near-survivor report produced
- AC27 PASS NOT_EVALUATED candidates are not survivors
- AC28 PASS NOT_EVALUATED candidates are not near-survivors
- AC29 PASS no deployables faked (deployable_count VIEW unchanged at 0)
