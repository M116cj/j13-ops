# 07 — Candidate Generation Report

**ORDER**: 0-9AC-CLOSE — Workstream E

## Generation Counts

| Axis | Candidate Records | Unique Formulas | Collisions Dropped | Unsupported Operators |
|---|---:|---:|---:|---:|
| H | 192 | 32 | 0 | 0 |
| C | 192 | 32 | 0 | 0 |
| D | 896 | 32 | 0 | 0 |
| **Total** | **1280** | **96** | **0** | **0** |

D total = 32 unique formulas × 14 symbols × 2 sides = 896.

## Identity Determinism (preserved from 0-9AB)

- alpha_hash = sha256(canonical_formula_text). No timestamp, no created_at.
- candidate_id = sha256(generation_id | axis_id | alpha_hash | symbol | timeframe | intended_side_mode).
- Verified by tests: `test_alpha_hash_deterministic_excludes_timestamp`, `test_candidate_id_deterministic`, `test_candidate_id_differs_by_axis`.

## Outputs

- `shadow_outputs/candidate_manifest.jsonl` — 1280 records
- `shadow_outputs/formula_collision_report.csv` — 0 collisions / 0 unsupported per axis

## Acceptance Mapping

- AC13 PASS H ≥ 192 (192)
- AC14 PASS C ≥ 192 (192)
- AC15 PASS D ≥ 192 plus all14 coverage (896 + d_symbol_coverage.csv)
- AC16 PASS candidate_manifest.jsonl produced
- AC17 PASS alpha_hash deterministic
- AC18 PASS candidate_id deterministic
- AC19 PASS formula collision rate reported (0 per axis)
- AC20 PASS unsupported operators fail closed (0 in this run)
