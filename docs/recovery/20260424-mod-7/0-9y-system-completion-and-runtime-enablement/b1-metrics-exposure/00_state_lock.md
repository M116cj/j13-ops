# 00 — State Lock (Subprogram B1)

**Master order:** 0-9Y / Subprogram B1 — Pipeline Metrics Exposure Fix
**Captured:** 2026-04-27T18:25Z (start of B1 work)

## Carry-forward from Subprogram A

| Field | Verified |
|---|---|
| HEAD | `486e726b698a2076e6df128f1a85d1bb5ccd2b41` (after PR #54 merge) |
| origin/main | `486e726b` (in sync) |
| Branch (capture) | main |
| §17.6 stale-check | FRESH 4/4 (workers from earlier session) |
| A1 telemetry | last 100 batches: residual=0, CI=0, UNKNOWN_REJECT=0 |
| DB v0.7.1 | 8/8 objects |
| deployable_count | 0 (carry-forward) |
| Risk register | A's 02_risk_register.md, 10 entries |

## Working tree at B1 start

```
 M calcifer/maintenance.log
 M calcifer/maintenance_last.json
 M calcifer/report_state.json
 M zangetsu/logs/engine.jsonl.1
```

Pre-existing runtime artifacts only.

## STOP-condition check

| Condition | Triggered |
|---|---|
| HEAD ≠ origin/main | NO |
| A1 runtime dead | NO |
| DB unavailable | NO |
| A1 telemetry regression | NO |

Baseline clean for source-touching work to begin.
