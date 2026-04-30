# 07 — Adverse Selection and Delay Model

**TEAM ORDER**: 0-9ZA-COMPLETE — Phase 7
**Date**: 2026-04-30
**Mode**: READ-ONLY / SHADOW-ONLY / DECISION-ONLY

## Objective

Quantify maker-only execution penalties:
- fill delay
- missed fill
- queue risk
- adverse selection after fill
- side-specific edge decay

## Required Inputs

| Input | Required For | Available | Verdict |
|---|---|---|---|
| bid/ask quote stream | fill timing | no | DATA_BLOCKED |
| trade prints | actual passive fill inference | no | DATA_BLOCKED |
| orderbook depth | queue risk | no | DATA_BLOCKED |
| mark price | adverse-movement measurement | partial | BLOCKED |
| funding series (per-timestamp, per-symbol) | side-aware carrying cost | partial | BLOCKED |

## Why OHLCV Is Insufficient

OHLCV cannot distinguish:

- a passive maker fill from a price-touch
- queue position
- partial fill
- missed fill
- spread capture
- fill delay
- adverse selection after actual fill
- bid-side vs. ask-side execution quality

Any model that maps an OHLCV bar that touches the bid → "long maker entry filled" would fabricate the very evidence this phase is meant to test, and is rejected by the order critical rule.

## Conceptual Model (DESIGN-ONLY, not measured)

### Delay Model

```
entry_delay_bars        — bars between signal trigger and passive fill
exit_delay_bars         — bars between exit trigger and passive fill
delay_to_edge_decay     — d(edge)/d(delay), per side
missed_opportunity_rate — fraction of signals that never fill before invalidation
```

### Adverse-Selection Model

```
post_fill_return_1bar
post_fill_return_3bar
post_fill_return_5bar
post_fill_return_10bar
```

Sign convention: a passive long entry that is "adversely selected" experiences negative post-fill return; a passive short entry experiences positive post-fill return.

### Queue-Risk Model

```
top_of_book_size        — depth at touch
estimated_queue_position — order arrival rank
queue_haircut           — fill-probability reduction from queue position
partial_fill_risk       — probability of incomplete fill before invalidation
```

## LONG Model Status

| Metric | Status |
|---|---|
| entry delay | DATA_BLOCKED |
| missed entry | DATA_BLOCKED |
| queue risk | DATA_BLOCKED |
| post-fill adverse return | DATA_BLOCKED |
| exit delay | DATA_BLOCKED |
| final net impact | DATA_BLOCKED |

## SHORT Model Status

| Metric | Status |
|---|---|
| entry delay | DATA_BLOCKED |
| missed entry | DATA_BLOCKED |
| queue risk | DATA_BLOCKED |
| post-fill adverse return | DATA_BLOCKED |
| exit delay | DATA_BLOCKED |
| final net impact | DATA_BLOCKED |

## COMBINED Model Status

| Metric | Status |
|---|---|
| net delay decay | DATA_BLOCKED |
| net adverse selection | DATA_BLOCKED |
| net queue haircut | DATA_BLOCKED |
| final net impact | DATA_BLOCKED |

## Verdict

**Result**: `DESIGN_READY_BUT_EMPIRICALLY_BLOCKED`

The adverse-selection / delay / queue-risk model is conceptually specified and would be implementable given the right data. Empirical measurement is blocked by missing market microstructure data (no bid/ask, no trade prints, no depth). No fabricated measurements are produced under this verdict.
