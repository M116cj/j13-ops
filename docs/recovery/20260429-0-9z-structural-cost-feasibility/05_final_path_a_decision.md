# 05 — FINAL PATH A DECISION

**TEAM ORDER**: 0-9Z-STRUCTURAL-COST-FEASIBILITY-AND-ROUTING-DECISION
**Date**: 2026-04-29
**Phase**: 5 / 8

## Decision matrix (per master-order Phase 5)

| Path | Feasibility | Required change | Risk | Recommendation |
|---|---|---|---|---|
| **A1 — fee tier upgrade** | Possible only at VIP 3+ (≥$100M/mo volume) | scale 1000× current notional, requires capital | scale risk; not in operator control | **NOT VIABLE** without major capital infusion |
| **A2 — maker-only routing** | Theoretical -52% cost, post-AS net -21% to -40%; borderline break-even | new execution-routing code (forbidden in 0-9Z); empirical fill data (unavailable) | adverse selection 30-80%; unmeasured | **CONDITIONAL** — needs SHADOW maker-fill experiment |
| **A3 — venue change** | Bybit/OKX/Kraken: similar fees; Coinbase higher | external switch | liquidity loss for alts | **NOT VIABLE** — no structural fee advantage |
| **A4 — timeframe shift** | 15m / 30m: still cost-dominated; 1h/4h fail A2_MIN_TRADES=25 | reconfigure data pipeline | A2 floor breach (forbidden) | **NOT VIABLE** |
| **A5 — instrument filter** | Stable-only: -21% cost. Insufficient alone. | universe restriction | reduced diversification | **PARTIAL** — combinable but not standalone |
| **B — architecture redesign** | horizon-aware min_hold, A2 V10 reconstruction | source code change | violates 0-9Z forbidden list | **OUT OF 0-9Z SCOPE** (next-order candidate) |
| **C — new alpha axis** | microstructure / orderbook / regime features | new feature engineering, may need new data | scope, may not solve cost wall | **OUT OF 0-9Z SCOPE** (next-order candidate) |

## Key cost-reduction matrix consolidated

| Lever | Cost cut | Sufficient (≥35%)? | Implementable in 0-9Z scope? | Empirically validatable? |
|---|---:|---|---|---|
| BNB 10% discount | -8.7% | ❌ | ✅ (no code change) | ✅ (verifiable on account) |
| VIP 1 (≥$15M/mo) | -17% | ❌ borderline | ❌ requires scale | external |
| VIP 3 (≥$100M/mo) | -35% | ✅ | ❌ requires scale | external |
| **Maker-only (theor.)** | **-52%** | **✅** | **❌ requires execution code** | **❌ no SHADOW available** |
| Maker-only + 60% AS | -21% | ❌ borderline | ❌ same | needs empirical |
| Stable instrument filter | -21% | ❌ alone | ✅ (config change) | ✅ (HE5-style replay) |
| Stable + maker-only optimistic | -52% effective | ✅ | ❌ same | needs empirical |
| Stable + maker-only conservative | -21% effective | ❌ borderline | ❌ same | needs empirical |
| Stable + maker-only pessimistic | -16% effective | ❌ insufficient | ❌ same | needs empirical |

## Path A verdict per master-order rule

> PATH_A_GO only if conservative net bps > 0 after fees + slippage + funding + fill penalty.

**Conservative scenario (60-70% adverse selection)**: net = -0.3 to +0.3 bps, **NOT robustly > 0**.

> PATH_A_CONDITIONAL if profitability requires external changes such as VIP tier or maker routing not yet available.

**This applies**: Path A requires **external/operator-level intervention**:
- Maker-only routing infrastructure (new execution layer outside zangetsu)
- OR account scale-up to VIP 3+ (capital intervention)

> PATH_A_NO_GO if only aggressive/unrealistic assumptions become profitable.

Under the *most aggressive* assumptions (Stable + maker-only + only 30% adverse selection), Path A becomes profitable. But this is **conditional on assumptions** that have not been empirically validated.

> PATH_A_INSUFFICIENT_DATA if account tier, fill model, or venue fee data cannot be verified.

**Partially applies**: Account tier was not verified (per forbidden constraint of not using API keys). Fill model is theoretical only.

## Final verdict

**`PATH_A_CONDITIONAL`**

**Rationale**: Path A (structural cost reduction) IS theoretically viable to flip net positive, but requires either:
1. **Maker-only execution routing infrastructure** (new external code, plus empirical adverse-selection measurement on zangetsu's specific signal style)
2. **Account scale to Binance VIP 3+** (external capital)
3. **Both, ideally** — Stable-tier-restricted + maker-only would deliver the strongest cost-reduction case

Without one of these external interventions, the cost wall **cannot be broken** within zangetsu's current codebase and 0-9Z's forbidden constraints.

## Conditions required for upgrade to PATH_A_GO

To upgrade `CONDITIONAL` → `GO`, the following must all be satisfied:
1. **Build maker-only SHADOW** (not in 0-9Z scope; requires execution code) OR external maker-router
2. **Measure adverse-selection** on zangetsu's signal style for ≥1000 trades in real / replay
3. **Verify operator's actual Binance fee tier** (likely regular without intervention)
4. **Validate that maker-only fill rate** for medium-frequency rank-extreme signals stays > 50% (otherwise sample-size collapses)
5. **Recompute** post-implementation cost/gross with empirical numbers

## Conditions for downgrade to PATH_A_NO_GO

If any of the following are true:
1. Adverse-selection measured > 70% on zangetsu signals
2. Fill rate < 50% in maker-only SHADOW
3. Gross edge erodes when entries are delayed by ≥3 bars
4. Binance VIP 1 not achievable in operator's planning horizon

## Next-order recommendation

Per master-order's mapping:
- `PATH_A_CONDITIONAL` → next order = **0-9ZA-CONDITION-CLOSURE**

Specifically, 0-9ZA should:
- Define the maker-only SHADOW evaluation framework (NEW code path, opt-in only, no live trading)
- Specify how to measure adverse selection without crossing forbidden lines
- Establish the data-collection protocol for the next decision

If 0-9ZA closure verifies the conditions ARE achievable, escalate to maker-only design (`0-9ZA-MAKER-ONLY-SHADOW-DESIGN`). If verification fails, escalate to `0-9AA-NEW-ALPHA-AXIS-SELECTION`.

## Verdict
**PHASE_5_COMPLETE — verdict: PATH_A_CONDITIONAL**

The cost wall CAN be broken structurally (within physical/business constraints), but NOT within zangetsu's current architecture and 0-9Z's forbidden-change list. Resolution requires external maker-routing infrastructure OR account-tier scale-up — both **outside this order's scope**.

## Next
Phase 6 — controlled diff (0-9Z is docs-only).
