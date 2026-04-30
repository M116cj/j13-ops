# 10 — Controlled Diff Report

**ORDER**: 0-9AD — Phase 9

## Source-Mutation Checks

| Area | Expected | Observed | Verdict |
|---|---|---|---|
| alpha generation (production) | no change | no change in zangetsu/services/* | PASS |
| Arena thresholds | no change | no change in arena_gates.py | PASS |
| A2_MIN_TRADES | remains 25 | 25 (verified arena_gates.py:48 + settings.py:29 + tests) | PASS |
| Arena pass / fail logic | no change | no change | PASS |
| champion promotion | no change | no change | PASS |
| deployable_count semantics | no change | VIEW returned 0 at run start AND post-merge | PASS |
| capital / risk engine | no change | no change | PASS |
| production execution path | no change | no change | PASS |
| production DB schema | no DDL | none | PASS |
| production DB data mutation | none | only read-only SELECT for status checks | PASS |
| CANARY | not started | not started | PASS |
| production rollout | not started | not started | PASS |
| live trading | none | none | PASS |
| Binance trading-key usage | none | none | PASS |
| arena_pipeline imports core_factory | NEVER | not present (test_core_factory_not_imported_by_production_pipeline PASS) | PASS |
| runtime worker restart | none | none | PASS |
| new axis introduced | NO | only C run | PASS |

## File Scope (staged)

NEW additions:
```
zangetsu/core_factory/next_batch_weights.py
zangetsu/tests/test_core_factory_next_batch_weights.py
```

MODIFIED (within shadow-only core_factory):
```
zangetsu/core_factory/shadow_batch_runner.py    (add survivor_report.csv writer + next_batch_weights.json writer)
```

EVIDENCE (under recovery folder):
```
zangetsu/docs/recovery/20260430-0-9ad-c-axis-shadow-mining-start/00_state_lock.md
…through…
zangetsu/docs/recovery/20260430-0-9ad-c-axis-shadow-mining-start/11_final_report.md
```

MACHINE OUTPUTS (under shadow_outputs/):
```
candidate_manifest.jsonl
shadow_batch_results.jsonl
reject_reason_summary.json
long_short_summary.csv
survivor_report.csv
near_survivor_report.csv
feedback_weights.json
next_batch_weights.json
formula_collision_report.csv
axis_scoreboard.csv
run_summary.json
h_clip_distribution.json (empty marker — no H axis in this run)
d_band_crossing_report.csv (empty — no D axis in this run)
d_symbol_coverage.csv (empty — no D axis in this run)
```

(Path-scoped `.gitignore` mirrors prior orders to allow shadow_outputs/*.jsonl past the repo *.jsonl rule.)

## Working-Tree Byproducts NOT Included

```
M calcifer/maintenance.log
M calcifer/maintenance_last.json
M calcifer/report_state.json
M zangetsu/logs/engine.jsonl.1
```

These are runtime byproducts of long-running services and remain unstaged.

## Tests

`pytest zangetsu/tests/test_core_factory_*.py` → **54 / 54 PASSED in 2.99 s** (re-verified post-write).

## Verdict

```
CONTROLLED_DIFF = SOURCE_AND_TESTS_AND_EVIDENCE_AND_OUTPUTS_ONLY
FORBIDDEN_DIFF = 0
```

**`CONTROLLED_DIFF_PASS`**

## Acceptance Mapping

- AC21 PASS tests pass (54/54)
- AC22 PASS controlled diff forbidden_diff = 0
- AC23 PASS A2_MIN_TRADES = 25 unchanged
- AC24 PASS Arena thresholds unchanged
- AC25 PASS champion promotion unchanged
- AC26 PASS deployable_count semantics unchanged
- AC27 PASS no live trading
- AC28 PASS no CANARY
- AC29 PASS no production rollout
- AC30 PASS no production DB mutation
- AC31 PASS no execution / capital / risk mutation
