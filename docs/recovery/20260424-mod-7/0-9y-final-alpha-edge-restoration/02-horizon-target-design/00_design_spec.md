# 00 — Horizon Target Design Spec

**Master Order:** 0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM
**Sub-order:** TEAM ORDER 0-9Y-HE0-HORIZON-TARGET-DESIGN-SPEC
**Phase:** 2
**Date (UTC):** 2026-04-28T03:08Z
**Author:** Claude Lead
**Status:** design-only — no implementation in this sub-order

## Mission recap

Design the multi-horizon target system for A1 alpha generation. Active horizons: **180 / 240 / 360** bars (1m K-lines = 3h / 4h / 6h). Current 60-bar is retained as a **baseline reference only** (no longer the active target). Implementation lives in HE1/HE2/HE3 (next sub-orders).

## Pre-existing infrastructure (relevant code already in repo)

| Component | File:line | Current behavior |
|---|---|---|
| Forward-return computation | `zangetsu/engine/components/alpha_engine.py:633-637` (`_forward_returns`) | reads `ALPHA_FORWARD_HORIZON` env (default 60); cumulative forward return over `horizon` bars |
| Forward-return invocation sites | `alpha_engine.py:673, 719, 800` | each evaluator path calls `self._forward_returns(close)` once per evaluation |
| Alpha hash | `alpha_engine.py:805` | `hashlib.md5(formula.encode("utf-8")).hexdigest()[:16]` — formula-only |
| Profile identity | `arena_pipeline.py` (per B1 evidence) | `generation_profile_id` already on telemetry events |
| B1 aggregate metrics | `arena_pass_rate_telemetry.py` | per-batch per-symbol/regime/lane metrics — must extend per-horizon |

## Design decisions

### D1. Active horizons constant

Add module-level constant in `arena_pipeline.py` (callable by orchestrator, evaluator, telemetry):

```python
# 0-9Y-HE0: active multi-horizon set for A1 alpha generation.
# Replaces the singleton 60-bar default. 60 retained as baseline reference
# only; the active set is selected per round by the orchestrator.
ACTIVE_A1_HORIZONS: tuple[int, ...] = (180, 240, 360)
```

Rationale: tuple, not list, to signal immutability. Module-level so tests can validate without reaching into runtime. Order: ascending.

### D2. Label construction (forward-return formula)

For a horizon `H` bars, the forward return at bar index `i`:

```
fwd_return[i] = (close[i + H] - close[i]) / max(close[i], EPS)   for i in [0, len(close) - H)
fwd_return[i] = NaN                                                for i in [len(close) - H, len(close))
```

`EPS = 1e-10` (existing; preserved). `NaN` for the last `H` bars is the **invalid-tail-bars** drop; the IC computation already drops invalid pairs via `np.isfinite` mask (`alpha_engine.py:109,114`).

The current `_forward_returns(close)` implementation already follows this pattern; HE1 only needs to parameterize `horizon` instead of reading the env var.

### D3. No-lookahead rule

For any candidate `c` evaluated at horizon `H`:

1. **Train window** — `train_close[0..N-H]` is the only OHLCV slice that may be used to compute the forward return label (no peeking past the train-window cutoff).
2. **Validation window** — analogously bounded; `val_close[0..M-H]` only.
3. **Cross-window leak prevention** — when train and val windows are adjacent, the last `H-1` train bars must NOT be used as the **target** because their `fwd_return` would be computed using val-window prices. The existing data preprocessor already produces train/val splits from non-overlapping ranges, so the only required change is dropping the last `H` train rows from the **label** array (the **alpha** array can still use those rows, it's only the label that leaks).
4. **Documentation invariant**: "No bar `i` may have `fwd_return[i]` computed using `close[j]` for any `j` outside the current window."

A unit test in HE1 must assert: `fwd_return[N-H : N]` is all NaN for any horizon `H` and any window length `N`.

### D4. Candidate horizon identity

Identity is critical because the GP search bloom filter dedupes by `alpha_hash`. Without horizon awareness, the same formula at horizon 180 and horizon 240 would collide and one would be silently dropped.

**Decision: introduce `candidate_id` as a composite identifier; preserve `alpha_hash` as formula-only.**

```python
# alpha_hash is unchanged: MD5(formula)[:16] — formula-only.
# candidate_id is new: alpha_hash composed with horizon.
candidate_id = f"{alpha_hash}_h{horizon}"
```

Why composite-id (not modify alpha_hash):
1. **Backward-compat**: existing 89 fresh-pool alphas have implicit horizon = 60. Modifying alpha_hash breaks DB joins on `formula_hash` field already on telemetry events.
2. **Bloom dedup** is per-(formula, horizon): each horizon search runs its own dedup pass. Composite-id simplifies this — bloom key is `candidate_id` for new code, `alpha_hash` for legacy paths.
3. **DB schema unchanged**: `champion_pipeline_*` tables already have a `candidate_id` text column (per 0-9X-DB-MIGRATION-MULTI-STAGE migration). HE1 will populate it.

### D5. Horizon budget split

Each round generates `POP_SIZE × N_GEN` evaluations against one (symbol, regime, lane). With three active horizons, the round budget splits **equally by default**:

```
per_horizon_budget = POP_SIZE × N_GEN / len(ACTIVE_A1_HORIZONS)   # rounded down per horizon
remainder = total_budget - sum(per_horizon_budgets)               # added to the LAST horizon (360) by convention
```

Why equal split (not weighted):
- No prior data to inform a weight (we don't yet know which horizon performs best — that's exactly what HE5 analysis will determine)
- Budget skew is a follow-up tuning decision after Phase-12 strategic-redesign decision; out of scope for HE0/HE1/HE2

The orchestrator — `arena_pipeline.py` round loop — selects the next horizon round-robin; the evaluator receives `horizon` as a parameter.

### D6. Telemetry fields (delegated to HE3 for plumbing; specified here)

Per master spec for HE3, every `arena_batch_metrics` event must expose:

- `active_horizons` (list of int)
- `entered_count_by_horizon` (dict horizon → int)
- `rejected_count_by_horizon`
- `passed_count_by_horizon`
- `reject_reason_distribution_by_horizon` (dict horizon → dict reason → count)
- `gross_pnl_by_horizon` / `net_pnl_by_horizon` / `total_cost_by_horizon`
- `trade_count_by_horizon` / `signal_density_by_horizon` / `win_rate_by_horizon`
- `train_sharpe_by_horizon` / `val_sharpe_by_horizon`
- `deployable_count_by_horizon`

Plus `aggregate_metrics_availability` flags must extend with the new keys (per B1 contract).

### D7. Legacy candidate handling

The 89 existing fresh-pool alphas (carry-forward from PR #44 migration) carry an **implicit horizon of 60**. HE1 must:

1. Backfill `candidate_id = f"{alpha_hash}_h60"` for these 89 rows in `champion_pipeline_fresh` (one-shot DB UPDATE — but **NOT in HE1**; this is a separate optional B-stream order if/when needed).
2. Treat them as "legacy 60-bar" cohort in any downstream analysis.

For HE1 itself: legacy alphas are not re-evaluated. They remain in the fresh pool with implicit horizon = 60 metadata. HE5 will analyze them as a separate cohort.

### D8. Validation gates unchanged

A1 / A2 / A3 / A4 / A5 gates continue to use the **same thresholds** regardless of horizon. The `BacktestResult` produced by an evaluator at any horizon is a drop-in replacement for the existing 60-bar `BacktestResult`. The validator does not need horizon awareness because the cost model and per-trade economics are still per-trade (not per-bar).

This means **no change** to:
- `arena_gates.arena2_pass / arena3_pass / arena4_pass`
- `A2_MIN_TRADES = 25`
- thresholds in `zangetsu/config/settings.py`
- champion promotion semantics

### D9. Cost model unchanged

The Binance Futures realistic cost (5–10 bps taker tier) is per-trade. Horizon affects **trade frequency** (longer horizon → fewer trades per window) but not per-trade cost. No change to `cost_per_trade` or `round_total_cost_bps` derivation.

### D10. A2_MIN_TRADES unchanged

A2_MIN_TRADES = 25 stays. With longer horizons, fewer trades per backtest window are expected — this raises **SIGNAL_TOO_SPARSE** rejection rate (see risk R1 below). That is intentional and documented; the order forbids weakening A2_MIN_TRADES.

## Per-horizon expected-trade math (sanity check)

Given:
- Train window = 140 000 1m bars = 2333 hours = 97 days
- Current 60-bar median observed: 989 trades per backtest at signal density 0.00702 trades/bar

Naive expected trades scale roughly as `density × (window - horizon)`. Density itself may shift because the strategy uses forward-return at horizon `H`:

| Horizon | Expected raw trade count (rough) | Pass A2_MIN_TRADES=25? |
|---|---|---|
| 60 (baseline) | 989 (observed) | YES |
| 180 | ~330 (3× longer hold; one trade per 3 entry signals would compress to ~330 trades) | YES |
| 240 | ~250 | YES |
| 360 | ~165 | YES |

All three active horizons should comfortably clear A2_MIN_TRADES = 25. The risk is bunching: if the strategy generates few signals at long horizons, some symbol/regime cohorts may dip under 25. Phase-5 (HE3) telemetry will surface this; Phase-6 (TF1) diagnosis will quantify the existing 60-bar baseline.

## Final verdict

```
COMPLETE_HORIZON_TARGET_DESIGN_READY
```

Design is specific enough that an HE1 implementer can build directly:
- Constants: `ACTIVE_A1_HORIZONS = (180, 240, 360)`
- Function signature: `_forward_returns(close, horizon: int) -> np.ndarray`
- Identity: `candidate_id = f"{alpha_hash}_h{horizon}"`
- Telemetry: extend B1 `aggregate_metrics` to include per-horizon dict fields
- DB: existing `candidate_id` column in `champion_pipeline_*` (no schema change)
- No validator / cost / threshold change

## Forbidden ops audit

**0** — design-only sub-order. No code, DB, runtime, threshold, validator, cost, alpha_zoo, CANARY, production, calibration touched.
