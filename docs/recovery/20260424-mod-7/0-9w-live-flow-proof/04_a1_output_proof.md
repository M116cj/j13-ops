# 04 — A1 Output Proof

## 1. Question

Distinguish between "A1 is cycling" and "A1 is generating usable candidates".

## 2. A1 Cycling Evidence

A1 workers (`arena_pipeline.py` × 4) are spawned every 5 min by `watchdog.sh` cron. Current cycle PIDs at observation: 482426 / 482435 / 482447 / 482461 (started 12:05).

| Worker log | mtime | Latest activity |
| --- | --- | --- |
| /tmp/zangetsu_a1_w0.log | 12:06:26Z | "Indicator cache built for XRPUSDT: 110 arrays (holdout)" |
| /tmp/zangetsu_a1_w1.log | 12:06:25Z | "Indicator cache built for DOGEUSDT: 110 arrays (holdout)" |
| /tmp/zangetsu_a1_w2.log | 12:06:28Z | numpy RuntimeWarning: overflow (non-fatal) |
| /tmp/zangetsu_a1_w3.log | 12:06:28Z | numpy RuntimeWarning: overflow (non-fatal) |

| engine.jsonl | last write | size |
| --- | --- | --- |
| zangetsu/logs/engine.jsonl | 12:05:06Z | 40 130 600 B |

→ A1 logs and engine.jsonl confirm **A1 is cycling**.

## 3. A1 → DB Output Evidence (the critical question)

| DB metric | Value |
| --- | --- |
| max(created_at) on champion_pipeline_fresh | **2026-04-21T04:34:21Z** |
| max(updated_at) on champion_pipeline_fresh | **2026-04-22T17:57:10Z** |
| max(created_at) on champion_pipeline_staging | **2026-04-21T04:34:21Z** |
| count(rows) created after PR #31 (env repair, 09:42Z) | **0** |
| count(rows) created after PR #32 (A23/A45 launcher, 10:22Z) | **0** |
| count(rows) created after PR #33 (feedback env, 10:49Z) | **0** |
| count(rows) created after PR #34 (champion_pipeline VIEW, 11:36Z) | **0** |
| count(staging rows) created since A1 came alive (09:52Z) | **0** |

→ Despite A1 actively cycling for **2h 12m+** today, **zero new rows** have appeared in either staging or fresh.

## 4. engine_telemetry (would-be A1 health metrics)

| Metric | Value |
| --- | --- |
| max(ts) | NULL — **table is empty** |
| count of rows since A1 alive | 0 |

→ A1 is also not writing any `engine_telemetry` row, even though that table is the documented sink for round_duration_ms / population_size / compile_success_count etc.

## 5. Visible Symptoms in A1 Logs

- A1 builds indicator caches successfully ("110 arrays, 25.2 MB" per symbol).
- A1 processes regime classifications ("Regime XRPUSDT: BULL_TREND" earlier in log history).
- 2 of 4 workers (w2, w3) emit numpy RuntimeWarning(overflow) — non-fatal but suggests sample data may be running into edge cases.
- No INSERT-related log lines appear.
- No exception that would explicitly halt the engine loop.

## 6. Possible Reasons A1 Doesn't Reach DB Insert

This order does **not** patch — only documents likely targets for a follow-up diagnosis order.

| Hypothesis | Evidence |
| --- | --- |
| A1 main loop never reaches the DB-insert phase (early exit / blocking await) | engine.jsonl advances but no INSERT log lines anywhere |
| admission_validator() always rejects new rows | admission_validator code requires `current_setting('zangetsu.admission_active', true)` to be 'true' at INSERT time (per v0.7.1 fresh_insert_guard); if A1 isn't setting that session variable, every INSERT into fresh would raise |
| A1 might be in a read-only / observation-only mode (env / config flag) | A1 process inherits cron env which only has ZV5_DB_PASSWORD; other behavioral env vars may control mode |
| Engine queue buffer not flushed | possible — would explain engine.jsonl writing but staging not |
| Numpy overflow in workers w2/w3 may abort their generation rounds before INSERT | non-fatal but may abort that worker's cycle |

→ Out of scope for this order — recommend follow-up diagnosis order (`0-9W-A1-OUTPUT-MATERIALIZATION-DIAGNOSIS`).

## 7. Phase 4 Classification

Per order §17:

| Verdict | Match? |
| --- | --- |
| A1_OUTPUT_CONFIRMED (A1 producing fresh candidate/lifecycle rows) | NO |
| A1_CYCLING_NO_OUTPUT (A1 logs advance but no fresh DB lifecycle movement) | **YES** ← exact match |
| A1_OUTPUT_REJECTED_EARLY (A1 produces but rows reject before candidate state) | NO (no INSERTs at all to reject) |
| A1_OUTPUT_UNKNOWN | NO |
| A1_OUTPUT_ERROR | NO (no fatal exceptions) |

→ **Phase 4 verdict: A1_CYCLING_NO_OUTPUT.**
