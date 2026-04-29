# 03 — FAILURE MODE DECOMPOSITION

**TEAM ORDER**: 0-9Y-HE5-DEPLOYABLE-FLOW-RECHECK
**Date**: 2026-04-29
**Phase**: 3 / 8

## Three failure modes (per master-order Phase 3)
1. **EDGE_TOO_WEAK** — gross PnL is insufficient
2. **COST_TOO_HIGH** — cost overwhelms otherwise-viable edge
3. **TRADE_POLICY_INEFFICIENT** — over-trading dilutes per-trade economics

## Evidence (from 3266-batch HE4 shadow window + DB pipeline)

### Question 1 — Is gross PnL sufficient?
| Statistic | Value |
|---|---:|
| `train_gross_pnl_median` | +2.43 bps |
| `train_gross_pnl_mean` | +2.41 bps |
| 99.94% of batches | gross > 0 |
| Best gross_pnl_median (non-degenerate) | +2.84 bps (DOGEUSDT h=240) |

**Gross is reliably positive.** The GP search produces alphas whose underlying expected PnL (before cost) is positive in 99.94% of batches. This is NOT an `EDGE_TOO_WEAK` problem — gross edge exists.

### Question 2 — Does cost overwhelm edge?
| Statistic | Value |
|---|---:|
| `round_total_cost_bps` median | 14.5 bps |
| `cost_over_gross_ratio` median | **1.55** (cost is 55% larger than gross) |
| Cost / gross at top-5 closest batches | 1.10–1.19 |
| Counterfactual at 0.5x cost: net > 0 batches | **3252 / 3266 (99.57%)** |
| Counterfactual at 0.7x cost: net > 0 batches | 842 / 3266 (25.78%) |
| Counterfactual at 0.9x cost: net > 0 batches | 1 / 3266 (0.03%) |

**Cost dominates the failure.** The structural cost-vs-gross imbalance is ~1.55:1. To reach net > 0 reliably, cost would need to drop below ~0.65× current. **This is a `COST_TOO_HIGH` problem, primarily.**

### Question 3 — Is trade count too high?
| Statistic | Value |
|---|---:|
| `train_total_trades_median` | 980 trades / batch / alpha |
| Per-trade gross | +0.00244 bps |
| Per-trade cost (= 14.5 / 980) | 0.0148 bps |
| Per-trade net | -0.00125 bps |

Per-trade economics: the system trades roughly 980 times to win a median 0.00244 bps gross — but loses 0.0148 bps per trade in cost. **Each trade is a net-loss event on average.**

TF3-style strength filtering (live-confirmed with q=0.95): improves per-trade gross by ~25-30% (+0.00244 → +0.00313), but absolute total cost reduces only proportionally to fewer trades (~5% of trades kept). Per-trade net improves but stays negative (-0.00125 → -0.00097, +22% improved). Total net per batch improves modestly (-1.22 → -0.06) but does not flip positive.

**Trade-policy inefficiency is real but secondary** to cost. Reducing trade count alone cannot solve net negativity in current pipeline.

## Failure-mode classification
| Mode | Severity | Evidence |
|---|---|---|
| EDGE_TOO_WEAK | ❌ NOT primary | gross > 0 in 99.94% of batches |
| **COST_TOO_HIGH** | **✅ PRIMARY** | cost/gross = 1.55 average; counterfactual 0.5x cost flips 99.57% positive |
| TRADE_POLICY_INEFFICIENT | ⚠️ SECONDARY | TF3 confirmed live: filtering improves but does not flip net positive |

## Why "cost is high" (mechanistic analysis)
- Cost model is **locked** by master order (forbidden to modify)
- Round-trip cost = 14.5 bps reflects realistic Binance trading fees + slippage
- Per-trade gross ≈ 0.00244 bps means ~6,000 trades needed to overcome a single round-trip cost
- The current alphas produce a per-trade edge ~6× too small to justify each trade's cost
- Either alphas need to be ~6× more selective in WHICH trades to take (way beyond TF3's q=0.95), OR the cost model assumption itself needs revisiting (forbidden)

## Inheritance from prior orders
- TF2 fixture predicted aggregation flips net positive; TF3 LIVE confirmed it improves but doesn't flip
- HE3 fixture predicted horizon flips net positive at h=360; HE4 LIVE falsified (no horizon edge)
- OP1 expanded primitive set; alphas now use richer formulas but gross is essentially unchanged
- → **All explored axes (TF, HE, OP) cannot overcome the cost structural barrier within forbidden constraints**

## Verdict
**FAILURE_MODE = COST_TOO_HIGH (primary) + TRADE_POLICY_INEFFICIENT (secondary)**

The system's gross edge is real and positive (mean +2.4 bps), but cost burn (14.5 bps round-trip × ~980 trades / batch) routinely exceeds it. No combination of TF/HE/OP axes within forbidden constraints can flip net positive.

## Next
Phase 4 — explicit counterfactual tests (cost reduction / trade reduction / win-rate uplift).
