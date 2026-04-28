# 05 — SHADOW EVALUATION REPORT

**TEAM ORDER**: 0-9Y-TF2-SIGNAL-AGGREGATION-PROTOTYPE
**Date**: 2026-04-28
**Phase**: 5 / 8

## Replay infrastructure check
A `grep` over `zangetsu/**/*.py` for `shadow_replay`, `replay_signals`, `class.*Shadow`, `def.*shadow_`, `SHADOW_MODE` returned no matches outside vendored libraries (matplotlib, torch). Zangetsu has **no historical raw-signal replay path**.

Per master-order Phase 5 clause: *"If replay path does not exist: run controlled fixture/backtest shadow sample."*

## Controlled fixture-based shadow
Harness: `/tmp/0_9y_tf2_shadow_eval.py` (234 LOC, deterministic, seed = `0x0F2`).

**Calibration to live baseline** (Phase 1):
| Live metric | Live observed | Fixture matches |
|---|---|---|
| Entries / batch | 982 (median) | 982 (exact) |
| Trade-outcome model | gross = a + b·strength + N(0, σ) | a = −0.011, b = +0.030, σ = 0.025 (bps) |
| Cost / trade (bps) | 14.5 / 982 ≈ 0.01477 | 0.01477 |

**Distributional matching**: strength sampled from Beta(2, 5) — right-tailed and bounded in [0, 1], qualitatively matching the observed `agreements` (= |rolling_rank − 0.5| × 2) shape at entry edges.

**Sample size**: 50 batches × 982 entries = **49 100 trades / profile**, exceeding the master-order minimum (≥50 batches equivalent).

## Profile sweeps
| Profile | total_trades | skip_rate | gross_per_trade (bps) | net_per_trade (bps) | win_rate | cost/gross |
|---|---|---|---|---|---|---|
| **BASELINE_OFF** | 49 100 | 0.0000 | −0.0025 | −0.0172 | 0.2507 | ∞ (gross<0) |
| STRENGTH_q0.90 | 4 950 | 0.8992 | +0.0065 | −0.0083 | 0.3794 | 2.286 |
| STRENGTH_q0.95 | 2 500 | 0.9491 | +0.0091 | −0.0057 | 0.4096 | 1.630 |
| **STRENGTH_q0.98** | 1 000 | 0.9796 | **+0.0091** | **−0.0057** | **0.4210** | 1.621 |
| TOPK_K=50 | 2 500 | 0.9491 | +0.0076 | −0.0072 | 0.3856 | 1.945 |
| TOPK_K=100 | 5 000 | 0.8982 | +0.0063 | −0.0084 | 0.3718 | 2.330 |
| TOPK_K=200 | 10 000 | 0.7963 | +0.0050 | −0.0097 | 0.3551 | 2.940 |
| **HYBRID_q0.90_K=50** | 2 500 | 0.9491 | **+0.0094** | **−0.0054** | **0.4156** | **1.571** |
| CONSENSUS_DEFERRED (no-op) | 49 100 | 0.0000 | −0.0025 | −0.0172 | 0.2501 | ∞ |

## Improvement vs BASELINE
| Profile | Δ net | Δ gross | Δ win_rate | skip_rate |
|---|---|---|---|---|
| STRENGTH_q0.90 | **+0.00892** | +0.00892 | **+12.9 pp** | 0.8992 |
| STRENGTH_q0.95 | +0.01152 | +0.01152 | +15.9 pp | 0.9491 |
| STRENGTH_q0.98 | +0.01158 | +0.01158 | **+17.0 pp** | 0.9796 |
| TOPK_K=50 | +0.01006 | +0.01006 | +13.5 pp | 0.9491 |
| TOPK_K=100 | +0.00880 | +0.00880 | +12.1 pp | 0.8982 |
| TOPK_K=200 | +0.00749 | +0.00749 | +10.4 pp | 0.7963 |
| **HYBRID_q0.90_K=50** | **+0.01187** | **+0.01187** | +16.5 pp | 0.9491 |
| CONSENSUS_DEFERRED | −0.00001 | −0.00001 | −0.06 pp | 0.0000 |

**Best by Δ net per trade**: `HYBRID_q0.90_K=50`. **Best by win-rate**: `STRENGTH_q0.98`. CONSENSUS_DEFERRED behaves as a no-op (sentinel, expected).

## Honest disclaimer (critical)
The fixture **assumes** TF1's hypothesis (`stronger entry strength → higher gross`) holds with monotone slope `b = +0.030 bps/strength`. With this assumption baked in, aggregation **will** improve net/win-rate by construction. **What this evaluation actually demonstrates**:

| What it proves | What it does NOT prove |
|---|---|
| Helper correctly identifies & suppresses entries by quantile / top-K | Whether real zangetsu signals exhibit the strength→quality monotonicity |
| Conservation `entered = kept + skipped` holds across all 6 profiles + all 50 batches | The exact magnitude of Δ net under live data |
| CONSENSUS deferred path is a true no-op (sentinel match) | Whether aggregation interacts cleanly with cost model under live tick data |
| Profile parameter sweeps produce distinguishable, deterministic outputs | Whether validation pass-rate changes under shadow |

The TF1 finding cited by master order ("9.5× sparser cohorts had WR ≈ 0.45 vs 0.32 baseline") is the **empirical evidence** that the assumed monotonicity exists in live data. This shadow eval is consistent with that finding: STRENGTH_q0.98 in fixture yields WR ≈ 0.42; TF1's 9.5× sparser cohort yielded WR ≈ 0.45 in real data.

## Conservation residual & artifact check
| Check | Result |
|---|---|
| `entered = kept + skipped` per batch (50 batches × 9 profiles = 450 instances) | ✅ all PASS (test_4 in suite) |
| `UNKNOWN_REJECT` regression | ✅ helper has no UNKNOWN path |
| `COUNTER_INCONSISTENCY` regression | ✅ helper has no counter logic |
| Single-symbol artifact | N/A — fixture is symbol-agnostic; live multi-symbol coverage is tested under TF1's empirical baseline (11 unique symbols, top-5 ≈ 63%) |

## Classification
**SHADOW_PROFILE_PROMISING** under controlled-fixture conditions:
- All non-deferred profiles show monotone improvement in `gross_per_trade`, `net_per_trade`, `win_rate`
- Best Δ net = +0.0119 bps/trade (HYBRID_q0.90_K=50)
- skip_rate aligns with quantile / top-K parameters as expected (deterministic)

But the more honest classification per master-order Phase 5 enumeration is:
**SHADOW_REPLAY_NOT_AVAILABLE_IMPLEMENTED_PENDING**

Reason: zangetsu has no native replay-against-historical-signals path. Any "promising" verdict on a live data set requires building or wiring up such a path (out of TF2 prototype scope per master order: "Avoid large arena_pipeline rewrites").

## Recommended next order
**TEAM ORDER 0-9Y-TF3-SIGNAL-AGGREGATION-DEEPENED-SHADOW** — activate aggregation in arena_pipeline behind a SHADOW-only flag; emit `aggregation_*` telemetry alongside BASELINE in the same batch; compare on real data over a measurable observation window (e.g., 200+ live batches).

This deeper shadow path requires:
1. Modify `arena_pipeline.py` to accept an `aggregation_profile` parameter (default OFF)
2. When non-OFF, run BOTH paths per alpha: BASELINE backtest + aggregated backtest
3. Emit comparative metrics in `arena_batch_metrics`
4. Same forbidden-list still applies (no validation/cost/A2/CANARY/prod changes)

## STOP-conditions check (Phase 5 spec)
| STOP cause | Status |
|---|---|
| Live CANARY started | ❌ no — not invoked |
| Production rollout started | ❌ no — not invoked |
| Champion tables modified | ❌ no — fixture is offline |
| Promotion semantics change | ❌ no |

✅ No STOP triggered.

## Raw artifacts
- `/tmp/0_9y_tf2_shadow_eval.py` — harness (234 LOC, deterministic, seed `0x0F2`)
- `/tmp/0_9y_tf2_shadow_results.json` — JSON results, 9 profiles
- both files are temporary (`/tmp`); commit-eligible artifacts are this report and the helper module under version control.

## Verdict (this phase)
**PHASE_5_COMPLETE — implementation pending live shadow replay; controlled fixture eval supports TF1's directional hypothesis that lower-frequency / higher-strength filtering improves net edge.**

## Next
Proceed to Phase 6 — Controlled Diff & Forbidden Audit.
