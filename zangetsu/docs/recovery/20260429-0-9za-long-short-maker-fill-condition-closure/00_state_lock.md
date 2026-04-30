# 00 — State Lock

**TEAM ORDER**: 0-9ZA-LONG-SHORT-MAKER-FILL-CONDITION-CLOSURE
**Date**: 2026-04-30
**Mode**: READ-ONLY / SHADOW-ONLY / DECISION-ONLY
**Parent**: 0-9Z-STRUCTURAL-COST-FEASIBILITY (verdict `PATH_A_CONDITIONAL`, commit 3cb5e08f)

## Frozen baseline

| Item | Value | Source |
|------|-------|--------|
| HEAD | `3cb5e08f0f24fe8716826524079c778942c551c1` | `git rev-parse HEAD` |
| Branch | `main` | `git rev-parse --abbrev-ref HEAD` |
| Last commit | `docs(zangetsu/0-9z): structural cost feasibility — PATH_A_CONDITIONAL` | `git log --oneline -1` |
| Repo dirty | only auto-generated logs (`calcifer/maintenance.log`, `calcifer/maintenance_last.json`, `calcifer/report_state.json`, `zangetsu/logs/engine.jsonl.1`) | `git status --porcelain` |
| Source LOC dirty | `0` | manual diff inspection |
| 0-9Y verdict | `EDGE_EXHAUSTED` (HE5) | `docs/recovery/20260424-mod-7/0-9y-final-alpha-edge-restoration/` (referenced in 0-9Z) |
| 0-9Z verdict | `PATH_A_CONDITIONAL` | `docs/recovery/20260429-0-9z-structural-cost-feasibility/07_final_report.md` |

## Runtime snapshot (Alaya, 2026-04-30 ~01:30 UTC)

### systemd

| Service | systemctl is-active |
|---------|---------------------|
| `arena-pipeline.service` | `inactive` |
| `arena23-orchestrator.service` | `inactive` |
| `arena45-orchestrator.service` | `inactive` |
| `dashboard-api.service` | `active` |
| `console-api.service` | `active` |

### Process inspection (`pgrep -af arena_pipeline`)

4 detached `arena_pipeline.py` workers running outside systemd:

```
450636  /home/j13/j13-ops/zangetsu/.venv/bin/python3 /home/j13/j13-ops/zangetsu/services/arena_pipeline.py
495625  /home/j13/j13-ops/zangetsu/.venv/bin/python3 /home/j13/j13-ops/zangetsu/services/arena_pipeline.py
3864147 /home/j13/j13-ops/zangetsu/.venv/bin/python3 services/arena_pipeline.py
3923355 /home/j13/j13-ops/zangetsu/.venv/bin/python3 /home/j13/j13-ops/zangetsu/services/arena_pipeline.py
```

These are pre-existing workers (PIDs 450636 / 495625 / 3864147 / 3923355). 0-9ZA does not stop, restart, or modify them.

### DB state (`deploy-postgres-1` / `zangetsu`)

| Source | Status | Count |
|--------|--------|------:|
| `champion_pipeline_fresh` | `ARENA2_REJECTED` | **89** |
| `champion_pipeline_staging` | `ARENA1_COMPLETE` | **184** |
| `champion_pipeline_rejected` | (any) | 0 |
| `zangetsu_status` VIEW | `deployable_count` | **0** |
| `zangetsu_status` VIEW | `deployable_historical` | 0 |
| `zangetsu_status` VIEW | `deployable_fresh` | 0 |
| `zangetsu_status` VIEW | `deployable_live_proven` | 0 |
| `zangetsu_status` VIEW | `last_live_at_age_h` | NULL |
| `paper_trades` | total rows | 0 |
| `trade_journal` | total rows | 0 |

> Note: order text said "89 ARENA2_REJECTED / 184 ARENA1_COMPLETE / 0 deployable" — confirmed exact match against live DB.

## Pre-action checks

| Check | Result |
|-------|--------|
| Repo on `main` | ✅ |
| 0-9Z parent verdict accessible at HEAD | ✅ (`git show 3cb5e08f:docs/recovery/20260429-0-9z-structural-cost-feasibility/07_final_report.md`) |
| Source runtime modified | ❌ (no source file in dirty list) |
| DB mutated | ❌ (read-only queries only) |
| CANARY active | ❌ (no CANARY service / process) |
| Production rollout in progress | ❌ |
| Alpha generation modified | ❌ |
| Arena thresholds touched | ❌ |
| `A2_MIN_TRADES` constant | unchanged (`= 25`, per 0-9Z reference) |
| Champion promotion modified | ❌ |
| `deployable_count` semantic | unchanged |
| Live trading mode | ❌ |
| Production trading key requested/used | ❌ |
| Calcifer deploy block | not present (`/tmp/calcifer_deploy_block.json` absent at task start) |

## Lock

Baseline frozen. Any mutation observed beyond this point invalidates the analysis and triggers STOP-1 .. STOP-18 as applicable.

