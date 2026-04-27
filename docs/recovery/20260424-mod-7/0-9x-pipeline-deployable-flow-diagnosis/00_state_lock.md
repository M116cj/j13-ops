# 00 — State Lock (Phase 0)

**Order:** TEAM ORDER 0-9X-PIPELINE-DEPLOYABLE-FLOW-DIAGNOSIS
**Captured:** 2026-04-27T17:57:59Z (Alaya UTC)

## Carry-forward state vs prior order

| Field | Prior (CANARY readiness) | Verified now | Status |
|---|---|---|---|
| HEAD | `0a34a14a65f913610e93cbd779a310ea5a2b8277` | same | ✅ |
| origin/main | `0a34a14a` | same | ✅ |
| Branch | main | main | ✅ |
| Workers | 4× A1 + A23 + A45 + Calcifer alive | same, ~56 min uptime | ✅ |
| §17.6 stale-check | FRESH 4/4 | FRESH 4/4 (worker boot 17:02:16Z, src mtime 15:38:10Z, +84min) | ✅ |
| A1 telemetry — last 100 batches | CI=0 / UNKNOWN_REJECT=0 / residual=0 | CI=0 / UNKNOWN_REJECT=0 / residual={0} | ✅ |
| DB v0.7.1 objects | 8/8 present | 8/8 present | ✅ |

## git status (working tree)

```
 M calcifer/maintenance.log
 M calcifer/maintenance_last.json
 M calcifer/report_state.json
 M zangetsu/logs/engine.jsonl.1
```

Same 4 runtime/log artifacts. **No source code changes.**

## Runtime processes

| Service | PID | Started (UTC) | Uptime | CPU | RSS |
|---|---|---|---|---|---|
| arena_pipeline w0 | 884780 | 17:02:16 | ~56m | 100% | 2.33 GB |
| arena_pipeline w1 | 884803 | 17:02:16 | ~56m | 100% | 2.27 GB |
| arena_pipeline w2 | 884895 | 17:02:16 | ~56m | 100% | 2.33 GB |
| arena_pipeline w3 | 884919 | 17:02:17 | ~56m | 100% | 2.20 GB |
| arena23_orchestrator | 885011 | 17:02 | ~56m | 0.6% | 1.65 GB |
| arena45_orchestrator | 885036 | 17:02 | ~56m | 0.6% | 1.27 GB |
| calcifer/supervisor.py | 885335 | 17:02 | ~56m | 0.0% | tiny |

## Watchdog

`/tmp/zangetsu_watchdog.log` last entries 17:55:01 `action=skipped reason=lockfile_present_main_loop_owns` for all workers — correct deferral. "all 8 services healthy" continues every 30 min.

## DB sanity

| Field | Value |
|---|---|
| `now()` | 2026-04-27 17:57:59.454922+00 |
| `current_database()` | zangetsu |
| `current_user` | zangetsu |

Row counts:

| Table | Rows |
|---|---|
| `champion_pipeline` (legacy view alias) | 89 |
| `champion_pipeline_fresh` | 89 |
| `champion_pipeline_staging` | 184 |
| `champion_pipeline_rejected` | 0 |
| `champion_legacy_archive` | 1564 |
| `engine_telemetry` | **0 rows ever** ⚠️ |

`zangetsu_status`:

```
deployable_count = 0  deployable_historical = 0  deployable_fresh = 0
deployable_live_proven = 0  active_count = 0  candidate_count = 0
champions_last_1h = 0  last_live_at_age_h = NULL
```

## A1 telemetry sanity (last 100 `arena_batch_metrics`)

Window: `2026-04-27T17:52:13Z → 2026-04-27T17:58:07Z` (~6 min)

| Field | Value |
|---|---|
| parsed events | 100 |
| residuals | `{0: 100}` (perfect conservation) |
| COUNTER_INCONSISTENCY | 0 |
| UNKNOWN_REJECT | 0 |
| reject distribution | `{COST_NEGATIVE: 971, SIGNAL_TOO_SPARSE: 21, LOW_BACKTEST_SCORE: 8}` |
| pass_rate | 0/1000 = 0.0% |

Telemetry continues to be clean post the previous two orders' fixes.

## Required Phase 0 classification

| Field | Status |
|---|---|
| HEAD status | `0a34a14a` matches `origin/main` ✅ |
| repo clean/dirty | dirty on **runtime artifacts only** (calcifer state + engine.jsonl.1 rotation); **source = clean** ✅ |
| runtime status | 4× A1 + A23 + A45 + Calcifer supervisor alive ✅ |
| lockfile status | 8 expected lockfiles present, no orphans ✅ |
| DB v0.7.1 status | 8/8 objects present, queryable ✅ |
| A1 telemetry sanity | CI=0 / UNKNOWN_REJECT=0 / residual=0 ✅ |
| known pipeline blocker | `deployable_count = 0` ever; A1 producing 0 admissions for 6.5 days; original 89 fresh all `ARENA2_REJECTED` (carry-forward) |

## STOP-condition check

| Condition | Triggered |
|---|---|
| repo dirty with **unexplained source changes** | NO |
| HEAD ≠ origin/main | NO |
| A1 runtime dead | NO |
| DB unavailable | NO |
| v0.7.1 objects missing | NO |
| A1 telemetry regression | NO |

**No STOP triggered.** Proceed to Phase 1.
