# 05 — D Universe Expansion Report

**ORDER**: 0-9AC-CLOSE — Workstream D

## Universe

D was expanded to all 14 available symbols (already in zangetsu/data/ohlcv/):

```
1000PEPEUSDT, 1000SHIBUSDT, AAVEUSDT, AVAXUSDT, BNBUSDT, BTCUSDT,
DOGEUSDT, DOTUSDT, ETHUSDT, FILUSDT, GALAUSDT, LINKUSDT, SOLUSDT, XRPUSDT
```

No external data source added. No orderbook / trade-print dependency.

## CLI

`--d-symbol-mode all14`

Implementation: `zangetsu.core_factory.shadow_batch_runner._symbols_for_axis` returns ALL14_SYMBOLS only when `axis_id == 'D'` and mode == 'all14'. H and C remain on 3-symbol base set.

## Per-Symbol Coverage (shadow_outputs/d_symbol_coverage.csv)

D candidate count per symbol = 64 (32 unique formulas × 2 side modes).
Total D candidates = 14 × 64 = 896.

## Tests

`zangetsu/tests/test_core_factory_d_universe_expansion.py`:

- `test_all14_count`: ALL14_SYMBOLS has 14 entries
- `test_d_uses_all14_when_mode_set`: D respects all14 mode
- `test_d_default_mode_uses_base`: D respects default mode
- `test_h_c_unchanged_by_d_symbol_mode`: H/C symbol set NOT affected

All 4 tests PASS.

## Acceptance Mapping

- AC12 PASS D expanded to all 14 available symbols
- AC15 PASS D ≥ 192 records + all14 coverage report (D = 896 records)
