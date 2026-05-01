# 05 — Visual Design Spec (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 2

## Mobile Viewport Setup

```html
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#000000">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
```

This makes the page render at the actual phone width (no shrink-to-fit), and on iOS the status bar matches the page background when added to the home screen.

## Responsive KPI Grid

```css
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
@media (min-width: 480px) { .kpi-grid { grid-template-columns: 1fr 1fr 1fr; } }
@media (min-width: 760px) { .kpi-grid { grid-template-columns: repeat(4, 1fr); } }
```

Phone (≤ 480 px) gets 2 columns, tablet 3, desktop 4 — no horizontal overflow at any breakpoint.

## Sticky Top Bar

`position: sticky; top: 0; z-index: 50;` — survives momentum scroll on iOS Safari.

## Fixed Bottom Nav

`position: fixed; bottom: 0;` with `padding-bottom: env(safe-area-inset-bottom)` to respect iPhone home-indicator area. 7 columns of equal width.

## Component Patterns

| Class | Purpose |
|---|---|
| `.kpi` | 60 px-tall card; uppercase label + 22 px monospace value |
| `.card` | 6 px radius dark panel |
| `.depth-row` | order-book-style horizontal bar (label / bar / pct count) |
| `.tbl` | dense data table (9 px header / 11 px body) |
| `.tag.{green,red,yellow,gray}` | inline status badge |
| `.pill.{green,red,yellow,gray}` | rounded health pill in topbar |

## Color Tokens (CSS `:root`)

| Token | Value | Use |
|---|---|---|
| --bg | #000 | App background |
| --panel | #0d1116 | Cards |
| --panel-2 | #11161d | Form controls |
| --border | #1b2230 | All borders |
| --fg | #e7eaf0 | Foreground text |
| --muted | #6b7280 | Captions / labels |
| --accent | #38bdf8 | Active nav / interactive |
| --green | #22c55e | Pass / healthy / positive |
| --red | #ef4444 | Reject / unhealthy / negative |
| --yellow | #f59e0b | Near-survivor / stale / warn |
| --gray | #4b5563 | NA / NO DATA / NOT_REACHED |
| --mono | ui-monospace, JetBrains Mono | All numeric values |

## Density Defaults

- Body font 13 px, monospace
- Card padding 8/10 px
- Section title 10 px uppercase muted
- KPI label 9 px / value 22 px / sub 9 px
- Tap target 44 px min on nav links
- Above-fold on iPhone 14 (390×844): topbar + 8 KPI cards + first ~6 reject-depth rows visible without scroll
