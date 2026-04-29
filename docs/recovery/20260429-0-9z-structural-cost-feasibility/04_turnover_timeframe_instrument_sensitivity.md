# 04 — TURNOVER / TIMEFRAME / INSTRUMENT SENSITIVITY

**TEAM ORDER**: 0-9Z-STRUCTURAL-COST-FEASIBILITY-AND-ROUTING-DECISION
**Date**: 2026-04-29
**Phase**: 4 / 8

## Question
Is the cost wall mostly turnover-driven? Can shifting timeframe / restricting instrument universe reduce cost/gross without weakening A2_MIN_TRADES=25?

## Current zangetsu turnover characteristics

From HE5 analysis (3266 batches × 3 horizons):
- `train_total_trades_median = 980 trades / batch / alpha` (across ~70-bar evaluation window inferred from 1m bars)
- `signal_density_per_bar = 0.007` (0.7% of bars trigger a signal per alpha)
- `min_hold = 60` bars, `cooldown = 60` bars (per alpha_signal.py)
- 1m timeframe (Binance perpetual, 1-minute bars; ~525,600 bars/year)

This is a **mid-frequency** strategy: ~980 trades over a typical 140,000-bar train window = ~0.7% turnover per bar (matches signal_density). Average hold ≈ 60 bars = 1 hour.

## Lever 1 — Timeframe shift (15m / 30m / 1h / 4h)

### Mechanism
Higher timeframe reduces bar count proportionally:
- 1m → 525,600 bars/year (current)
- 15m → 35,040 bars/year (15× less)
- 30m → 17,520 bars/year (30× less)
- 1h → 8,760 bars/year (60× less)
- 4h → 2,190 bars/year (240× less)

If signal density and hold parameters scale proportionally (e.g., min_hold = 4 bars on 15m = same 1-hour hold), trade count scales:
- 1m: ~980 trades / batch
- 15m: ~65 trades / batch
- 30m: ~33 trades / batch
- 1h: ~16 trades / batch
- 4h: ~4 trades / batch

### A2_MIN_TRADES interaction
- 1h timeframe: ~16 trades < 25 → **fails A2_MIN_TRADES=25**
- 4h timeframe: ~4 trades — way below A2 floor
- 30m timeframe: ~33 trades — barely above A2 floor (margin = 8 trades)
- 15m timeframe: ~65 trades — comfortable margin

### Cost-vs-gross expectation (per timeframe)
The **per-trade gross-edge** typically scales with **square root of holding time** (random walk assumption). So:
- 1m → 1h is 60× longer hold → gross/trade × √60 ≈ 7.7×
- Per-trade gross ≈ 0.00244 bps (current 1m) × 7.7 = **0.0188 bps per trade on 1h**
- Per-trade cost is unchanged (~14.5 bps round-trip) → cost/gross per trade ≈ 14.5 / 0.0188 = 770 (much WORSE per trade)

**But total trades drop too**: 16 trades × 14.5 bps cost = 232 bps total cost. Much smaller absolute cost burden.

### Approximate per-batch outcome (1h timeframe)
- gross_per_batch ≈ 16 trades × 0.0188 bps = 0.30 bps/alpha
- cost_per_batch = 16 × 14.5 / 980-equivalent... (no — cost is per trade so just 16 × 14.5 / scale-factor)

Actually let me recompute properly:
- Per-trade gross at 1h: ≈ 0.0188 bps (after sqrt-time scaling)
- Per-trade net (with cost): 0.0188 - 14.5 = **-14.5 bps per trade** (much worse!)

This is because per-trade cost (14.5 bps) is **fixed per round-trip regardless of timeframe**, while per-trade gross only grows by sqrt(time). The gross-cost imbalance gets WORSE as timeframe increases for fixed cost model.

| Timeframe | trades | per-trade gross | per-trade net | A2 OK? | Verdict |
|---|---:|---:|---:|---|---|
| 1m (current) | 980 | +0.00244 | -0.00125 | ✅ | net -1.22 / batch |
| 15m | ~65 | +0.0094 | -14.5 | ✅ | net much worse |
| 30m | ~33 | +0.0134 | -14.5 | ✅ | net worse |
| 1h | ~16 | +0.0188 | -14.5 | ❌ fails A2 | net much worse |

**Higher timeframe makes the per-trade economics WORSE, not better**, because cost (fixed per round-trip) grows in proportion to the bar duration only if positions are held for more bars — but if trades are mostly fee-driven (not edge-driven), longer hold doesn't help. zangetsu's gross is ~2.4 bps total, cost ~14.5 bps per round-trip — even ONE trade per batch loses 12 bps net. The 1m frequency of ~980 trades dilutes per-trade cost across many opportunities; higher timeframes concentrate the loss into fewer trades.

**Verdict**: Higher timeframes HURT zangetsu's economics in current form. Not a viable lever.

## Lever 2 — Instrument universe filtering (high-liquidity-only)

### Current universe (14 symbols across 3 tiers)
| Tier | Symbols | Cost per round-trip |
|---|---|---:|
| Stable | BTC/ETH/BNB/SOL/XRP/DOGE | 11.5 bps |
| Diversified | LINK/AAVE/AVAX/DOT/FIL | 14.5 bps |
| High-Vol | 1000PEPE/1000SHIB/GALA | 23.0 bps |

### Lever
Restrict to Stable tier only (BTC/ETH/BNB/SOL/XRP/DOGE):
- Cost cut: 14.5 → 11.5 average → **−21% effective cost**
- New net at +2.4 gross: -1.2 → -0.5 bps → still negative but closer

### A2 interaction
A2_MIN_TRADES is per-alpha-per-symbol, not aggregate. Restricting universe doesn't affect per-symbol trade count.

### Risk
- Reduces alpha-discovery diversification (fewer symbols → potentially overfit)
- HE4 confirmed all 3 horizons identical economics across all symbols → instrument selection alone unlikely to flip net positive
- Sample-size benefit: more concentrated trades may reduce variance of per-batch metrics

### Verdict
Instrument restriction reduces cost by ~21% — not enough alone (need ~35%) but **could combine with maker-only** to reach the threshold:
- Stable + maker-only theoretical: round_trip = 5.5 bps → −52% cost cut → 99% positive batches
- Stable + maker-only + 60% adverse selection: round_trip = 5.5 + 3.6 = 9.1 bps → break-even

This is the **same conclusion as Phase 3** for maker-only on Stable tier.

## Lever 3 — Trade-frequency reduction within current timeframe

### Mechanism (TF3-style)
Apply STRENGTH_FILTER (q=0.95-0.98) on top of current alpha generation:
- Trades drop from 980 → ~50-100 per batch
- TF3 LIVE confirmed: cost/gross 1.55 → 1.30 (-13%), net per batch -1.22 → -0.06
- Net per batch stays slightly negative

### Required for break-even
- Need cost/gross < 1.0 (gross > cost)
- TF3's tightest filter delivered cost/gross = 1.30 — not enough
- Even more aggressive (q=0.99 = top 1%) extrapolates to cost/gross ≈ 1.10 — STILL > 1.0

### Verdict
Trade-frequency reduction (without cost-side change) cannot flip net positive in zangetsu's current architecture. Confirmed by TF3 live data.

## Lever 4 — Combined: instrument + maker-only

### Theoretical best case
- Restrict to Stable tier (BTC/ETH/BNB/SOL/XRP/DOGE)
- Maker-only routing
- Optimistic adverse selection (30%)

Calculation:
- Stable maker-only base: 5.5 bps round-trip
- Adverse selection penalty (30% of saving): 30% × (11.5-5.5) = 30% × 6.0 = 1.8 bps
- Effective round-trip: 5.5 + 1.8 = **7.3 bps**
- HE5 break-even: 9.4 bps
- **Margin: +2.1 bps (median batch positive)**

### Conservative combined case
- Stable maker-only + 60% adverse selection
- Effective round-trip: 5.5 + (60% × 6.0) = 5.5 + 3.6 = **9.1 bps**
- Margin: +0.3 bps (barely positive median, ~50% of batches)

### Pessimistic combined case
- Stable maker-only + 70% adverse selection (Ait-Sahalia/Brunetti crypto)
- Effective: 5.5 + 4.2 = **9.7 bps**
- Margin: -0.3 bps (still negative median)

## Sensitivity table

| Variant | Gross bps | Cost bps | Cost/gross | Trade count | A2 risk | Verdict |
|---|---:|---:|---:|---:|---|---|
| 1m all 14 symbols + taker (current) | +2.4 | 14.5 | 1.55 | ~980 | OK | net -1.22 |
| 1m Stable-only + taker | +2.4 | 11.5 | 1.20 | ~980 (per sym) | OK | net -0.5 |
| 1m all + maker-only (theor.) | +2.4 | 5.5-7.0 | 0.42-0.58 | ~980 (×60% fill = ~588) | OK | net positive theoretical |
| 1m Stable + maker-only + 60% AS | +2.4 | 9.1 | 0.95 | ~588 (per sym) | OK | net barely positive |
| 1m + TF3 q=0.95 | +2.4 (slightly higher per trade) | 14.5 | 1.30 | ~50 | OK | net -0.06 (TF3 confirmed) |
| 15m + taker | +9.4 (sqrt-scaling) | 14.5 | 1.5 | ~65 | OK (margin 40) | net much worse per trade |
| 1h + taker | +18.8 | 14.5 | 0.77 | ~16 | ❌ fails A2 | A2 reject |

## Important rule (per master-order Phase 4 spec)
> Do not propose weakening A2_MIN_TRADES.

**No proposal here weakens A2_MIN_TRADES=25.** All cost-saving levers are evaluated against the existing floor. Higher timeframes (1h, 4h) explicitly fail A2 and are rejected.

## Verdict
**TURNOVER/TIMEFRAME/INSTRUMENT SENSITIVITY = LIMITED LEVERAGE WITHOUT MAKER-ONLY**

Findings:
- **Higher timeframe**: HURTS net (cost is fixed per round-trip, edge grows only sqrt-time)
- **Instrument restriction (Stable only)**: -21% cost — meaningful but insufficient alone
- **Trade-frequency reduction (TF3-style)**: -13% cost/gross — confirmed live to be insufficient
- **Combined Stable + maker-only**: theoretical break-even depending on adverse-selection magnitude (range: +2.1 / +0.3 / -0.3 bps margin)

The only combination that **could** work is Stable-tier + maker-only routing, but its actual viability depends on adverse-selection magnitude — currently unmeasured and unmeasurable without building maker execution code.

## Next
Phase 5 — final Path A decision matrix.
