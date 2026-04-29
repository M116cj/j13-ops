# 00 — STATE LOCK

**TEAM ORDER**: 0-9Z-STRUCTURAL-COST-FEASIBILITY-AND-ROUTING-DECISION
**Date**: 2026-04-29
**Phase**: 0 / 8
**Mode**: READ-ONLY / DECISION-ONLY

## Git
- HEAD: `bcf53cb5b4cfdd039bd9ea2c942488f01051cda2` (post-HE5, signed ED25519)
- origin/main: `bcf53cb5b4cfdd039bd9ea2c942488f01051cda2` ✅ in-sync
- Branch: `main`
- Working tree (zangetsu): only `zangetsu/logs/engine.jsonl.1` (runtime log)

## 0-9Y mission status
**COMPLETE** — `0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM` closed at HE5 with verdict `COMPLETE_HE5_EDGE_EXHAUSTED`.

## HE5 evidence location
`zangetsu/docs/recovery/20260424-mod-7/0-9y-final-alpha-edge-restoration/17-he5-deployable-flow-recheck/` — 8 files (all phases including 07_final_report.md).

## Cost model files identified (Phase 1 input)
- `zangetsu/config/cost_model.py` (108 LOC) — `CostModel` class + `SymbolCost` dataclass + `DEFAULT_COST_TABLE` (14 symbols × 3 tiers)
- `zangetsu/engine/components/backtester.py` — backtester applies `cost_frac = cost_bps / 10000.0` per trade in `_vectorized_backtest`
- `zangetsu/services/arena_pipeline.py` lines 1001, 1064 — call sites: `cost_bps = cost_model.get(sym).total_round_trip_bps`
- `zangetsu/services/arena23_orchestrator.py` lines 722, 1022 — A2/A3 call sites
- `zangetsu/services/arena45_orchestrator.py` lines 432, 757 — A4/A5 call sites

## Arena thresholds (from arena23_orchestrator.py)
- `A2_MIN_TRADES = 25` (line 779) — locked, forbidden to modify
- A3 also enforces `bt_a3.total_trades >= 25` (line 1094)
- Validation thresholds in `engine/components/alpha_signal.py`: `entry_rank_threshold=0.80`, `exit_rank_threshold=0.50`, `min_hold=60`, `cooldown=60` (all locked)

## Current cost/gross result (from HE5)
- `cost / gross = 1.55` (median over 3266 batches × 3 horizons)
- `train_gross_pnl_median = +2.4 bps`
- `train_net_pnl_median = -1.22 bps`
- `train_total_trades_median = 980`
- `round_total_cost_bps = 14.5` (Diversified tier; range 11.5-23.0 across tiers)
- 0 / 3266 batches with net > 0
- Closest GP-discovered batch to break-even: -0.27 bps
- HE5 counterfactual: 0.5x cost → 99.57% positive; 0.7x → 25.78% positive (tipping point)

## DB pipeline counts
| Table | Count | Status |
|---|---:|---|
| `champion_pipeline` | 89 | ARENA2_REJECTED |
| `champion_pipeline_staging` | 184 | ARENA1_COMPLETE |
| `champion_pipeline_fresh` | 89 | ARENA2_REJECTED |
| `champion_pipeline_rejected` | 0 | (empty) |

## Worker baseline state
Sample worker (PID 3864124): no `ARENA_*` / `HORIZON` / `ACTIVE_*` / `ARENA_AGGREGATION_*` / `ARENA_TF3_SHADOW` env. Workers running on commit `bcf53cb5` post-HE4 cleanup.

## Operator fee tier (preliminary — to be verified in Phase 2)
- Binance API key present at `/home/j13/.env.global` (read-only scope per j13 memory)
- **Per master-order forbidden constraints**: NOT using key for live API calls during 0-9Z
- Phase 2 will use public Binance fee schedule + scenario bands (conservative / base / aggressive) for unknown account-tier resolution

## Order completion chain
| Order | HEAD | Verdict |
|---|---|---|
| OP1 | `82056123` | OP1_PRIMITIVES_REGISTERED |
| TF2 | `3decabd4` | IMPLEMENTED_SHADOW_PENDING |
| TF3 | `0cef908d` | PROFILE_CONFIRMED |
| TF4 | `986932df` | INTEGRATION_DEFINED |
| HE1 | `bbd6fb42` | PLUMBING_READY |
| HE2 | `48be8071` | HORIZON_AWARE_GENERATION |
| HE3 | `b83c710c` | ECONOMICS_MEASURED |
| HE4 | `37346fee` | NO_HORIZON_EDGE |
| HE5 | `bcf53cb5` | EDGE_EXHAUSTED |

## STOP-conditions check (Phase 0 spec equivalent)
| STOP cause | Status |
|---|---|
| Repo dirty with source changes | ❌ no — only runtime log |
| HEAD != origin/main | ❌ no |
| Latest verdict missing | ❌ no — HE5 evidence exists |
| Cost model files missing | ❌ no — `config/cost_model.py` present |

✅ **STATE_LOCK_PASS** — proceed to Phase 1.

## 0-9Z evidence directory created
`/home/j13/j13-ops/docs/recovery/20260429-0-9z-structural-cost-feasibility/` — note this is at **repo root** under `docs/`, not under `zangetsu/docs/`, per master-order spec ("docs/recovery/20260429-0-9z-structural-cost-feasibility/").
