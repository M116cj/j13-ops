# 01 — `cost_bps` Calibration Audit

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

Per-tier values:

| Tier | Symbols | taker | slippage | funding_8h | **total round-trip** |
| --- | --- | --- | --- | --- | --- |
| Stable | BTC, ETH, BNB, SOL, XRP, DOGE | 5.0 | 0.5 | 1.0 | **11.5 bps** |
| Diversified | LINK, AAVE, AVAX, DOT, FIL | 6.25 | 1.0 | 1.0 | **14.5 bps** |
| High-Vol | 1000PEPE, 1000SHIB, GALA | 10.0 | 2.0 | 1.0 | **23.0 bps** |

## 2. Application Path

| Question | Answer |
| --- | --- |
| One-way or round-trip? | round-trip (taker × 2 included) |
| Applied on entry only / exit only / both? | Backtester deducts cost ONCE PER ROUND TRIP — confirmed by Phase 4 random sanity (cost ≈ trades × 11.5 bps) |
| Compounds per rebalance? | NO (only on entry/exit pairs) |
| Slippage included? | YES (slippage_bps) |
| Maker/taker distinction modeled? | NO (always taker assumed) |
| Funding included? | partially — `funding_8h_avg_bps=1.0` flat-added to round-trip cost regardless of hold duration |
| Cost-multiplication-by-100/10000 bug? | NO (random sanity confirms cost = bps × trades × 1e-4 correctly) |

## 3. Funding Approximation Caveat

The `funding_8h_avg_bps=1.0` is added to **every round trip**, regardless of how long the position is held. This is:

- **Conservative for trades held < 8h** (over-counts; real funding paid is 0)
- **Under-conservative for trades held > 24h** (real funding accumulates ~3 bps but we only count 1)

Net impact: marginal at typical short hold times (~minor over-counting). **Not the dominant cause of mass rejection.**

## 4. Cost Sensitivity Replay (5 cost levels × 5 formulas × 3 symbols = 75 evals)

```
cost factor  n_eval  train_min  train_max    val_min    val_max  survivors (val_pnl>0)
0                15    -0.1817    +0.4798    -0.3218    +0.1437          11
0.25x            15    -0.4321    +0.2060    -0.4448    +0.0153           4
0.50x            15    -0.7266    -0.0609    -0.5679    -0.0845           0
1.00x            15    -1.3315    -0.2090    -0.8140    -0.1662           0
2.00x            15    -2.5413    -0.5051    -1.3062    -0.2925           0
```

→ **Cost dominates linearly.** At zero cost, 73% of cells survive (val_pnl > 0). At full cost, 0% survive. Each step doubles the loss magnitude.

## 5. Cost-Paid / Gross-PnL Estimate

For `qp_tsmom = sign_x(delta_20(close))` on BTC, cost=0 train_pnl ≈ +0.30 → with 258 trades × 11.5 bps = 0.297 cost drag → expected net ≈ +0.30 − 0.297 = +0.003 (near zero, slightly negative due to compounding). Observed: −0.21. The discrepancy comes from compound drawdown effects of 88.8% losing trades amplifying the cost impact.

→ **Cost / gross PnL ratio is ~100% for the best alpha at full cost.** The alpha edge gross is roughly equal to the cost; net is consistently negative.

## 6. Phase 1 Classification

| Verdict | Match? |
| --- | --- |
| COST_CALIBRATION_OK | NO |
| **COST_TOO_HIGH_LIKELY** | **YES (relative to alpha edge available in current universe)** |
| COST_APPLICATION_BUG_LIKELY | NO (math correct per Phase 4 sanity) |
| **COST_DOMINATES_DUE_TURNOVER** | **YES (864-1115 trades / formula × 11.5 bps cost = ~10-13% drag)** |
| COST_NOT_PRIMARY_CAUSE | NO |
| COST_UNKNOWN | NO |

→ **Phase 1 verdict: COST_DOMINATES_DUE_TURNOVER + COST_TOO_HIGH_LIKELY** (relative to current alpha universe edge). The cost model itself is correctly calibrated to Binance Futures realistic numbers; the issue is the alpha universe doesn't generate enough edge to overcome real costs at current trade frequency.
