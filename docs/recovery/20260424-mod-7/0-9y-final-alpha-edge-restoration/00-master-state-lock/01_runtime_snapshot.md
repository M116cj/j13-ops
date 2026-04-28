# 01 — Runtime Snapshot

**Order:** TEAM ORDER 0-9Y-FINAL-0-MASTER-STATE-LOCK
**Phase:** 0 / sub-doc 01
**Captured (UTC):** 2026-04-28T02:55Z

## Worker process census (Alaya `ps`)

| PID | Process | lstart |
|---|---|---|
| 1364819 | `arena_pipeline.py` (w0) | Tue Apr 28 00:04:55 2026 |
| 1364842 | `arena_pipeline.py` (w1) | Tue Apr 28 00:04:55 2026 |
| 1364934 | `arena_pipeline.py` (w2) | Tue Apr 28 00:04:55 2026 |
| 1451007 | `arena_pipeline.py` (w3 — watchdog respawn) | Tue Apr 28 01:20:01 2026 |
| 1365067 | `arena23_orchestrator.py` | Tue Apr 28 00:04:56 2026 |
| 1365092 | `arena45_orchestrator.py` | Tue Apr 28 00:04:56 2026 |

**6 / 6 target workers alive.** Three of the four A1 workers are from the operator-authorized restart at 2026-04-28T00:04Z (Subprogram-C entry); w3 was watchdog-respawned at 01:20:01Z (~75 min ago) — confirms watchdog cold-boot patch (PRs #45 / #46) is operating correctly.

## Lockfile census (`/tmp/zangetsu/`)

All six target lockfiles present:
- `arena_pipeline_w0.lock`
- `arena_pipeline_w1.lock`
- `arena_pipeline_w2.lock`
- `arena_pipeline_w3.lock`
- `arena23_orchestrator.lock`
- `arena45_orchestrator.lock`

Plus housekeeping locks (`calcifer_supervisor.lock`, `arena13_feedback.lock`).

## Watchdog cron

Stable. Runs every 5 minutes. Last few ticks all reported "all 8 services healthy" or "lockfile_present_main_loop_owns" (steady state). No spurious restart attempts since the operator-authorized restart at 00:04Z apart from the legitimate w3 respawn at 01:20Z.

## Engine activity

`engine.jsonl` is advancing. Current latest `arena_batch_metrics` event timestamp = `2026-04-28T02:54:56Z` (within 1 minute of state-lock capture). Engine throughput is nominal (~6 batches/min × ~3 hours since restart = ~1000+ batches generated since FINAL-0 entry).

## Conclusion

Runtime is **stable, observable, and live**. No abnormalities. Workers are running the post-`d9d1783` codebase (taxonomy hotfix + accounting fix + B1 aggregate_metrics + Calcifer null-safe deploy_block + 0-9Y-C decomposition merged into the source).
