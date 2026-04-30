# TEAM ORDER 0-9ZA — FINAL REPORT

**Order**: 0-9ZA-LONG-SHORT-MAKER-FILL-CONDITION-CLOSURE (completed via 0-9ZA-COMPLETE Phase 5–12)
**Date**: 2026-04-30
**Mode**: READ-ONLY / SHADOW-ONLY / DECISION-ONLY / COMPLETION-ONLY

## Verdict

```
PATH_A_DATA_BLOCKED
```

**Secondary condition**: `EXECUTION_ARCH_REQUIRED_BEFORE_PATH_A_CAN_CONTINUE`

## Baseline

| Item | Value |
|---|---|
| HEAD | `3cb5e08f` |
| Parent order | 0-9Z STRUCTURAL COST FEASIBILITY |
| Parent verdict | PATH_A_CONDITIONAL |
| Current effective cost | ~14.5 bps |
| Break-even cost | ≤ 9.4 bps |
| Required cost cut | ~35% |
| Runtime | baseline (4 arena_pipeline workers) |
| DB pipeline | 184 ARENA1_COMPLETE (staging) / 89 fresh / 0 deployable / `last_live_at_age_h` = NULL |

## Completed Evidence

| Phase | Deliverable | Result |
|---|---|---|
| 0 | state lock | complete (prior) |
| 1 | fee tier / account verification | complete, READ-ONLY, no Binance API call |
| 2 | LONG / SHORT signal inventory | complete; per-side trade not persisted in DB at HEAD `3cb5e08f` |
| 3 | orderbook data availability | complete — DATA_BLOCKED (no bid/ask, depth, trade prints) |
| 4 | maker-fill SHADOW simulator design | complete — DESIGN-ONLY, no implementation |
| 5 | LONG-side maker-fill analysis | LONG_DATA_BLOCKED |
| 6 | SHORT-side maker-fill analysis | SHORT_DATA_BLOCKED |
| 7 | adverse selection / delay / queue-risk model | DESIGN_READY_BUT_EMPIRICALLY_BLOCKED |
| 8 | fee / slippage / funding decomposition | FINAL_NET_NOT_PROVABLE |
| 9 | VIP3 feasibility | VIP3_EXTERNAL_ONLY_OR_DATA_BLOCKED |
| 10 | combined decision matrix | PATH_A_DATA_BLOCKED |
| 11 | controlled-diff report | PASS — FORBIDDEN_DIFF = 0 |

## LONG Result

| Metric | Result |
|---|---|
| fill rate | DATA_BLOCKED |
| missed-fill rate | DATA_BLOCKED |
| delay (median / p90) | DATA_BLOCKED |
| queue risk | DATA_BLOCKED |
| adverse selection bps | DATA_BLOCKED |
| funding impact | BLOCKED_OR_PARTIAL |
| final net bps | NOT PROVABLE |
| A2 trade-count impact | DATA_BLOCKED |
| **verdict** | **LONG_DATA_BLOCKED** |

## SHORT Result

| Metric | Result |
|---|---|
| fill rate | DATA_BLOCKED |
| missed-fill rate | DATA_BLOCKED |
| delay (median / p90) | DATA_BLOCKED |
| queue risk | DATA_BLOCKED |
| adverse selection bps | DATA_BLOCKED |
| funding impact | BLOCKED_OR_PARTIAL |
| final net bps | NOT PROVABLE |
| A2 trade-count impact | DATA_BLOCKED |
| **verdict** | **SHORT_DATA_BLOCKED** |

## COMBINED Result

COMBINED is also DATA_BLOCKED because both LONG and SHORT are blocked. No combined-only profitability conclusion is accepted (rule §3 of the parent order, rule §8 of the 0-9ZA-COMPLETE order).

## Decision

PATH_A **cannot advance to GO** because:

- no bid / ask quote history
- no orderbook / depth data
- no trade-print data
- no empirical maker-fill proof
- no queue-risk measurement
- no adverse-selection measurement
- no missed-fill penalty estimate
- no A2 trade-count survival proof after missed fills
- VIP3 access is not verified as operationally available

PATH_A is **not rejected as NO_GO** because:

- maker-only was not empirically tested
- failure cannot be proven without market microstructure data

PATH_A is **not classified as CONDITIONAL_SIDE_SPECIFIC** because:

- neither LONG nor SHORT has empirical side-specific viability proof

PATH_A is **not classified as GO** because:

- final net bps is not provable for either side, and combined-only conclusions are forbidden

**Final verdict**: `PATH_A_DATA_BLOCKED`
**Secondary condition**: `EXECUTION_ARCH_REQUIRED_BEFORE_PATH_A_CAN_CONTINUE` — a maker-fill data-capture and replay layer is required before Path A can be re-judged.

## Recommended Next Order

### Option A — Continue Path A

```
TEAM ORDER 0-9ZB-MARKET-MICROSTRUCTURE-DATA-CAPTURE-SHADOW
```

Objective: Build a read-only capture of bid/ask, depth, trade prints, mark price, funding, and timestamp alignment for future maker-fill SHADOW replay. No live trading. No production execution change.

### Option B — Pivot away from cost-path closure

```
TEAM ORDER 0-9AA-NEW-ALPHA-AXIS-SELECTION
```

Objective: Stop spending time on structural-cost closure and select a new alpha axis (microstructure imbalance, liquidation / funding / OI, regime-conditional features, different timeframe, different instrument universe).

### Recommended sequence

1. Close 0-9ZA at this report → `PATH_A_DATA_BLOCKED`.
2. Choose:
   - **0-9ZB** if maker-only viability remains a strategic priority and j13 commits to building the data-capture layer.
   - **0-9AA** if faster strategic progress is preferred over closing the cost-path question.

## Final Statement

0-9ZA is complete as a decision-closure task.
Empirical maker-only viability is **not proven**.
Path A **cannot proceed** to maker-only execution design without market microstructure data capture and replay.

No live trading occurred. No production keys used. No DB mutation. No runtime patch. No source behavior change. Controlled diff = 0 forbidden mutations.
