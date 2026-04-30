# 15 — Controlled Diff Report

**ORDER**: 0-9AC-CLOSE — Workstream F

## Source-Mutation Checks

| Area | Expected | Observed | Verdict |
|---|---|---|---|
| alpha generation | no change | no change in zangetsu/services/* | PASS |
| Arena thresholds | no change | no change in services/arena_gates.py | PASS |
| A2_MIN_TRADES | remains 25 | 25 (verified arena_gates.py:48 + settings.py:29 + tests) | PASS |
| Arena pass / fail logic | no change | no change | PASS |
| champion promotion | no change | no change | PASS |
| deployable_count semantics | no change | no change (VIEW returned 0 at run start AND post-merge) | PASS |
| capital / risk engine | no change | no change | PASS |
| production execution path | no change | no change | PASS |
| production DB schema | no DDL | none | PASS |
| production DB data mutation | none | only read-only SELECT for status checks | PASS |
| CANARY | not started | not started | PASS |
| production rollout | not started | not started | PASS |
| live trading | none | none — no exchange order placed | PASS |
| Binance trading-key usage | none | none | PASS |
| arena_pipeline.py imports core_factory | NEVER | not present (test_core_factory_not_imported_by_production_pipeline PASS) | PASS |
| runtime worker restart | none | none | PASS |

## File Scope (staged for 0-9AC-CLOSE PR)

NEW additions:
```
zangetsu/core_factory/signal_processing.py
zangetsu/tests/test_core_factory_value_clip.py
zangetsu/tests/test_core_factory_band_crossing.py
zangetsu/tests/test_core_factory_d_universe_expansion.py
zangetsu/tests/test_core_factory_round2_invariants.py
zangetsu/tests/test_core_factory_axis_scoreboard_round2.py
```

MODIFIED (within shadow-only core_factory):
```
zangetsu/core_factory/economic_arena_adapter.py  (add EvaluationParams, lru_cache, clip+band hooks)
zangetsu/core_factory/shadow_batch_runner.py     (add CLI flags, ALL14_SYMBOLS, per-axis params)
```

EVIDENCE (under recovery folder):
```
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/00_state_lock.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/01_round2_scope_lock.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/02_round1_findings_summary.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/03_h_value_clip_implementation.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/04_d_band_crossing_implementation.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/05_d_universe_expansion_report.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/06_round2_tournament_design.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/07_candidate_generation_report.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/08_economic_arena_evaluation_report.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/09_long_short_report.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/10_reject_reason_report.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/11_survivor_near_survivor_report.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/12_feedback_weights_report.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/13_axis_scoreboard.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/14_gemini_adversarial_review.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/15_controlled_diff_report.md  (this file)
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/16_final_report.md
zangetsu/docs/recovery/20260430-0-9ac-multi-axis-round2-bounded/17_secret_hygiene_report.md
```

MACHINE OUTPUTS (under shadow_outputs/):
```
shadow_outputs/candidate_manifest.jsonl
shadow_outputs/shadow_batch_results.jsonl
shadow_outputs/axis_scoreboard.csv
shadow_outputs/reject_reason_summary.json
shadow_outputs/long_short_summary.csv
shadow_outputs/feedback_weights.json
shadow_outputs/near_survivor_report.csv
shadow_outputs/formula_collision_report.csv
shadow_outputs/h_clip_distribution.json
shadow_outputs/d_band_crossing_report.csv
shadow_outputs/d_symbol_coverage.csv
shadow_outputs/run_summary.json
```

(.gitignore re-include rule mirrors 0-9AB to allow shadow_outputs/*.jsonl past the repo *.jsonl rule; only inside this evidence folder.)

## Working-Tree Byproducts NOT Included

```
M calcifer/maintenance.log
M calcifer/maintenance_last.json
M calcifer/report_state.json
M zangetsu/logs/engine.jsonl.1
```

These are runtime byproducts of long-running services and remain unstaged.

## Tests

`pytest zangetsu/tests/test_core_factory_*.py` → **50 / 50 PASSED in 3.02s** (re-verified post-write).

## Verdict

```
CONTROLLED_DIFF = SOURCE_AND_TESTS_AND_EVIDENCE_AND_OUTPUTS_ONLY
FORBIDDEN_DIFF = 0
```

**`CONTROLLED_DIFF_PASS`**

## Acceptance Mapping

- AC12 PASS controlled diff reports forbidden_diff = 0
- AC13 PASS A2_MIN_TRADES = 25 unchanged
- AC14 PASS Arena thresholds unchanged
- AC15 PASS champion promotion unchanged
- AC16 PASS deployable_count unchanged
- AC17 PASS execution / capital / risk unchanged
- AC18 PASS no live trading
- AC19 PASS no CANARY
- AC20 PASS no production rollout
- AC21 PASS no production DB mutation
