# 00 — State Lock (Subprogram A)

**Master order:** MASTER ORDER 0-9Y-ZANGETSU-SYSTEM-COMPLETION-AND-RUNTIME-ENABLEMENT-v2
**Subprogram:** A — State Lock and Carry-Forward Audit
**Captured:** 2026-04-27T18:21:05Z

## Repository

| Field | Value |
|---|---|
| HEAD | `294bf4efe97578a968da359ceae65b86f7f42fe3` |
| origin/main | `294bf4ef` (in sync) |
| Branch (capture) | main |
| HEAD signature | RSA `B5690EEEBB952194` |
| Last commit | `docs(zangetsu): diagnose deployable flow blockage (#53)` |

## Working tree

```
 M calcifer/maintenance.log
 M calcifer/maintenance_last.json
 M calcifer/report_state.json
 M zangetsu/logs/engine.jsonl.1
```

Same four runtime / log artifacts (not source). Pre-existing dirty paths.

## Runtime processes

| Service | PID | Started (UTC) | Uptime | CPU | RSS |
|---|---|---|---|---|---|
| arena_pipeline w0 | 884780 | 17:02:16 | ~79m | 100% | 2.45 GB |
| arena_pipeline w1 | 884803 | 17:02:16 | ~79m | 100% | 2.38 GB |
| arena_pipeline w2 | 884895 | 17:02:16 | ~79m | 100% | 2.37 GB |
| arena_pipeline w3 | 884919 | 17:02:17 | ~79m | 100% | 2.24 GB |
| arena23_orchestrator | 885011 | 17:02 | ~79m | 0.4% | 1.65 GB |
| arena45_orchestrator | 885036 | 17:02 | ~79m | 0.4% | 1.27 GB |
| calcifer/supervisor.py | 885335 | 17:02 | ~79m | 0.0% | tiny |

§17.6 stale-check: workers booted 17:02:16Z, source mtime 15:38:10Z → FRESH 4/4 (carry-forward).

## Watchdog

`/tmp/zangetsu_watchdog.log` last batch 18:20:01: `action=skipped reason=lockfile_present_main_loop_owns` for all workers — correct deferral. "all 8 services healthy" continues.

## DB

| Field | Value |
|---|---|
| now() | 2026-04-27 18:21:05.952333+00 |
| current_database() | zangetsu |
| current_user | zangetsu |

| Table | Rows |
|---|---|
| `champion_pipeline` | 89 |
| `champion_pipeline_fresh` | 89 |
| `champion_pipeline_staging` | 184 |
| `champion_pipeline_rejected` | 0 |
| `champion_legacy_archive` | 1564 |
| `engine_telemetry` | **0 rows** ⚠️ |

`zangetsu_status`: deployable_count = 0; last_live_at_age_h = NULL; all other counters 0.

v0.7.1 DB objects: 8/8 present (verified prior order; no schema migration since).

## Telemetry sanity (last 100 `arena_batch_metrics`)

Window: `2026-04-27T18:15:07Z → 2026-04-27T18:21:03Z` (~6 min).

| Field | Value |
|---|---|
| parsed events | 100 |
| residuals | `{0: 100}` |
| COUNTER_INCONSISTENCY | 0 |
| UNKNOWN_REJECT | 0 |
| reject distribution | `{COST_NEGATIVE: 986, SIGNAL_TOO_SPARSE: 12, LOW_BACKTEST_SCORE: 2}` |
| pass_rate | 0/1000 = 0.0% |

Telemetry remains clean (PR #50 + PR #49 fixes verified live across 4 prior orders).

## Phase 0 classification

| Field | Status |
|---|---|
| HEAD == origin/main | ✅ `294bf4ef` |
| Repo source clean | ✅ (only runtime artifacts dirty) |
| Runtime status | ✅ 4× A1 + A23 + A45 + Calcifer alive |
| Lockfile status | ✅ 8/8 present |
| DB v0.7.1 status | ✅ 8/8 objects |
| A1 telemetry sanity | ✅ CI=0 / UNKNOWN_REJECT=0 / residual={0} |

No STOP triggered. Baseline is clean for 0-9Y program kickoff.
