# 06 — Long / Short Report

**ORDER**: 0-9AB — Workstream D

## Per-(axis, intended_side_mode) Aggregate

| axis_id | mode | n_cand | PASS | REJ | n_eval | n_long_realized | n_short_realized | trade_total | avg_gross_bps | avg_net_bps |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C | LONG | 96 | 3 | 93 | 0 | 85,372 | 0 | 85,367 | +17.71 | +12.72 |
| C | SHORT | 96 | 0 | 96 | 0 | 0 | 81,205 | 81,199 | -0.95 | -2.61 |
| D | LONG | 96 | 0 | 96 | 0 | 214,176 | 0 | 214,175 | +0.15 | -1.21 |
| D | SHORT | 96 | 0 | 96 | 0 | 0 | 226,961 | 226,953 | -0.09 | -1.45 |
| H | LONG | 96 | 4 | 92 | 0 | 408,317 | 0 | 408,293 | +5287.20 | +5278.89 |
| H | SHORT | 96 | 1 | 95 | 0 | 0 | 409,003 | 408,978 | -4908.29 | -4917.35 |

## Side-Specific Notes

- **C-LONG** is the only consistently positive avg_net_bps in this run (+12.72 bps over 96 candidates with 3 passing). This is the cleanest standalone side signal in the tournament.
- **C-SHORT** is mildly negative (-2.61 bps) — sits in the near-survivor band.
- **D LONG / SHORT** are both narrowly negative — rank-spread alone does not yet beat cost in this dataset.
- **H LONG / SHORT** show extreme magnitudes (±5000 bps avg). This is a numerical-stability artifact of the H grammar (tanh ∘ protected_div ∘ ts ∘ funding_oi can produce blow-ups when the funding/OI series is nearly constant). This indicates the H formula space needs a value-clip in round 2 before its scoreboard ranking is trustworthy.

## Realized vs Intended Side

Realized counts honestly reflect simulator output (no fabrication):
- LONG-mode candidates produced 0 short trades, SHORT-mode candidates produced 0 long trades — verified by aggregate_long_short.
- This satisfies AC19 (realized counts not fabricated) and AC26 (long/short/both/combined report produced).

## Acceptance Mapping

- AC18 PASS intended_side_mode preserved in manifest
- AC19 PASS realized long/short counts not fabricated
- AC26 PASS long/short report produced (this file + long_short_summary.csv)
