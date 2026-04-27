# 00 — State Lock (Phase 0)

**Order:** TEAM ORDER 0-9X-POST-RESTART-A1-TELEMETRY-VERIFICATION
**Phase:** 0 — State Lock
**Captured:** 2026-04-27T17:08:39Z (Alaya UTC)

## Repository state

| Field | Value |
|---|---|
| HEAD | `29c757e38112f915d4c026fa7e70479e4f2e37e4` |
| Branch | `main` |
| origin/main | `29c757e38112f915d4c026fa7e70479e4f2e37e4` (in sync) |
| HEAD signature | gpg RSA key `B5690EEEBB952194` (signed; pubkey not on Alaya, expected) |
| Last commit | `fix(zangetsu/a1): per-round delta accounting for arena_batch_metrics (#50)` |

## Repo working tree (`git status --short`)

```
 M calcifer/maintenance.log
 M calcifer/maintenance_last.json
 M calcifer/report_state.json
 M zangetsu/logs/engine.jsonl.1
```

**Classification:** runtime / state artifacts only — **NO source code changes.**

| File | Nature |
|---|---|
| `calcifer/maintenance.log` | Calcifer runtime maintenance log (continuously written by Calcifer supervisor) |
| `calcifer/maintenance_last.json` | Calcifer last-run state snapshot |
| `calcifer/report_state.json` | Calcifer reporting cursor |
| `zangetsu/logs/engine.jsonl.1` | Rotated engine log (replaced at workers' 17:02 restart) |

These are not `*.py` / `*.sql` / `*.toml` / `*.yaml` source. They reflect runtime activity of the calcifer supervisor and the engine logger between commits and the moment of capture. They predate this order and are out-of-scope.

## Runtime processes (`ps aux | grep -E arena_pipeline|arena23|arena45|watchdog`)

| Service | PID | Started (UTC) | CPU | RSS |
|---|---|---|---|---|
| arena_pipeline w0 | 884780 | 2026-04-27 17:02:16 | 103% | 2.07 GB |
| arena_pipeline w1 | 884803 | 2026-04-27 17:02:16 | 103% | 2.08 GB |
| arena_pipeline w2 | 884895 | 2026-04-27 17:02:16 | 103% | 2.06 GB |
| arena_pipeline w3 | 884919 | 2026-04-27 17:02:17 | 103% | 2.02 GB |
| arena23_orchestrator | 885011 | 2026-04-27 17:02 | 6% | 1.65 GB |
| arena45_orchestrator | 885036 | 2026-04-27 17:02 | 6% | 1.26 GB |
| watchdogd (kernel) | 162 | 2026-04-27 04:01 | — | — |
| /usr/sbin/watchdog | 3809 | 2026-04-27 04:01 | — | — |

## Lockfile state (`/tmp/zangetsu/`)

All 8 expected lockfiles present, mtimes 17:02 (worker boot) — correct for active service ownership:
- arena_pipeline_w{0,1,2,3}.lock
- arena23_orchestrator.lock, arena45_orchestrator.lock
- arena13_feedback.lock (17:05 — separate process)
- calcifer_supervisor.lock

## Watchdog log (`/tmp/zangetsu_watchdog.log`)

`2026-04-27T17:00:01 WATCHDOG: all 8 services healthy`

Cold-boot lines after 17:02 record `action=skipped reason=lockfile_present_main_loop_owns` for all workers — correct: watchdog defers when main loop owns lockfiles.

## Source sanity

### Taxonomy import (`zangetsu.services.arena_rejection_taxonomy.classify`)

```
reject_train_neg_pnl       -> (COST_NEGATIVE,        COST,           A2)
reject_combined_sharpe_low -> (LOW_BACKTEST_SCORE,  BACKTEST_SCORE, A1)
unknown_future_reason      -> (UNKNOWN_REJECT,      UNKNOWN,        UNKNOWN)
```

All three resolve correctly; UNKNOWN fallback maps to canonical `UNKNOWN_REJECT`.

### Delta-helper tokens in `zangetsu/services/arena_pipeline.py`

| Token | Present |
|---|---|
| `_compute_a1_reject_deltas` | True |
| `_A1_REJECT_STATS_KEYS` | True |
| `_A1_PREV_REJECT_STATS_SNAPSHOT` | True |

PR #50 helper + key-set + snapshot dict all in source.

### File mtime vs HEAD commit ts

| File | mtime (UTC) |
|---|---|
| `zangetsu/services/arena_pipeline.py` | 2026-04-27 15:38:10 |
| `zangetsu/services/arena_rejection_taxonomy.py` | 2026-04-27 15:07:38 |
| HEAD commit time | 2026-04-27T15:38:05+00:00 (commit ts `%cI`) |

## DB sanity (`docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu`)

| Field | Value |
|---|---|
| now() | 2026-04-27 17:08:39.731133+00 |
| current_database() | zangetsu |
| current_user | zangetsu |

```
 fresh | staging | legacy_archive | rejected
-------+---------+----------------+----------
    89 |     184 |           1564 |        0
```

### v0.7.1 DB objects (8 expected, 8 present)

`champion_legacy_archive`, `champion_pipeline_fresh`, `champion_pipeline_rejected`, `champion_pipeline_staging`, `engine_telemetry`, `fresh_pool_outcome_health` (view), `fresh_pool_process_health` (view), `zangetsu_status` (view).

## Required Phase 0 classification

| Field | Status |
|---|---|
| HEAD status | `29c757e3` matches `origin/main` ✅ |
| repo clean/dirty | dirty on **runtime artifacts only**; **source = clean** ✅ |
| runtime process status | 4× A1 + A23 + A45 alive ✅ |
| lockfile status | all 8 lockfiles present, no orphans ✅ |
| taxonomy import status | importable, all 3 probe inputs resolve canonically ✅ |
| delta-helper source status | all 3 tokens present in arena_pipeline.py ✅ |
| DB v0.7.1 sanity status | 8/8 objects present, queryable ✅ |
| A1 workers predate HEAD | **NO** — workers 17:02:16Z post-date source mtime 15:38:10Z by 84 min ✅ |

## STOP-condition check

| Condition | Triggered |
|---|---|
| repo dirty with **unexplained source changes** | NO (only runtime artifacts) |
| HEAD ≠ origin/main unexpectedly | NO (in sync) |
| source patch not present | NO (delta helper + key-set + snapshot dict all in source) |
| taxonomy mappings not importable | NO (all 3 resolved) |
| A1 runtime dead before restart | NO (4 workers alive) |
| DATABASE_URL unavailable | NO (DB queries returned) |
| v0.7.1 DB objects missing | NO (8/8 present) |

**No STOP condition triggered. Proceed to Phase 1.**
