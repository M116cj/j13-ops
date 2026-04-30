# 01 — Failure Context (0-9Y / 0-9Z / 0-9ZA)

**TEAM ORDER**: 0-9AA — Phase 1
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Why This Phase Exists

To prevent 0-9AA from re-selecting an axis that has already been exhausted, blocked, or proven unworkable inside the prior three orders.

## 0-9Y — `COMPLETE_HE5_EDGE_EXHAUSTED`

Source: `bcf53cb5 docs(zangetsu/he5): closure — EDGE_EXHAUSTED (system-wide deployable-flow recheck)` and the prior 0-9Y-* sub-orders (he0-he5, fs1, tf1-tf4, op1, b1-b3, c, d, final-0, checkpoint).

### What was tried inside the existing alpha family
- horizon multiplexing (60/180/240/360 bars) — `he1`-`he5`
- per-batch aggregate diagnostic metrics — `b1`
- engine_telemetry → JSONL canonical replacement — `b2`
- NULL-safe deploy_block writer — `b3` (Calcifer side)
- horizon target spec — `he0`
- economic edge decomposition — `c`
- strategic redesign decision — `d`
- master state lock — `final-0`
- feature-space quality audit — `fs1`
- trade-frequency / signal aggregation diagnosis — `tf1`-`tf4`
- 9 GP primitives × (20, 60, 240) — `op1`
- j13 Option A decision — `checkpoint`

### Net 0-9Y conclusion
- gross edge **exists** in the existing alpha family
- cost dominates the gross edge → no Arena-2 survival
- aggregation, horizon, and primitive variations all tuned out
- `deployable_count = 0` after the full sweep
- 0 alpha passed Arena-2

### Implication for 0-9AA
- The existing alpha axis is **searched out**; further variation inside the same primitive set is unlikely to produce a new edge.
- A **new alpha source** is required, not another modification of the exhausted axis.

## 0-9Z — `PATH_A_CONDITIONAL`

Source: `3cb5e08f docs(zangetsu/0-9z): structural cost feasibility — PATH_A_CONDITIONAL (#74)`.

### Numbers anchored
- Current effective cost ≈ 14.5 bps
- Break-even cost ≤ 9.4 bps
- Required cost cut ≈ 35%
- Only maker-only routing or VIP3+ theoretically reaches the threshold

### Implication for 0-9AA
- Any axis that produces another **high-turnover, low-edge** strategy will be killed by the same cost wall.
- Cost robustness is a hard scoring dimension (see 05).
- An axis that lowers turnover or raises gross edge per trade is structurally preferred.

## 0-9ZA — `PATH_A_DATA_BLOCKED`

Source: `6207bb1b docs(zangetsu/0-9za): close Phase 5-12 — PATH_A_DATA_BLOCKED (#75)`.

### What was confirmed
- No bid/ask quote history in `data/`
- No top-of-book or depth data
- No trade-print stream
- Maker-fill SHADOW simulator was **DESIGN-ONLY** — no empirical replay
- LONG_RESULT = SHORT_RESULT = COMBINED_RESULT = `DATA_BLOCKED`
- VIP3 access not verified inside evidence
- Final net bps **not provable** for either side

### Implication for 0-9AA
- Microstructure-imbalance axis (Axis A) inherits the same data block.
- Any axis whose viability proof depends on bid/ask, depth, or trade prints is **deferred** until a market-microstructure data-capture layer exists.
- Data readiness becomes a 20-weight scoring dimension (see 07).

## Combined Implication for Axis Selection

1. **Do not** propose another variant inside the exhausted alpha family.
2. **Do not** propose an axis whose only viability hinges on missing microstructure data.
3. **Do** propose axes that:
   - use already-available data (OHLCV / funding / OI),
   - reduce or stabilize turnover,
   - have separable LONG / SHORT mechanisms,
   - can survive A2_MIN_TRADES = 25 without contortion.
4. Microstructure remains a **deferred candidate** — high upside, blocked on data.

## Deliverable

`01_failure_context_from_0-9y_0-9z_0-9za.md` — frozen.
