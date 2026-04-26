# 01 — Runtime Service Parameter Audit

## 1. Service Process Inventory

| Service | PID | Uptime | Command | Working dir | Log file |
| --- | --- | --- | --- | --- | --- |
| A1 worker 0 | 629222 | 4h 13m | `python3 zangetsu/services/arena_pipeline.py` | `/home/j13/j13-ops` | `/tmp/zangetsu_a1_w0.log` |
| A1 worker 1 | 629244 | 4h 13m | `python3 zangetsu/services/arena_pipeline.py` | `/home/j13/j13-ops` | `/tmp/zangetsu_a1_w1.log` |
| A1 worker 2 | 629258 | 4h 13m | `python3 zangetsu/services/arena_pipeline.py` | `/home/j13/j13-ops` | `/tmp/zangetsu_a1_w2.log` |
| A1 worker 3 | 629269 | 4h 13m | `python3 zangetsu/services/arena_pipeline.py` | `/home/j13/j13-ops` | `/tmp/zangetsu_a1_w3.log` |
| A23 orchestrator | 207186 | 7h 35m | `python3 zangetsu/services/arena23_orchestrator.py` | `/home/j13/j13-ops` | `/tmp/zangetsu_a23.log` |
| A45 orchestrator | 207195 | 7h 35m | `python3 zangetsu/services/arena45_orchestrator.py` | `/home/j13/j13-ops` | `/tmp/zangetsu_a45.log` |

Python interpreter (all): `/home/j13/j13-ops/zangetsu/.venv/bin/python3`

## 2. Cron-Driven Helpers

| Cron entry | Cadence | Purpose |
| --- | --- | --- |
| `~/j13-ops/zangetsu/watchdog.sh` | */5 min | per-service health check + restart-only-dead-service |
| `arena13_feedback_env.sh` | */5 min | A13 feedback loop (single-shot) |
| `daily_data_collect.sh` | every 6 h | OHLCV refresh |
| `v8_vs_v9_metrics.py` | hourly | dashboard report |
| `signal_quality_report.py` | :30 hourly | dashboard report |
| `v10_factor_zoo_report.py` | :15 hourly | dashboard report |
| `v10_alpha_ic_analysis.py` | :45 hourly | dashboard report |
| `alpha_discovery` | */30 min | factor discovery |
| `zangetsu_snapshot.sh` | every minute | runtime metric snapshot |

## 3. Env Wrapper Chain

`watchdog.sh` and `arena13_feedback_env.sh` both source `~/.env.global` via `set -a; . "$HOME/.env.global"; set +a` before launching workers. This is the **single source of secrets** for cron-launched processes.

## 4. A23/A45 Idle State

A23/A45 logs show last activity at 09:53Z — "Service loop started" / "Daily reset complete: kept=0 retired=0 across 0 regimes". 7+ hours of silence. Consistent with empty `champion_pipeline` (0 rows — confirmed in Phase 7) → no Arena 2/3/4/5 candidates to promote.

## 5. A1 Activity (most recent batch)

```
batch_id: R50384-XRPUSDT-CONSOLIDATION
entered_count: 10
passed_count: 0
rejected_count: 18670
reject_rate: 1.0
reject_reason_distribution:
  COUNTER_INCONSISTENCY: 9330
  COST_NEGATIVE: 9319
  SIGNAL_TOO_SPARSE: 20
  INVALID_FORMULA: 1
```

→ **A1 reject distribution has shifted** away from `val_neg_pnl` (the bottleneck diagnosed in PRs 38-40). Now dominated by `COUNTER_INCONSISTENCY` and `COST_NEGATIVE` — both pre-val-backtest rejection paths in the GP fitness calculation. **Significant drift since prior governance orders.**

## 6. Classification

| Verdict | Match? |
| --- | --- |
| **RUNTIME_PARAMETERS_OK** | partial — services running, env wrappers correct, but reject distribution drift is unexplained |
| RUNTIME_WRAPPER_MISMATCH | NO |
| RUNTIME_STALE_PROCESS | NO (A23/A45 idle is correct given empty pipeline; not stale) |
| RUNTIME_ENV_DRIFT | NO (single .env.global, no override files) |
| **RUNTIME_UNKNOWN** | partial — the COUNTER_INCONSISTENCY+COST_NEGATIVE reject distribution is undocumented in prior orders |

→ **Phase 1 verdict: RUNTIME_PARAMETERS_OK with caveat — reject reason distribution shifted; needs Phase 5/8 cross-check.**
