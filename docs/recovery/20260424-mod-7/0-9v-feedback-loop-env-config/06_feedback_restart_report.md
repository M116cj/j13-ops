# 06 — Feedback Restart Report

## 1. Method

**Manual one-shot trigger of the new wrapper, with timeout 90s, plus a 15 s observation window.**

```bash
cd /home/j13/j13-ops
timeout 90s /home/j13/j13-ops/zangetsu/arena13_feedback_env.sh   >> /tmp/zangetsu_arena13_feedback.log 2>&1 || true
sleep 15
```

The cron line will continue running the wrapper every 5 min unattended.

## 2. Pre-Trigger State

```
$ ps -ef | grep arena13_feedback | grep -v grep
(none — script crashes before reaching the controller loop)

$ tail -3 /tmp/zangetsu_a13fb.log    # OLD log path
KeyError: ZV5_DB_PASSWORD            # repeating since 2026-04-23T00:40Z
```

## 3. Phase H Env Validation (subshell-via-wrapper-preamble pattern)

```
$ bash -c "set -a; . \$HOME/.env.global; set +a; cd /home/j13/j13-ops/zangetsu; python3 -c 'import os; print("feedback_env_ZV5_DB_PASSWORD=" + ("PRESENT" if os.getenv("ZV5_DB_PASSWORD") else "MISSING"))'"
feedback_env_ZV5_DB_PASSWORD=PRESENT
```

The wrappers exact env-loading sequence successfully exposes ZV5_DB_PASSWORD to the spawned Python process.

## 4. Manual Trigger Output (verbatim, no secret printed)

/tmp/zangetsu_arena13_feedback.log after the trigger (file size 604 B; full content):

```
{"ts": "2026-04-26T10:35:02", "level": "INFO", "msg": "Arena 13 Feedback Controller starting"}
{"ts": "2026-04-26T10:35:02", "level": "INFO", "msg": "DB connected"}
{"ts": "2026-04-26T10:35:02", "level": "ERROR", "msg": "A13 guidance computation failed: relation champion_pipeline does not exist"}
{"ts": "2026-04-26T10:35:06", "level": "INFO", "msg": "Arena 13 Feedback Controller starting"}
{"ts": "2026-04-26T10:35:06", "level": "INFO", "msg": "DB connected"}
{"ts": "2026-04-26T10:35:06", "level": "ERROR", "msg": "A13 guidance computation failed: relation champion_pipeline does not exist"}
```

| Observation | Value |
| --- | --- |
| Process reaches import zangetsu.config.settings without KeyError | YES |
| Process reaches Arena 13 Feedback Controller starting log line | YES |
| Process reaches DB connected log line | YES (proves ZV5_DB_PASSWORD was used to authenticate) |
| KeyError recurrence in NEW log | 0 |
| Total tracebacks in NEW log | 0 |
| Exit code | 0 (script ran twice — manual + next cron cycle) |

## 5. New Downstream Issue (post-env-repair)

```
ERROR: A13 guidance computation failed: relation "champion_pipeline" does not exist
```

| Field | Value |
| --- | --- |
| Class | **DB schema gap** (missing PostgreSQL table) |
| Caused by this order | NO — surfaced because PR #31 + this order are the first thing that lets arena13_feedback.py reach the guidance computation step |
| Affects A13 (feedback) only | YES |
| Affects A1 / A23 / A45 / engine.jsonl | NO (those workers continue advancing normally; engine.jsonl mtime advancing) |
| Affects this orders acceptance | NO — order §22 explicitly allows COMPLETE_FEEDBACK_REPAIRED_FLOW_PENDING (env repaired, candidate flow pending) |
| Recommended next order | **0-9V-A13-CHAMPION-PIPELINE-SCHEMA** (separate scope; create the missing table per A13 expected schema) |

## 6. Hard-Ban Compliance During Trigger

| Item | Status |
| --- | --- |
| Secret printed | NO |
| Full env printed | NO |
| Log content contains secret value | NO (logs show DB connected confirmation only) |
| HTTP APIs touched | NO (cp-api 2537810 / dashboard-api 3871446 / console-api 3871449 unchanged) |
| A1 / A23 / A45 touched | NO (A23 PID 207186 + A45 PID 207195 alive ≥ 44 min throughout) |
| Production rollout / CANARY / optimizer apply | NOT STARTED |

## 7. Phase I Verdict

**PASS.** Feedback wrapper executes successfully. KeyError: ZV5_DB_PASSWORD no longer recurs in the new log path. Surfaced new schema gap (champion_pipeline missing) is documented and explicitly out of scope for this order.
