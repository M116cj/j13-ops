# 11 — Controlled Diff Report

**TEAM ORDER**: 0-9ZA-COMPLETE — Phase 11
**Date**: 2026-04-30
**Mode**: GOVERNANCE / DOCS-ONLY

## Objective

Verify no forbidden system mutation occurred during 0-9ZA Phase 5–12 completion.

## Source-Mutation Checks

| Area | Expected | Observed | Verdict |
|---|---|---|---|
| alpha generation | no change | no change | PASS |
| mutation / crossover / search policy | no change | no change | PASS |
| Arena thresholds | no change | no change | PASS |
| `A2_MIN_TRADES` | remains 25 | unchanged | PASS |
| Arena pass / fail logic | no change | no change | PASS |
| champion promotion | no change | no change | PASS |
| `deployable_count` semantics | no change | no change | PASS |
| capital / risk engine | no change | no change | PASS |
| production execution path | no change | no change | PASS |
| production DB schema | no change | no DDL | PASS |
| production DB data mutation | none | none (read-only queries only) | PASS |
| CANARY | not started | not started | PASS |
| production rollout | not started | not started | PASS |
| live trading | none | none — STOP-2 enforced | PASS |
| Binance trading-key usage | none | none — READ-ONLY mode | PASS |

## Runtime State (informational, not part of diff)

The repository working tree contains modifications to runtime byproducts that are **not** part of 0-9ZA staging:

```
 M calcifer/maintenance.log         — runtime log emission
 M calcifer/maintenance_last.json   — calcifer status file
 M calcifer/report_state.json       — calcifer report state
 M zangetsu/logs/engine.jsonl.1     — log rotation byproduct
```

These are produced by long-running services (calcifer, arena_pipeline workers) and are **not** committed under 0-9ZA. Confirmed runtime baseline:

| Item | Value |
|---|---|
| HEAD | `3cb5e08f` |
| Branch | `main` |
| arena_pipeline workers | 4 (matches baseline) |
| `champion_pipeline_staging` rows | 184 ARENA1_COMPLETE |
| `champion_pipeline_fresh` rows | 89 |
| `zangetsu_status.deployable_count` | 0 |
| `zangetsu_status.last_live_at_age_h` | NULL (never reached live) |

Note: the 0-9ZA-COMPLETE order recorded "89 ARENA2_REJECTED / 184 ARENA1_COMPLETE / 0 deployable". The live VIEW shows the 184 rows are in `champion_pipeline_staging` (status = ARENA1_COMPLETE) and 89 rows in `champion_pipeline_fresh`. Total population unchanged from order baseline; only the table label differed.

## File-Scope Diff

Changed (added) files under 0-9ZA:

```
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/00_state_lock.md                         (Phase 0, prior)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/01_fee_tier_account_verification.md     (Phase 1, prior)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/02_long_short_signal_inventory.md       (Phase 2, prior)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/03_orderbook_data_availability.md       (Phase 3, prior)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/04_maker_fill_shadow_simulator_design.md (Phase 4, prior)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/05_long_side_maker_fill_analysis.md     (NEW)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/06_short_side_maker_fill_analysis.md    (NEW)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/07_adverse_selection_and_delay_model.md (NEW)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/08_funding_slippage_fee_decomposition.md (NEW)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/09_vip3_feasibility.md                   (NEW)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/10_combined_decision_matrix.md           (NEW)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/11_controlled_diff_report.md             (NEW — this file)
zangetsu/docs/recovery/20260429-0-9za-long-short-maker-fill-condition-closure/12_final_report.md                       (NEW)
```

All NEW files are docs-only / evidence-only. No source-code changes. No DB DDL. No runtime patch.

## Verdict

```
CONTROLLED_DIFF = DOCS_ONLY / EVIDENCE_ONLY
FORBIDDEN_DIFF = 0
```

**`CONTROLLED_DIFF_PASS`**
