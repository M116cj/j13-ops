# 02 — Axis Tournament Design

**ORDER**: 0-9AB — Workstream A

## Tournament Setup

| Parameter | Value |
|---|---|
| generation_id | `0-9ab-shadow-v1` |
| candidate-count-per-axis target | 128 |
| symbols | BTCUSDT, ETHUSDT, SOLUSDT |
| timeframe | 15m |
| side modes | LONG, SHORT |
| total candidate target | ≥ 384 (3 axes × 128) |
| unique-formula target per axis | 32 |
| round-trip cost | 14.5 bps (anchored from 0-9Z) |
| evaluator | shadow Economic Arena adapter (no DB write, no API) |

## Axis Roles

| Axis | Role | Components |
|---|---|---|
| H | primary | regime gate × funding/OI direction × cross-sectional rank |
| C | shadow | regime conditional |
| D | shadow | cross-sectional rank |
| E | fallback | liquidity / volume shock (used only if H/C/D fail core-factory) |
| A | deferred | microstructure imbalance (data-blocked, held for 0-9ZB) |

## Evaluation Pipeline

```
Formulas (per axis)
  -> CandidateRecord = formula × symbol × timeframe × intended_side_mode × axis
  -> evaluate_candidate(load OHLCV/funding/OI -> evaluate AST -> sign-flip trades -> arena_gates A2)
  -> EvaluationResult.status ∈ {PASSED, REJECTED, ERROR, NOT_EVALUATED}
```

## Scoring Weights (out of 100)

| Category | Weight |
|---|---:|
| candidate_generation | 15 |
| formula_diversity | 15 |
| long_short_balance | 10 |
| economic_result_quality | 25 |
| cost_robustness | 15 |
| reject_reason_quality | 10 |
| feedback_usability | 10 |

## Falsification Anchors (from 0-9AA Phase 8)

| Axis | Reference |
|---|---|
| H | gross-per-trade ≥ 25 bps |
| C | gross-per-trade ≥ 25 bps |
| D | rank spread ≥ 30 bps |

These are **signal-quality references**, not deployment claims.
