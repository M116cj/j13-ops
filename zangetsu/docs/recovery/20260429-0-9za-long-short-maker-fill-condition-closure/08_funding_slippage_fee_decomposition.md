# 08 — Funding / Slippage / Fee Decomposition

**TEAM ORDER**: 0-9ZA-COMPLETE — Phase 8
**Date**: 2026-04-30
**Mode**: READ-ONLY / SHADOW-ONLY / DECISION-ONLY

## Objective

Decompose effective cost by LONG, SHORT, and COMBINED.

## Known From 0-9Z (PATH_A_CONDITIONAL closure)

| Item | Value |
|---|---:|
| Current effective cost | ~14.5 bps |
| Break-even cost | ≤ 9.4 bps |
| Required cost cut | ~35% |
| Current model | taker-only |
| `maker_bps` in current path | dead data (taker-only routing) |

## Required Net-bps Formula

```
net_bps = gross_bps
        - maker_fee_bps
        - taker_fee_bps_if_any
        - slippage_bps
        - adverse_selection_bps
        - missed_fill_opportunity_cost_bps
        - funding_bps
```

## Cost-Component Availability

| Component | LONG | SHORT | COMBINED | Status |
|---|---|---|---|---|
| gross edge | known from HE5 aggregate, side split partial | known from HE5 aggregate, side split partial | known | PARTIAL |
| maker fee | scenario only | scenario only | scenario only | AVAILABLE (scenario) |
| taker fee | known / scenario | known / scenario | known / scenario | AVAILABLE |
| slippage | not empirically measured | not empirically measured | not empirically measured | DATA_BLOCKED |
| adverse selection | not measured | not measured | not measured | DATA_BLOCKED |
| missed-fill penalty | not measured | not measured | not measured | DATA_BLOCKED |
| funding | unknown / partial | unknown / partial | unknown / partial | BLOCKED_OR_PARTIAL |
| final net | not provable | not provable | not provable | DATA_BLOCKED |

## Fee Scenarios (informational only — does not constitute a final-net proof)

| Scenario | Maker bps | Taker bps | Round-trip bps | Note |
|---|---:|---:|---:|---|
| Current tier (Binance VIP0/1, taker-only) | n/a | ~5 | ~10 | matches 0-9Z baseline ~14.5 bps after slippage/funding |
| Maker-only @ current tier | ~2 | n/a | ~4 | requires fill proof not available |
| VIP3 maker-only | ~0–1 | n/a | ~0–2 | requires VIP3 access not verified (see 09) |

These scenarios are *not* a maker-only viability proof — they assume 100% maker fill rate and zero adverse selection, both of which are explicitly DATA_BLOCKED.

## LONG Result

LONG final maker-only net bps **cannot be calculated** because slippage, fill delay, missed fills, queue risk, adverse selection, and side-aware funding are not empirically available.

## SHORT Result

SHORT final maker-only net bps **cannot be calculated** because slippage, fill delay, missed fills, queue risk, adverse selection, and side-aware funding are not empirically available. Funding asymmetry vs. LONG side compounds the gap.

## COMBINED Result

COMBINED result **cannot be used for the final verdict** because LONG and SHORT are both data-blocked. Per the order, no combined-only conclusion is allowed.

## Verdict

```
FEE_SCENARIO_AVAILABLE
FUNDING_PARTIAL_OR_UNKNOWN
SLIPPAGE_BLOCKED
ADVERSE_SELECTION_BLOCKED
MISSED_FILL_BLOCKED
FINAL_NET_NOT_PROVABLE
```

**Final**: `FINAL_NET_NOT_PROVABLE`
