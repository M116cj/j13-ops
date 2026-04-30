# 09 — Next-Batch Weights Report

**ORDER**: 0-9AD — Phase 8

## Generation Rule (next_batch_weights.next_batch_weights_from_summary)

Maps reject_reasons in this batch to recommended generator-weight deltas for the NEXT batch, per order §9. Refuses to fabricate when rejected_total == 0 (returns EMPTY_WITH_REASON).

## Overall (from 1753 evaluated rejections, status = OK)

| Reason | Share | Failure Mode | Action | Grammar Weight Δ |
|---|---:|---|---|---:|
| no_trades_generated | 60.4% | NO_TRADES_GENERATED | increase_trigger_density_or_adjust_regime_condition | -0.10 |
| non_positive_net | 33.4% | TRAIN_NEG_PNL | reduce_similar_grammar_family | -0.20 |
| too_few_trades | 6.3% | SIGNAL_TOO_SPARSE | increase_denser_signal_variants | -0.15 |

## Recommended Actions for 0-9AE (above 5% share threshold)

Sorted by share descending:

1. **NO_TRADES_GENERATED** (60.4% share) → bias C-grammar toward formulas with denser sign-changes; reduce families that consistently produce flat/monotonic signals.
2. **TRAIN_NEG_PNL** (33.4%) → penalise grammar branches whose firing trades net-negative pre-validation; tighten regime gate.
3. **SIGNAL_TOO_SPARSE** (6.3%) → add denser windows (e.g., w=5/10) for ts ops; reduce w=60 variants.

UNKNOWN_REJECT: 0 → no taxonomy gap requires expansion this batch.

## Per-Axis

`per_axis.C` = same as overall (single axis).

## Boundary Compliance

- next_batch_weights are **input to the next generator batch only**, not a deployable signal.
- They do NOT change Arena thresholds, A2_MIN_TRADES, champion promotion, or deployable_count semantics.
- Future scale-up (0-9AE) MAY use these deltas to bias formula sampling weights inside combination_grammar; the deltas do NOT modify the grammar source code or formula primitives in this PR.

## Acceptance Mapping

- AC20 PASS next_batch_weights.json produced
