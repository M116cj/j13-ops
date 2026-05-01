# 11 — Controlled Diff Report

**ORDER**: 0-9AF — Phase 7

## Source-Mutation Checks

| Area | Expected | Observed | Verdict |
|---|---|---|---|
| alpha generation (production) | no change | no change | PASS |
| Arena thresholds | no change | no change in arena_gates.py | PASS |
| A2_MIN_TRADES | remains 25 | 25 (verified arena_gates.py:48 + settings.py:29 + tests) | PASS |
| Arena pass / fail logic | no change | no change | PASS |
| champion promotion | no change | no change | PASS |
| deployable_count semantics | no change | VIEW returned 0 at deploy AND post-merge | PASS |
| capital / risk engine | no change | no change | PASS |
| production execution path | no change | no change | PASS |
| production DB schema | no DDL | none | PASS |
| production DB data mutation | none | dashboard reads OHLCV parquet only via core_factory; no SELECT against zangetsu DB | PASS |
| live trading | none | none | PASS |
| CANARY | not started | not started | PASS |
| production rollout | not started | not started | PASS |
| arena_pipeline mutation | none | none | PASS |
| arena_pipeline imports core_factory | NEVER | not present (existing test_core_factory_invariants.py PASS) | PASS |
| dashboard (0-9AF modules) imports arena_pipeline | NEVER | not present (test_dashboard_contracts.py::test_dashboard_does_not_import_arena_pipeline PASS) | PASS |
| dashboard (0-9AF modules) imports shadow_batch_runner | NEVER | not present (test_dashboard_contracts.py::test_dashboard_does_not_import_core_factory_runner PASS) | PASS |
| dashboard write actions | NONE | UI exposes only read filters / search | PASS |

## File Scope (NEW additions only — no overwrites of existing source)

### Dashboard package (28 files)
zangetsu/dashboard/{config,app}.py
zangetsu/dashboard/data_sources/{__init__,parsers,runtime_health,batch_artifacts}.py
zangetsu/dashboard/view_models/{__init__,overview,arenas,candidates,survivors,feedback,health}.py
zangetsu/dashboard/components/{__init__,freshness_badge,charts,metric_cards,tables,filters}.py
zangetsu/dashboard/pages/{01_Overview,02_Core_Factory,03_Arena_A1,04_Arena_A2,05_Arena_A3,06_Candidates,07_Survivors,08_Rejects,09_Feedback,10_System_Health}.py

### Tests (5 files)
zangetsu/tests/dashboard/{__init__,test_parsers,test_freshness_logic,test_view_models,test_no_fake_zero,test_dashboard_contracts}.py

### Ops & scripts (3 files)
ops/systemd/zangetsu-dashboard.service
scripts/zangetsu/run_dashboard.sh
scripts/zangetsu/make_dashboard_screenshots.py

### Modified (1 file)
zangetsu/dashboard/__init__.py — lazy `__getattr__` re-export of `create_dashboard_app` so the observability code can be imported in environments without fastapi. The legacy `create_dashboard_app` API still works in environments where fastapi IS installed.

### Evidence (13 reports + 10 PNG artifacts)
zangetsu/docs/recovery/20260501-0-9af-internal-observability-dashboard-v1/00_state_lock.md
…through…
zangetsu/docs/recovery/20260501-0-9af-internal-observability-dashboard-v1/12_final_report.md
zangetsu/docs/recovery/20260501-0-9af-internal-observability-dashboard-v1/artifacts/{overview,core_factory,arena_a1,arena_a2,arena_a3,candidates,survivors,rejects,feedback,system_health}_page.png

## Working-Tree Byproducts NOT Included

`M calcifer/maintenance.log`, `M calcifer/maintenance_last.json`, `M calcifer/report_state.json`, `M zangetsu/logs/engine.jsonl.1` — runtime byproducts, not staged.

## Tests

- `pytest zangetsu/tests/dashboard/` (venv) → **22 / 22 PASSED in 0.29 s**
- `pytest zangetsu/tests/test_core_factory_*.py` (system python) → **54 / 54 PASSED in 3.00 s**

## Live State (verified post-merge)

- systemd service: `active (running)` since 2026-05-01 01:37:10 UTC
- `/_stcore/health` returns `ok`
- bind: 127.0.0.1:8785 only (verified `ss -tlnp | grep :8785`)

## Verdict

```
CONTROLLED_DIFF = SOURCE_AND_TESTS_AND_EVIDENCE_AND_OPS_ONLY
FORBIDDEN_DIFF = 0
```

`CONTROLLED_DIFF_PASS`
