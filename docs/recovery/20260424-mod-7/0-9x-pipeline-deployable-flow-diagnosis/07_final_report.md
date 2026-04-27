# 07 — Final Report

**Order:** TEAM ORDER 0-9X-PIPELINE-DEPLOYABLE-FLOW-DIAGNOSIS

## Final verdict

```
DIAGNOSED_FEATURE_SPACE_EXHAUSTED
```

(Co-active with `DIAGNOSED_SIGNAL_NO_EDGE` per Phase 3. The two are facets of the same root cause: under the current "60-bar forward return on OHLCV+indicator" formulation, GP+LGBM cannot generate alphas with edge that exceeds realistic Binance Futures cost.)

## Summary table

| Field | Value |
|---|---|
| HEAD | `0a34a14a65f913610e93cbd779a310ea5a2b8277` |
| Runtime status | A1 w0–w3 + A23 + A45 + Calcifer alive; ~56 min uptime; §17.6 FRESH 4/4 |
| DB status | v0.7.1 8/8 objects present; 89 fresh / 184 staging / 1564 legacy / 0 rejected / 0 engine_telemetry |
| Candidate flow classification (Phase 1) | `FLOW_BLOCKED_AFTER_A1` (current 6.5 d: `FLOW_ALL_REJECTED_AT_A1`; legacy 89: `FLOW_HAS_FRESH_NO_DEPLOYABLES`) |
| A1 reject root cause (Phase 2) | `A1_REJECT_DOMINANT_COST_NEGATIVE` — 98.7% of 5000 alphas; 500/500 batch dominance |
| Signal / cost (Phase 3) | `SIGNAL_NO_EDGE` |
| Validation gates (Phase 4) | `VALIDATION_GATES_WORKING_AS_DESIGNED_WEAK_CANDIDATES` |
| Feature / data (Phase 5) | `FEATURE_SPACE_EXHAUSTED` |
| deployable_count | 0 ever |
| last_live_at_age_h | NULL |
| CANARY can proceed | **NO** |
| alpha_zoo can unblock | **NO** unless separately authorized as cold-start path |
| production rollout can proceed | **NO** |
| Forbidden ops | 0 |

## Recommended strategic path

Per AKASHA carry-forward decision tree:

| Path | Description | Estimated cost | Recommendation |
|---|---|---|---|
| **P1 — pipeline repair** (change target) | Switch from 60-bar forward return to triple-barrier / vol-normalized return / regime-conditional prediction | low–medium (target relabel + fitness re-anchor) | **Probe first** — cheapest, may unstick the existing universe |
| **P2 — feature/formula universe expansion** | Add order-book snapshots + funding rate derivatives + cross-symbol correlations | ~1–2 weeks new infra | Strong second choice if P1 doesn't yield edge |
| **P3 — horizon/problem redesign** | Tick-data pipeline + high-frequency backtester + 1-min alternative kline | ≥ 2–4 weeks new infra | Largest cost; deepest commitment; saves only if P1 and P2 both fail |
| **P0 — closure** | Acknowledge sunk cost; preserve scaffolding (data / backtester / gate / telemetry / policy / paper-trade) for future reuse; stop GP+LGBM development under current formulation | 0 (decision-only) | Honest fallback if j13 strategically prefers to redirect resources |

This evidence supports that **continuing to tune within the current formulation is futile**: 6.5 days of live runtime + AKASHA-recorded 10 h offline replay all converge on `SIGNAL_NO_EDGE` against realistic cost.

## Why each verdict / bucket lands where it does

| Phase | Verdict | Why not the alternates |
|---|---|---|
| 1 — flow | `FLOW_BLOCKED_AFTER_A1` | `FLOW_HAS_DEPLOYABLES` ✗ (0 ever); `FLOW_DB_EMPTY_RUNTIME_ACTIVE` ✗ (DB has 89+184+1564 rows, just no deployables); `FLOW_DATA_INSUFFICIENT` ✗ (4500 alphas tested across 14 symbols / 5 regimes is plenty) |
| 2 — A1 reject | `A1_REJECT_DOMINANT_COST_NEGATIVE` | `A1_REJECT_DOMINANT_LOW_BACKTEST_SCORE` ✗ (only 0.4%); `A1_REJECT_DOMINANT_SIGNAL_TOO_SPARSE` ✗ (0.9%); `A1_REJECT_TELEMETRY_STILL_UNRELIABLE` ✗ (CI=0, UNKNOWN_REJECT=0, residual=0) |
| 3 — signal/cost | `SIGNAL_NO_EDGE` | `SIGNAL_EDGE_EXISTS_COST_TOO_STRICT` ✗ (cost is realistic Binance tier; PR #41 proved lower cost yields SINGLE_SYMBOL_ARTIFACT); `SIGNAL_OVERFITS_TRAIN_FAILS_VALIDATION` ✗ (failure is at TRAIN, not validation); `SIGNAL_METRICS_NOT_EXPOSED` ✗ (bucket-level metrics sufficient for verdict) |
| 4 — gates | `VALIDATION_GATES_WORKING_AS_DESIGNED_WEAK_CANDIDATES` | `VALIDATION_GATES_TOO_STRICT` ✗ (`net_pnl ≤ 0` cannot be loosened without admitting money-losing alphas; PR #41 proves looser cost is unsafe); `VALIDATION_GATES_REQUIRE_DESIGN_REVIEW` ✗ (gates implement j13's 2026-04-20 mandate correctly) |
| 5 — feature/data | `FEATURE_SPACE_EXHAUSTED` | `FORMULA_UNIVERSE_STALE` ✗ (bloom_hits=0; 4454 unique alphas); `FEATURE_SPACE_TOO_NARROW` ✗ (126 indicator terminals × 35 operators is wide); `DATA_QUALITY_BLOCKER` ✗ (compile_err=0, val_error=0, 14 symbols loaded clean); `MARKET_REGIME_NO_EDGE` ✗ (failure uniform across all 5 regimes) |

## Decision-matrix-routed next order

Per the order's decision matrix:

| Diagnosed root cause | Recommended next order |
|---|---|
| signal has no edge **and** feature space exhausted | `TEAM ORDER 0-9Y-ALPHA-UNIVERSE-REDESIGN-PLAN` ← matches |
| cost too strict but gross edge exists | `TEAM ORDER 0-9X-COST-MODEL-CALIBRATION-REVIEW` |
| validation gates too strict | `TEAM ORDER 0-9X-VALIDATION-GATE-DESIGN-REVIEW` |
| data quality blocker | `TEAM ORDER 0-9X-DATA-QUALITY-REPAIR` |
| insufficient metrics | `TEAM ORDER 0-9X-PIPELINE-METRICS-EXPOSURE-FIX` |
| pipeline wiring gap | `TEAM ORDER 0-9X-PIPELINE-WIRING-REPAIR` |

## Next recommended order

```
TEAM ORDER 0-9Y-ALPHA-UNIVERSE-REDESIGN-PLAN
```

The "redesign" should explicitly include:

1. j13 strategic decision among `P1 / P2 / P3 / 結案` (no code change without j13 directive).
2. If P1: scope the target-relabel work (triple-barrier vs vol-normalized vs regime-conditional) + estimated time.
3. If P2: scope the data pipeline expansion (order-book / funding / cross-symbol) — AKASHA estimate ~1–2 weeks.
4. If P3: scope the tick-data + 1-min alt-kline + high-frequency backtester — deepest investment.
5. If 結案: define what to preserve (scaffolding / paper-trade / telemetry / gates) and what to retire.

## Parallel-track recommended sub-orders (P1 priority)

These are independent of the main strategic decision and should run in parallel:

| Sub-order | Reason |
|---|---|
| `TEAM ORDER 0-9X-PIPELINE-METRICS-EXPOSURE-FIX` | Add `gross_pnl` exposure to A1 telemetry so the gross-vs-cost split is observable per alpha. Currently Phase 3 cannot directly distinguish `gross<0` from `0<gross<cost` — the upgrade would let future diagnoses separate these populations. |
| `TEAM ORDER 0-9X-ENGINE-TELEMETRY-DIAGNOSIS` | `engine_telemetry` table 0 rows ever; `fresh_pool_process_health` view blank. v0.7.1 dual-evidence governance has only outcome side functional. |
| `TEAM ORDER 0-9X-CALCIFER-NULL-SAFETY-PATCH` | §17.3 `last_live_at_age_h > 6` is NULL when no live champion exists; predicate never fires. Patch to `COALESCE(last_live_at_age_h, 999) > 6`. |

## Forbidden ops summary

| Action | Status |
|---|---|
| source code modified | NO |
| DB schema modified | NO |
| validator logic modified | NO |
| thresholds modified | NO |
| A2_MIN_TRADES changed | NO (== 25 verified at canonical sites) |
| alpha generation / mutation / sampling changed | NO |
| Arena pass/fail semantics changed | NO |
| champion promotion / deployable_count semantics changed | NO |
| execution / capital / risk / order-router config modified | NO |
| Binance / API secret scope modified | NO |
| DB guards weakened | NO |
| alpha_zoo injection run | NO |
| live CANARY started | NO |
| production rollout started | NO |
| runtime calibration modified | NO |
| healthy workers killed | NO |
| Alaya hard reset | NO |
| force-push | NO |
| logs wiped | NO |

**Forbidden ops: 0.**

## Honest caveats

1. The pipeline does not currently expose per-alpha `gross_pnl` to telemetry; without that field, this diagnosis cannot fully separate `gross < 0` from `0 < gross < cost`. The aggregate evidence (cost is realistic; PR #41 proved lower-cost admits artifacts; 4.5k unique alphas all fail; AKASHA states the formulation is exhausted) is sufficient to conclude `FEATURE_SPACE_EXHAUSTED` / `SIGNAL_NO_EDGE`, but a finer-grained diagnostic is recommended.
2. The original 89 `champion_pipeline_fresh` alphas have a different failure profile (degenerate raw OHLCV formulas reaching A2 then failing `too_few_trades`) than the current 6.5-day pipeline (Epoch B, indicator-using, failing at A1 train fitness). This is consistent with v0.7.1 governance physically separating Epoch A from Epoch B; the legacy 89 are not directly relevant to current A1 behavior.
3. `engine_telemetry` table being empty since v0.7.1 deployment is a separate observability gap. It does not block this diagnosis (the `arena_batch_metrics` JSONL stream provides equivalent signal), but it should be diagnosed independently.
4. §17.3 NULL-safety predicate gap means Calcifer cannot turn RED while `last_live_at_age_h` is NULL — so "NO_BLOCK" cannot be trusted as a green signal during the cold-start period.
