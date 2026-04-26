# 01 — Old Runtime Inventory

## 1. Inventory timestamp

UTC: `2026-04-26T04:26:03Z`

## 2. Alaya host

- Host: `j13@100.123.49.102` (Tailscale)
- Repo path: `/home/j13/j13-ops`
- Access: PASS (SSH connected, repo path exists, read access OK)

## 3. Git state

| Field | Value |
| --- | --- |
| Current SHA | `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52` |
| Current branch | **`phase-7/p7-pr4b-a2-a3-arena-batch-metrics`** (NOT `main`) |
| origin/main SHA | `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52` (stale local view, before fetch) |
| Working tree status | **DIRTY** (see §4) |

After `git fetch origin`:

```
f5f62b2b..73b931d2  main       -> origin/main
ahead/behind: 0 / 10
```

Alaya is **0 commits ahead, 10 commits behind** origin/main. The 10 behind correspond exactly to the 10 PRs we shipped from Mac:

```
PR #18  P7-PR4B           A2/A3 aggregate Arena batch metrics
PR #19  0-9O-B            Dry-run feedback budget allocator
PR #20  0-9R              Sparse-candidate optimization design
PR #21  0-9P              Generation profile passport persistence
PR #22  0-9P-AUDIT        Profile attribution audit / replay
PR #23  0-9R-IMPL-DRY     Sparse-candidate dry-run consumer
PR #24  0-9S-READY        CANARY readiness gate
PR #25  0-9S-CANARY       CANARY observer module
PR #26  0-9S-OBSERVE-FAST CANARY observation runner
PR #27  0-9S-CANARY-OBSERVE-COMPLETE  Replay + observation runner
```

## 4. Working tree dirty state

`git status --porcelain=v1`:

```
 M calcifer/maintenance.log
 M calcifer/maintenance_last.json
 M calcifer/report_state.json
 M zangetsu/services/arena23_orchestrator.py
 M zangetsu/services/arena_pass_rate_telemetry.py
 M zangetsu/services/generation_profile_metrics.py
?? calcifer/deploy_block_state.json
?? docs/governance/snapshots/2026-04-24T221219Z-pre-p7-pr4b.json
?? zangetsu/tests/test_a2_a3_arena_batch_metrics.py
```

| Category | File | Change | Risk if ff |
| --- | --- | --- | --- |
| Runtime service | `zangetsu/services/arena23_orchestrator.py` | +155 / -1 | Will conflict with PR #18 P7-PR4B `_p7pr4b_*` markers (NOT present in Alaya dirty version: 0 hits) |
| Runtime helper | `zangetsu/services/arena_pass_rate_telemetry.py` | +247 / -11 | Will conflict with PR #18 helpers (`normalize_arena_stage` / `build_a2_batch_metrics` / `build_a3_batch_metrics`: 0 hits in Alaya dirty version) |
| Profile metrics | `zangetsu/services/generation_profile_metrics.py` | +18 / -6 | DOES contain confidence enum (7 hits for `CONFIDENCE_A1_A2_A3` / `LOW_SAMPLE_SIZE`); may overlap PR #18 partially |
| Calcifer state | `calcifer/maintenance.log` | runtime state | should be `.gitignore`-d; safe to discard |
| Calcifer state | `calcifer/maintenance_last.json` | runtime state | same |
| Calcifer state | `calcifer/report_state.json` | runtime state | same |
| Calcifer state | `calcifer/deploy_block_state.json` | runtime state (untracked) | same |
| Untracked snapshot | `docs/governance/snapshots/2026-04-24T221219Z-pre-p7-pr4b.json` | governance snapshot | should be moved or kept |
| Untracked test | `zangetsu/tests/test_a2_a3_arena_batch_metrics.py` | test file | conflicts with PR #18 (already on main) |

## 5. Active runtime processes

```
caddy   4639   postgres: zangetsu zangetsu (Apr21, 30:58 CPU)
caddy   4892   postgres: zangetsu akasha (Apr21)
caddy   4982   postgres: zangetsu akasha (Apr21)
j13     2537810  cp_api/.venv/bin/python server.py    (Apr24, 4:23)
j13     3871446  uvicorn zangetsu.dashboard.run:app --port 9901   (Apr23)
j13     3871449  uvicorn zangetsu.console.run:app --port 9900     (Apr23)
70      3737124  postgres: zangetsu (recent)
```

**No `arena_pipeline` / `arena23_orchestrator` / `arena45_orchestrator` process running.** The arena pipeline is currently stopped (engine.jsonl last write: `2026-04-23 00:35:54`).

## 6. Active systemd services

```
console-api.service       loaded active running   Zangetsu V5 Console API
cp-api.service            loaded active running   cp_api — Zangetsu Control Plane API
dashboard-api.service     loaded active running   Zangetsu V5 Dashboard API
```

These are HTTP API frontends, NOT the arena pipeline. They will continue running through replacement.

## 7. tmux

`error connecting to /tmp/tmux-1000/default (No such file or directory)` — no tmux sessions.

## 8. Crontab (zangetsu-related entries)

```
*/5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1
0 */6 * * * /home/j13/j13-ops/zangetsu/scripts/daily_data_collect.sh
*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1
0 3 * * 0 find /tmp -maxdepth 1 \( -name "zangetsu_*.log.[0-9]" ... \) -mtime +7 -delete
0 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python3 scripts/v8_vs_v9_metrics.py > /tmp/v9_metrics_latest.md 2>&1
30 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python3 scripts/signal_quality_report.py > /tmp/v9_signal_quality_latest.md 2>&1
```

`watchdog.sh` runs every 5 min — likely the arena pipeline launcher. `arena13_feedback.py` runs every 5 min.

## 9. Logs

```
zangetsu/logs/dashboard.log         316 B    Apr 11
zangetsu/logs/engine.jsonl          38 MB    Apr 23 00:35  (308579 lines)
zangetsu/logs/engine.jsonl.1        2.5 MB   Apr 16
zangetsu/logs/pipeline-v2.log       9 KB     Apr 16
zangetsu/logs/r2_n4_watchdog.stdout 4.5 KB   Apr 22
```

Last engine.jsonl line:

```json
{"ts": "2026-04-23T00:35:54", "level": "INFO", "msg": "Stopped. a4_processed=0 a4_passed=0 a5_matches=0"}
```

Engine has been **stopped since Apr 23**. No live arena_batch_metrics.jsonl. No sparse_candidate_dry_run_plans.jsonl.

## 10. Python / venv

```
/usr/bin/python3            (system, not venv)
Python 3.12.3
.venv:                      (none at top level — venv is at zangetsu/.venv per process list)
```

Active Python processes use `/home/j13/j13-ops/zangetsu/.venv/bin/python3` and
`/home/j13/j13-ops/zangetsu/control_plane/cp_api/.venv/bin/python`.

## 11. Module presence (post-PR-A baseline)

| Module | Present on Alaya |
| --- | --- |
| `zangetsu/services/arena_pipeline.py` | YES (pre-P7-PR4B baseline) |
| `zangetsu/services/arena23_orchestrator.py` | YES (with dirty WIP) |
| `zangetsu/services/arena45_orchestrator.py` | YES |
| `zangetsu/services/arena_gates.py` | YES |
| `zangetsu/services/arena_pass_rate_telemetry.py` | YES (with dirty WIP) |
| `zangetsu/services/feedback_budget_allocator.py` | **MISSING** (shipped via PR #19) |
| `zangetsu/services/feedback_budget_consumer.py` | **MISSING** (shipped via PR #23) |
| `zangetsu/services/feedback_decision_record.py` | YES (PR #17) |
| `zangetsu/services/sparse_canary_observer.py` | **MISSING** (shipped via PR #25) |
| `zangetsu/services/generation_profile_metrics.py` | YES (with dirty WIP) |
| `zangetsu/services/generation_profile_identity.py` | YES (PR #17) |
| `zangetsu/tools/profile_attribution_audit.py` | **MISSING** (shipped via PR #22) |
| `zangetsu/tools/sparse_canary_readiness_check.py` | **MISSING** (shipped via PR #25) |
| `zangetsu/tools/run_sparse_canary_observation.py` | **MISSING** (shipped via PR #26) |
| `zangetsu/tools/replay_sparse_canary_observation.py` | **MISSING** (shipped via PR #27) |

## 12. Conclusion

Alaya is on **PR-A baseline (`f5f62b2`)** with **dirty WIP** that does NOT match the final P7-PR4B implementation now on origin/main. **0 ahead, 10 behind**. Cannot fast-forward over dirty state.

Per order §7: **STOP — BLOCKED_DIRTY_STATE.**
