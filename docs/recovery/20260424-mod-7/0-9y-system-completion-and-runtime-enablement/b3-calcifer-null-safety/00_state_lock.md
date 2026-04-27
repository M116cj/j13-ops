# 00 — State Lock (Subprogram B3)

**Master order:** 0-9Y / Subprogram B3 — Calcifer NULL-Safety Patch
**Captured:** 2026-04-27T18:50Z

## Carry-forward

| Field | Verified |
|---|---|
| HEAD | `9e84a20bb933ea63465ecf6843f906422c66010b` (after PR #56 / B2 merge) |
| origin/main | `9e84a20b` (in sync) |
| §17.6 stale-check on B1 source | still STALE (workers from 17:02; B1 source mtime 18:35) — orthogonal to B3 |
| A1 telemetry | last 100 batches: residual=0, CI=0, UNKNOWN_REJECT=0 (carry-forward) |
| DB v0.7.1 | 8/8 objects |
| zangetsu_status | deployable_count = 0; last_live_at_age_h = NULL (this is the input to the predicate B3 is fixing) |
| /tmp/calcifer_deploy_block.json | **does not exist** before B3 patch (this is the false-green being fixed) |
| /tmp/calcifer_process_green.json | exists, color=GREEN — process side is healthy independent of outcome side |

## Working tree

Same 4 runtime-artifact dirty paths.

## STOP-condition check

| Condition | Triggered |
|---|---|
| HEAD ≠ origin/main | NO |
| A1 runtime dead | NO |
| DB unavailable | NO |
| Telemetry regression | NO |

Baseline clean.
