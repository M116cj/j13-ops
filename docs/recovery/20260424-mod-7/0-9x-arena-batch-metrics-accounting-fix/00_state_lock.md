# 00 — State Lock

Order: TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX
Phase: 0
Captured (UTC): 2026-04-27T15:13Z
Captured-by: Claude Lead

## Repo state

| Field | Value |
|---|---|
| Mac HEAD | `0370b3efb5914ee6e8bbcd35958bb2c2d4f6e8ea` |
| Alaya HEAD | `0370b3efb5914ee6e8bbcd35958bb2c2d4f6e8ea` (parity) |
| origin/main | `0370b3efb5914ee6e8bbcd35958bb2c2d4f6e8ea` |
| Branch | `main` (pre-hotfix) |

Repo clean of source modifications at state lock. Mac and Alaya are in parity at the head of the previous order's PR (#49 — taxonomy hotfix).

## Worker process state (Alaya)

`workers_alive=6` — A1 w0/w1/w2/w3 + A23 + A45 — all running since `2026-04-27T08:04Z` (≈ 7 h cumulative stats by now).
`lockfiles=6` — all six target lockfiles present.

Watchdog cron stable; no restart attempts since cold-boot recovery.

## DB sanity (v0.7.1)

`docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu`:
- `champion_pipeline` count = `89`

Schema PASS.

## Known root cause carry-over

From `0-9x-a1-reject-distribution-shift-diagnosis/05_counter_inconsistency_root_cause.md`:

> COUNTER_INCONSISTENCY is a per-emit residual delta from `entered_count − passed_count − rejected_count` going negative. The structural defect is that `stats` (initialized at `arena_pipeline.py:707-723`) is worker-lifetime cumulative while `entered_count = len(alphas)` passed into `_emit_a1_batch_metrics_from_stats_safe()` is per-round. After warmup, cumulative `rejected_count >> entered_count` and the negative-residual branch trips every emit.

This hotfix fixes that telemetry bug. The taxonomy bug (PR #43 missing entries) is already closed (PR #49).

## STOP-condition evaluation

| STOP condition | Triggered? |
|---|---|
| repo dirty with unexplained source modifications | NO |
| HEAD ≠ origin/main unexpectedly | NO — parity verified |
| A1 runtime dead | NO — 6/6 alive |
| DATABASE_URL unavailable | NO — DB reached via `docker exec` |
| v0.7.1 DB objects missing | NO |

**No STOP. Proceed to Phase 1.**

## Q1 / Q2 / Q3 for this order

- **Q1 Adversarial (5-dim)**:
  - Input boundary: empty stats, all-zero current, current==previous, current<previous (rollback) — all handled
  - Silent failure: snapshot updates unconditionally; missing keys default to 0
  - External dependency: pure helper has no DB/network/import dep beyond stdlib
  - Concurrency: per-process module-level state; each worker has its own dict
  - Scope creep: only `arena_pipeline.py` (helper + state) + new test file
- **Q2 Structural**: existing residual-correction branch preserved (still adds `COUNTER_INCONSISTENCY` for genuinely-negative residuals); tests assert no spurious CI for valid data
- **Q3 Efficiency**: 1 new helper function + 1 module-level constant + 1 module-level state dict + 1 test file (6 tests); 7 evidence docs (target ≤ 8)
