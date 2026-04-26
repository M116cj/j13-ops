# 07 — Runtime Switch Report

## 1. Switch Performed

**PARTIAL** — code-path switch happened automatically through the existing watchdog cron line (the documented launcher), but worker initialization is blocked by a **pre-existing environment-configuration issue** introduced by commit `fe1c0bc0` (2026-04-20, "security(repo): purge hardcoded DB password + untrack .env files"), which removed the hardcoded `DB_PASSWORD` fallback in `zangetsu/config/settings.py:99` and now requires `ZV5_DB_PASSWORD` to be set in cron's environment.

This is not a regression introduced by 0-9V-REPLACE-RESUME or 0-9V-CLEAN. It is the same root cause for the original 2026-04-23 pipeline stop documented in PR #28 `09_runtime_switch_report.md`. Engine.jsonl has not advanced since `2026-04-23T00:35Z`.

→ Final status: **COMPLETE_SYNCED_SHADOW_ONLY** (per order §16 allowed statuses).

## 2. Runtime Manager

| Service | Manager | State | Notes |
| --- | --- | --- | --- |
| `console-api.service` | systemd | running | HTTP API; UNTOUCHED through replacement (PID 3871449, since Apr 23) |
| `cp-api.service` | systemd | running | Control Plane API; UNTOUCHED (PID 2537810, since Apr 24) |
| `dashboard-api.service` | systemd | running | Dashboard API; UNTOUCHED (PID 3871446, since Apr 23) |
| `arena_pipeline_w0..w3` (A1) | cron `*/5 * * * * watchdog.sh` | crash-loop | watchdog spawns from new SHA; workers exit on `KeyError: ZV5_DB_PASSWORD` |
| `arena23_orchestrator` (A2/A3) | cron via watchdog | crash-loop | same env error |
| `arena45_orchestrator` (A4/A5) | cron via watchdog | crash-loop | same env error |
| `arena13_feedback.py` | cron `*/5 * * * *` direct | TBD | runs via cron `*/5` line; behavior unverified this run |
| `calcifer-supervisor.service` | systemd | running | UNTOUCHED |
| `calcifer-miniapp.service` | systemd | running | UNTOUCHED |
| Postgres / akasha sidecars | docker / systemd | running | UNTOUCHED |

→ HTTP APIs preserved exactly as required. No service restarted by this order.

## 3. Code-Path Switch Evidence

| Field | Value |
| --- | --- |
| Source file mtime (post-CLEAN fast-forward) | `2026-04-26 06:06` (UTC) for `arena_pipeline.py` and `arena23_orchestrator.py` |
| Watchdog cron interval | `*/5 * * * *` |
| Watchdog last cycle | `2026-04-26T08:30:01Z` (spawned `w0..w3` from new SHA) |
| Old worker PIDs (pre-replacement, same crash-loop pattern) | observed Apr 23 → present, all crashing on env var |
| New worker PIDs (post-fast-forward source) | `33428`, `33450`, `33468`, `33477` (08:30:01 cycle); previously `22280..22310`, `12505..12535`, `2057..2105` etc. — each cycle replaces the prior, and each is launched from the post-CLEAN source. |
| §17.6 stale-service check | PROC_START > SOURCE_MTIME for each new spawn (workers are NEWER than source) → **FRESH per §17.6** even though they crash immediately afterward |

Per §17.6 "running process ≥ source mtime" rule: the workers ARE running newer code than what is on disk for source, even though they fail-fast on env. The launcher path is genuinely on the new SHA.

## 4. Old PIDs

| Process | Old PID | Notes |
| --- | --- | --- |
| `arena_pipeline_w0` | 22280 (last 08:25 cycle) | crashed on env, replaced |
| `arena_pipeline_w1` | 22289 | same |
| `arena_pipeline_w2` | 22301 | same |
| `arena_pipeline_w3` | 22310 | same |
| `cp-api` | 2537810 | UNTOUCHED |
| `dashboard-api` | 3871446 | UNTOUCHED |
| `console-api` | 3871449 | UNTOUCHED |

## 5. New PIDs

| Process | New PID (latest watchdog cycle observed) | State |
| --- | --- | --- |
| `arena_pipeline_w0` | 33428 (spawned 08:30:01) | dead (crashed on env, ~30 s) |
| `arena_pipeline_w1` | 33450 | dead |
| `arena_pipeline_w2` | 33468 | dead |
| `arena_pipeline_w3` | 33477 | dead |
| HTTP APIs | unchanged | running |

→ The code-path is on the new SHA. Functional uptime is blocked by the env issue.

## 6. Working Directory

`/home/j13/j13-ops` — unchanged.

## 7. Logs Writing Status

| File | Status |
| --- | --- |
| `engine.jsonl` | NOT WRITING (last write `2026-04-23T00:35Z`; pipeline cannot reach the engine loop) |
| `dashboard.log` | NOT WRITING (last write Apr 11; idle service) |
| `/tmp/zangetsu_a1_w0..w3.log` | WRITING (each cycle records the `KeyError: ZV5_DB_PASSWORD` traceback) |
| `/tmp/zangetsu_a23.log`, `/tmp/zangetsu_a45.log` | WRITING (same traceback) |
| `/tmp/zangetsu_watchdog.log` | WRITING (every 5 min, "DEAD → restart" pattern) |
| `console-api`, `cp-api`, `dashboard-api` systemd journals | WRITING normally |

No log file was deleted, modified, or rotated by this order.

## 8. Telemetry Writing Status

| File | Status |
| --- | --- |
| `arena_batch_metrics.jsonl` | NOT WRITING (PR #18 emitter only fires after the orchestrator reaches the 20-iteration boundary; orchestrator cannot pass init) |
| `sparse_candidate_dry_run_plans.jsonl` | NOT WRITING (consumer not in runtime, by design) |

No telemetry file was deleted, modified, or rotated.

## 9. Errors Observed

```
File "/home/j13/j13-ops/zangetsu/config/settings.py", line 99, in <module>
    DB_PASSWORD: str = os.environ["ZV5_DB_PASSWORD"]  # no fallback — must be set in env
KeyError: ZV5_DB_PASSWORD
```

Reproduces in all 6 worker logs (`/tmp/zangetsu_a1_w0..w3.log`, `/tmp/zangetsu_a23.log`, `/tmp/zangetsu_a45.log`).

| Field | Value |
| --- | --- |
| First introduced by | commit `fe1c0bc0` (2026-04-20) |
| Surface area | All cron-spawned workers; HTTP APIs unaffected (they have env passed via systemd unit files, not cron) |
| In scope of THIS order | NO — this order is a runtime replacement, not an env-config order. The hard bans explicitly forbid modifying `.env` / secrets / runtime services. |
| Resolution | Requires a separate authorized order from j13 to add `ZV5_DB_PASSWORD` to either `/home/j13/.env.global` or the cron line preamble (or to replace cron with a systemd unit that loads the env file). |

## 10. Rollback Readiness

| Field | Value |
| --- | --- |
| Rollback feasible | YES |
| Rollback SHA | `f5f62b2bc27a448dcf41c9ff6f6c847cb01c56c52` (pre-CLEAN, pre-RESUME) |
| Rollback procedure | Documented in `docs/recovery/20260424-mod-7/0-9v-replace/rollback_commands.sh` |
| Note | Rollback would NOT fix the env issue (the issue exists at `f5f62b2b` too — that SHA is post-`fe1c0bc0`). Rollback is preserved purely for governance integrity. |

## 11. Hard-Ban Audit

| Forbidden action | Performed? |
| --- | --- |
| rsync / scp Mac repo over Alaya | NO |
| overwrite `/home/j13/j13-ops` manually | NO |
| delete logs / telemetry / `.env` / secrets / runtime state | NO |
| Hard-reset / force-pull / merge divergent | NO |
| restart HTTP API services | NO |
| modify alpha generation / formula / mutation / search policy / budget / weights / thresholds / Arena pass/fail / champion / deployable_count / execution / capital / risk | NO |
| connect optimizer / allocator / consumer to generation runtime | NO |
| create apply path / runtime-switchable APPLY mode | NO |
| start CANARY / production rollout | NO |

→ All hard bans honored.

## 12. Phase G Verdict

→ **PARTIAL switch performed.** Code-path on new SHA via existing cron+watchdog launcher; HTTP APIs preserved; worker init blocked by pre-existing env-config issue (out of scope for this order). Recommend separate **TEAM ORDER 0-9V-ENV-CONFIG** to authorize and apply the env-var fix, after which workers will reach the engine loop and start emitting `arena_batch_metrics.jsonl`.

→ Final status: **COMPLETE_SYNCED_SHADOW_ONLY**.
