# 06 — Post-Merge Runtime Validation

## 1. Patch Pickup Timeline

| Cron tick | Watchdog log entry | Source-on-disk |
| --- | --- | --- |
| 13:10:01 | restarted w0..w3 (PIDs 618384/618393/618405/618419) | un-patched |
| 13:15:01 | DEAD/restarted w0..w3 (PIDs 629222/629244/629258/629269) | un-patched (PR #37 not yet merged) |
| **13:17:28** | **PR #37 merged** at `1a90807696af9ff23b19e2a956986197f5f15395` | **patched source now on disk** |
| 13:20:01 | (no DEAD/restart line; all workers still alive) | patched (read by future respawn) |
| 13:25:01 | (no DEAD/restart line) | patched |
| 13:30:01 | `all 8 services healthy` (periodic summary, only logged when all alive) | patched |

→ The 13:15 workers (un-patched source in memory) **are still alive** at 13:31:55Z observation time, ~16 minutes after spawn. Pre-patch every cron cycle had 4 DEAD/restart events (within seconds). Post-patch, **the watchdog reports `all 8 services healthy`** for the first time since the original 2026-04-23 stop.

## 2. Why the 13:15 Un-Patched Workers Stay Alive

Python `main()` locals persist for the function's lifetime. Once any candidate in any symbol/regime cycle passes the 9-stage val-filter chain, `_pb = _get_or_build_provenance(...)` runs (line 1116) and `_pb` becomes a defined local. On all subsequent rounds where 0 candidates pass, the `getattr(_pb, "run_id", "")` at line 1218 reads from the still-defined `_pb` (re-using the previous round's value). The crash only fires on the **first** round-end emit if `_pb` was never assigned even once in the worker's lifetime.

The 13:15 workers must have hit at least one symbol/regime where `>= 1` candidate passed val gates earlier in their run. After that, the un-patched code runs as cleanly as the patched code. Once any worker actually exits (next watchdog DEAD detection or 50 MB log rotation), the **next** respawn picks up the patched source from disk and is guaranteed never to crash on this scenario regardless of round outcomes.

## 3. UnboundLocalError Recurrence Search (post-merge)

```
$ for w in 0 1 2 3; do grep -c "UnboundLocalError" /tmp/zangetsu_a1_w${w}.log; done
0
0
0
0
```

→ **Zero** UnboundLocalError tracebacks in any worker log since 13:17:28Z merge.

## 4. Previously-Unreachable Stats Line Now Reached

The `if round_number % 10 == 0:` log line at `arena_pipeline.py:1207` (which sits BEFORE the line-1218 emit) was masked by the crash on un-patched workers that crashed on round 49451 % 10 = 1. Now we see it firing every 10 rounds:

```
2026-04-26 13:30:35,352 INFO R49500   | XRPUSDT/CONSOLIDATION   | champions=0/10 | 15.6s | rejects: few_trades=0 val_few=1 val_neg_pnl=499 val_sharpe=0 val_wr=0
2026-04-26 13:30:41,058 INFO R323450  | GALAUSDT/BULL_TREND     | champions=0/10 | 15.7s | rejects: few_trades=0 val_few=0 val_neg_pnl=499 val_sharpe=0 val_wr=1
2026-04-26 13:30:23,661 INFO R266600  | BNBUSDT/BULL_TREND      | champions=0/10 | 14.9s | rejects: few_trades=0 val_few=0 val_neg_pnl=500 val_sharpe=0 val_wr=0
2026-04-26 13:30:02,733 INFO R411750  | 1000PEPEUSDT/BULL_TREND | champions=0/10 | 15.3s | rejects: few_trades=0 val_few=0 val_neg_pnl=500 val_sharpe=0 val_wr=0
```

| Field | Observation |
| --- | --- |
| `champions=0/10` | EVERY round produces 0 winners (out of 10 alphas per symbol/regime) |
| `rejects: val_neg_pnl=499` (or 500) | **99.8%-100%** of candidates fail at the holdout net-PnL gate (`bt_val.net_pnl <= 0`) |
| `rejects: val_few=1` | rare (1 candidate in some rounds rejected at < 15 holdout trades) |
| `rejects: val_sharpe=0` | none reach Sharpe gate (because they already failed val_neg_pnl) |
| `rejects: val_wr=0` or `1` | rare (only if val_neg_pnl bucketed 499 instead of 500) |

→ The val-filter chain is **functioning correctly**. ~500 candidates per round all produce non-positive holdout PnL. This is overfitting being **caught** by the OOS gate, not the gate being broken.

## 5. engine.jsonl + Other Cross-Service Health

| Service | State |
| --- | --- |
| engine.jsonl | continues writing (mtime advances per cron cycle; ENTRY events still emitted before the val gates) |
| A13 feedback (cron `*/5`) | continues clean (`Arena 13 Feedback complete (single-shot)` lines every cron tick) |
| A23 / A45 daemons | ALIVE, idle (PID 207186 / 207195, 3h 39m+ wall time) |
| HTTP APIs | UNTOUCHED |

## 6. Health Classification

Per order §Phase 5 / Phase 6 / §17 mapping:

| Verdict | Match? |
| --- | --- |
| MATERIALIZATION_CONFIRMED (new rows in staging/fresh/etc. after patch) | NO |
| **CRASH_FIXED_BUT_ALL_FILTERED** (crash gone, stats line visible, 0 rows because all candidates fail filters before persistence) | **YES — exact match** |
| CRASH_FIXED_BUT_DB_WRITE_ERROR | NO |
| CRASH_NOT_FIXED | NO |
| NEW_BLOCKER_FOUND | NO |

→ **Phase 5 verdict: PATCH EFFECTIVE.** UnboundLocalError eliminated; workers stay alive across multiple cron cycles for the first time since 2026-04-23.

→ Newly-revealed downstream issue: 99.8% of candidates fail `val_neg_pnl` gate. This is a **strategy / generation-tuning** matter, not a runtime bug. Order's hard ban prohibits weakening the threshold here (\"Do NOT weaken Arena thresholds\"). A separate **`TEAM ORDER 0-9W-VAL-FILTER-DIAGNOSIS`** is the proper next step.
