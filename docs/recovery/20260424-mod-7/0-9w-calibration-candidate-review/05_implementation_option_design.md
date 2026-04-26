# 05 — Implementation Option Design

## Option A — Lower global cost_bps from 1.0x to 0.5x

| Attribute | Detail |
| --- | --- |
| Description | Edit `zangetsu/config/cost_model.py` Stable tier `taker_bps` from 5.0 to 2.5 (or apply 0.5x multiplier to `total_round_trip_bps`) |
| Files affected | `zangetsu/config/cost_model.py` (1 file, ~6 lines) |
| Runtime impact | Every backtest re-evaluates with halved cost; val_neg_pnl gate becomes ~50% looser |
| Validation impact | Survivor pool floods with cells that should fail in live (Phase 3 shows 8/8 are artifacts) |
| Governance risk | **HIGH** — model diverges from real execution; survivor selection is corrupted |
| Test requirements | Cannot be safely tested without first implementing maker fill measurement (Phase 4 R1, R9) |
| Rollback path | Trivial git revert |
| **Recommendation** | **REJECT** |

## Option B — Add execution-mode-aware cost model

| Attribute | Detail |
| --- | --- |
| Description | Extend `SymbolCost` with `maker_fill_rate` (default 0.0); compute cost as `(maker_bps × maker_fill_rate + taker_bps × (1-maker_fill_rate)) × 2 + slippage + funding`. Default unchanged (taker-only) until measurement layer exists. |
| Files affected | `zangetsu/config/cost_model.py` (~30 lines extension); backtester cost lookup unchanged at call site |
| Runtime impact | NONE if maker_fill_rate stays at 0.0 (default = current behavior) |
| Validation impact | NONE (cost identical with default config) |
| Governance risk | LOW — additive, defaultable to current behavior |
| Test requirements | Unit test that maker_fill_rate=0.0 reproduces current `total_round_trip_bps`; unit test that maker_fill_rate=1.0 reduces cost as expected |
| Rollback path | Trivial git revert; configuration set to maker_fill_rate=0.0 makes it inert |
| **Recommendation** | **MAYBE — but needs paired observation infrastructure (R1, R9) to actually use** |

## Option C — Add symbol-specific cost calibration

| Attribute | Detail |
| --- | --- |
| Description | Override `taker_bps`, `slippage_bps`, `funding_8h_avg_bps` per symbol based on measured live execution data |
| Files affected | `cost_model.py` already supports per-symbol; would also need a measurement source (DB telemetry → per-symbol updates) |
| Runtime impact | Per-symbol cost diverges from tier defaults |
| Validation impact | Some symbols become easier to pass val gate, others harder |
| Governance risk | MEDIUM — requires governance review of each symbol-level change |
| Test requirements | Same as Option B + per-symbol audit |
| Rollback path | Per-symbol revert |
| **Recommendation** | **MAYBE — better deferred until execution-mode-aware model (Option B) is in place** |

## Option D — Add dry-run-only calibrated validation branch

| Attribute | Detail |
| --- | --- |
| Description | Add `cost_model_dry_run` flag in val_filter chain that runs validation TWICE (current cost + half cost) and emits both results to telemetry. Live decisions still based on full-cost result. |
| Files affected | `arena_pipeline.py` val_filter section + telemetry schema |
| Runtime impact | ~2x backtest CPU per candidate; emits dual-cost evaluation to logs |
| Validation impact | NONE (live promotion still based on full cost) |
| Governance risk | LOW — observation only; no policy change |
| Test requirements | Output format check; comparable PnL distributions |
| Rollback path | Disable feature flag |
| **Recommendation** | **MAYBE — useful for ongoing observability but not addressing the root cause** |

## Option E — Keep cost unchanged and redesign formula universe

| Attribute | Detail |
| --- | --- |
| Description | Accept that 11.5 bps is realistic for current execution; focus alpha generation on higher-edge formulas (longer horizons, multi-timeframe, regime-conditional) |
| Files affected | `alpha_zoo_injection.py` (formula list expansion); GP fitness function (longer-horizon features); strategy parameters |
| Runtime impact | New alpha population; A1/A23 GP search re-converges |
| Validation impact | NONE in cost / threshold semantics; some new alpha types may pass val_neg_pnl gate |
| Governance risk | MEDIUM — formula universe expansion requires research / paper review |
| Test requirements | Each new formula category needs offline replay before zoo injection |
| Rollback path | Per-formula revert |
| **Recommendation** | **YES — this addresses Phase 8 H7 (alpha universe weakness, 60% confidence)** |

## Option F — Expand calibration matrix before any implementation

| Attribute | Detail |
| --- | --- |
| Description | Re-run a wider matrix: 11 symbols × 30+ formulas × 5 cost levels × 5 ET × 5 MH = ~80k cells. Aim: find robust survivors that span ≥2 symbols with positive train AND val PnL. |
| Files affected | `0-9wch-replay.py` enhancement (more symbols, more formulas, more granularity) |
| Runtime impact | Offline only — ~30 minutes wall time given current 29.6s for 663 cells |
| Validation impact | NONE (offline) |
| Governance risk | LOW — pure offline observation |
| Test requirements | Replay sanity tests reproduce existing matrix as a subset |
| Rollback path | n/a (read-only) |
| **Recommendation** | **YES — provides decision-grade evidence before any model change** |

## Option G (NEW) — Build maker order routing infrastructure

| Attribute | Detail |
| --- | --- |
| Description | Implement maker-first order routing in `zangetsu/execution/` (currently absent). Post limit orders 1 tick inside the spread; fall back to taker after timeout. Measure observed maker fill rate per symbol. |
| Files affected | NEW execution module (~500 lines); telemetry schema for fill mode tracking |
| Runtime impact | Different live execution behavior; expected lower realized cost |
| Validation impact | Eventually feeds into cost_model maker_fill_rate; until measured, cost_model unchanged |
| Governance risk | **HIGH** — touches order routing; requires execution / capital / risk review |
| Test requirements | Paper trading on testnet; CANARY before production |
| Rollback path | Feature flag |
| **Recommendation** | **PARALLEL TRACK — addresses the root cause (real execution cost) rather than the model. Larger scope, separate governance order.** |

## Comparative Summary Table

| Option | Implementation Risk | Helps Survivors? | Addresses Root Cause? | Recommended? |
| --- | --- | --- | --- | --- |
| A — Lower cost_bps globally | HIGH | yes superficially | NO (fakes survival) | **REJECT** |
| B — Execution-mode-aware cost | LOW (additive) | NO without observation | partial | maybe later |
| C — Symbol-specific cost | MEDIUM | NO without observation | partial | defer to after B |
| D — Dual-cost dry-run telemetry | LOW | NO (observation only) | NO | maybe — observability only |
| E — Formula universe redesign | MEDIUM | YES if new alphas have edge | YES (H7) | **RECOMMENDED** |
| F — Expand calibration matrix | LOW | provides better evidence | provides better evidence | **RECOMMENDED** |
| G — Maker order routing | HIGH | YES if successful | YES (real cost reduction) | **PARALLEL TRACK** |

## Phase 5 Verdict

→ The safest immediate next step is a combination of:
- **Option F** (expanded calibration matrix) for offline evidence-grade analysis, paired with
- **Option E** (formula universe redesign) for alpha-side improvement.

Cost-model changes (Options A, B, C) should be **deferred** until either:
- maker order routing infrastructure (Option G) is in place AND measured, OR
- the formula universe redesign (Option E) demonstrably produces survivors at the current 1.0x cost.
