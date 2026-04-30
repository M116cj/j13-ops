# 04 — Candidate Generation Report

**ORDER**: 0-9AB — Workstream D

## Run Parameters

- generation_id: 0-9ab-shadow-v1
- axes: H, C, D
- symbols: BTCUSDT, ETHUSDT, SOLUSDT
- timeframe: 15m
- side modes: LONG, SHORT
- target per-axis: 128 (expanded to 192 via 32 formulas × 3 symbols × 2 side modes)
- unique-formula target: 32 per axis

## Generation Counts

| Axis | Candidate Records | Unique Formulas | Collisions Dropped | Unsupported Operators |
|---|---:|---:|---:|---:|
| H | 192 | 32 | 0 | 0 |
| C | 192 | 32 | 0 | 0 |
| D | 192 | 32 | 0 | 0 |
| **Total** | **576** | **96** | **0** | **0** |

192 records per axis = 32 unique formulas × 3 symbols × 2 side modes. Exceeds AC8/9/10 minimum of 128 and AC11 minimum of 384. Unique-formula target of 32 met per axis (AC12).

## Identity Determinism Checks

- alpha_hash = sha256(canonical_formula_text) — verified by test_alpha_hash_deterministic_excludes_timestamp.
- candidate_id = sha256(generation_id | axis | alpha_hash | symbol | timeframe | side_mode) — verified by test_candidate_id_deterministic and test_candidate_id_differs_by_axis.

## Outputs

- shadow_outputs/candidate_manifest.jsonl — 576 records.
- shadow_outputs/formula_collision_report.csv — 0 collisions, 0 unsupported operators per axis.

## Acceptance Mapping

- AC8 PASS H = 192 ≥ 128
- AC9 PASS C = 192 ≥ 128
- AC10 PASS D = 192 ≥ 128
- AC11 PASS total = 576 ≥ 384
- AC12 PASS unique formulas = 32 per axis ≥ 32
- AC13 PASS candidate_manifest.jsonl produced
- AC14 PASS alpha_hash deterministic
- AC15 PASS candidate_id deterministic
- AC16 PASS formula collision rate reported (0/192 per axis)
- AC17 PASS unsupported operators fail closed (0 in this run)
- AC18 PASS intended side metadata preserved
