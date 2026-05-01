# 0-9AF V3 — FINAL REPORT

**Order**: 0-9AF-MOBILE-TERMINAL-V3 (response to owner: V2 unusable on phone)
**Date**: 2026-05-01
**Mode**: MOBILE-FIRST UI/UX REDESIGN / READ-ONLY OBSERVABILITY

## Verdict

```
DASHBOARD_MOBILE_TERMINAL_V3_DEPLOYED_GREEN
```

## Owner Complaint Resolution

> 參考 OKX 介面，目前頁面在手機上根本沒辦法用，純黑背景，精簡乾淨，要可以隨時觀測整個系統。

V3 ditches Streamlit (broken on phone) for FastAPI + Jinja2 + pure HTML/CSS:
- pure black (#000) background
- mobile viewport meta + responsive 2/3/4-col KPI grid
- sticky top status bar with 6 colored health pills
- bottom fixed nav with 7 tabs (HOME / FUNNEL / CANDS / REJ / SURV / FEED / HLTH)
- 8 dedicated pages covering every system view
- auto-refresh every 30 s
- no JS framework — server-rendered HTML for fastest mobile TTFB

## Internal URL (UNCHANGED for the operator)

**`http://100.123.49.102:8785/`**

Same URL as V1 / V2; phone bookmark still works. Service swap is transparent.

## 8 Pages Delivered

| Path | Page | Source |
|---|---|---|
| / | Overview | run_summary + results + symbol top-list + reject depth |
| /funnel | Arena Funnel + Side split + Reject depth | a1 + a2 + survivor + near + side breakdown |
| /candidates | Candidate Explorer | results + 4 filter selects + search box |
| /candidate/{cid} | Candidate Detail | results + manifest lookup |
| /rejects | Reject Explorer | REJECTED rows by reason / by symbol / by side |
| /survivors | Survivors / Near (strictly separated) | survivor_report.csv + near_survivor_report.csv |
| /feedback | Feedback weights + Next-batch actions | feedback_weights.json + next_batch_weights.json |
| /health | Per-source freshness + parser state | freshness_for() per artifact |

## Latest Batch Snapshot (currently shown)

```
generation_id:     0-9ad-c-axis-mining-v1
candidates_total:  1792
PASSED:            39
REJECTED:          1753
NOT_EVALUATED:     0
ERROR:             0
UNKNOWN_REJECT:    0
A2_MIN_TRADES:     25 (unchanged)
```

## Mobile Validation

Real headless-Chrome screenshot at iPhone 14 Pro viewport (390 px) confirmed:
- Pure black background end-to-end
- Top status bar legible at single-line: ZANGETSU TERM v3 + MODE SHADOW + AXIS C + UNK 0 + NEV 0 + ERR 0 + FRESH (state)
- KPI cards in 2-column grid above fold (2.18% pass rate, 39 PASSED green, 1066 NEAR yellow)
- Reject depth bars visible with red horizontal pressure bars
- Symbol table rendered with sortable columns
- Bottom nav fixed at viewport bottom: HOME ● / FUNNEL ▼ / CANDS ≡ / REJ ✕ / SURV ★ / ...
- All numeric values monospace (DejaVu Sans Mono)

## Truthfulness Compliance

- No fake zero — `NO DATA` / `MISSING` / `NOT_REACHED` / `EMPTY_WITH_REASON` / `no survivors` distinct from numeric 0
- NOT_EVALUATED separate from REJECTED — separate topbar pills + separate arena VM fields
- Survivor strictly separate from near-survivor — two distinct `<table>` blocks on /survivors
- Survivor != Deployable — `zangetsu_status.deployable_count` = 0 unchanged
- A3 / A4 / A5 hard-coded NOT_REACHED in /funnel
- 5 freshness states (FRESH / STALE / OLD / MISSING / ERROR) — distinct colored tags

## Read-Only Defense in Depth (5 layers)

1. **HTTP layer**: `test_app_is_read_only_no_write_paths` enumerates routes; no POST/PUT/PATCH/DELETE
2. **Template layer**: only `<form method="get">`; no POST forms
3. **Code layer**: `test_no_write_call_patterns` greps for to_sql / .execute / subprocess / os.system / shutil.rmtree
4. **OS layer**: systemd `ProtectHome=read-only` + `ProtectSystem=strict` + `PrivateTmp=yes` + `NoNewPrivileges=yes`
5. **Network layer**: bind `100.123.49.102` (Tailscale only); no public exposure

## Tests

- Mobile contract suite: **10 / 10 PASSED**
- V2 terminal contract suite: **4 / 4 PASSED** (kept passing — kept for rollback)
- V1 dashboard view-model suite: **22 / 22 PASSED** (V3 reuses these view-models)
- core_factory regression: **54 / 54 PASSED**
- **Combined: 90 / 90 PASSED**

## Gemini UX Review

**`PASS`** (gemini-2.5-flash) — confirmed mobile-usable, dense, dark, observability-oriented, read-only.

## Internal Team Decision Discussion

All Category A/B autonomous decisions executed without owner ping:

1. (Category B) Drop Streamlit — V2 unusable on phone (owner verdict). Switch to FastAPI + Jinja2.
2. (Category A) Pure HTML/CSS over React + Vite — server-rendered HTML wins on mobile TTFB; no Node/npm/build pipeline.
3. (Category A) Auto-refresh via meta tag, not JS — no framework overhead.
4. (Category B) Same Tailscale URL via systemd drop-in — phone bookmark unchanged.
5. (Category A) Read-only enforced at 5 layers (HTTP / template / code / OS / network).
6. (Category A) Gemini retry with explicit "NOT OKX — borrow patterns" framing after first attempt's literal misread.

No Category C actions taken.

## Acceptance Criteria — All PASS

| AC | Status |
|---|---|
| AC1 — V2 article/streamlit replaced | PASS (V2 service stop+disabled; V3 runs on port 8785) |
| AC2 — pure black mobile UI | PASS (verified screenshot) |
| AC3 — sticky top status bar | PASS |
| AC4 — bottom fixed nav | PASS (7 tabs) |
| AC5 — Overview / Funnel / Candidates / Detail / Rejects / Survivors / Feedback / Health | PASS (8 pages) |
| AC6 — filters work | PASS (form GET) |
| AC7 — search works | PASS |
| AC8 — auto-refresh | PASS (meta http-equiv 30 s) |
| AC9 — freshness badges | PASS |
| AC10 — no fake zero | PASS (test) |
| AC11 — NOT_EVALUATED separate | PASS (test) |
| AC12 — Survivor separate from near | PASS (test) |
| AC13 — read-only at 5 layers | PASS (route test + pattern test + OS hardening + Tailscale-only bind) |
| AC14 — internal deployment | PASS (systemd active) |
| AC15 — screenshots captured | PASS (8 PNGs from headless Chrome at 390 px) |
| AC16 — tests pass | PASS (90/90 combined) |
| AC17 — Gemini UX review | PASS |
| AC18 — controlled diff forbidden_diff = 0 | PASS |

## Final Statement

ZANGETSU operator now has a true mobile-first observability dashboard at the same Tailscale URL the V1 and V2 dashboards used. V3 replaces Streamlit (which was unusable on phone — owner's verdict) with FastAPI + Jinja2 + pure HTML/CSS: pure black background, mobile viewport meta, sticky top status bar with 6 health pills, responsive KPI grid, fixed bottom nav with 7 tabs, 8 system views, auto-refresh every 30 s. Truthfulness contracts inherited unchanged from V1 (no fake zero, NOT_EVALUATED separate from REJECTED, survivor separate from near-survivor, survivor != deployable). Read-only enforced at 5 layers. systemd-hardened, Tailscale-only, 90/90 tests, Gemini PASS, forbidden_diff = 0.

## Next Order

This order is observability — does not produce a successor mining order. Mining mainline continues per parent chain:

```
0-9AE-C-AXIS-MINING-BATCH-2
```

The mobile dashboard surfaces 0-9AE outputs automatically when its recovery folder lands.
