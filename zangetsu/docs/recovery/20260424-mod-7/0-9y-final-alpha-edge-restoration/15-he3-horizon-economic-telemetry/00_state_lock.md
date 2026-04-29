# 00 — STATE LOCK

**TEAM ORDER**: 0-9Y-HE3-HORIZON-ECONOMIC-TELEMETRY
**Date**: 2026-04-29
**Phase**: 0 / 8

## Git
- Branch: `main`
- HEAD: `48be8071734195c39b56e562225023d31fcf4a36` (post-HE2, signed ED25519)
- origin/main: `48be8071734195c39b56e562225023d31fcf4a36` ✅ in-sync
- Working tree (zangetsu): only `zangetsu/logs/engine.jsonl.1` (runtime log) — no source dirty.

## TF / HE stack present
| Module | Path | Status |
|---|---|---|
| TF2 helper | `zangetsu/services/signal_aggregation.py` | ✓ |
| TF3 shadow | `zangetsu/services/tf3_shadow.py` | ✓ |
| TF4 production config | `zangetsu/services/aggregation_config.py` | ✓ |
| HE1 horizon config | `zangetsu/services/horizon_config.py` | ✓ |
| HE2 (in arena_pipeline + alpha_engine + passport) | (extends existing files) | ✓ |

## Stack regression
```
pytest -q test_he2_horizon_aware_generation.py test_he1_horizon_config.py \
            test_tf4_aggregation_config.py test_tf3_shadow.py test_signal_aggregation.py
→ 52 passed in 0.41s ✅
```

## Worker baseline state
Live worker env (sample PID 2963114): no `ARENA_HORIZON_*` / `ACTIVE_A1_HORIZONS` / `ALPHA_FORWARD_HORIZON` / `ARENA_AGGREGATION_*` / `ARENA_TF3_SHADOW` set → confirmed baseline mode (single horizon=60).

## HE2 fields present in batch metrics
HE2 emits the following in `_b1_aggregate_metrics` (verified by HE2 patch report and HE2 test #9):
- `horizon` (always emitted; default 60)
- `selected_horizon` (alias of horizon)
- `active_horizons` (only when multi-horizon)
- `horizon_mode` (only when multi-horizon)
- `generation_profile_horizon` (only when h≠60)
- `horizon_config` (existing HE1 dict)

## Per-alpha data lists (populated per round, source for HE3 horizon_metrics)
| List | Initialized | Populated |
|---|---|---|
| `_b1_train_gross_pnl: list[float]` | line 1064 (per round, per (sym, regime)) | line 1190 (per alpha) |
| `_b1_train_net_pnl: list[float]` | line 1065 | line 1194 |
| `_b1_train_total_trades: list[int]` | line 1066 | line 1198 |
| `_b1_train_win_rate: list[float]` | line 1068 | line 1206 |
| `_b1_round_total_cost_bps_for_sym: float` | line 1056-1062 | (set per symbol from cost_model) |
| `_b1_signal_density` | computed at line 1520 | (derived from `_b1_train_total_trades`) |

These are the source data for HE3's per-horizon aggregation. All already exist; HE3 only needs to assemble them into a `horizon_metrics[selected_horizon] = {...}` dict at the same emission point.

## Order status
| Order | Status |
|---|---|
| OP1 | COMPLETE (`82056123`) |
| TF2 | COMPLETE (`3decabd4`) |
| TF3 | COMPLETE (`0cef908d`) |
| TF4 | COMPLETE (`986932df`) |
| HE1 | COMPLETE (`bbd6fb42`) |
| HE2 | COMPLETE (`48be8071`) |

## Telemetry sanity
- UNKNOWN_REJECT: 0 across recent batches ✅
- COUNTER_INCONSISTENCY: 0 ✅
- Conservation residual: 0 ✅

## STOP-conditions check (Phase 0 spec)
| STOP cause | Status |
|---|---|
| Telemetry regression | ❌ no — 52 PASS, baseline batches clean |
| Runtime unstable | ❌ no — workers running, last batches verified |
| HE2 fields missing | ❌ no — `horizon` / `selected_horizon` etc. all present per HE2 PR #70 evidence |

✅ **STATE_LOCK_PASS** — proceed to Phase 1.
