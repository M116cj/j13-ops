# 01 — HE0 Risk Register

**Sub-order:** TEAM ORDER 0-9Y-HE0-HORIZON-TARGET-DESIGN-SPEC
**Phase:** 2 / sub-doc 01

The seven risks enumerated in the master-order spec, each with concrete mitigation that HE1/HE2/HE3 must implement.

## R1. Longer horizon lowers trade frequency

| Field | Value |
|---|---|
| **Risk** | Per-window trade count drops as horizon grows; risk of dipping under A2_MIN_TRADES=25 in some cohorts |
| **Severity** | MEDIUM — uniformly low trade count would surface as `SIGNAL_TOO_SPARSE` reject; not a strategy failure but a sample-size issue |
| **Likelihood** | LOW for 180/240; MEDIUM for 360 (estimated baseline ~165 trades per window for 360 — well above 25 but tighter buffer) |
| **Detection** | HE3 telemetry: `trade_count_by_horizon`, `signal_density_by_horizon`. Phase-5 dashboards must surface per-cohort min/median/max trade counts |
| **Mitigation** | None at HE1/HE2/HE3 level — A2_MIN_TRADES=25 is locked. If 360-bar surfaces below-25 cohorts, document in HE5 analysis as expected behavior |
| **Action item for HE2** | Generation budget split equal across horizons; do NOT skew toward shorter horizons just to ensure trade count |

## R2. SIGNAL_TOO_SPARSE may rise

| Field | Value |
|---|---|
| **Risk** | The `reject_reason_distribution` may shift toward `SIGNAL_TOO_SPARSE` for the longer horizons |
| **Severity** | LOW — `SIGNAL_TOO_SPARSE` is already a real, deterministic-mapped canonical reason in `RAW_TO_REASON` (per 0-9Y-A taxonomy); not a bug |
| **Likelihood** | MEDIUM at 360-bar; LOW at 180/240 |
| **Detection** | HE3 telemetry: `reject_reason_distribution_by_horizon` |
| **Mitigation** | Per-horizon distribution exposure in HE3. Phase-10 (HE5) analysis must classify each horizon explicitly (`HORIZON_VALID_DEPLOYABLES_FOUND`, `HORIZON_NEAR_BREAKEVEN_PROMISING`, `HORIZON_COST_NEGATIVE_DOMINANT`, `HORIZON_SIGNAL_TOO_SPARSE`, ...). |
| **Action item for HE3** | `aggregate_metrics_availability_by_horizon` must include `signal_density_by_horizon: True` so consumers can detect sparsity per cohort |

## R3. Funding exposure may rise

| Field | Value |
|---|---|
| **Risk** | Longer hold time increases exposure to perpetual funding rates (Binance Futures funding settles every 8h) |
| **Severity** | MEDIUM — at 360 bars (6h) one full funding event may occur per round-trip; at 240 (4h) every other round-trip; at 180 (3h) often less than one funding event per trip |
| **Likelihood** | HIGH at 360; MEDIUM at 240; LOW at 180 |
| **Detection** | If `funding_cost_separate` becomes True in B1's availability flags (currently False; bundled in `cost_per_trade`), HE5 can isolate funding contribution. Otherwise: aggregate `total_cost_by_horizon` will simply be larger for longer horizons |
| **Mitigation** | NONE at HE1-HE3 level. Cost model is locked. Funding cost is **already** baked into the realistic per-trade cost estimate (5–10 bps taker tier already accounts for funding average across regime). HE5 must NOT propose lowering cost; it can only document if funding-related cost spikes are seen on long-horizon-only |
| **Action item for HE5** | If horizon=360 has >2× the cost of horizon=180 in observed `total_cost_by_horizon`, flag as funding-driven anomaly and recommend horizon=180 as the productive baseline |

## R4. Horizon-specific overfit risk

| Field | Value |
|---|---|
| **Risk** | A formula that accidentally fits the 360-bar fwd-return distribution may not generalize; with three horizons in parallel, more search space → more chance of finding spurious survivors |
| **Severity** | HIGH — overfitting at this stage would surface as `train > 0` `val < 0` (classic overfit), exactly the pattern that 0-9Y-C explicitly searched for and did NOT find at 60-bar. Multi-horizon doesn't change validator math but does increase candidate count |
| **Likelihood** | MEDIUM — increases linearly with horizon count |
| **Detection** | HE3 telemetry: `train_sharpe_by_horizon` vs `val_sharpe_by_horizon`. Phase-10 (HE5) per-horizon train→val divergence test (replicating 0-9Y-C Phase 4 method per horizon) |
| **Mitigation** | Validator stack (A1/A2/A3/A4) is mathematically correct (per #53 Phase 4) and is the primary defense; combined-Sharpe gate must continue to require positive `combined_sharpe`. Multi-horizon mass-search must NOT relax any threshold |
| **Action item for HE5** | Per-horizon train→val pair analysis. Any horizon with classic-overfit pattern (train_sharpe > 1, val_sharpe < 0) flagged as `HORIZON_ARTIFACT_ONLY` |

## R5. Candidate hash collision risk

| Field | Value |
|---|---|
| **Risk** | If `alpha_hash = MD5(formula)[:16]` is used as identity but multiple horizons produce the same formula, bloom dedup drops one of them |
| **Severity** | HIGH — silent drop = hidden capability loss |
| **Likelihood** | DETERMINISTIC if alpha_hash alone is used (will happen on every duplicate-formula occurrence) |
| **Detection** | HE1 unit test: same formula at different horizons produces distinct `candidate_id`. Bloom dedup must use `candidate_id`, not `alpha_hash` |
| **Mitigation** | Per HE0 design D4: `candidate_id = f"{alpha_hash}_h{horizon}"`. Composite identity. **alpha_hash itself remains formula-only** to preserve backward-compat with the 89 legacy alphas |
| **Action item for HE1** | Bloom filter usage in `arena_pipeline.py:bloom_*` calls must be reviewed; `bloom_add(candidate_id)` not `bloom_add(alpha_hash)` |

## R6. Label leakage risk

| Field | Value |
|---|---|
| **Risk** | Cross-window leakage: when computing fwd_return at horizon H using bars `[i, i+H]`, if `i + H` falls into the *next* window's range (val window for a train sample, or out-of-sample for val), the label is contaminated |
| **Severity** | CRITICAL — would invalidate every backtest |
| **Likelihood** | NONZERO if not explicitly mitigated; the existing 60-bar code already drops the last 60 bars of the label, so the same pattern just needs extending |
| **Detection** | HE1 unit test: assert `fwd_return[N-H : N]` is all NaN for any window length N and any horizon H |
| **Mitigation** | Per HE0 design D3: drop last `H` rows of the label per window. The forward-return function in `alpha_engine.py:633-637` already does this for the env-var horizon; HE1 only needs to use the parameterized `horizon` correctly |
| **Action item for HE1** | Three explicit unit tests: `test_label_no_leak_180`, `test_label_no_leak_240`, `test_label_no_leak_360` — each asserts last `H` of fwd_return is NaN |

## R7. Cannot average horizon metrics for pass/fail

| Field | Value |
|---|---|
| **Risk** | The temptation: "this batch's median net across all horizons is +0.3 bps, so this batch passed". This is **wrong** because each horizon is a separate cohort; mixing them in one statistic obscures which horizon (if any) is actually edged |
| **Severity** | HIGH — would propagate misleading verdicts to HE5 / HE6 |
| **Likelihood** | LOW if the spec is followed — but a real risk if a downstream consumer treats `aggregate_metrics` as scalar |
| **Detection** | Documentation. Code-review during HE3. HE5 must explicitly classify EACH horizon separately |
| **Mitigation** | All telemetry is **per-horizon**; aggregate scalars (e.g., `train_gross_pnl_median`) on the batch may continue to exist as a population summary, but HE5 must use per-horizon fields for verdict classification |
| **Action item for HE5** | Per-horizon classification mandatory: each of {180, 240, 360} gets its own verdict (`HORIZON_VALID_DEPLOYABLES_FOUND` / etc.). The master verdict is then a function of those three sub-verdicts |

## Summary risk matrix

| Risk | Severity | Likelihood | Mitigation owner |
|---|---|---|---|
| R1 trade frequency drops | MED | LOW-MED | HE3 telemetry; HE5 analysis |
| R2 SIGNAL_TOO_SPARSE rises | LOW | MED-HIGH at 360 | HE3 distribution; HE5 explicit classification |
| R3 funding exposure rises | MED | HIGH at 360 | HE5 anomaly flag; cost stays locked |
| R4 horizon-specific overfit | HIGH | MED | HE3 train-val pair; HE5 explicit divergence test |
| R5 candidate hash collision | HIGH | DETERMINISTIC if not fixed | HE1 composite candidate_id (D4) |
| R6 label leakage | CRITICAL | NONZERO if not mitigated | HE1 unit tests (D3 / R6) |
| R7 cannot average horizon | HIGH | LOW if spec followed | HE5 per-horizon verdict |

The two CRITICAL/HIGH risks (R5, R6) have deterministic mitigations specified in HE0 design D3 and D4; HE1 must implement both with unit tests.
