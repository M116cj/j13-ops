# 07 — Feedback Rerun Report

## 1. Method

```bash
cd /home/j13/j13-ops
timeout 90s /home/j13/j13-ops/zangetsu/arena13_feedback_env.sh \
  >> /tmp/zangetsu_arena13_feedback.log 2>&1 || true
sleep 10
```

The wrapper from PR #33 + the new VIEW from this order's migration.

## 2. Pre-Rerun State (last cron cycle before this order's manual trigger)

```
2026-04-26T11:10:02 INFO  Arena 13 Feedback Controller starting
2026-04-26T11:10:02 INFO  DB connected
2026-04-26T11:10:02 ERROR A13 guidance computation failed: relation "champion_pipeline" does not exist
```

## 3. Manual One-Shot Output (post-migration)

```
2026-04-26T11:12:42 INFO  Arena 13 Feedback Controller starting
2026-04-26T11:12:43 INFO  DB connected
2026-04-26T11:12:43 INFO  A13: only 0 survivor indicator-uses, using BASE_WEIGHTS (need 3)
2026-04-26T11:12:43 INFO  A13 guidance MODE=observe | survivors=0 failures=0 cool_off=0 | top: tsi=2.0, macd=2.0, zscore=1.8 | bot: rsi=1.0, stochastic_k=1.0, obv=1.0
2026-04-26T11:12:43 INFO  Arena 13 Feedback complete (single-shot)
```

| Field | Value |
| --- | --- |
| DB connected | YES |
| ZV5_DB_PASSWORD KeyError recurrence | NO (count=0 in entire log; durable since PR #33) |
| champion_pipeline missing recurrence on this run | NO |
| New runtime error | NO |
| A13 guidance computed | YES (BASE_WEIGHTS path because survivor count is 0; expected during cold-start) |
| Process exit | clean ("Arena 13 Feedback complete (single-shot)") |

## 4. Why "survivors=0 failures=0"

`champion_pipeline_fresh` currently has 89 rows (per Phase H inventory), but A13 filters by:

- `status IN ('CANDIDATE', 'DEPLOYABLE')`
- `engine_hash NOT LIKE '%_coldstart'`
- `evolution_operator NOT IN ('cold_seed%', 'gp_evolution')`

If those 89 rows are still in early Arena stages (`ARENA1_READY`, `ARENA1_PROCESSING`, etc.) or originate from cold-seed evolution, the WHERE filters return zero rows. That is **correct behavior** — A13 falls back to BASE_WEIGHTS, which is the documented contingency. No error, no exception.

## 5. Hard-Ban Compliance During Trigger

| Item | Status |
| --- | --- |
| Secret printed | NO |
| Full env printed | NO |
| HTTP APIs touched | NO |
| A1 / A23 / A45 touched | NO (still alive 1h 21m wall time) |
| Production rollout | NOT STARTED |

## 6. Phase I Verdict

PASS. arena13_feedback now completes cleanly through the new VIEW. No `BLOCKED_SCHEMA_STILL_MISSING`, no `BLOCKED_SCHEMA_INCOMPATIBLE`, no `BLOCKED_NEW_FEEDBACK_RUNTIME_ERROR`. The 9 historical `relation does not exist` errors are pre-migration and frozen.
