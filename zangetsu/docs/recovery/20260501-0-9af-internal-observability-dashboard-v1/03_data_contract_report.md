# 03 — Data Contract Report

**ORDER**: 0-9AF — Phase 3

## Source Inventory

| Key | Path (under shadow_outputs/) | Parser | Required fields |
|---|---|---|---|
| candidate_manifest | candidate_manifest.jsonl | parse_jsonl | candidate_id, axis_id, alpha_hash, symbol, timeframe, intended_side_mode, grammar_family, primitive_family, formula |
| shadow_batch_results | shadow_batch_results.jsonl | parse_jsonl | candidate_id, axis_id, status, reject_reason, blocker_reason, gross_bps, net_bps, trade_count, long_trade_count, short_trade_count, a1_pass, a2_pass |
| reject_reason_summary | reject_reason_summary.json | parse_json | overall.rejected_total, overall.rejected_by_reason, overall.unknown_reject_count |
| long_short_summary | long_short_summary.csv | parse_csv | axis_id, intended_side_mode, n_*, avg_*_bps |
| survivor_report | survivor_report.csv | parse_csv | candidate_id (+) status PASSED rows |
| near_survivor_report | near_survivor_report.csv | parse_csv | candidate_id, net_bps in [-5, 0] |
| feedback_weights | feedback_weights.json | parse_json | overall.status, overall.weights |
| next_batch_weights | next_batch_weights.json | parse_json | overall.status, overall.recommended_actions |
| formula_collision_report | formula_collision_report.csv | parse_csv | axis_id, collisions_dropped, unsupported_operator_count, unique_formulas_kept |
| axis_scoreboard | axis_scoreboard.csv | parse_csv | axis_id, total, rank |
| run_summary | run_summary.json | parse_json | a2_min_trades, axes, candidates_total, overall_reject_summary |

## Parser State Semantics

| State | Meaning | UI rendering |
|---|---|---|
| OK | file exists, parsed, ≥ 1 row | normal render |
| EMPTY | file exists, parses, 0 rows | 'No rows' info |
| MISSING | file does not exist | 'NO DATA' badge |
| ERROR | parse failure | 'ERROR' badge + note |

## Freshness State Semantics

| State | Threshold |
|---|---|
| FRESH | age ≤ 6h |
| STALE | 6h < age ≤ 3d |
| OLD | age > 3d |
| MISSING | file does not exist |
| ERROR | stat() failure |

## Latest Batch Discovery

`load_latest_batch()` selects the most recent `docs/recovery/*-shadow*` folder. If none, falls back to the most recent recovery folder of any kind. Operator can override by reading from a specific folder via `load_batch_from_folder(path)`.
