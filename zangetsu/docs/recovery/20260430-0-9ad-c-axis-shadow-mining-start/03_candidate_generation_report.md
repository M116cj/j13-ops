# 03 — Candidate Generation Report

**ORDER**: 0-9AD — Phase 3

## Generation Counts

| Axis | Candidate Records | Unique Formulas | Collisions Dropped | Unsupported Operators |
|---|---:|---:|---:|---:|
| C | 1792 | 64 | 0 | 0 |

C total = 64 unique formulas × 14 symbols × 2 side modes = 1792.

## Identity Determinism

- alpha_hash = sha256(canonical_formula_text). Excludes timestamp / created_at / random seed.
- candidate_id = sha256(generation_id | axis | alpha_hash | symbol | timeframe | side_mode).
- Verified by test_alpha_hash_deterministic_excludes_timestamp + test_candidate_id_deterministic.

## Outputs

- `shadow_outputs/candidate_manifest.jsonl` — 1792 records.
- `shadow_outputs/formula_collision_report.csv` — 0 collisions / 0 unsupported ops.

## Acceptance Mapping

- AC5 PASS candidate_count target 1024 (achieved 1792)
- AC6 PASS minimum 512 (achieved 1792)
- AC7 PASS unique_formula_count = 64 (≥ 64)
- AC8 PASS formula_collision_rate reported (0)
- AC9 PASS unsupported_operator_count reported (0)
- AC10 PASS candidate_manifest.jsonl produced
- AC12 PASS every candidate has status (after Phase 4 evaluation)
