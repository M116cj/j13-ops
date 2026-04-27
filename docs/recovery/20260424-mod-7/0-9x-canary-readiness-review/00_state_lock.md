# 00 — State Lock (Phase 0)

**Order:** TEAM ORDER 0-9X-CANARY-READINESS-REVIEW
**Captured:** 2026-04-27T17:25:27Z (Alaya UTC)

## Carry-forward state vs prior order

| Field | Prior order asserted | Verified now | Status |
|---|---|---|---|
| HEAD | `ca91249753a19af22bc064a8f781e7704cf84a3b` | `ca91249753a19af22bc064a8f781e7704cf84a3b` | ✅ |
| origin/main | `ca912497` | `ca912497` | ✅ in sync |
| Branch (capture) | main | main | ✅ |
| HEAD signature | RSA `B5690EEEBB952194` | same key | ✅ |
| 0-9X-POST-RESTART verdict | `COMPLETE_POST_RESTART_TELEMETRY_VERIFIED` | unchanged | ✅ |
| A1 telemetry CI | 0 | 0 (last 100 batches) | ✅ |
| A1 telemetry UNKNOWN_REJECT | 0 | 0 (last 100 batches) | ✅ |
| Conservation | 96/96 residual=0 | 100/100 residual=0 | ✅ |
| Mac / Alaya sync | SYNCED | SYNCED | ✅ |
| Forbidden ops carry-over | 0 | 0 | ✅ |

## git status

```
 M calcifer/maintenance.log
 M calcifer/maintenance_last.json
 M calcifer/report_state.json
 M zangetsu/logs/engine.jsonl.1
```

Same 4 runtime artifacts as Phase 0 of the prior order; **no source code changes.**

## Runtime processes

| Service | PID | Started (UTC) | Uptime at capture | CPU | RSS |
|---|---|---|---|---|---|
| arena_pipeline w0 | 884780 | 17:02:16 | 23m 11s | 100% | 2.07 GB |
| arena_pipeline w1 | 884803 | 17:02:16 | 23m 10s | 100% | 2.07 GB |
| arena_pipeline w2 | 884895 | 17:02:16 | 23m 10s | 100% | 2.06 GB |
| arena_pipeline w3 | 884919 | 17:02:17 | 23m 10s | 100% | 2.04 GB |
| arena23_orchestrator | 885011 | 17:02 | ~23m | 1.4% | 1.65 GB |
| arena45_orchestrator | 885036 | 17:02 | ~23m | 1.4% | 1.26 GB |
| calcifer/supervisor.py | 885335 | 17:02 | ~23m | 0.0% | tiny |
| calcifer-miniapp | 1023 | 04:01 | ~13h | 0.1% | 55 MB |

§17.6 stale-check (carry-forward): all 4 A1 workers post-date `arena_pipeline.py` mtime by 84 min → **FRESH**.

## Lockfiles (`/tmp/zangetsu/`)

8 expected lockfiles all present, mtimes 17:02 (worker boot) plus arena13_feedback.lock at 17:25.

## Watchdog log

Latest entry batch `2026-04-27T17:25:01`: all workers `action=skipped reason=lockfile_present_main_loop_owns` — correct deferral.

## DB sanity

| Field | Value |
|---|---|
| now() | 2026-04-27 17:25:27.302569+00 |
| current_database() | zangetsu |
| current_user | zangetsu |

| Table | Rows |
|---|---|
| `champion_pipeline` (legacy view alias) | 89 |
| `champion_legacy_archive` | 1564 |
| `champion_pipeline_fresh` | 89 |
| `champion_pipeline_staging` | 184 |
| `champion_pipeline_rejected` | 0 |
| `engine_telemetry` | **0 rows ever** ⚠️ |

`zangetsu_status` outcome metric:

```
deployable_count        = 0
deployable_historical   = 0
deployable_fresh        = 0
deployable_live_proven  = 0
active_count            = 0
candidate_count         = 0
champions_last_1h       = 0
last_live_at_age_h      = NULL  (never had a live champion)
ts                      = 2026-04-27 17:25:27.407251+00
```

## Telemetry sanity (last 100 arena_batch_metrics)

Window: `2026-04-27T17:19:57Z → 2026-04-27T17:25:51Z` (~6 min).

| Field | Value |
|---|---|
| parsed events | 100 |
| residual distribution | `{0: 100}` (perfect conservation) |
| COUNTER_INCONSISTENCY total | 0 |
| UNKNOWN_REJECT total | 0 |
| reject distribution | `{COST_NEGATIVE: 961, SIGNAL_TOO_SPARSE: 33, LOW_BACKTEST_SCORE: 6}` |
| pass_rate | 0/1000 = 0.0% |
| generation_profile mix | `gp_541a313e770c4424`: 52, `gp_26f478846fd0f729`: 48 |

Fix verified: A1 telemetry remains clean (CI=0, UNKNOWN_REJECT=0) and conservation holds — but **0% pass rate** is the upstream signal flagged in Phase 1.

## STOP-condition check

| Condition | Triggered |
|---|---|
| repo dirty with unexplained source changes | NO |
| HEAD ≠ origin/main | NO |
| A1 runtime dead | NO |
| DB unavailable | NO |
| v0.7.1 objects missing | NO (8/8 present) |
| A1 telemetry regression | NO (last 100 still clean) |

**No STOP triggered. Proceed to Phase 1.**
