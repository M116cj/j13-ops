# TEAM ORDER 0-9Z FINAL REPORT

**TEAM ORDER**: 0-9Z-STRUCTURAL-COST-FEASIBILITY-AND-ROUTING-DECISION
**Date**: 2026-04-29
**Phase**: 7 / 8 (final)
**Mode**: READ-ONLY / DECISION-ONLY

## Verdict
**PATH_A_CONDITIONAL**

Cost wall CAN be broken structurally to reach net-positive economics, BUT requires either:
1. **Maker-only execution-routing infrastructure** (new external code outside zangetsu's scope) + empirical adverse-selection measurement
2. **Account scale to Binance VIP 3+** (≥$100M monthly volume — capital intervention)

Both conditions sit OUTSIDE 0-9Z's forbidden-change list and outside zangetsu's current architecture. Within strict 0-9Z constraints (no source change, no execution code, no live API calls, no production rollout), Path A cannot be unconditionally validated.

## Baseline (carried forward from HE5)
- HE5 verdict: `COMPLETE_HE5_EDGE_EXHAUSTED`
- gross_pnl_median: **+2.4 bps** per batch (median across 3266 HE4 batches)
- net_pnl_median: **−1.22 bps** per batch
- cost / gross ratio: **1.55** (cost is 55% larger than gross)
- round_total_cost_bps: 14.5 (Diversified tier; 11.5 Stable; 23.0 High-Vol)
- 0 / 3266 batches achieved net > 0
- deployable_count: **0** permanent
- Required cost cut for break-even (median): **~35%** (cost ≤ 9.4 bps)
- Required cost cut for 99%-positive: **~50%** (cost ≤ 7.25 bps)

## Findings

### 1. Cost model
- Formula: `total_round_trip_bps = (taker_bps × 2) + slippage_bps + funding_8h_avg_bps`
- **TAKER-ONLY**, static, per-tier
- `maker_bps` defined in dataclass but **DEAD DATA** (never consumed by `total_round_trip_bps`)
- Cost applied **per round-trip** in backtester (no double-count, no undercount)
- Funding included as fixed 1.0 bps per round-trip
- Slippage included as 0.5 / 1.0 / 2.0 bps per tier (Stable / Diversified / High-Vol)

### 2. Fee / venue / tier matrix
| Lever | Cost cut |
|---|---:|
| BNB 10% discount | -8.7% (insufficient) |
| Binance VIP 1 (≥$15M/mo) | -17% (borderline) |
| Binance VIP 3 (≥$100M/mo) | **-35%** (just sufficient) |
| Binance VIP 5 (≥$1B/mo) | -43% |
| Maker-only theoretical | **-52%** (most powerful single lever) |
| Venue change (Bybit/OKX/Kraken) | ~0% (similar fees across crypto futures) |

### 3. Maker-only feasibility
- **Theoretical** cost cut: -52% (Stable tier: 11.5 → 5.5 bps)
- **Adverse selection penalty** (literature, 30-80% of rebate eaten): 1.8 - 4.2 bps lost
- **Real cost cut after adverse selection**: -16% to -44%
- **Median realistic case** (60% AS): -21% cost cut → cost = 9.1 bps → **margin +0.3 bps** (just below 50% break-even)
- **Conservative case** (70% AS, Ait-Sahalia/Brunetti crypto): -16% cut → cost = 9.7 bps → **margin -0.3 bps** (still negative)
- **Optimistic case** (30% AS, informed alpha): -44% cut → cost = 7.3 bps → margin +2.1 bps (median positive)
- **Implementation blocker**: zangetsu has NO maker-only execution code; market-order vectorized backtester only. Building maker-fill simulator is outside 0-9Z scope.

### 4. Timeframe / instrument
- **Higher timeframe (15m / 30m / 1h)**: HURTS economics (per-trade cost is fixed; gross only sqrt-time-grows; high TF concentrates losses)
- **1h timeframe**: ~16 trades / batch — fails A2_MIN_TRADES=25 (FORBIDDEN to weaken)
- **Stable-tier instrument restriction**: -21% cost — meaningful but insufficient alone
- **Stable + maker-only combined**: theoretical break-even at adverse-selection ≤ 60%
- **TF3-style strength filter**: confirmed live -13% cost/gross — insufficient (verdict NO_HORIZON_EDGE-equivalent on cost axis)

### 5. Slippage / funding
- Slippage modeled per-tier (0.5 / 1.0 / 2.0 bps) — reasonable for retail-size orders, **understated for large size**
- Funding modeled as 1.0 bps per round-trip — reasonable for direction-neutral strategies, **understated for directional alphas under regime stress**
- Both are **conservatively static** in current model; real values can spike in volatility events

## Decision

### Recommended path
**0-9Z verdict = PATH_A_CONDITIONAL.** Specifically:
- The cost-reduction levers identified (maker-only or VIP3+) are the right answer
- But neither can be implemented or empirically measured under 0-9Z's forbidden constraints
- The next legitimate order is **conditions-closure** to determine which path is achievable

### Rejected paths
- **A1 fee tier upgrade only**: insufficient unless VIP 3+ (capital constraint)
- **A3 venue change**: no structural fee advantage on alternate exchanges
- **A4 timeframe shift**: HURTS economics; 1h+ fails A2 floor
- **B architecture redesign** (without cost change): rejected by HE5 (EDGE_EXHAUSTED — TF + HE + OP series cannot flip net positive without cost-side change)
- **C new alpha axis** (microstructure / orderbook / regime): viable next-axis but requires new master order; potentially solves cost-vs-edge balance via stronger gross signal

### Conditions required for PATH_A_GO upgrade
1. Build a **maker-fill SHADOW simulator** (separate code path, not currently in zangetsu)
2. Measure empirical **adverse-selection rate** on zangetsu signals (≥1000 trades worth of fill data)
3. Verify operator's actual Binance fee tier (one read-only API call to `GET /fapi/v1/account`)
4. Re-evaluate post-implementation cost/gross with measured numbers

If all 4 conditions satisfy break-even conservatively → upgrade to `PATH_A_GO`.
If conditions cannot be satisfied within reasonable timeframe → downgrade to `PATH_A_NO_GO` and proceed to `0-9AA-NEW-ALPHA-AXIS-SELECTION`.

## Acceptance criteria status (master-order spec)

| AC | Description | Status |
|---|---|---|
| AC1 | ZANGETSU cost path documented | ✅ Phase 1 (file:line traced) |
| AC2 | Break-even cost bps calculated | ✅ Phase 1 (~9.4 bps median; ~7.25 bps for 99%) |
| AC3 | Required cost reduction recalculated | ✅ ~35% median; ~50% for 99% |
| AC4 | Exchange/tier scenarios compared | ✅ Phase 2 (10 scenarios across 9 VIP tiers + alternate venues) |
| AC5 | Maker-only includes fill delay + adverse selection | ✅ Phase 3 (literature 30-80%, mid-case 60%) |
| AC6 | Funding & slippage explicit | ✅ Phase 1 + Phase 4 (modeled + caveats) |
| AC7 | At least 3 structural alternatives compared | ✅ 7 paths (A1-A5, B, C) |
| AC8 | Final verdict GO / CONDITIONAL / NO_GO / INSUFFICIENT_DATA | ✅ **PATH_A_CONDITIONAL** |
| AC9 | No source behavior change | ✅ Phase 6 (zero source LOC change) |
| AC10 | No live trading or production execution | ✅ confirmed throughout |
| AC11 | Controlled diff reports docs-only / read-only | ✅ Phase 6 |
| AC12 | Gate-A / Gate-B pass on PR | (to be confirmed in Phase 8) |

**All 11 measurable acceptance criteria PASS.** AC12 pending Phase 8.

## Q1 / Q2 / Q3
- **Q1 (5 dims)**: PASS — analysis is read-only / docs-only; zero failure surface; all forbidden touches verified clear
- **Q2**: PASS — recovery path = retain prior state; 0-9Z introduces no new failure modes
- **Q3**: PASS — minimal, exactly what the master order required

## Forbidden ops audit
**0** — 0-9Z is pure docs-only analysis. No source code change, no DB write, no env activation, no worker restart, no Binance API key usage.

## Honest acknowledgement

**Path A's cost intervention is the most data-supported next-step**, but 0-9Z determined it cannot be validated within 0-9Z's strict forbidden-change constraints. The next order (`0-9ZA-CONDITION-CLOSURE`) needs to:
1. Define a SHADOW maker-fill simulator (NEW code path, opt-in only)
2. Specify how to measure adverse selection in a read-only / replay manner
3. Run the experiment, collect empirical data, and produce a definitive PATH_A_GO / NO_GO call

If `0-9ZA` cannot establish a validation protocol within reasonable forbidden constraints, the alternative is `0-9AA-NEW-ALPHA-AXIS-SELECTION` — pivoting to microstructure or other features that produce a stronger gross edge per trade.

## Final state
- **0-9Z mission**: COMPLETE with verdict `PATH_A_CONDITIONAL`
- **0-9Y master**: closed at HE5 (EDGE_EXHAUSTED)
- **Live runtime**: baseline preserved (no env, no restart, no API calls)
- **Source code**: zero modifications throughout 0-9Z
- **DB state**: zero modifications (all queries SELECT-only)

## Next Order

Per master-order spec mapping:
- **PATH_A_CONDITIONAL → 0-9ZA-CONDITION-CLOSURE**

Specifically `0-9ZA` should:
- Establish maker-only SHADOW evaluation framework (new opt-in code path, NOT live trading)
- Specify adverse-selection measurement methodology for zangetsu's signal style
- Verify operator account tier (single read-only Binance API call to `/fapi/v1/account`)
- Produce GO / NO-GO based on empirical fill data

Alternative if `0-9ZA` cannot proceed (forbidden constraints too strict):
- **0-9AA-NEW-ALPHA-AXIS-SELECTION** — microstructure / orderbook / liquidations / regime-conditional features

## Verdict (final)
**PATH_A_CONDITIONAL**

Cost reduction is the right answer. Implementation is outside 0-9Z's scope. Next order must establish empirical validation pathway.
