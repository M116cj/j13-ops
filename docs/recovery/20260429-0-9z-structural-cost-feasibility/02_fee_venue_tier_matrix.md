# 02 — FEE / VENUE / TIER MATRIX

**TEAM ORDER**: 0-9Z-STRUCTURAL-COST-FEASIBILITY-AND-ROUTING-DECISION
**Date**: 2026-04-29
**Phase**: 2 / 8

## Methodology
Use **public Binance Futures fee schedule** (well-documented, no live API access required). Compare against zangetsu's hard-coded assumptions and alternate venues. For unknown account-tier, build conservative / base / aggressive scenario bands.

## Reference: Binance USDT-M Perpetual Futures fee schedule (regular tier)

Per Binance's published schedule (well-documented — primary source: binance.com/futures/trading-rules/perpetual/futures-vip-tier):

| VIP Level | 30-day USD volume threshold | BNB balance | Maker | Taker |
|---|---|---|---:|---:|
| Regular (VIP 0) | < $15M | — | 2.0 bps | 5.0 bps |
| VIP 1 | ≥ $15M | ≥ 25 BNB | 1.6 bps | 4.0 bps |
| VIP 2 | ≥ $50M | ≥ 100 BNB | 1.4 bps | 3.5 bps |
| VIP 3 | ≥ $100M | ≥ 250 BNB | 1.2 bps | 3.0 bps |
| VIP 4 | ≥ $600M | ≥ 500 BNB | 1.0 bps | 2.7 bps |
| VIP 5 | ≥ $1B | ≥ 1000 BNB | 0.8 bps | 2.5 bps |
| VIP 6 | ≥ $2.5B | ≥ 1750 BNB | 0.6 bps | 2.4 bps |
| VIP 7 | ≥ $5B | ≥ 3000 BNB | 0.4 bps | 2.3 bps |
| VIP 8 | ≥ $12.5B | ≥ 4500 BNB | 0.2 bps | 2.2 bps |
| VIP 9 | ≥ $25B | ≥ 5500 BNB | 0.0 bps | 1.7 bps |

**With BNB-fee-discount** (10% off): a regular trader pays effectively 1.8 maker / 4.5 taker bps if BNB balance maintained.

**With API key referral / market-maker program**: select traders may receive negative maker fees (rebates) — typically -0.5 to -1.0 bps.

## zangetsu's current cost model vs Binance regular tier

| Tier | zangetsu taker_bps (current) | Binance regular taker | Match? |
|---|---:|---:|---|
| Stable (BTC/ETH/etc.) | 5.0 | 5.0 | ✅ exact |
| Diversified (LINK/AAVE/etc.) | 6.25 | 5.0 | ⚠️ 25% conservative buffer |
| High-Vol (PEPE/SHIB/etc.) | 10.0 | 5.0 | ⚠️ 100% conservative buffer (extra-spread) |

**zangetsu assumes regular-tier (VIP 0) Binance fees**. The Stable tier matches Binance exactly. Diversified and High-Vol tiers add a "spread/slippage buffer" via inflated taker_bps (which conflates fee+spread into one number).

## Account tier hypotheses (since actual tier not verified to avoid live API call)

### Hypothesis A — Operator on regular tier (most likely default)
- maker = 2.0 bps, taker = 5.0 bps (Stable)
- Current zangetsu assumption matches
- → **Cost model accurate for Stable; conservative for Diversified/HighVol**

### Hypothesis B — Operator with BNB discount (10% off)
- maker = 1.8 bps, taker = 4.5 bps
- → 10% cost reduction across the board
- New round-trip (Stable, taker-only): (4.5×2) + 0.5 + 1.0 = **10.5 bps** (vs current 11.5 = -8.7%)
- Still well above the 9.4 bps break-even threshold

### Hypothesis C — VIP 1 tier (≥$15M / 30 days)
- maker = 1.6 bps, taker = 4.0 bps
- New round-trip (Stable): (4.0×2) + 0.5 + 1.0 = **9.5 bps** (vs current 11.5 = -17%)
- **Just barely above 9.4 bps break-even threshold**
- → would tip ~50% of batches positive at this cost

## Effective round-trip bps matrix (taker-only execution)

| Scenario | maker_bps | taker_bps | slip | funding | round_trip_bps (Stable) | Δ vs current | Tipping ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Current zangetsu** | 2.0 | 5.0 | 0.5 | 1.0 | **11.5** | baseline | ~50% positive at 9.4 bps |
| Binance VIP 0 + BNB | 1.8 | 4.5 | 0.5 | 1.0 | 10.5 | -8.7% | not enough |
| Binance VIP 1 | 1.6 | 4.0 | 0.5 | 1.0 | **9.5** | -17% | borderline (≈50%) |
| Binance VIP 2 | 1.4 | 3.5 | 0.5 | 1.0 | 8.5 | -26% | likely 60-80% |
| Binance VIP 3 | 1.2 | 3.0 | 0.5 | 1.0 | 7.5 | -35% | likely 90%+ |
| Binance VIP 5 | 0.8 | 2.5 | 0.5 | 1.0 | 6.5 | -43% | likely 99%+ |

**Key insight**: To reach the 9.4 bps break-even via fee tier alone requires VIP 1 or higher (≥$15M monthly volume). For typical retail / small-fund accounts this is **out of reach**.

## Effective round-trip bps matrix (maker-only execution, theoretical)

| Scenario | maker_bps | slip (maker) | funding | round_trip_bps (Stable) | Δ vs current taker | Tipping ratio |
|---|---:|---:|---:|---:|---:|---:|
| **Current zangetsu — maker theoretical** | 2.0 | 0.5 | 1.0 | **5.5** | -52% | likely 99%+ |
| Binance VIP 0 + BNB | 1.8 | 0.5 | 1.0 | 5.1 | -56% | 99%+ |
| Binance VIP 5 | 0.8 | 0.5 | 1.0 | 3.1 | -73% | near 100% |
| Maker rebate (-0.5 bps) | -0.5 | 0.5 | 1.0 | 0.5 | -96% | 100% (any positive gross is profitable) |

**Maker-only on regular tier alone** is sufficient to drop cost from 11.5 → 5.5 bps (-52%), well past the 7.25 bps "99% positive" threshold from HE5 counterfactual. **This is the highest-leverage cost reduction available without account-tier change.**

But maker-only requires the **fill model assumption** to be realistic. Phase 3 evaluates this rigorously.

## Alternative venues (cursory survey)

| Venue | Maker | Taker | Spot vs Futures | Notes |
|---|---:|---:|---|---|
| Binance Futures (regular) | 2.0 | 5.0 | Futures (USDT-M Perp) | current zangetsu assumption |
| Bybit Futures (VIP 0) | 2.0 | 5.5 | Futures | similar; slightly higher taker |
| OKX Futures (regular) | 2.0 | 5.0 | Futures | similar |
| Coinbase Advanced (Pro) | 8.0 | 12.0 | Spot | much higher; not viable |
| Kraken Futures | 2.0 | 5.0 | Futures | similar; lower volume on alts |
| dYdX v4 | 2.0 | 5.0 (regular) | Futures (decentralized) | varying liquidity per pair |

**No venue offers a structural taker-fee advantage** large enough to single-handedly solve the cost wall. Switching venues alone is unlikely to deliver the 35%+ cost cut needed.

## Per-symbol slippage realism check (zangetsu's assumptions)

| Tier | zangetsu slippage_bps | Realistic 1m bar avg (typical retail order) | Match? |
|---|---:|---:|---|
| Stable (BTC/ETH/BNB) | 0.5 | 0.5 - 1.0 | ✅ reasonable |
| Diversified (LINK/AAVE) | 1.0 | 1.0 - 2.0 | ✅ reasonable |
| High-Vol (PEPE/SHIB) | 2.0 | 2.0 - 5.0 | ⚠️ possibly optimistic; spread can spike |

**Slippage is approximately realistic** for typical retail order sizes (< $50k notional per trade). For larger sizes, slippage scales linearly to quadratically; not modeled.

## Funding realism check
- `funding_8h_avg_bps = 1.0` for all symbols — single average across regimes
- Real funding range: -10 to +10 bps per 8h depending on market state (positive in bull, negative in bear)
- Net funding pays *or* receives based on direction (long pays positive funding; short receives)
- For an alpha that is direction-neutral over time, net funding cost averages near zero
- For a directional alpha (e.g., always long), funding can be a meaningful cost or rebate

**Conservative approximation**: zangetsu's 1.0 bps assumption is a reasonable average for direction-neutral strategies. For directional strategies, funding could add ±5-10 bps of variability — **not modeled**.

## Verdict on Phase 2

| Lever | Cost cut | Sufficient for break-even (≥35%)? |
|---|---:|---|
| BNB fee discount | -8.7% | ❌ no |
| Binance VIP 1 (≥$15M/mo) | -17% | ❌ borderline (50% batches positive) |
| Binance VIP 3 (≥$100M/mo) | -35% | ✅ yes (median batch positive) |
| **Maker-only routing (regular tier)** | **-52%** | ✅ **yes (99% positive)** |
| Venue change (Bybit/OKX/Kraken) | ~0% | ❌ no |

**Two viable paths**:
1. **Account upgrade to VIP 3+** (requires ≥$100M monthly volume — substantial scale-up, not feasible without external capital)
2. **Maker-only execution routing** (theoretically viable on regular tier; **requires Phase 3 fill-model validation**)

## Verdict
**FEE_VENUE_TIER_MATRIX_COMPLETE** — only two paths can deliver ≥35% cost reduction:
- Account VIP 3+ (capital constraint, out of reach for typical setup)
- Maker-only routing (theoretically achievable on regular tier — **requires fill probability + adverse selection analysis in Phase 3 to determine real-world feasibility**)

## Next
Phase 3 — maker-only feasibility (fill delay + adverse selection penalties).
