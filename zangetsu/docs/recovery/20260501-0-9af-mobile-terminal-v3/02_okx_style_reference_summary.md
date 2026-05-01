# 02 — OKX-Style Reference Summary (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 2

## What V3 Borrowed from Exchange-App UX

| Mobile-app pattern | V3 mapping (read-only) |
|---|---|
| Pure-black status-aware background | `background: #000`; `<meta name="theme-color" content="#000">`; iOS app-capable mode |
| Sticky compact top bar with health pills | `<header class="topbar">` with brand + 6 colored pills + UTC clock |
| Bottom fixed nav with icon+label | `<nav class="bottomnav">` with 7 tabs (HOME/FUNNEL/CANDS/REJ/SURV/FEED/HLTH) |
| Card-based content panels | `.card` with consistent dark border + monospace title |
| Order-book / depth ladder | reject-reason `.depth` rows with red horizontal bars |
| Dense numeric tables | `.tbl` with 9 px uppercase header + 11 px body + green/red color rules |
| Big primary numbers | `.kpi .val` 22 px bold, color by kind |
| Tap-target friendly | min 44 px touch area on nav links and form selects |
| Auto-refresh on hold | `<meta http-equiv="refresh" content="30">` (no JS framework needed) |

## What V3 Did NOT Copy

- OKX brand / colors / logos / proprietary assets
- Trading controls (Buy/Sell/Submit/Cancel)
- Order placement / write affordances
- Account / wallet / PnL screens
- External market-data API connections
- User accounts / auth surfaces

The mapping above keeps the **mobile-app navigation feel** while binding all functionality strictly to the read-only mining observability domain.

## Style Tokens

| Token | Value | Use |
|---|---|---|
| --bg | #000 (pure black) | App background |
| --panel | #0d1116 / #11161d | Cards / status bar |
| --border | #1b2230 | Card borders |
| --fg | #e7eaf0 | Foreground text |
| --muted | #6b7280 | Captions / labels |
| --accent | #38bdf8 | Active nav / interactive |
| --green / --red / --yellow / --gray | semantic | Pass / reject / near / NA |
| --mono | ui-monospace, JetBrains Mono | All numeric values |
