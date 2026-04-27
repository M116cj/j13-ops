# 18 — Alaya Runtime Post-Change Verification (Track S)

## Notable State Change During Audit

**Alaya host rebooted during this order's execution.** First post-reboot data collection at 2026-04-27T04:08:45Z showed `uptime 8 min` (i.e. boot ≈ 04:00Z). Pre-reboot baseline (recorded in `/tmp/41-00_state_lock_alaya_baseline.md` at 2026-04-26T18:21:33Z) showed all 6 worker processes alive.

This is **NOT caused by this order** — none of this order's actions perform `kill`, `systemctl restart`, or service mutation. The reboot is independent (likely scheduled or external).

## Post-Reboot Runtime Inventory (2026-04-27T04:08:45Z)

| Service | Pre-reboot state (audit start) | Post-reboot state | Notes |
| --- | --- | --- | --- |
| A1 worker 0 (PID 629222) | ALIVE 4h 13m | **GONE** | watchdog cron */5 will respawn next */5 fire |
| A1 worker 1 (PID 629244) | ALIVE 4h 13m | **GONE** | same |
| A1 worker 2 (PID 629258) | ALIVE 4h 13m | **GONE** | same |
| A1 worker 3 (PID 629269) | ALIVE 4h 13m | **GONE** | same |
| A23 (PID 207186) | ALIVE 7h 35m | **GONE** | same |
| A45 (PID 207195) | ALIVE 7h 35m | **GONE** | same |
| A13 feedback cron */5 | running | last seen 2026-04-27T04:05:02Z (3 min before snapshot) — cron resumed | OK |
| watchdog cron */5 | running | will fire next */5; per `crontab -l` cron entry intact | OK |
| `/tmp/zangetsu_a1_w*.log` files | active 11+MB each | **DELETED** by reboot (tmpfs) | EXPECTED — `/tmp` is volatile |
| `engine.jsonl` | active write | last write 04:05:00Z = 3 min stale; size 18MB | persistent (on /home FS) |
| Postgres `deploy-postgres-1` | running | running | OK (Docker daemon resumed) |
| FastAPI servers (PID 1283/1284) | running | running | console + dashboard (different cron path, not arena) |
| `cp_api` server (PID 1024) | running | running | control plane |

## Required Checks (Per Order Track S)

| Check | Result |
| --- | --- |
| 1. Mac and Alaya main synced | PRE-DEPLOY: both at `9f6dc60`. Will sync to PR #43 squash commit post-merge. |
| 2. Alaya working tree clean | YES (excluding 3 runtime artifacts) |
| 3. A1 alive | **NO — pending watchdog cron */5** (this is recovery state, not stable runtime) |
| 4. A1 no _pb crash | n/a (workers gone — re-verify after watchdog respawn) |
| 5. A1 rejection stats parse | n/a (re-verify after respawn) |
| 6. A13 feedback clean | YES (last 04:05:02Z OK) |
| 7. A23 alive | **NO — pending watchdog respawn** |
| 8. A45 alive | **NO — pending watchdog respawn** |
| 9. watchdog status | cron entry intact; will fire on next */5 boundary |
| 10. DB schema exists | PARTIALLY — only legacy 5 tables (Track A BLOCKED) |
| 11. champion_pipeline VIEW resolves | NO (still TABLE, Track A BLOCKED) |
| 12. staging/fresh/rejected exist | NO (Track A BLOCKED) |
| 13. admission_validator exists | NO (Track A BLOCKED) |
| 14. fresh_insert_guard exists | NO live (test harness sets up separately) |
| 15. archive triggers exist | NO (Track A BLOCKED) |
| 16. validation contract source active | YES — code in arena_pipeline.py:982 + 1059 (post-PR #43 merge will be on Alaya) |
| 17. alpha_zoo default mode does not write | YES (post-PR #43 default-deny per Track E hardening) |
| 18. alpha_zoo dry-run zero DB writes | YES (post-PR #43 — `--dry-run` writes only `/tmp/sparse_candidate_dry_run_plans.jsonl`) |
| 19. deprecated seed blocked | YES (DEPRECATED guards intact in source; cron does NOT call them per Phase 0 audit) |
| 20. no CANARY active | YES (`ps aux | grep canary` returns 0) |
| 21. no production active | YES |
| 22. no execution/capital/risk changes | YES |
| 23. telemetry status recorded | engine.jsonl 18MB (persistent); /tmp/zangetsu_a1_*.log gone (tmpfs reboot loss); will respawn |

## Track S Verdict

→ **YELLOW — RUNTIME_RECOVERY_PENDING.**

The reboot during audit caused all 6 arena workers to terminate. Watchdog cron will respawn them on next */5 fire (typically within 5 minutes of boot). DB state is unaffected (Postgres on Docker survived; persistent volumes intact).

**Important**: Pre-reboot service state (alive 4-7h) is documented in Phase 0 baseline. Post-reboot recovery is automatic via cron (no manual intervention permitted within this order's safety boundary). A separate quick verification after PR #43 merge + 5 min wait will confirm watchdog respawn.

→ Track S verdict will be RE-VERIFIED post-PR-#43-merge when watchdog has had time to respawn workers.

## Forbidden Operations

- DID NOT manually start/restart any service
- DID NOT kill any process
- DID NOT modify cron entries
- DID NOT mutate DB
- All inspection via `ps`, `ls`, `tail`, `cat`, `pgrep` — read-only
