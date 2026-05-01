# 03 — V3 Mobile Terminal Product Spec

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 2

## Mobile-First Layout

```
┌──────────────────────────────────┐
│ TOP STATUS BAR (sticky)          │
│ ZANGETSU · TERM v3 · UTC clock   │
│ [MODE][AXIS][UNK][NEV][ERR][FR]  │
├──────────────────────────────────┤
│ MAIN (scrollable, padding 8/10)  │
│ • per-page sections in cards     │
│ • KPI grid auto 2/3/4 col        │
│ • depth bars / tables / forms    │
├──────────────────────────────────┤
│ BOTTOM NAV (fixed, 7 tabs)       │
│ HOME ▼ FUNNEL ≡ CANDS ✕ REJ ★    │
│ SURV ↻ FEED ♥ HLTH               │
└──────────────────────────────────┘
```

## 8 Routes

| Path | Page | Source |
|---|---|---|
| / | Overview | run_summary + results + symbol top-list + reject depth |
| /funnel | Arena Funnel + Side split + Reject depth | a1 + a2 + survivor + near + side breakdown |
| /candidates | Candidate Explorer | results + 4 filter selects + search box |
| /candidate/{cid} | Candidate Detail | results + manifest lookup (formula/grammar/primitive) |
| /rejects | Reject Explorer | REJECTED rows by reason / by symbol / by side |
| /survivors | Survivors / Near-survivors (strictly separated) | survivor_report.csv + near_survivor_report.csv |
| /feedback | Feedback weights + Next-batch actions | feedback_weights.json + next_batch_weights.json |
| /health | Per-source freshness + parser state | freshness_for() per artifact |

Plus `/_stcore/health` and `/healthz` for uptime probes.

## Operator Workflow on Phone (≤ 10 s)

1. Open URL → land on Overview
2. Glance at top pill bar — 6 colored badges = system health snapshot
3. Scan KPI grid — see PASSED / REJECTED / NEAR / pass rate
4. Tap REJ tab → see why candidates die (red depth bars)
5. Tap SURV tab → see what survived (green) and what almost survived (yellow)
6. Tap CANDS → search by id; tap any row → full detail page

## Refresh Cadence

- HTML auto-refreshes every 30 s via `<meta http-equiv="refresh">`.
- No JS framework, no WebSocket, no service-worker — minimal surface.
