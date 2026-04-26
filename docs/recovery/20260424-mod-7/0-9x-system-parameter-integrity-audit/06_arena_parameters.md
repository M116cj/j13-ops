# 06 — Arena Parameter Audit

## 1. A2 Thresholds

| Parameter | Source | Value | Frozen |
| --- | --- | --- | --- |
| `A2_MIN_TRADES` | `zangetsu/services/arena_gates.py:48` | **25** | YES (matches expected) |
| `A2_MIN_TRADES` (settings.py mirror) | `zangetsu/config/settings.py:29` | **25** | aligned via Patch H1 (2026-04-20) |
| `A2_MIN_TOTAL_PNL` (j01) | `j01/config/thresholds.py` | 0.0 | YES |
| `A2_MIN_TOTAL_PNL` (j02) | `j02/config/thresholds.py` | 0.0 | YES |
| Test enforcement | `tests/test_arena_pass_rate_telemetry.py:422` | A2_MIN_TRADES = 25 | YES |

→ **A2_MIN_TRADES = 25 confirmed unchanged across 4 source-code locations and 1 test.** No drift.

## 2. A3 Thresholds (per-strategy)

| Parameter | j01 | j02 |
| --- | --- | --- |
| `A3_SEGMENTS` | 5 | 5 |
| `A3_MIN_TRADES_PER_SEGMENT` | 15 | 15 |
| `A3_WR_FLOOR` | 0.45 | 0.45 |
| `A3_MIN_WR_PASSES` | 4 | 4 |
| `A3_MIN_PNL_PASSES` | 4 | 4 |

## 3. A4 Thresholds (regime stability)

| Parameter | j01 |
| --- | --- |
| `A4_REGIME_WR_FLOOR` | 0.40 |
| `A4_MIN_TRADES_PER_REGIME` | 10 |
| `A4_MIN_OTHER_REGIMES_PASS` | 1 |

## 4. A5 Thresholds (paper-trade shadow)

| Parameter | j01 |
| --- | --- |
| `A5_WINDOW_DAYS` | 14 |
| `A5_MIN_TRADES` | 30 |
| `A5_WR_FLOOR` | 0.45 |
| `A5_MIN_TOTAL_PNL` | 0.0 |
| `A5_MAX_CONSECUTIVE_NEG_DAYS` | 3 |

## 5. Champion Promotion / Deployable

`zangetsu/services/feedback_decision_record.py:38` references `A2_MIN_TRADES_UNCHANGED` as a CODE_FROZEN field — this is a governance marker that the A2 gate should not be modified.

The deployable_count materialization path (per VERSION_LOG v0.7.1) was supposed to use `champion_pipeline_fresh` table + `admission_validator` function. Phase 7 confirms **these database objects do NOT exist** in the current Postgres state.

## 6. Rejection Taxonomy / UNKNOWN_REJECT Handling

Per `arena_pipeline.py` and related code:
- Reject reasons emitted in `arena_batch_metrics` event include `COST_NEGATIVE`, `COUNTER_INCONSISTENCY`, `SIGNAL_TOO_SPARSE`, `INVALID_FORMULA`
- Validation-stage rejects: `reject_val_constant`, `reject_val_error`, `reject_val_few_trades`, `reject_val_neg_pnl`, `reject_val_low_sharpe`, `reject_val_low_wr`
- An `UNKNOWN_REJECT` register existed in earlier orders — current batch metrics show 0 unknown rejects, which is good

## 7. Telemetry Emission

`engine_telemetry` table inserts attempted at `arena_pipeline.py:329` — **wrapped in `try/except ... pass`**. If the table doesn't exist (Phase 7 confirms it doesn't), failures are silently swallowed. Counters continue running in-memory but never persist.

## 8. Special Confirmations Per Order

| Confirmation | Status |
| --- | --- |
| A2_MIN_TRADES = 25 | YES |
| No Arena threshold weakening since prior order | confirmed (j01 thresholds.py + arena_gates.py + settings.py all match approved values) |
| No pass/fail semantics drift | confirmed |
| No deployable_count semantics drift | partial — semantics intact in CODE, but DB pipeline path is broken (Phase 7) |
| `UNKNOWN_REJECT` controlled | YES (0 unknown in current batch) |

## 9. Classification

| Verdict | Match? |
| --- | --- |
| **ARENA_PARAMS_OK** | **YES** — all numeric thresholds intact |
| ARENA_THRESHOLD_DRIFT | NO |
| **ARENA_TELEMETRY_RISK** | **YES** — `engine_telemetry` insert silently swallows exceptions; insert target table does not exist |
| ARENA_UNKNOWN | NO |

→ **Phase 6 verdict: ARENA_PARAMS_OK + ARENA_TELEMETRY_RISK.** Arena threshold values are unchanged and protected. However, the silent telemetry insert failure is a YELLOW finding that compounds the Phase 7 DB schema gap.
