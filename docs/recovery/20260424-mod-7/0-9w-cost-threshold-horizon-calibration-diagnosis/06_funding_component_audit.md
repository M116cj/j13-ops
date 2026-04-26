# 06 — Funding Component Audit

## 1. Source Definition

`zangetsu/config/cost_model.py`:

```python
@dataclass(frozen=True)
class SymbolCost:
    taker_bps: float           # taker fee in basis points
    maker_bps: float           # maker fee (rebate if negative)
    funding_8h_avg_bps: float  # average 8-hour funding rate
    slippage_bps: float        # estimated market-order slippage

    @property
    def total_round_trip_bps(self) -> float:
        return (self.taker_bps * 2) + self.slippage_bps + self.funding_8h_avg_bps
```

For the Stable tier (BTC, ETH, SOL, etc.):
- `taker_bps = 5.0`
- `slippage_bps = 0.5`
- `funding_8h_avg_bps = 1.0`
- → `total_round_trip_bps = 11.5`

## 2. Application Semantics

The backtester deducts `total_round_trip_bps` once per closed trade (entry+exit pair). This is verified by Phase 4 sanity:

```
random_seeded BTCUSDT train: 46642 trades × 11.5 bps × 1e-4 = 5.36 (cost-only PnL drag)
observed net_pnl = -54.0 ≈ 5.36 × compounding factor
```

The `funding_8h_avg_bps = 1.0` component is **flat-added to every round trip**, regardless of how long the position is held.

## 3. Funding Realism Check

Realistic funding model on Binance Futures:
- Funding interval: 8 hours
- Average funding rate (BTC/ETH 2024-2026): ~0.005-0.015% per 8h period (≈ 0.5-1.5 bps per 8h)
- Real funding paid = (funding_rate × hold_duration_in_8h_periods) × side

Current model approximation:

| Hold duration | Real funding paid (bps, mean) | Modeled funding (bps) | Bias |
| --- | --- | --- | --- |
| 1 hour | 1/8 × 1.0 = 0.125 | 1.0 | **over-counts** by ~0.875 bps |
| 1 bar (1 min) | 1/480 × 1.0 = 0.002 | 1.0 | **over-counts** by ~1.0 bps |
| 4 hours | 0.5 | 1.0 | over-counts by 0.5 bps |
| 8 hours | 1.0 | 1.0 | matches |
| 24 hours | 3.0 | 1.0 | **under-counts** by 2.0 bps |
| 7 days | 21.0 | 1.0 | under-counts by 20.0 bps |

## 4. Net Impact at Current Operating Regime

j01 strategy stats (from current run):
- median trade hold = ~10-20 bars (10-20 min, well below 8 hours)
- 95th percentile hold ≤ 120 bars (2 hours)

→ Real funding paid per round trip ≈ 0.025-0.25 bps. Model adds 1.0 bps per round trip. **Over-counts by ~0.75 bps per round trip on average.**

For a typical formula: 864 trades × 0.75 bps = 0.065 PnL drag from funding over-counting alone.

## 5. Removing Funding Over-Count: Would It Save the Day?

If we remove the `funding_8h_avg_bps` component entirely (set to 0), Stable tier round-trip becomes 10.5 bps (saves ~9% of cost). Re-applying to Phase 1 cost sensitivity table:

| Cost factor | Current (with 1 bps funding) | Without funding (effective 0.91x) |
| --- | --- | --- |
| 1.00x | 0 survivors | ~0 survivors (extrapolated; well below the 0.5x threshold where survivors emerge) |

→ Removing funding entirely is approximately a 0.91x cost factor — between 1.0x (0 survivors) and 0.5x (0 survivors). **Removing funding alone does not produce survivors.**

## 6. Phase 6 Classification

| Verdict | Match? |
| --- | --- |
| FUNDING_OK | NO (the flat-per-trip approximation is not exact; over-counts at typical hold times) |
| **FUNDING_MINOR_OVER_COUNT** | **YES — over-counts by ~0.75 bps per RT at j01's typical hold time** |
| FUNDING_MAJOR_BUG | NO (magnitude is small relative to cost wall) |
| FUNDING_NOT_PRIMARY_CAUSE | YES (removing funding component entirely does not produce survivors) |
| FUNDING_UNKNOWN | NO |

→ **Phase 6 verdict: FUNDING_MINOR_OVER_COUNT, FUNDING_NOT_PRIMARY_CAUSE.** The funding term is technically over-counted at current hold durations but the magnitude is small enough that removing it does not flip any reject-to-survivor outcome at the val_neg_pnl gate.

**Recommendation (information only, no runtime change in this order)**: model funding as `(hold_bars / 480) × funding_8h_avg_bps` instead of flat-per-trip. This is a separate design refinement and would be tracked under a future calibration order.
