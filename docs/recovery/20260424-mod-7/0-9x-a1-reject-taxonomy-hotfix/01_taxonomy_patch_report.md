# 01 — Taxonomy Patch Report

Order: TEAM ORDER 0-9X-A1-REJECT-TAXONOMY-HOTFIX
Phase: 1 + 2 (combined: confirmation + patch)
Date (UTC): 2026-04-27
Author: Claude Lead

## Before patch

### `RAW_TO_REASON` membership (verified by direct module import on Mac at `9f4bf8a`)

```python
from zangetsu.services.arena_rejection_taxonomy import classify, RAW_TO_REASON

>>> "reject_train_neg_pnl" in RAW_TO_REASON
False
>>> "reject_combined_sharpe_low" in RAW_TO_REASON
False
>>> classify("reject_train_neg_pnl")[0].value
"UNKNOWN_REJECT"
>>> classify("reject_combined_sharpe_low")[0].value
"UNKNOWN_REJECT"
>>> len(RAW_TO_REASON)
22
```

Both PR #43 keys absent → fall through `classify()` → `UNKNOWN_REJECT`. Diagnosis confirmed; matches previous order's findings.

### Target mapping plan

| Stats key | Existing closest analogue | Target canonical reason | Justification |
|---|---|---|---|
| `reject_train_neg_pnl` | `reject_neg_pnl` (line 248), `reject_val_neg_pnl` (line 252) — both → `COST_NEGATIVE` | `COST_NEGATIVE` | Train-window negative PnL is the same "candidate had non-positive realized PnL" semantic family as `reject_neg_pnl` and `reject_val_neg_pnl`. |
| `reject_combined_sharpe_low` | `reject_val_low_sharpe` (line 253), `reject_val_low_wr` (line 254) — both → `LOW_BACKTEST_SCORE` | `LOW_BACKTEST_SCORE` | Combined train+val Sharpe gate is the same "backtest-score-below-threshold" semantic family as the existing `*_low_sharpe` / `*_low_wr` keys. |

No new `RejectionReason` enum members are introduced. The taxonomy module's docstring guarantees "RAW_TO_REASON is additive: new mappings may be added; existing mappings may not be removed without a separate authorized order" — additions only, no edits to the 18-member enum.

### Why this is observability-only

- `arena_pipeline.py` is **not** touched; the reject decision logic and validator gates are unchanged.
- Adding `RAW_TO_REASON` entries only changes how the existing rejections are **labelled** in `arena_batch_metrics.reject_reason_distribution`.
- The validator's reject decision (`if neg_pnl: stats[...] += 1`) is not modified.
- A2_MIN_TRADES, threshold values, generation budgets, sampling weights, alpha mutation logic — all untouched.

## Patch applied (Phase 2)

File: `zangetsu/services/arena_rejection_taxonomy.py`

Diff:
```diff
-    # arena_pipeline.py — A1 reject counters (see stats dict at arena_pipeline.py:517)
+    # arena_pipeline.py — A1 reject counters (see stats dict at arena_pipeline.py:707)
     "reject_few_trades": RejectionReason.SIGNAL_TOO_SPARSE,
     "reject_neg_pnl": RejectionReason.COST_NEGATIVE,
+    # PR #43 (commit c873857) added the train-window negative-PnL gate.
+    # Same family as reject_neg_pnl / reject_val_neg_pnl. Mapped to
+    # COST_NEGATIVE to close the UNKNOWN_REJECT fallback path identified
+    # in TEAM ORDER 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS.
+    "reject_train_neg_pnl": RejectionReason.COST_NEGATIVE,
     "reject_val_constant": RejectionReason.INVALID_FORMULA,
     "reject_val_error": RejectionReason.INVALID_FORMULA,
     "reject_val_few_trades": RejectionReason.SIGNAL_TOO_SPARSE,
     "reject_val_neg_pnl": RejectionReason.COST_NEGATIVE,
     "reject_val_low_sharpe": RejectionReason.LOW_BACKTEST_SCORE,
     "reject_val_low_wr": RejectionReason.LOW_BACKTEST_SCORE,
+    # PR #43 also added the combined train+val Sharpe gate. Same family
+    # as reject_val_low_sharpe / reject_val_low_wr (backtest-score
+    # rejection). Mapped to LOW_BACKTEST_SCORE.
+    "reject_combined_sharpe_low": RejectionReason.LOW_BACKTEST_SCORE,
```

Stats:
- 2 new dict entries
- 6 new comment lines (3 per new entry)
- 1 stale comment line-number fixed (`arena_pipeline.py:517` → `:707`, matching current `stats` initialization site)

`arena_pipeline.py` was NOT modified. The order's STOP-condition "patch would require validator logic changes" is NOT triggered.

## After patch

### Re-verified by direct module reload on Mac

```python
>>> "reject_train_neg_pnl" in RAW_TO_REASON
True
>>> "reject_combined_sharpe_low" in RAW_TO_REASON
True
>>> classify("reject_train_neg_pnl")[0].value
"COST_NEGATIVE"
>>> classify("reject_combined_sharpe_low")[0].value
"LOW_BACKTEST_SCORE"
>>> classify("some_totally_unknown_reason_for_fallback_test")[0].value
"UNKNOWN_REJECT"
>>> len(RAW_TO_REASON)
24
```

- 22 → 24 entries (+2)
- Both PR #43 keys now classify deterministically to non-`UNKNOWN_REJECT` canonical reasons.
- Existing entries unchanged (verified separately by `test_existing_core_mappings_unchanged`).
- UNKNOWN_REJECT fallback intact for truly unknown reasons.

## Fallback behavior proof

The `classify()` function in `arena_rejection_taxonomy.py:285-328` returns `RejectionReason.UNKNOWN_REJECT` whenever neither exact match nor substring match succeeds. The patched dict only **adds** entries; the fallback logic is identical. New test `test_unknown_reject_fallback_still_works` enforces this.

## Validator behavior

Unchanged. The patch lives entirely in the taxonomy module (a passive INSTRUMENTATION-ONLY layer per its docstring). No call site of `arena_pipeline.py` or `arena_gates.py` was modified. Engine pass / fail decisions, thresholds, and counter increments behave identically before and after the patch.
