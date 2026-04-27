# 04 — Validation Gate Diagnosis (Phase 4)

**Phase 4 Verdict:** `VALIDATION_GATES_WORKING_AS_DESIGNED_WEAK_CANDIDATES`

The validation gate stack (A1 fitness → A2 → A3 → A4) is mathematically and structurally consistent with j13's 2026-04-20 design anchor. The dominant rejection (98.7% `reject_train_neg_pnl`) fires at the **A1 fitness layer**, not at A2/A3/A4. Loosening the train-net-PnL ≤ 0 gate would admit money-losing alphas — that is unsafe by design.

## Gate stack canonical reference

### A1 — fitness on train window (`zangetsu/services/arena_pipeline.py:1041–1048`)

```python
if float(bt.net_pnl) <= 0:
    stats["reject_train_neg_pnl"] += 1
    _emit_a1_lifecycle_safe(... reject_reason="TRAIN_NEG_PNL" ...)
```

Reject if train-window backtest **net** PnL ≤ 0 (cost subtracted). Cannot be loosened without admitting net-loss alphas.

Other A1 buckets (lower priority):
- `reject_few_trades` — alpha produced fewer than minimum trades on train
- `reject_neg_pnl` — legacy gate (unused in V10 path; `reject_neg_pnl=0` in all stats lines)
- `reject_val_few_trades` / `reject_val_neg_pnl` / `reject_val_low_sharpe` / `reject_val_low_wr` / `reject_val_constant` / `reject_val_error` — validation-window mirrors of the train gate
- `reject_combined_sharpe_low` — V10 combined train+val sharpe gate

### A2 — coarse OOS PnL gate (`zangetsu/services/arena_gates.py:43–55`)

```python
A2_MIN_TRADES: int = 25
def arena2_pass(trades):
    n = len(trades)
    if n < A2_MIN_TRADES:
        return GateResult(False, "too_few_trades", {"trades": n, "min": A2_MIN_TRADES})
    total_pnl = float(sum(t.pnl for t in trades))
    if total_pnl <= 0:
        return GateResult(False, "non_positive_pnl", {"trades": n, "total_pnl": total_pnl})
    return GateResult(True, "ok", {"trades": n, "total_pnl": total_pnl})
```

Two short-circuit checks: trade count then total PnL. `A2_MIN_TRADES = 25` (Patch H1 2026-04-20: aligned from 30 → 25 to match `arena23_orchestrator`).

### A3 — time-segment stability (`arena_gates.py:75–125`)

```
A3_SEGMENTS = 5
A3_MIN_TRADES_PER_SEGMENT = 15
A3_MIN_WR_PASSES = 4
A3_MIN_PNL_PASSES = 4
A3_WR_FLOOR = 0.45
```

≥ 4 of 5 segments with WR > 0.45 AND ≥ 4 with PnL > 0 on the holdout middle 1/3.

### A4 — market-regime stability (`arena_gates.py:130+`)

```
A4_REGIME_WR_FLOOR = 0.40
A4_MIN_TRADES_PER_REGIME = 10
A4_MIN_OTHER_REGIMES_PASS = 1
```

WR > 0.40 in training regime AND in ≥ 1 other regime on the holdout last 1/3.

## Which gate rejects first?

Order of evaluation (per `arena_pipeline.py` flow):

1. **A1 fitness — `reject_train_neg_pnl`** ← currently absorbing 98.7% of all generated alphas
2. A1 fitness — `reject_few_trades` ← absorbs the alphas with too few train trades
3. A1 validation gates (val_few / val_neg_pnl / val_sharpe / val_wr / etc.) ← absorbs the ≈ 1–2% that pass train
4. A1 `combined_sharpe_low` ← currently 0 (alphas don't reach it)
5. A2 `arena2_pass` (`too_few_trades` / `non_positive_pnl`) ← only reached after A1 admits
6. A3 `arena3_pass` (segment stability) ← only reached after A2 passes
7. A4 `arena4_pass` (regime stability) ← only reached after A3 passes

Gates are **sequential and short-circuiting**. The first failure terminates evaluation for that alpha. The current pipeline never reaches gate #5 (A2) because gate #1 absorbs everything.

## Are gates operating on train, validation, or combined metrics?

| Gate | Window |
|---|---|
| A1 train fitness (`reject_train_neg_pnl`) | TRAIN (140k bars / 70%) |
| A1 `reject_few_trades` | TRAIN |
| A1 `val_*` gates | VAL (configurable subset of training data) |
| A1 `combined_sharpe_low` | TRAIN + VAL |
| A2 `arena2_pass` | HOLDOUT first 1/3 (60k × 1/3 = 20k bars) |
| A3 `arena3_pass` | HOLDOUT middle 1/3, 5 segments |
| A4 `arena4_pass` | HOLDOUT last 1/3, regime-tagged |

Train fitness uses train-window data. Validation uses a separate val window inside the train slice. The 60% / 30% holdout sequence (60% train inner / 30% holdout) gives A2/A3/A4 their own fresh data. **Sane separation; not a leakage concern.**

## Are gates newly added by PR #43 blocking everything?

PR #43 introduced governance physical separation (legacy archive / fresh / staging / rejected) and `admission_validator` plpgsql function with three structural gates (alpha_hash format, epoch=B_full_space, arena1_score finite). It also added the 11-field provenance NOT NULL constraint.

`admission_validator` rejection routes to `champion_pipeline_rejected` table. Current state: **`champion_pipeline_rejected` has 0 rows** — meaning `admission_validator` has never rejected anything since v0.7.1 deploy. It is not blocking the pipeline.

The 184 staging rows (89 admitted + 95 admitted_duplicate) confirm the validator is correctly admitting historical alphas; the `admitted_duplicate` route handles re-submissions. PR #43's gates are not the problem.

## Is gate behavior consistent with intended SOL-artifact prevention?

Yes. The PR #41 retro ("all 8 cost=0.5x survivors are SINGLE_SYMBOL_ARTIFACT — calibration BLOCKED") demonstrated that a *looser* cost yielded artifact alphas that did not generalize. Restoring full cost re-asserted the train-net-PnL gate; current behavior (98.7% reject) is the **expected** consequence of that decision. The gate is doing its job: refusing to admit money-losing alphas.

## Would loosening gates be unsafe?

| Loosening | Effect | Safety |
|---|---|---|
| `if bt.net_pnl <= 0` → `if bt.net_pnl <= -X` (allow small loss) | admits explicitly-losing alphas | UNSAFE — money-losing in train guarantees worse OOS |
| Reduce cost in cost_model.py | admits alphas that fail at live cost | UNSAFE — PR #41 proved this produces SINGLE_SYMBOL_ARTIFACT |
| `A2_MIN_TRADES` lower than 25 | admits low-trade-count alphas | UNSAFE — already aligned at 25 (Patch H1); lower would re-introduce sample-size noise |
| Drop A3 / A4 stability gates | admits alphas without regime/time stability | UNSAFE — j13's 2026-04-20 design explicitly requires these ("穩定的 pnl/勝率/交易次數") |
| Loosen `A3_WR_FLOOR` (0.45) / `A4_REGIME_WR_FLOOR` (0.40) | admits alphas with weak win rates | UNSAFE — would remove the very property the gates exist to enforce |

**No safe loosening is available.** The gate stack is at the correct strictness for the j13 "production-grade champion" mandate.

## Is there evidence that gate design is wrong vs candidates truly weak?

Candidates appear truly weak:
1. Symbol coverage: 14 / 14 active. Diverse.
2. Regime coverage: 5 / 5 distinct. Diverse.
3. Lane coverage: both j01 baseline and j02 exploration. Diverse.
4. Generation novelty: `bloom_hits = 0` and `compile_err = 0` — alphas are new and well-formed.
5. Failure profile: 98.7% fail train fitness; this is uniform across the 4 dimensions above.
6. Historical 89 alphas had `indicator_alpha_ratio_pct = 0` — degenerate raw OHLCV formulas, no indicator depth.
7. AKASHA carry-forward states the formulation is exhausted.

The convergent signal across these data points is that **the alpha-generation universe under "60-bar forward return on OHLCV+indicator" cannot produce alphas with edge above realistic transaction cost.** The gate stack is correctly rejecting that universe.

## Required Phase 4 classification

```
VALIDATION_GATES_WORKING_AS_DESIGNED_WEAK_CANDIDATES
```
