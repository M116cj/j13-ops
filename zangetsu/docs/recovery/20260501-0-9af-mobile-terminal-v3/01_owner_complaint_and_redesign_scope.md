# 01 — Owner Complaint and Redesign Scope

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 1

## Owner Complaint (verbatim)

> 參考 OKX 交易所的介面和 UI/UX 設計，目前的頁面根本就沒辦法用，先著重在手機端的排版背景要純黑色，內容要精簡乾淨我要可以透過這個 Dashboard 隨時觀測到整個系統的所有細節

Translation:
> Reference the OKX exchange UI/UX. The current page (V2 Streamlit terminal) is essentially unusable on mobile. Focus on phone layout: pure black background, concise/clean content. Want to monitor all system details at any time via this dashboard.

## Why V2 Streamlit Failed on Phone

- Streamlit's column system uses fixed pixel widths internally — they overflow on a 390 px phone viewport.
- Sidebar collapses awkwardly; selectors become unreadable.
- KPI cards don't reflow to single column.
- Bottom-tab area scrolls horizontally, hiding rows.
- No mobile viewport meta; iOS Safari renders at desktop width then shrinks.
- Streamlit's deep DOM nesting is heavy for a phone CPU.

## V3 Redesign Direction

- Drop Streamlit. Use **FastAPI + Jinja2** for server-rendered HTML.
- **Pure black** (#000) background, monospace font.
- **Mobile viewport meta** + responsive 2→3→4 column KPI grid.
- **Sticky top status bar** with 6 colored health pills (MODE / AXIS / UNK / NEV / ERR / FRESH / A2_MIN).
- **Bottom fixed nav** with 7 tabs (HOME / FUNNEL / CANDS / REJ / SURV / FEED / HLTH) — OKX-app style.
- **Card-based** content panels with consistent borders.
- **Auto-refresh every 30 s** via meta tag (no JS overhead).
- **Click-to-detail** for candidates → routed page with full metadata.

## Scope Lock — IN

- New package `zangetsu/dashboard_mobile/` (FastAPI app + 8 Jinja templates + CSS + static)
- New systemd unit `zangetsu-dashboard-mobile.service`
- Replaces V2 `zangetsu-dashboard-terminal.service` on the same port 8785

## Scope Lock — OUT

- No write controls; no mining triggers; no execution triggers
- No threshold / Arena logic / champion promotion / deployable_count semantic mutation
- No public internet exposure
- No fake zero
- No NOT_EVALUATED / REJECTED collapse
- No SURVIVOR / NEAR_SURVIVOR collapse
