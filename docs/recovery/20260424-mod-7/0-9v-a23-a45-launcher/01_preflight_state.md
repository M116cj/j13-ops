# 01 — Preflight State

## 1. Timestamp / Host

| Field | Value |
| --- | --- |
| Timestamp (UTC) | 2026-04-26T09:48:35Z |
| Host | `j13@100.123.49.102` (Tailscale) |
| Repo | `/home/j13/j13-ops` |
| SSH access | PASS |

## 2. Git State

| Field | Expected | Actual | Match |
| --- | --- | --- | --- |
| Branch | `main` | `main` | ✅ |
| HEAD | `f50e8cba7b5180605abcc08306446f79686aef60` | `f50e8cba7b5180605abcc08306446f79686aef60` | ✅ |
| origin/main | `f50e8cba...` | `f50e8cba7b5180605abcc08306446f79686aef60` | ✅ |
| Ahead/behind | 0 / 0 | 0 / 0 | ✅ |
| Working tree | clean | clean | ✅ |

## 3. Prior-Order Confirmations

| Order | Status |
| --- | --- |
| 0-9V-CLEAN (PR #29) | COMPLETE_CLEAN at `41796663` |
| 0-9V-REPLACE-RESUME (PR #30) | COMPLETE_SYNCED_SHADOW_ONLY at `5ab95bfe` → `6fdb4c93` |
| 0-9V-ENV-CONFIG (PR #31) | COMPLETE_ENV_REPAIRED at `f50e8cba` |

## 4. A1 Status (verified pre-existing healthy)

| Field | Value |
| --- | --- |
| `engine.jsonl` last write | `2026-04-26T09:47:27Z` (1 minute before this snapshot — actively cycling) |
| Watchdog last cycle | `2026-04-26T09:45:01Z` — restarted `arena_pipeline_w0..w3` PIDs `187987/187999/188008/188037` |
| `arena_pipeline_w*` lockfiles | 4 / 4 present in `/tmp/zangetsu/` |
| Cron | `*/5 * * * *` watchdog runs every 5 min on the patched script |
| Live worker count at snapshot moment | 0 (between cycles — workers exit cleanly per A1's batch design and respawn at 09:50) |

→ A1 generation pipeline is healthy on the post-CLEAN code; engine.jsonl is advancing.

## 5. Current Blocker (this order's target)

| Component | State |
| --- | --- |
| `arena23_orchestrator` (A2/A3) | NOT LAUNCHED — no lockfile in `/tmp/zangetsu/`, watchdog never iterates it |
| `arena45_orchestrator` (A4/A5) | NOT LAUNCHED — same |
| `/tmp/zangetsu_a23.log` last write | `2026-04-23T00:40:01Z` (3-day-old `KeyError: 'ZV5_DB_PASSWORD'` traceback — stale, pre-dates 0-9V-ENV-CONFIG) |
| `/tmp/zangetsu_a45.log` last write | `2026-04-23T00:40:02Z` (same) |
| `arena_batch_metrics.jsonl` | MISSING — A23 is the producer; until A23 runs, no batch metrics |

## 6. Root Cause for A23/A45 Absence

The watchdog's main loop iterates `$LOCK_DIR/*.lock`. It only manages services whose lockfile is already present. The orchestrators' `acquire_lock(name)` creates the lockfile only when launched. So if no other process bootstraps the lockfile, watchdog never spawns the orchestrator. This is the chicken-and-egg launcher gap.

The watchdog code DOES have correct case branches for both:

```bash
arena23_orchestrator)
  cmd="$VENV $BASE/services/arena23_orchestrator.py"
  ;;
arena45_orchestrator)
  cmd="$VENV $BASE/services/arena45_orchestrator.py"
  ;;
```

So the launcher LOGIC exists. Only the lockfile bootstrap is missing.

## 7. Phase A Verdict

→ **PASS.** Repo clean, A1 healthy, env-fix applied, exact blocker isolated to A23/A45 lockfile bootstrap. Proceed to Phase B inventory.
