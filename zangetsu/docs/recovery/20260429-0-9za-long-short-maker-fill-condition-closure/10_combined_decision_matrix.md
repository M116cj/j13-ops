# 10 — Combined Decision Matrix

**TEAM ORDER**: 0-9ZA-COMPLETE — Phase 10
**Date**: 2026-04-30
**Mode**: READ-ONLY / DECISION-ONLY

## Objective

Combine LONG, SHORT, COMBINED, VIP3, maker-only, and data-availability evidence into one final Path A decision.

## Decision Matrix

| Path | LONG | SHORT | COMBINED | A2 Safe? | Required External Condition | Risk | Verdict |
|---|---|---|---|---|---|---|---|
| Current taker-only | fails cost wall (~14.5 bps > 9.4) | fails cost wall | fails cost wall | 0 deployable | none | known negative net | NO_GO under current architecture (already known from 0-9Z) |
| Current maker-only | DATA_BLOCKED | DATA_BLOCKED | DATA_BLOCKED | unknown | bid/ask + trade prints + depth | fill / adverse unknown | DATA_BLOCKED |
| VIP3 taker-only | account blocked | account blocked | account blocked | unknown | VIP3 access | volume unrealistic / unproven | DATA_BLOCKED / EXTERNAL_ONLY |
| VIP3 maker-only | DATA_BLOCKED | DATA_BLOCKED | DATA_BLOCKED | unknown | VIP3 + maker-fill proof | execution architecture missing | DATA_BLOCKED |
| Stable symbols + maker-only | DATA_BLOCKED | DATA_BLOCKED | DATA_BLOCKED | unknown | liquidity + fill evidence | unmeasured | DATA_BLOCKED |
| Long-only maker | DATA_BLOCKED | n/a | DATA_BLOCKED | unknown | side-filter governance order | no long fill proof | DATA_BLOCKED |
| Short-only maker | n/a | DATA_BLOCKED | DATA_BLOCKED | unknown | side-filter governance order | no short fill proof | DATA_BLOCKED |

## Decision Rules Applied

### PATH_A_GO is rejected because:

- LONG net bps **not proven** (05)
- SHORT net bps **not proven** (06)
- adverse selection **not measured** (07)
- missed-fill penalty **not measured** (07, 08)
- queue risk **not measured** (07)
- A2 trade count after missed fills **not proven** (05/06)
- final net **not provable** (08)
- VIP3 access **not verified** (09)

### PATH_A_NO_GO is not used because:

- maker-only was **not empirically tested**
- failure cannot be proven without market microstructure data
- declaring NO_GO without conservative evidence would itself be fabrication

### PATH_A_CONDITIONAL_SIDE_SPECIFIC is not used because:

- neither LONG nor SHORT has empirical side-specific viability proof
- one-sided GO requires real fill evidence, which is data-blocked for both

### PATH_A_EXECUTION_ARCH_REQUIRED is valid as a secondary condition because:

- maker-fill proof requires a new data-capture / replay capability not present in current zangetsu architecture
- HE5 / 0-9Z confirmed taker-only architecture; no maker execution engine exists
- closing 0-9ZA → next-order recommendation is `0-9ZB-MARKET-MICROSTRUCTURE-DATA-CAPTURE-SHADOW`

## Final Classification

**`PATH_A_DATA_BLOCKED`**

Secondary condition: `EXECUTION_ARCH_REQUIRED_BEFORE_PATH_A_CAN_CONTINUE`
