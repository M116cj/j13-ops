# 00 — Phase 8 Checkpoint Inputs

**Master Order:** 0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM
**Sub-order:** TEAM ORDER 0-9Y-CHECKPOINT-HORIZON-VS-FEATURE-EXPANSION
**Phase:** 8
**Date (UTC):** 2026-04-28T~04:00Z
**Author:** Claude Lead

## Inputs from prior phases

| Phase | Sub-order | Verdict | Key data |
|---|---|---|---|
| 0 | FINAL-0 | `COMPLETE_MASTER_BASELINE_LOCKED` | HEAD `e8b988b` baseline locked |
| 1 | D | `DECISION_PATH_A_PLUS_C_HORIZON_AND_TRADE_FREQUENCY` | Horizon (A) + trade-frequency (C) chosen as primary axes |
| 2 | HE0 | `COMPLETE_HORIZON_TARGET_DESIGN_READY` | Active horizons 180/240/360; composite candidate_id design specified |
| 6 | TF1 | `DIAGNOSED_LOWER_FREQUENCY_COULD_IMPROVE_EDGE` | Q1-Q4 net delta +1.04 bps; AUC 0.835; top-decile 9.5× sparser → WR 0.45 vs 0.32 → net 49× better |
| 7 | FS1 | `FEATURE_SPACE_TOO_REDUNDANT_NEEDS_OPERATOR_EXPANSION` | 9 unregistered primitives in `alpha_primitives.py`; structural cross-asset / regime / microstructure gaps |

## Critical findings raised at this checkpoint

### 1. From TF1 — sparse beats dense

The 60-bar baseline already shows that fewer-but-stronger trades produce dramatically better net economics. Top-decile-by-sharpe is the top-decile-by-net (same 10 batches), not a metric-selection artifact. The mechanism is direct: cost scales linearly with trade count (Pearson +0.83); per-trade gross decays with frequency (Pearson −0.37); aggressive over-trading erodes net.

**Implication**: the trade-frequency axis is real and addressable WITHOUT touching A2_MIN_TRADES, validation, or cost. A signal-aggregation prototype is feasible.

### 2. From FS1 — grammar is operator-poor

The current GP grammar registers 35 operators but the codebase ships 9 fully-implemented primitives that the GP cannot reach (`ts_sum`, `ts_mean`, `ts_std`, `ts_argmax`, `ts_argmin`, `covariance`, `rolling_scale`, `log_x`, `exp_x`). Additionally, `indicator.py` declares ~130 cross_asset / volume_micro / multi_timeframe / statistical features not wired to the GP pset.

**Implication**: testing horizons 180/240/360 under the current operator-poor grammar would yield results that conflate "horizon X is best" with "horizon X is where depth-6 compositions happen to approximate the missing primitives". The horizon results would be contaminated by grammar limitations.

## Three checkpoint options

### Option A — OP1 → TF2 → HE1...HE5 (recommended)

Pre-pend grammar expansion (`TEAM ORDER 0-9Y-OP1-PRIMITIVE-REGISTRATION`) AND signal-aggregation prototype (`TEAM ORDER 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE`) BEFORE horizon plumbing/generation/telemetry/shadow.

| Pro | Con |
|---|---|
| Addresses both bottleneck axes (grammar + frequency) before measuring horizon impact | Slightly longer total timeline (~1-2 extra days) |
| HE5 horizon outcome table reflects horizon economics, not grammar limitations | Two extra orders to manage |
| TF1+FS1 evidence directly motivates both pre-pended orders | Higher coordination cost |

### Option B — OP1 → HE1...HE5 (TF2 deferred)

Pre-pend only grammar expansion; defer signal aggregation until HE5 results are known.

| Pro | Con |
|---|---|
| Cleaner horizon test (only one new variable: grammar) | Misses the strong TF1 signal that frequency is a primary driver |
| TF2 can be informed by HE5 horizon results | Horizon results may still show "every horizon cost-dominated" if frequency wasn't addressed |

### Option C — HE1...HE5 directly (no pre-pending)

Original master plan, no modifications.

| Pro | Con |
|---|---|
| Fastest path to HE5 verdict | High contamination risk per FS1 finding |
| Matches the already-merged HE0 design spec | TF1's strong frequency signal ignored — likely yields HE5 conclusion that all horizons are cost-dominated regardless |
| | Risks invalidating HE5 results for the wrong reason |

## j13's checkpoint decision

(Captured in `02_decision.md`; one-line summary: **OPTION A**)
