# 02 — Round 1 Findings Summary

**ORDER**: 0-9AC-CLOSE — Phase 0 / Workstream A

## Round 1 (0-9AB) Outcome

Verdict: `MULTI_AXIS_CONTINUE_ONE_MORE_ROUND`

Triggers:
1. Scoreboard spread < 3 pts (C=89.12 / H=88.81 / D=86.21)
2. Gemini auth unavailable (verdict cap)

## Per-Axis Round 1 Issues

| Axis | Round 1 Score | Issue |
|---|---:|---|
| C | 89.12 | strongest score; baseline preserved; only +12.72 bps avg net on LONG side (3 PASSED) |
| H | 88.81 | numerical blow-up (avg net ±5000 bps from tanh ∘ protected_div compositions); 5 PASSED but unreliable |
| D | 86.21 | 0 PASSED; 174 near-survivors; sign-flip too sparse → 170/192 no_trades_generated |

## Lessons Carried Into Round 2

1. **Cap signal magnitude before computing trades** → motivates p99 clip for H.
2. **Sign-flip is too coarse for signals that drift slowly** → motivates band-crossing for D at multiple k values.
3. **3-symbol subset distorts cross-sectional rank** → motivates D all14 expansion.
4. **Gemini cap is binding** → motivates explicit env-loaded retry.
