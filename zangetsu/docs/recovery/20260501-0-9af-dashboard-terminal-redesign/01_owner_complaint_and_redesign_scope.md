# 01 — Owner Complaint and Redesign Scope

**ORDER**: 0-9AF-REDESIGN — Phase 1

## Owner Complaint (verbatim from order)

> The current dashboard is too article-like / report-like.
> Owner wants an OKX-style exchange terminal experience:
> dense, visual, real-time, panel-based, fast to scan, operator-oriented.

## Redesign Direction

Replace V1 article layout with single-page terminal:
1. Sticky dark top status bar (HEAD / Mode / Axis / Freshness / counts / UTC clock)
2. 10-card KPI strip
3. 3-zone body: left sidebar selectors / center funnel + reject-depth / right candidate drawer
4. Bottom tabs: Candidates / Rejects / Survivors / Feedback / Health

## Scope Lock — IN

- New package `zangetsu/dashboard_terminal/` (separate from V1 `zangetsu/dashboard/`; reuses V1 view_models which are already tested)
- New systemd unit `zangetsu-dashboard-terminal.service`
- Replaces V1 service on port 8785

## Scope Lock — OUT (forbidden by order §4)

- No write controls; no mining triggers; no execution triggers
- No live trading; no CANARY; no production rollout
- No threshold / Arena logic / champion promotion / deployable_count semantic mutation
- No public internet exposure
- No fake zero
- No NOT_EVALUATED / REJECTED collapse
- No SURVIVOR / NEAR_SURVIVOR collapse
