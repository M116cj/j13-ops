# 02 — C-Axis Mining Design

**ORDER**: 0-9AD — Phase 2

## Run Parameters

```
generation_id:    0-9ad-c-axis-mining-v1
axis:             C (Regime Conditional)
mode:             SHADOW ONLY
candidate target: 1024 (achieved: 1792 — 64 unique formulas × 14 symbols × 2 side modes)
unique formula:   64 target met
symbols:          14-symbol universe (all available in zangetsu/data/ohlcv/)
timeframe:        15m
side modes:       LONG, SHORT
trigger:          sign_flip (axis-C default)
value clip:       not applied for axis C
cost (round-trip): 14.5 bps
```

## 14-Symbol Universe

```
1000PEPEUSDT, 1000SHIBUSDT, AAVEUSDT, AVAXUSDT, BNBUSDT, BTCUSDT,
DOGEUSDT, DOTUSDT, ETHUSDT, FILUSDT, GALAUSDT, LINKUSDT, SOLUSDT, XRPUSDT
```

## Exact Command Used

```
python -m zangetsu.core_factory.shadow_batch_runner \
  --mode shadow \
  --generation-id 0-9ad-c-axis-mining-v1 \
  --candidate-count-per-axis 1792 \
  --axes C \
  --symbols 1000PEPEUSDT,1000SHIBUSDT,AAVEUSDT,AVAXUSDT,BNBUSDT,BTCUSDT,DOGEUSDT,DOTUSDT,ETHUSDT,FILUSDT,GALAUSDT,LINKUSDT,SOLUSDT,XRPUSDT \
  --timeframe 15m \
  --output zangetsu/docs/recovery/20260430-0-9ad-c-axis-shadow-mining-start/shadow_outputs/
```

(Note: `--candidate-count-per-axis 1792` chosen so that with 14 × 2 = 28 (symbol × side) expansion, formulas_per_axis math yields exactly 64 unique C-axis formulas.)

## C Grammar Family (combination_grammar._grammar_C)

C-axis grammar: nested time-series transforms over OHLCV — leaf field → ts_unary → unary_transform → ts_unary. Uses 4 ts ops (delta / ts_mean / ts_std / ts_rank) × 4 windows (5/10/20/60) × 3 transforms (neg/sign/tanh) over 5 base fields (open/high/low/close/volume). Theoretical formula space ≫ 64; 64 unique drawn deterministically by seeded RNG.

## Evaluation Method

`zangetsu.core_factory.economic_arena_adapter.evaluate_candidate`:
1. Load OHLCV parquet (cached per symbol).
2. Resample 1m → 15m via timestamp bucket aggregation.
3. Walk AST against curated primitive inventory (fail-closed on unsupported ops).
4. Generate trades via signal sign-flip filtered by intended_side_mode.
5. Compute net_bps = mean(returns) − round-trip cost (14.5 bps).
6. Apply A2 gate: trade_count ≥ 25 AND total_pnl − cost > 0.
7. Status PASSED / REJECTED with reject_reason / NOT_EVALUATED with blocker_reason / ERROR.

## Feedback Method

`rejection_feedback.summarize_reject_reasons` + `rejection_feedback.feedback_weights_from_summary` → `feedback_weights.json`.
`next_batch_weights.next_batch_weights_from_summary` → `next_batch_weights.json` mapping reject reasons to generator-weight adjustments per order §9.

## Identity Rules

- alpha_hash = sha256(canonical_formula_text); excludes timestamp/created_at.
- candidate_id = sha256(generation_id | axis | alpha_hash | symbol | timeframe | side_mode).
- Verified by tests `test_alpha_hash_deterministic_excludes_timestamp`, `test_candidate_id_deterministic`, `test_candidate_id_differs_by_axis`.
