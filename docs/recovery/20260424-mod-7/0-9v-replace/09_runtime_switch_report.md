# 09 — Runtime Switch Report

## 1. Switch performed

**NO** — gate failed at G1 + G2. Per order §13.4 / §12:

> "If launcher is unknown: Status = BLOCKED_RUNTIME_LAUNCHER_UNKNOWN. Do not switch runtime."
> "If any critical gate fails: Status = BLOCKED_REPLACEMENT_GATE. Do not switch runtime process."

Both gate failures and the launcher-unknown soft-failure (arena pipeline
launched via cron + watchdog rather than a single named systemd unit)
combine into one outcome: **NO RUNTIME SWITCH.**

## 2. Runtime manager

| Service | Manager | Status |
| --- | --- | --- |
| `console-api.service` | systemd | running (HTTP API; stays up through replacement) |
| `cp-api.service` | systemd | running (Control Plane API; stays up) |
| `dashboard-api.service` | systemd | running (HTTP API; stays up) |
| `arena_pipeline` (A1) | cron `*/5 * * * * watchdog.sh` | **STOPPED** since 2026-04-23 (engine.jsonl last write) |
| `arena13_feedback.py` | cron `*/5 * * * * services/arena13_feedback.py` | runs every 5 min |
| `arena23_orchestrator` (A2/A3) | unknown | **STOPPED** (no process visible) |
| `arena45_orchestrator` (A4/A5) | unknown | **STOPPED** (no process visible) |

The arena pipeline as a whole is **idle** — `watchdog.sh` checks every 5
min but apparently isn't relaunching the pipeline (or pipeline exits
cleanly after each round). This is consistent with the "Stopped"
message in the last engine.jsonl line.

## 3. Old PID

| Process | PID | Notes |
| --- | --- | --- |
| Arena pipeline | (none — stopped) | Last seen Apr 23 |
| arena23_orchestrator | (none) | |
| arena45_orchestrator | (none) | |
| cp-api | 2537810 | Apr 24, NOT touched |
| dashboard-api | 3871446 | Apr 23, NOT touched |
| console-api | 3871449 | Apr 23, NOT touched |

## 4. New PID

(none — no switch)

## 5. Working directory

`/home/j13/j13-ops` (unchanged).

## 6. Logs writing status

| Field | Value |
| --- | --- |
| `engine.jsonl` last write | 2026-04-23T00:35:54Z (arena pipeline stopped) |
| `dashboard.log` last write | 2026-04-11 |
| HTTP API services | `console-api`, `cp-api`, `dashboard-api` actively writing systemd journal |

No logs were touched by this PR.

## 7. Telemetry writing status

| File | Status |
| --- | --- |
| `arena_batch_metrics.jsonl` | NOT WRITING (file doesn't exist; pipeline stopped + emitter not deployed) |
| `sparse_candidate_dry_run_plans.jsonl` | NOT WRITING (consumer not deployed) |
| `engine.jsonl` | NOT WRITING (pipeline stopped Apr 23) |

No telemetry was touched by this PR.

## 8. Errors

None observed during inventory / safety / telemetry / gate phases. SSH
access OK, repo path OK, `git fetch` OK. The "errors" reported are the
absence of expected files (because the new code isn't on Alaya yet),
not actual failures.

## 9. Rollback readiness

| Field | Value |
| --- | --- |
| Old SHA captured | `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52` |
| Old branch captured | `phase-7/p7-pr4b-a2-a3-arena-batch-metrics` |
| Dirty diff captured | YES (diff stat documented; full diff available via `git diff` until cleanup) |
| Untracked files captured | YES (3 files documented) |
| Rollback commands documented | YES (see `rollback_commands.sh` in this directory) |
| Rollback feasible after eventual switch | YES |

## 10. Conclusion

```
Switch performed: NO
Runtime manager: cron + (unknown — likely watchdog.sh) + systemd (HTTP APIs only, untouched)
Old PID: arena pipeline = STOPPED; HTTP APIs = preserved
New PID: (none)
Logs writing: HTTP APIs continue writing systemd journal; engine.jsonl idle since Apr 23
Telemetry writing: none (pipeline idle + emitters not deployed)
Errors: none (only documented missing files)
Rollback ready: YES
```

**Phase I outcome: SKIPPED per gate fail.**
