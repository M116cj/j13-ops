# 08 — Survivor / Near-Survivor Report

**ORDER**: 0-9AB — Workstream D

## Definitions (per survivor_bank.py + order §6/§8)

- **Survivor**: status == PASSED.
- **Near-survivor**: status == REJECTED with net_bps in [−5.0, 0.0] (within 5 bps of break-even).
- NOT_EVALUATED candidates are NEVER survivors or near-survivors.
- ERROR candidates are NEVER survivors or near-survivors.

## Counts

| Axis | Survivors (PASSED) | Near-survivors (REJECTED, net in [-5,0]) |
|---|---:|---:|
| H | 5 | 82 |
| C | 3 | 150 |
| D | 0 | 174 |
| **Total** | **8** | **406** |

## Survivors Are Not Deployables

Per AC30: survivors here are PASSED in the shadow Economic Arena (A2 gate cleared with the simple sign-flip simulator). They do NOT carry a champion-promotion claim and DO NOT increment zangetsu_status.deployable_count. The deployable_count VIEW remains 0 — verified at run start.

## NOT_EVALUATED Separation Verified

- NOT_EVALUATED count in this run = 0 → no separation conflict arose at runtime.
- The classification rule is enforced regardless of the run by survivor_bank.is_survivor / is_near_survivor and is verified by test_not_evaluated_never_survivor.

## Outputs

- shadow_outputs/near_survivor_report.csv — 406 rows.
- Survivor candidates can be filtered from shadow_batch_results.jsonl by status == PASSED (8 rows).

## Acceptance Mapping

- AC27 PASS survivor / near-survivor report produced
- AC28 PASS NOT_EVALUATED candidates are not survivors
- AC29 PASS NOT_EVALUATED candidates are not near-survivors
- AC30 PASS no deployables faked (deployable_count VIEW unchanged at 0)
