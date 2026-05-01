# 12 — Controlled Diff Report

**ORDER**: 0-9AF-REDESIGN — Phase 7

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
| production DB data mutation | none | dashboard never writes; only reads file artifacts | PASS |
| live trading | none | none | PASS |
| CANARY | not started | not started | PASS |
| production rollout | not started | not started | PASS |
| arena_pipeline mutation | none | none | PASS |
| dashboard_terminal imports arena_pipeline | NEVER | absent (test_terminal_does_not_import_arena_pipeline PASS) | PASS |
| dashboard_terminal imports shadow_batch_runner | NEVER | absent (test_terminal_does_not_import_shadow_batch_runner PASS) | PASS |
| dashboard_terminal write actions | NONE | no st.form_submit_button / to_sql / subprocess / os.system / shutil.rmtree (test_terminal_no_write_actions PASS) | PASS |
| public internet exposure | NONE | bind 100.123.49.102 (Tailscale only); 0.0.0.0 NOT used | PASS |

## File Scope (NEW)

### Terminal package (9 files)
```
zangetsu/dashboard_terminal/__init__.py
zangetsu/dashboard_terminal/app.py
zangetsu/dashboard_terminal/theme.py
zangetsu/dashboard_terminal/panels/__init__.py
zangetsu/dashboard_terminal/panels/top_status_bar.py
zangetsu/dashboard_terminal/panels/kpi_strip.py
zangetsu/dashboard_terminal/panels/arena_funnel.py
zangetsu/dashboard_terminal/panels/reject_depth.py
zangetsu/dashboard_terminal/panels/sidebar_filter.py
zangetsu/dashboard_terminal/panels/candidate_drawer.py
zangetsu/dashboard_terminal/panels/bottom_tabs.py
```

### Tests (1 file)
```
zangetsu/tests/dashboard_terminal/__init__.py
zangetsu/tests/dashboard_terminal/test_terminal_imports.py
```

### Ops & scripts (2 files)
```
ops/systemd/zangetsu-dashboard-terminal.service
scripts/zangetsu/run_dashboard_terminal.sh
scripts/zangetsu/make_terminal_screenshots.py
```

### Evidence (14 reports + 10 PNG artifacts)
```
zangetsu/docs/recovery/20260501-0-9af-dashboard-terminal-redesign/00..13.md
zangetsu/docs/recovery/20260501-0-9af-dashboard-terminal-redesign/artifacts/{terminal_overview, arena_funnel, arena_detail_a1, arena_detail_a2, candidate_explorer, candidate_detail_drawer, reject_depth_panel, survivor_near_survivor_panel, feedback_panel, system_health_panel}.png
```

### Modified

None. V1 `zangetsu/dashboard/` is untouched (the terminal IMPORTS its view-models; no edits).

## Working-Tree Byproducts NOT Included

```
M calcifer/maintenance.log
M calcifer/maintenance_last.json
M calcifer/report_state.json
M zangetsu/logs/engine.jsonl.1
```

## Tests

- Terminal contract suite: **4 / 4 PASSED** (panels present + no forbidden imports + no write patterns)
- V1 dashboard suite: **22 / 22 PASSED** (still green; terminal reuses these view-models)
- core_factory regression: **54 / 54 PASSED** (system python)
- Combined: **80 / 80 PASSED**

## Live State (verified post-deploy)

- `systemctl --user is-active zangetsu-dashboard-terminal.service` → `active`
- `/_stcore/health` → `ok`
- Listener: `100.123.49.102:8785` only (Tailscale interface)
- V1 `zangetsu-dashboard.service` stopped + disabled

## Verdict

```
CONTROLLED_DIFF = SOURCE_AND_TESTS_AND_EVIDENCE_AND_OPS_ONLY
FORBIDDEN_DIFF = 0
```

`CONTROLLED_DIFF_PASS`
