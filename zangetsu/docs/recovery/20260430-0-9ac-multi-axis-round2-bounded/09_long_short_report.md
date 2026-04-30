# 09 — Long / Short Report

**ORDER**: 0-9AC-CLOSE — Workstream E

## Per-(axis, intended_side_mode)

| Axis | Mode | n | PASSED | REJECTED | Realized LONG trades | Realized SHORT trades |
|---|---|---:|---:|---:|---:|---:|
| C | LONG | 96 | 9 | 87 | 565,679 | 0 |
| C | SHORT | 96 | 0 | 96 | 0 | 559,696 |
| D | LONG | 448 | 0 | 448 | 1,789,733 | 0 |
| D | SHORT | 448 | 0 | 448 | 0 | 1,830,355 |
| H | LONG | 96 | 11 | 85 | 195,450 | 0 |
| H | SHORT | 96 | 0 | 96 | 0 | 264,587 |

## Side-Specific Notes

- **C-LONG** is the only axis-side with non-zero PASSED count besides H-LONG: 9 PASSED out of 96 candidates with avg net_bps positive (see 13 scoreboard).
- **C-SHORT** all rejected; consistent with Round 1 finding that regime-conditional SHORT side is harder to gate cleanly.
- **D LONG/SHORT** both 0 PASSED. Band-crossing produced ~3.6M total trades but per-trade gross stayed below cost. Universe expansion to 14 symbols increased trade volume but did not invert cost wall.
- **H-LONG** 11 PASSED with p99 clip applied. Compared to Round 1, blow-ups are bounded but residual outliers remain (correction_success 5/10).

## Realized vs Intended Side

LONG-mode candidates produced 0 short trades; SHORT-mode candidates produced 0 long trades. Verified by aggregate; no fabrication.

## Acceptance Mapping

- AC18 PASS intended_side_mode preserved
- AC19 PASS realized counts not fabricated (different per axis-side, derived from simulator)
- AC21 PASS long/short report produced (this file + long_short_summary.csv)
