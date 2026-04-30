# 06 — Round 2 Tournament Design

**ORDER**: 0-9AC-CLOSE — Workstream E

## Run Parameters

```
generation_id:                0-9ac-round2
candidate-count-per-axis:     192
axes:                         H, C, D
symbols (H, C):               BTCUSDT, ETHUSDT, SOLUSDT
symbols (D, all14):           14 symbols (see 05)
timeframe:                    15m
side modes:                   LONG, SHORT
unique-formula target / axis: 32
H value clip:                 p99_abs
D trigger:                    band_crossing
D band_k list:                0.5, 1.0, 1.5
Rolling sigma window:         20
```

## Exact Command Used

```
python -m zangetsu.core_factory.shadow_batch_runner \
  --mode shadow \
  --generation-id 0-9ac-round2 \
  --candidate-count-per-axis 192 \
  --axes H,C,D \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT \
  --d-symbol-mode all14 \
  --timeframe 15m \
  --h-value-clip p99_abs \
  --d-trigger band_crossing \
  --d-band-k 0.5,1.0,1.5 \
  --output zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/shadow_outputs/
```

## Scoring (Round 2 weights, total 110 incl. correction bonus)

| Category | Weight |
|---|---:|
| candidate_generation_success | 15 |
| formula_diversity | 15 |
| long_short_balance | 10 |
| economic_result_quality | 25 |
| cost_robustness | 15 |
| reject_reason_quality | 10 |
| feedback_usability | 10 |
| **correction_success** (new) | **10** |
| Total | **110** |

Correction success rule:

| Axis | Metric | Score Mapping |
|---|---|---|
| H | numeric blow-up resolved | 10 if no \|net\|>1000 in any candidate; 5 otherwise |
| C | baseline preserved | 10 (always; C had no Round-1 issue requiring correction) |
| D | no_trades_generated reduced | 10 if share < 50%; 7 if < 80%; 3 otherwise |

## Selection Rule

Per order §12: winner selected if score lead ≥ 3.0 AND Gemini PASS / PASS_WITH_NOTES.

If lead < 3.0 → MULTI_AXIS_CONTINUE_ONE_FINAL_ROUND
If lead ≥ 3.0 but Gemini unavailable → MULTI_AXIS_CONTINUE_ONE_FINAL_ROUND (or owner override per §4.2)
If lead ≥ 3.0 AND Gemini PASS → AXIS_C_SELECTED_FOR_SCALEUP
