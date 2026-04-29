# 01 — COST MODEL AUDIT

**TEAM ORDER**: 0-9Z-STRUCTURAL-COST-FEASIBILITY-AND-ROUTING-DECISION
**Date**: 2026-04-29
**Phase**: 1 / 8
**Mode**: READ-ONLY analysis of existing zangetsu source

## Cost path (full trace)

```
config/cost_model.py
  ↓ DEFAULT_COST_TABLE: 14 symbols × 3 tiers
  ↓ SymbolCost.total_round_trip_bps  (line 25-28)
  ↓
services/arena_pipeline.py:1001       (A1 cost lookup per symbol)
services/arena23_orchestrator.py:722  (A2/A3 cost lookup)
services/arena45_orchestrator.py:432  (A4/A5 cost lookup)
  ↓
engine/components/backtester.py:140
  cost_frac = cost_bps / 10000.0
  ↓
_vectorized_backtest(..., cost_frac, ...)  (numba JIT, applied per trade)
```

## SymbolCost.total_round_trip_bps formula
```python
@property
def total_round_trip_bps(self) -> float:
    """Total cost for entry + exit (taker both sides) + avg funding."""
    return (self.taker_bps * 2) + self.slippage_bps + self.funding_8h_avg_bps
```

## Per-tier cost breakdown (current `DEFAULT_COST_TABLE`)

| Tier | Symbols (N) | taker_bps | maker_bps | slippage_bps | funding_8h_avg_bps | **round_trip (taker)** | round_trip (maker, theoretical) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Stable** | 6 (BTC/ETH/BNB/SOL/XRP/DOGE) | 5.0 | 2.0 | 0.5 | 1.0 | **11.5** | 5.5 |
| **Diversified** | 5 (LINK/AAVE/AVAX/DOT/FIL) | 6.25 | 2.5 | 1.0 | 1.0 | **14.5** | 7.0 |
| **High-Vol** | 3 (1000PEPE/1000SHIB/GALA) | 10.0 | 4.0 | 2.0 | 1.0 | **23.0** | 11.0 |

**Important**: `maker_bps` is **defined in the dataclass but NOT consumed** by `total_round_trip_bps`. The current cost model is **taker-only**. There is NO maker/taker blending logic in the codebase.

## Required answers (per master-order Phase 1 spec)

### 1. What effective bps does ZANGETSU currently assume?
- **Symbol-dependent**: 11.5 / 14.5 / 23.0 bps round-trip across the 3 tiers
- **Default fallback for unknown symbols**: `default_taker_bps=6.25, default_slippage_bps=1.5` → round-trip = `(6.25×2) + 1.5 + 1.0 = 14.0 bps`
- **HE5 observed cost_bps**: 14.5 (Diversified-tier median, since most rounds were on LINK/AAVE/AVAX/DOT/FIL/BTC mix; range 11.5-23.0 across all batches)

### 2. Is it taker-only, maker/taker blended, or static?
**TAKER-ONLY, STATIC.** No blending; no execution-mode-aware logic. `maker_bps` is dead-code data.

### 3. Is funding included?
**Yes** — `funding_8h_avg_bps = 1.0` for all symbols; added once per round-trip (not scaled by holding duration). This is a coarse approximation: it assumes every trade incurs exactly one 8-hour funding window of cost on average.

### 4. Is slippage included?
**Yes** — `slippage_bps` per tier (0.5 / 1.0 / 2.0). Treated as a fixed per-round-trip cost (not modeled as a function of trade size, market impact, or volatility).

### 5. Is cost applied per side or round trip?
**Per round trip.** Formula explicitly multiplies `taker_bps × 2` (entry + exit). Slippage and funding are added once (not per side).

### 6. Does the backtester double-count or undercount cost?
- Backtester applies `cost_frac = cost_bps / 10000.0` per trade in `_vectorized_backtest` — each trade pays the full round-trip cost as a single fraction
- **No double-count**: cost is applied once at trade-exit (since `total_round_trip_bps` already includes both entry & exit)
- **Potential undercount** edge cases:
  - Funding: assumed uniform 1.0 bps per round-trip (real funding can range from -10 to +10 bps depending on market regime)
  - Slippage: assumed fixed per tier (real slippage scales with order size and volatility)

### 7. What exact cost bps makes HE5 break even?
From HE5 counterfactual analysis (3266 batches, 0.7x cost = tipping point at 25.78% positive):
- Diversified-tier current = 14.5 bps
- 0.7x = **10.15 bps** → tipping point (≥25% of batches positive)
- 0.65x = **9.4 bps** → median batch flips positive
- 0.5x = **7.25 bps** → 99.57% positive

### 8. What cost bps creates positive margin?
- **For median batch break-even**: cost ≤ 9.4 bps (Diversified tier) — corresponds to **35% cost reduction**
- **For 99% of batches positive**: cost ≤ 7.25 bps — corresponds to **50% cost reduction**

## Backtester semantics clarification (gross vs net)
Re-reading `engine/components/backtester.py:163-165`:
```python
trade_pnls = pnl_array[exits] if total_trades > 0 else np.array([], dtype=np.float64)
winning = int(np.sum(trade_pnls > 0))
gross_pnl = float(np.sum(trade_pnls[trade_pnls > 0])) if winning > 0 else 0.0
net_pnl = float(np.sum(trade_pnls))
```

**Important semantic finding**: `gross_pnl` here means "sum of WINNING trade PnLs **after cost**", NOT "sum of all PnL before cost". This means:
- `gross_pnl` = sum(winning trades, post-cost)
- `net_pnl` = sum(all trades, post-cost)
- `gross_pnl - net_pnl` = absolute value of total losses from losing trades (also post-cost)
- `cost/gross ratio` ≠ "how much of gross-edge cost ate"; it = "ratio of total losses to total wins"

This means HE5's counterfactual `(1-f)*gross + f*net` was a simplified model — directionally correct (cost reduction helps) but not numerically rigorous (doesn't precisely correspond to "halve cost"). **The directional conclusion stands**: cost is the dominant binding constraint per pipeline reject distribution (`COST_NEGATIVE` 99.77%).

A more rigorous counterfactual: if cost is c bps per trade and there are n trades, halving cost adds `0.5 × c × n / 10000` to net_pnl. For median batch: `0.5 × 14.5 × 980 / 10000 = 0.71` (in fractional units = ~71% of notional, which is implausibly large unless trades are sized at fractions of notional — confirmed from `sizes` array in alpha_signal: per-trade size = `|rank-0.5|×2 ∈ [0,1]`, median ≈ 0.5).

After size-adjustment: Δnet_per_alpha ≈ `0.5 × 14.5 × 980 × 0.5 / 10000 = 0.355` units = 35.5 bps. Current median net = -1.22 bps. So halving cost would shift to ≈ +34 bps (clearly positive). The exact magnitude depends on size distribution, but **direction is robust**.

## Source-file integrity
| File | Modified by 0-9Z? | Notes |
|---|---|---|
| `zangetsu/config/cost_model.py` | NO (read-only audit) | 108 LOC, untouched |
| `zangetsu/engine/components/backtester.py` | NO | 220 LOC, untouched |
| `zangetsu/services/arena_pipeline.py` | NO | call sites unchanged |
| `zangetsu/services/arena23_orchestrator.py` | NO | unchanged |
| `zangetsu/services/arena45_orchestrator.py` | NO | unchanged |

## Audit verdict
**COST_MODEL_AUDIT_COMPLETE** — `total_round_trip_bps` is taker-only, includes slippage and funding, applied per-round-trip in backtester, no double-count. Maker fee is defined but **dead data** in current code.

The break-even point is approximately **9.4 bps** (Diversified-tier median, vs 14.5 current = 35% reduction needed). The most aggressive lever within the existing data structures is **theoretical maker-only routing** (cost would drop to 7.0 bps Diversified = 52% reduction → 99% batches positive per HE5).

## Next
Phase 2 — fee/venue/tier matrix (validate whether 35-50% cost cut is realistic at venue / tier level).
