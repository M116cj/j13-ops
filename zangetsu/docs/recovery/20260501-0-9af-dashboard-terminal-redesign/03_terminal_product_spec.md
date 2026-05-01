# 03 — Terminal Product Spec

**ORDER**: 0-9AF-REDESIGN — Phase 2

## Single-Page Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ STICKY TOP STATUS BAR                                                          │
│ ZANGETSU TERMINAL v2 · HEAD · MODE · AXIS · BATCH · GEN_ID                     │
│ FRESHNESS · A2_MIN_TRADES · UNKNOWN_REJECT · NOT_EVAL · ERROR · UTC            │
├──────────────────────────────────────────────────────────────────────────────┤
│ 10-CARD KPI STRIP                                                              │
│ Candidates · Passed · Rejected · Near · Pass rate · Unknown ·                  │
│ NotEval · Error · Dom rej · Axis                                               │
├──────────────────────┬─────────────────────────────────────────┬──────────────┤
│ LEFT SIDEBAR         │ CENTER  (~70% width)                    │ RIGHT (~30%)  │
│ Batch (selectbox)    │ ARENA FUNNEL (Generated→A1→A2→Surv)     │ CANDIDATE     │
│ Symbol filter        │ A3 / A4 / A5: NOT_REACHED               │ DETAIL DRAWER │
│ Side filter          │ Survivor / Near badge row               │ status badge  │
│ Arena filter         │                                         │ symbol/side/tf│
│ SEARCH box           │ REJECT DEPTH PANEL                      │ axis/grammar  │
│                      │ no_trades_generated  ████████ 60.4%     │ alpha_hash    │
│                      │ non_positive_net     ████   33.4%       │ gross/cost/net│
│                      │ too_few_trades       ██     6.3%        │ trades L/S    │
│                      │ UNKNOWN_REJECT       [0]                │ reject reason │
│                      │                                         │ near eligible │
│                      │                                         │ formula (mono)│
├──────────────────────┴─────────────────────────────────────────┴──────────────┤
│ BOTTOM TABS:                                                                   │
│ [CANDIDATES] [REJECTS] [SURVIVORS] [FEEDBACK] [HEALTH]                         │
│ table with row-click → drawer / stacked rejects / strict survivor split /      │
│ next-batch action table / per-source freshness table                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Operator Workflow (in 10 seconds)

1. Glance at TOP STATUS BAR — green badges everywhere = healthy
2. Scan KPI STRIP — see PASSED / REJECTED / NEAR / Dominant Reject
3. Look at FUNNEL — confirm pipeline isn't stuck at any gate
4. Scan REJECT DEPTH — identify dominant failure mode
5. Click any row in CANDIDATES tab → DRAWER shows full detail
6. Switch tabs to drill into REJECTS / SURVIVORS / FEEDBACK / HEALTH

## Code

- `zangetsu/dashboard_terminal/app.py` — the entire single-page terminal in ~75 lines
- `zangetsu/dashboard_terminal/theme.py` — dark CSS injection (~80 rules)
- `zangetsu/dashboard_terminal/panels/` — 7 panel modules (status bar, KPI strip, funnel, depth, sidebar, drawer, tabs)
- View models reused from V1: `zangetsu/dashboard/view_models/*` (no duplication, already tested)
