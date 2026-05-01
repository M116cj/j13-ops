# 06 — Data Contract Report

**ORDER**: 0-9AF-REDESIGN — Phase 3

## Source Inventory (reused from V1; no new contract)

The terminal reads the SAME 11 artifacts the V1 dashboard already proved correct, plus `run_summary.json`. Contracts are unchanged → no new contract risk introduced by V2.

| Key | Path under shadow_outputs/ | Parser | Used by terminal |
|---|---|---|---|
| candidate_manifest | candidate_manifest.jsonl | parse_jsonl | drawer (formula / grammar / primitive lookup) |
| shadow_batch_results | shadow_batch_results.jsonl | parse_jsonl | KPI strip, funnel, depth, candidates tab, drawer |
| reject_reason_summary | reject_reason_summary.json | parse_json | reject depth panel, rejects tab |
| long_short_summary | long_short_summary.csv | parse_csv | (available for future per-side trend tab) |
| survivor_report | survivor_report.csv | parse_csv | survivors tab |
| near_survivor_report | near_survivor_report.csv | parse_csv | survivors tab |
| feedback_weights | feedback_weights.json | parse_json | feedback tab |
| next_batch_weights | next_batch_weights.json | parse_json | feedback tab — recommended actions |
| formula_collision_report | formula_collision_report.csv | parse_csv | (available for V2.1 unique-formula widget) |
| axis_scoreboard | axis_scoreboard.csv | parse_csv | (available for multi-axis trend) |
| run_summary | run_summary.json | parse_json | top status bar, KPI strip |

## Latest-Batch Discovery

Sidebar lists ALL recovery folders sorted by name DESC. Default selection: most recent folder containing 'shadow' (currently `20260430-0-9ad-c-axis-shadow-mining-start`). Operator can pick any historical batch.

## Freshness Semantics (unchanged from V1)

| State | Threshold | UI tag |
|---|---|---|
| FRESH | age ≤ 6h | green badge |
| STALE | 6h < age ≤ 3d | yellow badge |
| OLD | age > 3d | red badge |
| MISSING | file does not exist | gray NA badge |
| ERROR | stat() fails | red ERROR badge |

## Parser Semantics (unchanged from V1)

`OK / EMPTY / MISSING / ERROR` — see V1 `parsers.py`. The terminal renders them as colored badges in the System Health tab and as conditional "NO DATA" / "NO REJECTED CANDIDATES" / etc. text in each panel.
