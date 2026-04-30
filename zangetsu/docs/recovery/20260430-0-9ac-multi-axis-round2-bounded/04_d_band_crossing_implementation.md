# 04 — D Band-Crossing Implementation

**ORDER**: 0-9AC-CLOSE — Workstream C

## Module

`zangetsu/core_factory/signal_processing.py` — `signal_to_trades_band_crossing(signal, close, intended_side_mode, *, band_k, rolling_sigma_window)`

## Algorithm

1. Compute rolling std of signal over `rolling_sigma_window` bars (causal, NaN-safe via 0-fill).
2. Bands: upper = +band_k × rolling_std, lower = -band_k × rolling_std.
3. LONG entry: signal crosses up through upper band (and prior bar was at/below).
4. SHORT entry: signal crosses down through lower band.
5. LONG exit: signal returns to ≤ 0 OR crosses below lower band → flip-to-short permitted.
6. SHORT exit: signal returns to ≥ 0 OR crosses above upper band → flip-to-long permitted.
7. Skip bars where rolling_std ≤ 0 (band undefined).

## CLI Flags

```
--d-trigger band_crossing
--d-band-k 0.5,1.0,1.5
--rolling-sigma-window 20
```

Main D pass uses median k (= 1.0). The runner additionally evaluates a sample
of D formulas at k = 0.5 and k = 1.5 for the d_band_crossing_report.csv.

## Metadata (in shadow_batch_results.jsonl per row)

`trigger_type`: "band_crossing" / "sign_flip"
`band_k`: <float>

## Tests Proving Behavior

`zangetsu/tests/test_core_factory_band_crossing.py`:

- `test_band_crossing_generates_trades`: produces > 0 trades on a normal random signal
- `test_band_crossing_supports_three_k_values`: k = 0.5 produces ≥ k = 1.5 triggers (monotonic)
- `test_band_crossing_long_mode_excludes_shorts`: LONG mode → 0 short trades
- `test_band_crossing_short_mode_excludes_longs`: SHORT mode → 0 long trades

All 4 tests PASS.

## Round 2 Headline (d_band_crossing_report.csv)

Per-band aggregate over 32 D unique formulas × BTCUSDT × LONG sample:

| band_k | samples | n_passed | n_no_trades | n_other_rej | mean_trade_count | mean_net_bps |
|---:|---:|---:|---:|---:|---:|---:|
| 0.5 | 32 | (see csv) | (see csv) | (see csv) | highest | varies |
| 1.0 | 32 | (see csv) | (see csv) | (see csv) | medium | varies |
| 1.5 | 32 | (see csv) | (see csv) | (see csv) | lowest | varies |

(Numbers in machine output `shadow_outputs/d_band_crossing_report.csv`.)

## Acceptance Mapping

- AC9 PASS D band-crossing implemented
- AC10 PASS k = 0.5 / 1.0 / 1.5 supported
- AC11 PASS no_trades_generated reported per band
