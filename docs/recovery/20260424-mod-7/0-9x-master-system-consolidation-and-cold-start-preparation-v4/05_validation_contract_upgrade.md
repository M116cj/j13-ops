# 05 — Validation Contract Boundary and Implementation

## 1. Pre-PR #43 Active Gates

In `arena_pipeline.py:worker_main`, in execution order:

| # | Gate | Threshold | Reject reason | Stage |
| --- | --- | --- | --- | --- |
| 1 | Train trade count | < 30 | `reject_few_trades` (tagged `SIGNAL_TOO_SPARSE`) | post-train backtest |
| 2 | Val constant | std < 1e-10 | `reject_val_constant` | val backtest |
| 3 | Val error | exception | `reject_val_error` | val backtest |
| 4 | Val trade count | < 15 | `reject_val_few_trades` | post-val |
| 5 | Val net PnL | ≤ 0 | `reject_val_neg_pnl` | post-val |
| 6 | Val Sharpe | < 0.3 | `reject_val_low_sharpe` | post-val |
| 7 | Val Wilson WR | < 0.52 | `reject_val_low_wr` | post-val |

## 2. New Gates Added (PR #43, NG2 from order 4-1)

| # | Gate | Threshold | Reject reason | Insertion point |
| --- | --- | --- | --- | --- |
| **NEW** | **Train net PnL** | **≤ 0** | **`reject_train_neg_pnl`** (lifecycle reason `TRAIN_NEG_PNL`) | after gate 1 (train trade count), BEFORE val backtest — saves CPU |
| **NEW** | **Combined Sharpe** | **(train_sharpe + val_sharpe) / 2 < 0.4** | **`reject_combined_sharpe_low`** | after gate 7 (val_low_wr), BEFORE scoring |

Insertion code (verified syntax-OK):

```python
# After train trade count gate (line ~982):
if float(bt.net_pnl) <= 0:
    stats["reject_train_neg_pnl"] += 1
    _emit_a1_lifecycle_safe(
        stage_event=_SE_EXIT, status=_LS_REJECTED,
        alpha_hash=alpha_hash, source_pool=sym,
        reject_reason="TRAIN_NEG_PNL", log=log,
    )
    continue

# After val_low_wr gate (line ~1050):
combined_sharpe = (float(bt.sharpe_ratio) + float(bt_val.sharpe_ratio)) / 2.0
if combined_sharpe < 0.4:
    stats["reject_combined_sharpe_low"] += 1
    continue
```

## 3. Cross-Symbol Consistency (NG3) — DEFERRED

The current per-cell loop processes one (symbol, alpha) pair at a time. Implementing cross-symbol consistency at the val-filter level would require:
- Aggregating same-formula evaluations across multiple symbols within a round
- Deferring promotion until ≥2/3 symbols have completed
- Refactoring the per-cell continuation logic to support batched aggregation

This is a substantial architectural change. **Deferred to a follow-up order** with status `CROSS_SYMBOL_CONSISTENCY_PENDING_REFACTOR`. The downstream Arena 2/3/4 already provides regime + segment + cross-window consistency checks that partially compensate.

In the meantime, **the train_neg_pnl gate (NG2 part 1) blocks the most common single-symbol artifact pattern** observed in PR #41 (8/8 SOL survivors at cost=0.5x had negative train PnL).

## 4. Updated Rejection Taxonomy

The `reject_*` keys are forwarded to `arena_rejection_taxonomy.classify(raw_reason=stats_key, arena_stage="A1")` which maps them to canonical names. The two new keys (`reject_train_neg_pnl`, `reject_combined_sharpe_low`) flow through the same classifier; if the classifier doesn't yet have explicit mappings, it falls back to the raw key name (which is still emitted in batch metrics).

A follow-up order should add explicit canonical names `TRAIN_NEG_PNL` and `COMBINED_SHARPE_LOW` to `arena_rejection_taxonomy.py` for consistency with the lifecycle reject_reason emitted by `_emit_a1_lifecycle_safe`.

## 5. Required Rejection Reasons Coverage (per order)

| Required reason | Coverage |
| --- | --- |
| `TRAIN_NEG_PNL` | YES (PR #43 — emitted via lifecycle) |
| `VAL_NEG_PNL` | YES (`reject_val_neg_pnl`) |
| `COMBINED_SHARPE_LOW` | YES (PR #43 — counter-only; canonical name pending taxonomy update) |
| `CROSS_SYMBOL_INCONSISTENT` | DEFERRED (architectural refactor needed) |
| `NUMERIC_INVALID` | YES (`reject_val_constant` + `nan_to_num` clamping) |
| `CONSTANT_SIGNAL` | YES (`reject_val_constant`) |
| `COST_NEGATIVE` | YES (existing — fitness-stage reject) |
| `COUNTER_INCONSISTENCY` | YES (existing — fitness-stage reject) |

## 6. Shared-Contract Verification

The new gates are inline in `arena_pipeline.py:worker_main`. The same signal-generation + backtest path is used by:
- A1 GP candidates (per-round inside `worker_main`)
- alpha_zoo offline replay (PR #39 `/tmp/0-9wzr-offline-replay.py`)
- calibration matrix replay (PR #40 `/tmp/0-9wch-replay.py`)

**For the offline replay scripts to apply the new gates, they must import the same val_filter logic.** Currently they implement their own pass/fail checks (val_pnl > 0). A follow-up order should extract the val_filter chain into a reusable helper module — this consolidation is itself a Phase-5 acceptance criterion (`AC9: Validation contract is shared by GP, alpha_zoo replay, calibration replay, and future cold-start path`).

For this PR, the offline replay scripts are not modified (they live in `/tmp/`). The follow-up order will refactor them into `zangetsu/services/val_filter.py` as a canonical module.

## 7. Tests

PR #43 adds explicit gate-level tests (see Phase 11). Existing val_filter tests in `zangetsu/tests/test_*` continue to pass with the additive new gates (no existing gate is weakened).

## 8. Phase 5 Verdict

| Item | Status |
| --- | --- |
| Existing gates retained | YES |
| `train_pnl > 0` gate | **IMPLEMENTED** |
| `val_pnl > 0` gate | already existed (`reject_val_neg_pnl`) |
| `combined_sharpe ≥ 0.4` gate | **IMPLEMENTED** |
| Cross-symbol consistency ≥ 2/3 | **DEFERRED** — architectural refactor required |
| SOL-only artifact blocked | partially — train_neg_pnl gate blocks the artifact pattern observed in PR #41 |
| Train-negative survivor blocked | **YES** |
| Low combined_sharpe blocked | **YES** |

→ **Phase 5 verdict: VALIDATION_CONTRACT_PARTIALLY_UPGRADED.** 2 of 4 new gates implemented. Cross-symbol consistency deferred to a separate order. The 2 implemented gates DIRECTLY address the SOL-only artifact pattern documented in PR #41.
