# 12 — Controlled Diff Report (V3)

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 — Phase 7

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
| production DB data mutation | none | dashboard never writes; reads file artifacts only | PASS |
| live trading | none | none | PASS |
| CANARY | not started | not started | PASS |
| production rollout | not started | not started | PASS |
| arena_pipeline mutation | none | none | PASS |
| dashboard_mobile imports arena_pipeline | NEVER | absent (test_no_arena_pipeline_or_runner_imports PASS) | PASS |
| dashboard_mobile imports shadow_batch_runner | NEVER | absent (test_no_arena_pipeline_or_runner_imports PASS) | PASS |
| dashboard_mobile write actions | NONE | route enumeration test forbids POST/PUT/PATCH/DELETE; pattern test forbids to_sql/.execute/subprocess/os.system/shutil.rmtree | PASS |
| public internet exposure | NONE | bind 100.123.49.102 (Tailscale only); 0.0.0.0 NOT used | PASS |

## File Scope (NEW)

### Mobile package (12 files)
```
zangetsu/dashboard_mobile/__init__.py
zangetsu/dashboard_mobile/app.py
zangetsu/dashboard_mobile/static/style.css
zangetsu/dashboard_mobile/templates/_base.html
zangetsu/dashboard_mobile/templates/_topbar.html
zangetsu/dashboard_mobile/templates/_bottomnav.html
zangetsu/dashboard_mobile/templates/overview.html
zangetsu/dashboard_mobile/templates/funnel.html
zangetsu/dashboard_mobile/templates/candidates.html
zangetsu/dashboard_mobile/templates/candidate_detail.html
zangetsu/dashboard_mobile/templates/rejects.html
zangetsu/dashboard_mobile/templates/survivors.html
zangetsu/dashboard_mobile/templates/feedback.html
zangetsu/dashboard_mobile/templates/health.html
```

### Tests (1 file, 10 test cases)
```
zangetsu/tests/dashboard_mobile/__init__.py
zangetsu/tests/dashboard_mobile/test_routes.py
```

### Ops & scripts (3 files)
```
ops/systemd/zangetsu-dashboard-mobile.service
scripts/zangetsu/run_dashboard_mobile.sh
scripts/zangetsu/make_mobile_screenshots.py
```

### Evidence (14 reports + 8 PNG screenshots)
```
zangetsu/docs/recovery/20260501-0-9af-mobile-terminal-v3/00..13.md
zangetsu/docs/recovery/20260501-0-9af-mobile-terminal-v3/artifacts/{overview, funnel, candidates, candidate_detail, rejects, survivors, feedback, health}.png
```

### Modified

None. V1 `zangetsu/dashboard/` and V2 `zangetsu/dashboard_terminal/` are untouched (V3 IMPORTS V1's view-models; no edits).

## Working-Tree Byproducts NOT Included

```
M calcifer/maintenance.log
M calcifer/maintenance_last.json
M calcifer/report_state.json
M zangetsu/logs/engine.jsonl.1
```

## Tests

- Mobile contract suite: **10 / 10 PASSED**
- V2 terminal contract suite: **4 / 4 PASSED** (still green)
- V1 dashboard view-model suite: **22 / 22 PASSED** (terminal + mobile both reuse these)
- core_factory regression: **54 / 54 PASSED** (system python)
- Combined: **90 / 90 PASSED**

## Live State (verified post-deploy)

- `systemctl --user is-active zangetsu-dashboard-mobile.service` → `active`
- `/_stcore/health` → `{"status":"ok"}`
- All 7 routes (`/`, `/funnel`, `/candidates`, `/rejects`, `/survivors`, `/feedback`, `/health`) → HTTP 200
- Listener: `100.123.49.102:8785` only (Tailscale interface)
- V2 `zangetsu-dashboard-terminal.service` stop+disabled
- V1 `zangetsu-dashboard.service` stop+disabled (since 0-9AF V1)

## Verdict

```
CONTROLLED_DIFF = SOURCE_AND_TESTS_AND_EVIDENCE_AND_OPS_ONLY
FORBIDDEN_DIFF = 0
```

`CONTROLLED_DIFF_PASS`
