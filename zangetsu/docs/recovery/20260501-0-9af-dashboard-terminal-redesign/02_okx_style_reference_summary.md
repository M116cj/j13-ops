# 02 — OKX-Style Reference Summary

**ORDER**: 0-9AF-REDESIGN — Phase 2

## What We Borrowed (UX Patterns Only)

| OKX-style pattern | ZANGETSU-Terminal mapping (read-only) |
|---|---|
| Sticky top market info bar | Top status bar (HEAD / Mode / Axis / Freshness / counts) |
| Dense KPI strip | 10-card KPI row (Candidates, Passed, Rejected, Near, Pass rate, Unknown, NotEval, Error, Dom rej, Axis) |
| Left market selector panel | Sidebar batch / symbol / side / arena selectors |
| Center chart panel | Arena funnel + reject depth |
| Right side detail panel (positions) | Candidate detail drawer (formula, gross/cost/net) |
| Bottom tabbed tables (orders/trades) | Candidates / Rejects / Survivors / Feedback / Health |
| Order-book depth ladder | Reject-depth panel — horizontal bars with red-pressure semantics |
| Pass/fail color language | Green = pass; red = reject; yellow = near-survivor; gray = NO DATA / NOT_REACHED |
| Monospace for numbers | All numeric values rendered with `ui-monospace, JetBrains Mono` |

## What We Did NOT Copy

- OKX brand / colors / logos / proprietary assets
- Any trading control (Buy / Sell / Submit / Cancel)
- Any order placement or write affordance
- Any account / wallet / PnL screens
- Any market-data API connection
- Any user accounts / auth surface

The mapping above keeps the visual UX while binding the functionality strictly to the read-only mining observability domain (per order §4.2).

## Style Anchors

- Background: `#0b0f17` (near-black)
- Panel: `#11161f` / `#161c27`
- Border: `#1f2735`
- Foreground: `#e2e8f0` (cool gray-100)
- Muted: `#64748b`
- Accent (active selection): `#38bdf8` (cyan)
- Pass / Reject / Near / NA: `#22c55e` / `#ef4444` / `#f59e0b` / `#475569`
