# 10 — Controlled Diff Report

**TEAM ORDER**: 0-9AA — Phase 10
**Date**: 2026-04-30
**Mode**: GOVERNANCE / DOCS-ONLY

## Objective

Verify selection-only behavior — no implementation, no runtime mutation, no DB mutation, no production rollout, no live trading.

## Source-Mutation Checks

| Area | Expected | Observed | Verdict |
|---|---|---|---|
| alpha generation | no change | no change | PASS |
| mutation / crossover / search policy | no change | no change | PASS |
| Arena thresholds | no change | no change | PASS |
| `A2_MIN_TRADES` | remains 25 | unchanged (verified at `arena_gates.py:48`, `settings.py:29`) | PASS |
| Arena pass / fail logic | no change | no change | PASS |
| champion promotion | no change | no change | PASS |
| `deployable_count` semantics | no change | no change | PASS |
| capital / risk engine | no change | no change | PASS |
| production execution path | no change | no change | PASS |
| production DB schema | no DDL | none | PASS |
| production DB data mutation | none | only read-only `SELECT` queries | PASS |
| CANARY | not started | not started | PASS |
| production rollout | not started | not started | PASS |
| live trading | none | none | PASS |
| Binance trading-key usage | none | none | PASS |

## Runtime State (informational, not part of diff)

The repository working tree contains modifications to runtime byproducts that are **not** part of 0-9AA staging:

```
 M calcifer/maintenance.log         — calcifer log emission
 M calcifer/maintenance_last.json   — calcifer status file
 M calcifer/report_state.json       — calcifer report state
 M zangetsu/logs/engine.jsonl.1     — log rotation byproduct
```

These are produced by long-running services (calcifer, arena_pipeline workers) and are NOT included in the 0-9AA commit. Confirmed runtime baseline:

| Item | Value |
|---|---|
| HEAD | `6207bb1b` |
| Branch | `main` (work commits on `phase-7/0-9aa-new-alpha-axis-selection`) |
| arena_pipeline workers | 4 |
| `champion_pipeline_staging` ARENA1_COMPLETE | 184 |
| `champion_pipeline_fresh` | 89 |
| `zangetsu_status.deployable_count` | 0 |
| `zangetsu_status.last_live_at_age_h` | NULL |

## File-Scope Diff (under 0-9AA)

Added (NEW) files only — all under `zangetsu/docs/recovery/20260430-0-9aa-new-alpha-axis-selection/`:

```
00_state_lock.md
01_failure_context_from_0-9y_0-9z_0-9za.md
02_candidate_axis_inventory.md
03_data_availability_matrix.md
04_long_short_axis_viability.md
05_cost_and_turnover_risk_matrix.md
06_a2_arena_survival_assessment.md
07_axis_scoring_model.md
08_top_axis_deep_dive.md
09_final_axis_decision.md
10_controlled_diff_report.md      (this file)
11_final_report.md
```

All 12 files are docs-only / decision-only. No source-code change. No DB DDL. No runtime patch. No model / config / threshold change.

## Verdict

```
CONTROLLED_DIFF = DOCS_ONLY / EVIDENCE_ONLY
FORBIDDEN_DIFF = 0
```

**`CONTROLLED_DIFF_PASS`**

## Deliverable

`10_controlled_diff_report.md` — frozen.
