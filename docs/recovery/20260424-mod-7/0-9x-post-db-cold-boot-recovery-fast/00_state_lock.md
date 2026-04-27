# 00 — Phase 0 State Lock

Order: TEAM ORDER 0-9X-POST-DB-COLD-BOOT-RECOVERY-FAST
Generated: 2026-04-27T08:11Z (Alaya UTC)
Operator: Claude (j13-ops repo on Alaya)

## Repo state

- Working tree: dirty BUT every modification is explainable and in-scope.
- HEAD: `7cb67e497cbd20cf54ddec7269fe8551bd51b88b` (matches order target).
- Branch: `main`.
- `origin/main`: `7cb67e497cbd20cf54ddec7269fe8551bd51b88b` (Mac+Alaya synced, PR #44 merged).
- Last commit (signed): `feat(db-migration/0-9x-multi-stage): COMPLETE_DB_MIGRATED_V071 (#44)` — GPG signature present (no public key on Alaya for verification, expected).

### git status --short

```
 M calcifer/maintenance.log              # runtime artifact (log appender), NOT source
 M calcifer/maintenance_last.json        # runtime status JSON, NOT source
 M calcifer/report_state.json            # runtime status JSON, NOT source
 M zangetsu/logs/engine.jsonl.1          # rotated engine log, NOT source
 M zangetsu/watchdog.sh                  # IN-SCOPE: cold-boot patch (Phase 2 deliverable)
?? zangetsu/tests/test_watchdog_cold_boot.py  # IN-SCOPE: Phase 5 deliverable
```

Classification: NOT a STOP condition. The order's STOP rule is "repo dirty
with **unexplained** source modifications". The four `M` entries under
`calcifer/` and `zangetsu/logs/` are non-source runtime files that the
running daemons rewrite continuously; they will be excluded from the
commit. The two in-scope changes (`watchdog.sh`, new test) are exactly
what Phases 2 and 5 of this order require.

## Runtime processes (verified live, 2026-04-27T08:08Z)

| Service                 | PID     | Started        | State |
|-------------------------|---------|----------------|-------|
| arena_pipeline_w0       | 278020  | 2026-04-27 08:04 | Rl (running) |
| arena_pipeline_w1       | 278025  | 2026-04-27 08:04 | Rl (running) |
| arena_pipeline_w2       | 278030  | 2026-04-27 08:04 | Rl (running) |
| arena_pipeline_w3       | 278035  | 2026-04-27 08:04 | Rl (running) |
| arena23_orchestrator    | 278077  | 2026-04-27 08:04 | Sl (running) |
| arena45_orchestrator    | 278100  | 2026-04-27 08:04 | Sl (running) |
| console_api (port 9900) | 1283    | 04:01           | Ssl   |
| dashboard (port 9901)   | 1284    | 04:01           | Ssl   |
| cp_api server.py        | 1024    | 04:01           | Ssl   |

A1/A23/A45 worker processes are CURRENTLY ALIVE.

## Lockfiles (verified, /tmp/zangetsu/)

```
arena13_feedback.lock        2026-04-27 08:05
arena23_orchestrator.lock    2026-04-27 08:04
arena45_orchestrator.lock    2026-04-27 08:04
arena_pipeline_w0.lock       2026-04-27 08:04
arena_pipeline_w1.lock       2026-04-27 08:04
arena_pipeline_w2.lock       2026-04-27 08:04
arena_pipeline_w3.lock       2026-04-27 08:04
calcifer_supervisor.lock     2026-04-27 04:01
```

All six required worker lockfiles are present (timestamps match process
start at 08:04 → workers self-write their lockfiles via
`zangetsu.services.pidlock.acquire_lock`).

## Cron + supervision

- `*/5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1` — active.
- No systemd `--user` units (expected — these workers are cron + lockfile-driven).
- `arena13_feedback_env.sh` is a separate `*/5` cron, not in scope.

## Watchdog log evidence (the cold-boot pass IS already in the watchdog file and ran at 08:05)

```
[ZANGETSU_COLD_BOOT] worker=arena_pipeline_w0 action=skipped reason=lockfile_present_main_loop_owns ts=2026-04-27T08:05:01
[ZANGETSU_COLD_BOOT] worker=arena_pipeline_w1 action=skipped reason=lockfile_present_main_loop_owns ts=2026-04-27T08:05:01
[ZANGETSU_COLD_BOOT] worker=arena_pipeline_w2 action=skipped reason=lockfile_present_main_loop_owns ts=2026-04-27T08:05:01
[ZANGETSU_COLD_BOOT] worker=arena_pipeline_w3 action=skipped reason=lockfile_present_main_loop_owns ts=2026-04-27T08:05:01
[ZANGETSU_COLD_BOOT] worker=arena23_orchestrator action=skipped reason=lockfile_present_main_loop_owns ts=2026-04-27T08:05:01
[ZANGETSU_COLD_BOOT] worker=arena45_orchestrator action=skipped reason=lockfile_present_main_loop_owns ts=2026-04-27T08:05:01
```

Cold-boot pass is correctly idempotent on the happy-path (lockfile present
→ skip). The actual cold-boot-from-zero behavior must still be exercised
by Phase 5 sandbox tests because the present runtime was hand-restarted
at 08:04 before the patched watchdog tick at 08:05.

## DB sanity (psql via deploy-postgres-1 docker container)

```
DATABASE_URL=postgresql://zangetsu:${ZV5_DB_PASSWORD}@127.0.0.1:5432/zangetsu

select now(), current_database(), current_user;
             now              | current_database | current_user
------------------------------+------------------+--------------
 2026-04-27 08:10:30.77533+00 | zangetsu         | zangetsu

select to_regclass('public.champion_pipeline'), to_regclass('public.champion_pipeline_staging'), to_regclass('public.champion_pipeline_fresh');
 champion_pipeline |          staging          |          fresh
-------------------+---------------------------+-------------------------
 champion_pipeline | champion_pipeline_staging | champion_pipeline_fresh
```

v0.7.1 contract objects are visible.

## Engine log signal (last lines)

`zangetsu/logs/engine.jsonl` advances; A1 candidate lifecycle entries
(ENTERED → REJECTED with `TRAIN_NEG_PNL` etc.) flowing for ETHUSDT pool.
Confirms A1 worker stack is reaching the rejection-classifier path.

## Classification

| Item                                  | Status                            |
|---------------------------------------|-----------------------------------|
| repo clean/dirty                      | dirty (in-scope changes only)     |
| current HEAD                          | 7cb67e49 (matches order)          |
| worker processes alive/missing        | ALL ALIVE (4xA1, A23, A45)        |
| lockfiles alive/missing               | ALL PRESENT (6/6 required)        |
| watchdog cold-boot capable/incapable  | CAPABLE (patch present + ran at 08:05) |
| DB schema visible/invisible           | VISIBLE (v0.7.1 contract intact)  |

## STOP rule outcome

- repo dirty with unexplained source modifications? → **NO** (all `M`s explained above; the two in-scope changes are exactly what this order asks for).
- DATABASE_URL unavailable?                         → **NO** (constructable from `ZV5_DB_PASSWORD`; psql works inside `deploy-postgres-1`).
- DB v0.7.1 objects missing?                        → **NO** (champion_pipeline + staging + fresh all present).

**Phase 0 RESULT: PROCEED to Phase 1.**

## Q1 dimensions (this phase)

| Dimension                       | Outcome |
|---------------------------------|---------|
| Input boundary (read-only)      | PASS — no inputs accepted |
| Silent failure propagation      | PASS — every command piped `2>&1` and explicitly inspected |
| External dependency failure     | PASS — DB reached via docker fallback when host `psql` absent |
| Concurrency / race              | N/A — snapshot read |
| Scope creep                     | PASS — stayed inside state-lock; did not touch alpha / Arena / thresholds |
