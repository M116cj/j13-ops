# 07 — Runtime Health Check

## 1. Live Process Snapshot

| Service | PID | Wall time at observation | CPU | State |
| --- | --- | --- | --- | --- |
| `arena23_orchestrator` | 207186 | ~ 5 min | 7% (polling-driven idle) | ALIVE |
| `arena45_orchestrator` | 207195 | ~ 5 min | 7% (polling-driven idle) | ALIVE |
| `arena_pipeline_w0..w3` | (cycling per cron `*/5`) | typically ~30 s per cycle | 99% during run | CYCLING |
| `cp-api`, `dashboard-api`, `console-api` | 2537810 / 3871446 / 3871449 | days | low | ALIVE (UNTOUCHED) |

→ A23 and A45 daemons are now stable; their idle CPU pattern matches the documented polling-driven design.

## 2. `engine.jsonl` Progress

| Field | Value |
| --- | --- |
| Path | `zangetsu/logs/engine.jsonl` |
| Last write at observation | `2026-04-26T09:57:17Z` |
| Status | actively advancing during A1 cron cycles |

→ Engine loop healthy. The cycle pattern is: every 5 min cron triggers watchdog → spawns A1 workers → workers run for ~30 s writing to engine.jsonl → exit cleanly → watchdog respawns next cycle.

## 3. KeyError Recurrence Search

```
$ grep "KeyError: 'ZV5_DB_PASSWORD'" /tmp/zangetsu_a23.log /tmp/zangetsu_a45.log /tmp/zangetsu_a1_w*.log | awk '$0 ~ /^[^:]+:[0-9]+/'
(no matches in any worker log since 09:52 trigger)
```

| Log | Last `KeyError` line | Since 0-9V-A23-A45-LAUNCHER trigger? |
| --- | --- | --- |
| `/tmp/zangetsu_a23.log` | 2026-04-23T00:40:01Z (stale; pre-PR-#31) | NO |
| `/tmp/zangetsu_a45.log` | 2026-04-23T00:40:02Z (stale; pre-PR-#31) | NO |
| `/tmp/zangetsu_a1_w0..w3.log` | none recent | NO |

→ Zero `KeyError: ZV5_DB_PASSWORD` recurrence in any service that this order targets.

## 4. Side Observation — `arena13_feedback.py` (out of scope)

```
$ grep "KeyError" /tmp/zangetsu_a13fb.log | tail -3
... still printing KeyError: 'ZV5_DB_PASSWORD' ...
```

Diagnostic only: the cron line `*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1` runs the feedback script **directly**, bypassing `watchdog.sh` and therefore **not loading** `~/.env.global`. This is a **pre-existing** condition (the cron line predates the watchdog preamble) and is **not in this order's scope**, which is "A23/A45 launcher restoration".

→ Documented for a separate follow-up order (e.g. **0-9V-FEEDBACK-LOOP-ENV-CONFIG**, parallel to PR #31's pattern but applied to the bare-cron arena13 line).

## 5. A23 / A45 Initial Activity (proves not crashing on startup)

```
A23:
  09:53:00 INFO Loaded 1000SHIBUSDT: train=140000 + holdout=60000 bars
  09:53:00 INFO Loaded GALAUSDT: train=140000 + holdout=60000 bars
  09:53:01 INFO Wavelet denoising active for BTCUSDT/train
  09:53:01 INFO Data cache: 14 symbols loaded
  09:53:01 INFO Service loop started
A45:
  09:53:00 INFO Data loaded: 14 symbols (holdout split)
  09:53:00 INFO Arena 4+5 Orchestrator running (v9: shared_utils dedup + ATR/TP fixes)
  09:53:00 INFO Daily reset complete: kept=0 retired=0 across 0 regimes
```

→ Both orchestrators successfully:
- imported `zangetsu.config.settings` (no KeyError)
- connected to the database (otherwise `Loaded <symbol>: train=...` would not print)
- entered their respective service loops

## 6. Health Classification

Per order §13:

> "PASS: A23/A45 alive or cleanly waiting for input, no crash."

→ **PASS.** A23 and A45 are alive and waiting for upstream A1 candidates.

## 7. Phase H Verdict

→ **PASS.** No `BLOCKED_RUNTIME_ERROR`.
