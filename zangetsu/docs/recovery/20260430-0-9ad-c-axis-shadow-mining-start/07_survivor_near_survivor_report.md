# 07 — Survivor / Near-Survivor Report

**ORDER**: 0-9AD — Phase 7

## Definitions

- **Survivor (PASSED)**: cleared shadow A2 gate (trade_count ≥ 25 AND total post-cost net > 0).
- **Near-survivor**: status == REJECTED AND net_bps in [-5.0, 0.0] (per survivor_bank.is_near_survivor).
- NOT_EVALUATED candidates are NEVER survivors or near-survivors.
- ERROR candidates are NEVER survivors or near-survivors.
- Survivors are NOT deployables — deployable_count semantics unchanged.

## Counts

| Class | Count |
|---|---:|
| Survivors (status = PASSED) | 39 |
| Near-survivors (REJECTED, net in [-5, 0]) | 1066 |
| NOT_EVALUATED | 0 |
| ERROR | 0 |

## Per-Side Survivors

| Side | Survivors | Near-survivors |
|---|---:|---:|
| LONG | 36 | 460 |
| SHORT | 3 | 606 |

## Best Symbols by Survivor Count

| Symbol | Survivors |
|---|---:|
| AVAXUSDT | 5 |
| SOLUSDT | 5 |
| AAVEUSDT | 4 |
| BNBUSDT | 4 |
| 1000SHIBUSDT | 3 |
| DOGEUSDT | 3 |
| ETHUSDT | 3 |
| 1000PEPEUSDT, BTCUSDT, FILUSDT, GALAUSDT, LINKUSDT, XRPUSDT | 2 each |
| DOTUSDT | 0 |

## Survivor Categories (per order §8.1)

- **A1 survivor**: all 39 candidates have a1_pass = True (trade_count ≥ 5).
- **A2 survivor**: all 39 cleared the shadow A2 gate.
- **A3 survivor**: not assessed in 0-9AD (out of scope; A3 / A4 / A5 require segmented holdout, deferred to scale-up order 0-9AE).
- **deployable candidate**: NONE — a survivor here is a candidate that could move to deeper Arena gates, NOT a champion. zangetsu_status.deployable_count remains 0.

## Outputs

- `shadow_outputs/survivor_report.csv` — 39 PASSED rows.
- `shadow_outputs/near_survivor_report.csv` — 1066 near-survivor rows.

## Acceptance Mapping

- AC17 PASS survivor_report.csv produced
- AC18 PASS near_survivor_report.csv produced
- (AC: no fake deployables) deployable_count VIEW = 0 unchanged
