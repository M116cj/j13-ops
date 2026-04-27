# 02 — A1 Reject Root-Cause Breakdown (Phase 2)

**Phase 2 Verdict:** `A1_REJECT_DOMINANT_COST_NEGATIVE`

## Aggregate over last 500 `arena_batch_metrics` events

Window: `2026-04-27T17:28:39Z → 2026-04-27T17:58:46Z` (~30 min, 500 batches × 10 alphas = 5000 alphas evaluated)

| Metric | Value |
|---|---|
| total_entered | 5000 |
| total_passed | **0** |
| pass_rate | 0.0% |

### Aggregate `reject_reason_distribution`

| Reason | Count | % |
|---|---|---|
| `COST_NEGATIVE` | 4935 | 98.7% |
| `SIGNAL_TOO_SPARSE` | 44 | 0.9% |
| `LOW_BACKTEST_SCORE` | 21 | 0.4% |
| `COUNTER_INCONSISTENCY` | 0 | 0.0% |
| `UNKNOWN_REJECT` | 0 | 0.0% |

### Top reason **by batch dominance**

```
COST_NEGATIVE: 500 / 500 batches
```

**Every single batch** in the 500-batch window has `COST_NEGATIVE` as its top reject reason. There is no batch where any other bucket dominates.

## Symbol & regime coverage (last 500 batches)

Symbols (14/14 active):

```
LINKUSDT 60   SOLUSDT 53     GALAUSDT 44      1000PEPEUSDT 41
DOTUSDT 40    1000SHIBUSDT 39  XRPUSDT 38     BNBUSDT 36
AAVEUSDT 35   FILUSDT 31     DOGEUSDT 25      AVAXUSDT 23
BTCUSDT 21    ETHUSDT 14
```

Regimes (5 distinct):

```
BULL_TREND 189   BEAR_TREND 150   BEAR_RALLY 79
CONSOLIDATION 44   ACCUMULATION 38
```

Generation profiles (both lanes active):

| profile | count | lane |
|---|---|---|
| `gp_541a313e770c4424` | 256 | j01 baseline |
| `gp_26f478846fd0f729` | 244 | j02 exploration |

The block is **uniform across symbol, regime, profile, and lane**. It is not a coverage / data-availability artifact.

## Cross-reference: runtime per-round summary stats

Sample direct from runtime logs (these come from `arena_pipeline.py` per-round logger, distinct emit path from `arena_batch_metrics`):

```
R272000 | LINKUSDT/BULL_TREND | champions=0/10 | 14.9s |
  rejects: few_trades=19 train_neg=1967 val_few=4 val_neg_pnl=8
           val_sharpe=2 val_wr=0 combined_sharpe=0

V10 STATS W2 R272000 | evolutions=200 alphas_evaled=2000 bloom_hits=0 compile_err=0 inserted=0 |
  reject_few_trades=19 reject_neg_pnl=0 reject_train_neg=1967
  reject_val_few=4 reject_val_neg=8 reject_val_sharpe=2 reject_val_wr=0
  reject_combined_sharpe=0 reject_val_err=0 reject_val_const=0 |
  bloom_size=89

R49500 (W0): evolutions=50 alphas_evaled=500 inserted=0 |
  reject_train_neg=499 reject_val_neg=1
```

Per round across both lanes:
- `reject_train_neg` is the dominant gate (≈98–99% of all evaluated alphas)
- `reject_few_trades` and `reject_val_*` together cover the remaining ~1–2%
- `reject_combined_sharpe`, `reject_val_err`, `reject_val_const` always 0
- `bloom_hits=0` ⇒ generation produces alphas not previously seen (no recycling)
- `bloom_size=89` ⇒ the bloom filter contains exactly the 89 historical admitted alphas (consistent with v0.7.1 staging `admitted` count)
- `compile_err=0` ⇒ generated alphas compile cleanly; no AST / interpreter issue

## Mapping runtime gate → telemetry bucket

`zangetsu/services/arena_pipeline.py` `_A1_REJECT_STATS_KEYS`:

```python
"reject_few_trades", "reject_neg_pnl", "reject_train_neg_pnl",
"reject_val_constant", "reject_val_error", "reject_val_few_trades",
"reject_val_neg_pnl", "reject_val_low_sharpe", "reject_val_low_wr",
"reject_combined_sharpe_low",
```

The `reject_train_neg_pnl` increment site (line 1042–1048):

```python
if float(bt.net_pnl) <= 0:
    stats["reject_train_neg_pnl"] += 1
    _emit_a1_lifecycle_safe(
        stage_event=_SE_EXIT, status=_LS_REJECTED,
        alpha_hash=alpha_hash, source_pool=sym,
        reject_reason="TRAIN_NEG_PNL", log=log,
    )
```

Comment in source confirms: "…at cost=0.5x had negative train PnL but positive val PnL." The fitness backtest is on **TRAIN data with cost subtracted**. `net_pnl ≤ 0` after cost is the trigger.

The taxonomy mapping (verified in 0-9X-POST-RESTART-A1-TELEMETRY-VERIFICATION):

```
reject_train_neg_pnl  →  COST_NEGATIVE   (RejectionCategory.COST, ArenaStage.A2)
```

So the **runtime stat `reject_train_neg` and the telemetry bucket `COST_NEGATIVE` are the same population.**

## Whether any pass path exists

Searched `reject_reason_distribution` for any non-zero `passed_count` in the last 500 batches: **0 / 500 had `passed_count > 0`.** Searched runtime stats lines for `champions=N/10` with N > 0 across the 30-min window: **0 occurrences.**

There is **no observable pass path** in the active pipeline.

## Has any deployable candidate appeared?

```
SELECT deployable_count FROM zangetsu_status;  → 0
SELECT COUNT(*) FROM champion_pipeline_fresh WHERE status='DEPLOYED';  → 0
SELECT MAX(arena3_completed_at) FROM champion_pipeline_fresh;  → NULL
SELECT MAX(arena4_completed_at) FROM champion_pipeline_fresh;  → NULL
```

No deployable has ever existed. The 89 fresh stopped at A2.

## Required Phase 2 classification

```
A1_REJECT_DOMINANT_COST_NEGATIVE
```

98.7% of all rejections, 500/500 batches dominant. The runtime per-round logs corroborate: `reject_train_neg` is the gate firing. **The block is at A1 internal training-window net-PnL fitness, not at any later validation gate.**
