# 13 — Axis Scoreboard

**ORDER**: 0-9AC-CLOSE — Workstream E

## Round 2 Final Ranking

| Rank | Axis | Total | Generation | Diversity | L/S Bal | Econ | Cost | Reject Q | Feedback | Correction |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **C** | **99.10** | 15.00 | 15.00 | 9.89 | 14.21 | 15.00 | 10.00 | 10.00 | **10.00** |
| 2 | **H** | **91.70** | 15.00 | 15.00 | 7.39 | 14.31 | 15.00 | 10.00 | 10.00 | **5.00** |
| 3 | **D** | **89.31** | 15.00 | 15.00 | 9.78 | 14.53 | 12.00 | 10.00 | 10.00 | **3.00** |

(Score totals exceed 100 because round-2 adds the 10-pt correction_success category — ceiling = 110.)

## Spread

- C – H gap = **7.40** points (≥ 3.0 → winner threshold satisfied)
- C – D gap = 9.79 points
- H – D gap = 2.39 points

## Selection Verdict

Per order §12 + AC32:
- C lead = 7.40 ≥ 3.0  ✓
- Gemini = PASS (see 14)  ✓
- Tests 50/50 PASS  ✓
- forbidden_diff = 0 (see 15)  ✓
- Axis has valid Economic Arena evaluation (192/192 evaluated)  ✓
- Axis does not win solely from unevaluated candidates (9 PASSED + 95 near-survivors)  ✓

→ `AXIS_C_SELECTED_FOR_SCALEUP`

## Acceptance Mapping

- AC31 PASS axis scoreboard ranks H/C/D
- AC32 PASS winner selected with score lead ≥ 3.0 AND Gemini PASS
