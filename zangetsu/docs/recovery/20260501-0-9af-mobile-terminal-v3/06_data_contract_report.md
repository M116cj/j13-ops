# 06 — Data Contract Report (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 3

## Source Inventory (UNCHANGED from V1/V2)

V3 reads exactly the same artifacts V1 and V2 already proved correct. No new contract risk introduced.

| Key | Path under shadow_outputs/ | V3 page(s) using it |
|---|---|---|
| candidate_manifest | candidate_manifest.jsonl | /candidate/{cid} (formula/grammar/primitive lookup) |
| shadow_batch_results | shadow_batch_results.jsonl | / + /funnel + /candidates + /candidate/{cid} + /rejects + /survivors |
| reject_reason_summary | reject_reason_summary.json | / (top reject reasons) + /funnel (depth) |
| long_short_summary | long_short_summary.csv | (loaded by view-models; not directly rendered in V3) |
| survivor_report | survivor_report.csv | /survivors |
| near_survivor_report | near_survivor_report.csv | /survivors |
| feedback_weights | feedback_weights.json | /feedback |
| next_batch_weights | next_batch_weights.json | /feedback (recommended actions) |
| formula_collision_report | formula_collision_report.csv | (available; not yet rendered in V3) |
| axis_scoreboard | axis_scoreboard.csv | (available; not yet rendered) |
| run_summary | run_summary.json | / + topbar (axes, a2_min_trades) |

## Latest-Batch Discovery

Each request calls `load_latest_batch()` which selects the most recent `docs/recovery/*-shadow*` folder. (V1/V2 had a sidebar selector; V3 keeps it implicit on mobile to maximize content area — operator can pin specific historical folders in a future V3.1.)

## Freshness Semantics (UNCHANGED)

| State | Threshold | Topbar pill | /health table tag |
|---|---|---|---|
| FRESH | age ≤ 6h | green | green |
| STALE | 6h < age ≤ 3d | yellow | yellow |
| OLD | age > 3d | red | red |
| MISSING | file does not exist | gray | gray |
| ERROR | stat() fails | red | red |

## Parser State Semantics

`OK / EMPTY / MISSING / ERROR` — same as V1, surfaced via `<span class="tag">` badges on /health.
