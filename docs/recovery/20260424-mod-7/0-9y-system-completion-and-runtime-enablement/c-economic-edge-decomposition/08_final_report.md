# 08 — Final Report (Subprogram C)

**Order:** TEAM ORDER 0-9Y-C-ECONOMIC-EDGE-DECOMPOSITION
**Phase:** 8
**Date (UTC):** 2026-04-28T00:14Z
**Author:** Claude Lead

## 1. Final verdict

```
DECOMPOSED_GROSS_EDGE_LOST_TO_COST
```

Secondary findings (compounding, not independent roots): `WIN_RATE_STRUCTURALLY_LOW`, `TRADE_FREQUENCY_AMPLIFIES_COST`, `NO_HIDDEN_COHORT_EDGE`, `VAL_NOT_REACHED`.

## 2. HEAD before / after

| | Before | After (post-merge) |
|---|---|---|
| Mac HEAD | `d9d178348b6ec37cbef9212579a7d4b35bf0cd73` | TBD (Phase 9) |
| Alaya HEAD | `d9d178348b6ec37cbef9212579a7d4b35bf0cd73` | TBD (Phase 9) |

## 3. Files changed (docs-only)

| Path | Type |
|---|---|
| `docs/recovery/.../c-economic-edge-decomposition/00_state_lock.md` | new |
| `docs/recovery/.../c-economic-edge-decomposition/01_live_snapshot.md` | new |
| `docs/recovery/.../c-economic-edge-decomposition/02_gross_vs_cost_decomposition.md` | new (subagent) |
| `docs/recovery/.../c-economic-edge-decomposition/03_per_cohort_breakdown.md` | new (subagent) |
| `docs/recovery/.../c-economic-edge-decomposition/04_train_val_divergence.md` | new (subagent) |
| `docs/recovery/.../c-economic-edge-decomposition/05_signal_density.md` | new (subagent) |
| `docs/recovery/.../c-economic-edge-decomposition/06_synthesis.md` | new |
| `docs/recovery/.../c-economic-edge-decomposition/07_controlled_diff_report.md` | new (governance subagent) |
| `docs/recovery/.../c-economic-edge-decomposition/08_final_report.md` | this file |

**No source / config / test / DB schema change.** One operator-authorized worker restart was performed at subprogram entry per j13 directive (option A: 重啟); no other runtime modification.

## 4. Headline numbers

| Metric | Value | Interpretation |
|---|---|---|
| Batches analyzed | 106 | Post-restart, schema_version `0-9y-b1-v1` |
| `entered_count` | 10 / batch | constant |
| `passed_count` | 0 / batch | constant — no champions emerge |
| `reject_reason_distribution` | `{COST_NEGATIVE: 10}` | 100 % of batches |
| `COUNTER_INCONSISTENCY` | 0 | PR #50 chain-fix verified live |
| `UNKNOWN_REJECT` | 0 | PR #49 chain-fix verified live |
| `train_gross_pnl_median` | 2.46 bps | always positive (0/106 ≤ 0) |
| `train_gross_minus_net_median` (cost charged) | 3.60 bps | exceeds gross |
| `train_net_pnl_median` | -1.33 bps | structurally negative |
| Cost-to-gross ratio | 1.54× | cost dominates gross by 54% |
| `train_win_rate_median` | 0.32 | structurally low; max 0.494 (zero batches reach 50%) |
| `signal_density_per_bar` | 0.00702 | ample (median ~989 trades / 140k bars) |
| Batches with `gross > cost` | 4 / 106 (3.8%) | rare but nonzero |
| Batches with `gross > 0 AND net > 0` | 2 / 106 (1.9%) | truly tradeable |
| Hidden-cohort edge | NONE | 0 / 14 (symbol × regime) cells with median(gross) > median(cost) |
| Val ran | 14 / 106 batches (13.2%) | most alphas die at train |
| Combined sharpe passed | 0 / 106 (0%) | even val-survivors fail combined |
| Train→val classic overfit | 0 / 14 val-seen | no overfitting; both train and val cost-negative |
| Density-vs-net correlation | INVERSE | sparser quartile has BEST net (−0.29 vs Q3's −1.75) |

## 5. Causal chain (one paragraph)

Alpha generation produces signals with small positive gross edge (median 2.46 bps); win rate is structurally low (median 32%, never ≥ 50%); high trade frequency (~989 trades / batch) at low WR multiplies cost burn; per-trade cost (14.5 bps round-trip) and aggregate cost charged (3.60 bps median) outpace aggregate gross (2.46 bps median); net is negative (−1.33 bps median); validator correctly rejects 100% with COST_NEGATIVE; no symbol or regime cohort beats cost; sparser-density quartile actually has BETTER net (suggesting trade-frequency reduction would help, but cannot fix WR-cost gap alone). Cost model and validator stack are both mathematically correct and locked.

## 6. What's NOT the cause

- ❌ NOT negative gross edge (gross is always positive)
- ❌ NOT per-symbol concentration (uniform across 14 symbols × 3 regimes)
- ❌ NOT train→val overfitting (both train and val are cost-negative when val runs)
- ❌ NOT insufficient signal density (density is ample; sparsity actually correlates with BETTER net)
- ❌ NOT a telemetry artifact (PRs #48-50 chain-fix verified live; conservation residual = 0 in 106/106)

## 7. Recommended downstream subprograms

Per the carry-forward audit, this is a strategic redesign question, not a bug fix. Forward path:

| Subprogram | Recommended action |
|---|---|
| **D — Strategic Redesign Decision** | j13 to choose redesign axis: (a) target/horizon to expose larger gross-per-trade (e.g., 240-bar fwd return vs current 60-bar), (b) feature space to enable higher-WR signals (e.g., add order-book / funding-rate cross-symbol features), (c) trade-frequency policy (e.g., signal aggregation, hold-time gates to reduce cost burn). Cost itself is locked; cannot weaken. |
| **E\*** | Implementation of D's choice. Likely additive, behind feature flag, with new generation_profile_id. |
| **F — Deployable Flow Recheck** | Re-run Subprogram C analysis on the new generation profile. Acceptance: at least one cohort with sustained `gross > cost`. |
| **G — CANARY Readiness** | Gated by F + a stable champion population. |
| **H — Production Rollout** | Gated by G + j13 sign-off. |

## 8. Forbidden ops audit

**0**

| Item | Status |
|---|---|
| threshold change | NO |
| validation change | NO |
| A2_MIN_TRADES change (25 unchanged) | NO |
| Arena pass/fail / champion promotion / deployable_count change | NO |
| alpha_zoo run | NO |
| live CANARY started | NO |
| production rollout | NO |
| runtime calibration | NO |
| DB write | NO |
| cost model change | NO |
| validator stack change | NO |
| force-push | NO |
| hard reset Alaya | NO |
| log wipe | NO |
| operator-authorized worker restart | YES — j13 directive, documented in `00_state_lock.md` |

## 9. Q1 / Q2 / Q3 self-check (final)

- **Q1 Adversarial (5-dim)**: PASS — 4 parallel subagents each anchored verdict to specific numbers; no inferred-from-inference; population coverage explicit (val=14/106, combined=0/106 disclosed); cohort uniformity verified across all (symbol × regime × lane); β-pattern vs negative-gross distinction explicitly tested with count of `gross ≤ 0` = 0
- **Q2 Structural**: PASS — read-only; runtime untouched after the operator-authorized restart; chain-fix from PRs #48-50 verified live with 106/106 conservation
- **Q3 Efficiency**: PASS — 8 evidence files (target ≤ 9; `09_*` not needed because no patch); 4 subagents in parallel for Phases 2-5; 1 subagent for Phase 7 governance; Lead synthesis in 1 doc; full subprogram completed in single Mac+Alaya session

## 10. Telegram status

Phase 9 message will be sent to Thread 356 after PR merge.

## 11. Master plan position

A → B1 → B2 → B3 → **C ✓** → D → checkpoint → E* → F → G → H

C is complete. The next step requires **j13 strategic-redesign decision (D)** before any implementation work proceeds. The forbidden-ops list remains in effect: alpha_zoo, CANARY, and production rollout stay BLOCKED until D / E* / F / G / H sequence completes.
