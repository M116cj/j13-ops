# 02 — Economic Realism Review

Goal: determine whether `cost = 0.5x` (= 5.75 bps round-trip for the Stable tier) is economically defensible relative to actual Binance Futures executions.

## 1. Current Cost Model Definition

`zangetsu/config/cost_model.py:DEFAULT_COST_TABLE`:

| Tier | Symbols | maker_bps | taker_bps | slippage_bps | funding_8h_avg_bps | total_round_trip_bps |
| --- | --- | --- | --- | --- | --- | --- |
| Stable | BTC, ETH, BNB, SOL, XRP, DOGE | 2.0 | **5.0** | 0.5 | 1.0 | **11.5** |
| Diversified | LINK, AAVE, AVAX, DOT, FIL | 2.5 | 6.25 | 1.0 | 1.0 | 14.5 |
| High-Vol | 1000PEPE, 1000SHIB, GALA | 4.0 | 10.0 | 2.0 | 1.0 | 23.0 |

```python
total_round_trip_bps = (taker_bps * 2) + slippage_bps + funding_8h_avg_bps
```

## 2. Assumptions Decomposed (Stable tier @ 11.5 bps)

| Component | Per round trip | Notes |
| --- | --- | --- |
| taker × 2 | 10.0 bps | assumes 100% taker, 0% maker on BOTH legs |
| slippage | 0.5 bps | flat constant, not size-dependent |
| funding | 1.0 bps | flat-added regardless of hold duration |
| **TOTAL** | **11.5 bps** | round-trip |

## 3. Real-World Binance USDT-M Futures Fee Schedule (2024-2026)

| Account tier | Maker | Taker | Source |
| --- | --- | --- | --- |
| VIP 0 (default retail) | 2.0 bps | **5.0 bps** | binance.com/en/fee/futureFee |
| VIP 0 + BNB discount (10%) | 1.8 bps | 4.5 bps | same |
| VIP 1 (≥$15M 30-day vol) | 1.6 bps | 4.0 bps | same |
| VIP 2 (≥$50M 30-day vol) | 1.4 bps | 3.5 bps | same |
| Maker rebate (negative maker fee, VIP 4+) | -0.4 bps | 2.6 bps | applies above $1B 30-day vol |

**Current model uses VIP 0 taker = 5.0 bps**, which is the conservative correct number for a small retail account with no BNB discount. Realistic for the project's current scale.

## 4. Execution Mode Sensitivity

A 100% taker assumption is **the worst case**. Real-world execution mix:

| Execution mode | Round-trip cost (Stable, BNB discount off) |
| --- | --- |
| 100% taker / 100% taker (current model) | 5×2 + 0.5 + 1 = **11.5 bps** |
| 100% taker / 100% maker (entry market, exit limit) | 5+2 + 0.5 + 1 = **8.5 bps** |
| 100% maker / 100% maker | 2×2 + 0.5 + 1 = **5.5 bps** ≈ **0.5x of current** |
| 100% maker + BNB discount + slippage 0 | 1.8×2 + 0 + 1 = **4.6 bps** |

→ **The 5.75 bps target (cost=0.5x) is approximately the cost of 100% maker execution with no slippage**, which IS feasible on Binance Futures **but only if**:
- the strategy can post limit orders that consistently fill (not market urgency-based)
- slippage is genuinely zero or near-zero (small order sizes vs deep order books)

## 5. Whether Current 1.0x Cost Is Conservative

| Argument | Assessment |
| --- | --- |
| Taker 5.0 bps assumes VIP 0 — at current account size, this is the correct retail tier | NEUTRAL |
| Slippage 0.5 bps for Stable symbols is **probably under-conservative** for orders > $50k notional but accurate for small orders | NEUTRAL |
| Funding 1.0 bps flat is **over-conservative for short-hold trades** (median hold ~10-20 bars; real funding ~0.025-0.25 bps) | OVER-CONSERVATIVE by ~0.75 bps |
| 100% taker assumption is **worst-case** | OVER-CONSERVATIVE if any maker fills happen |
| Maker/taker fee distinction not modeled | MISSING capability — the model cannot represent maker-favoured executions |

**Net assessment**: the current 11.5 bps cost is **realistic worst-case** (full taker, retail tier, flat funding over-count, conservative slippage). It is NOT overly punitive — it is the correct ceiling for a small retail account that cannot reliably post passive limit orders.

The **5.75 bps target represents an aggressive maker-heavy execution profile** that the current zangetsu pipeline does NOT yet implement (no maker order routing, no resting limit logic, no post-only flag).

## 6. Cost Paid / Gross Edge Ratio

For the best surviving cell at cost=0.5x (`wqb_s01 SOL ET=0.70 MH=360`):

| Metric | Value |
| --- | --- |
| val_pnl (net at cost=0.5x) | +0.1275 |
| val_trades | 340 |
| Modeled cost paid | 340 × 5.75 bps × 1e-4 ≈ 0.196 |
| Implied gross PnL | val_pnl + cost = +0.1275 + 0.196 ≈ **+0.323** |
| Cost / gross ratio | 0.196 / 0.323 = **60.7%** |

→ Even at the BEST cost=0.5x survivor, **60% of the gross edge is consumed by cost.** A 50% increase in cost (back to 1.0x) wipes the entire edge.

This is **economically marginal** — the strategy lives in a thin window where any execution slippage, fee tier change, or funding rate shift could flip net PnL negative.

## 7. Slippage Realism Check

Stable tier slippage_bps=0.5 — is this realistic?

| Order size (USD notional) | BTCUSDT typical slippage on Binance Futures | Realistic? |
| --- | --- | --- |
| $1k | <0.1 bps | model overshoots |
| $10k | ~0.2 bps | reasonable |
| $50k | ~0.5 bps | **matches model** |
| $200k | ~1.0-1.5 bps | model under-shoots |
| $1M+ | ~3-5 bps | model significantly under-shoots |

→ For trade sizes ≤ $50k notional, the 0.5 bps slippage is realistic. For larger sizes, the current model UNDER-counts slippage. Not a contradiction with calibration claim — the matrix evals are dimensionless trade-pair PnL units, not size-weighted.

## 8. Funding Realism Check

Funding model: 1.0 bps flat per round trip.

Real funding paid on a typical j01 trade:
- Median hold: ~10-20 bars (= 10-20 min)
- Real funding paid = (hold/480) × funding_rate ≈ (15/480) × 1.0 = 0.031 bps
- Model adds 1.0 bps
- → **Model OVER-counts funding by ~0.97 bps per RT** at typical hold

This is significant. Removing funding alone reduces RT cost from 11.5 → 10.5 (≈0.91x). Still not enough to cross the survivor threshold (cost=0.5x is 5.75 bps).

## 9. Classifications

| Classification | Match? |
| --- | --- |
| COST_0_5X_REALISTIC | **partial** — IF execution shifts to 100% maker AND slippage stays ≤ 0.5 bps |
| **COST_0_5X_OPTIMISTIC_BUT_PLAUSIBLE** | **YES** — achievable under maker-heavy execution; not at current pipeline state |
| COST_0_5X_UNREALISTIC | NO — empirically achievable on Binance Futures |
| CURRENT_COST_TOO_CONSERVATIVE | partial — over-counts funding by ~0.75 bps; otherwise realistic for taker-heavy execution |
| **COST_MODEL_NEEDS_EXECUTION_SPLIT** | **YES** — cannot reach 0.5x without modeling maker/taker fill ratio; current single-bps abstraction is too crude |
| INSUFFICIENT_EVIDENCE | NO |

## 10. Phase 2 Verdict

→ **COST_0_5X_OPTIMISTIC_BUT_PLAUSIBLE + COST_MODEL_NEEDS_EXECUTION_SPLIT.**

Cost = 0.5x represents a 100%-maker fill profile with zero slippage assumption. This is **achievable on Binance Futures** but requires:
1. Maker order routing infrastructure (zangetsu does NOT yet have this)
2. Strategy changes to post passive limits (current j01 uses market orders)
3. Acceptance that maker fills are NOT guaranteed — real fill rate may be 60-80%, leaving residual taker exposure

**A blanket global cost reduction from 1.0x to 0.5x is NOT economically defensible** without first implementing maker/taker execution split modeling. The current 11.5 bps cost is a reasonable ceiling for the project's current execution capability (market-order-based).

The economic gap between current execution capability and the calibration window is **6 bps round-trip** — closeable only by infrastructure work, not by lowering the cost constant.
