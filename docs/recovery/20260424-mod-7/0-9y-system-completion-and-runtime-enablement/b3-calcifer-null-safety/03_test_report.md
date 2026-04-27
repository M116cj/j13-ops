# 03 — Test Report (Subprogram B3)

## New tests

`zangetsu/tests/test_b3_calcifer_outcome_predicate.py` — 9 tests:

```
============================== 9 passed in 0.02s ==============================
```

| # | Test | Status |
|---|---|---|
| 1 | `test_b3_healthy_no_block_when_deployable_count_positive` | ✅ |
| 2 | `test_b3_cold_start_returns_unknown_blocked` | ✅ |
| 3 | `test_b3_regression_returns_red` | ✅ |
| 4 | `test_b3_recovery_window_returns_no_block` | ✅ |
| 5 | `test_b3_boundary_age_equal_6_is_no_block` | ✅ |
| 6 | `test_b3_boundary_age_just_over_6_is_red` | ✅ |
| 7 | `test_b3_false_green_prevention` | ✅ |
| 8 | `test_b3_no_bypass_path_for_zero_deployable` | ✅ |
| 9 | `test_b3_handles_float_zero_age` | ✅ |

## Regression sweep

```
$ cd zangetsu && .venv/bin/python -m pytest \
    tests/test_arena_batch_metrics_accounting.py \
    tests/test_a2_a3_arena_batch_metrics.py \
    tests/test_arena_pass_rate_telemetry.py \
    tests/test_b1_aggregate_metrics_exposure.py \
    tests/test_b3_calcifer_outcome_predicate.py -q

121 passed in 0.73s
```

**121 total tests pass: 102 pre-existing + 10 B1 + 9 B3.** No regression.

## Bash syntax check

```
$ bash -n calcifer/calcifer_v071_watch.sh
(no output, exit 0)
```

## Live integration check

The patched bash script was executed against live DB:

```
Before: /tmp/calcifer_deploy_block.json — does not exist
After:  /tmp/calcifer_deploy_block.json — present, status=UNKNOWN_BLOCKED
```

Live deploy_block content:

```json
{
  "status": "UNKNOWN_BLOCKED",
  "iso": "2026-04-27T18:53:27Z",
  "reason": "cold_start_no_live_champion_ever",
  "deployable_count": 0,
  "last_live_at_age_h": null,
  "predicate": "0-9Y-B3-NULL-SAFE",
  "writer": "calcifer_v071_watch.sh"
}
```

This is the **expected behavior** per the predicate spec: dc=0 + age=NULL → UNKNOWN_BLOCKED.

The process-side file (`/tmp/calcifer_process_green.json`) remained GREEN — process side and outcome side are properly decoupled per v0.7.1 dual-evidence governance.

## Pass-criteria check (master order's B3 spec)

| Master-order criterion | Status |
|---|---|
| identify predicate | ✅ (01_predicate_trace.md — full trace + spec analysis) |
| reproduce NULL non-red behavior | ✅ (current state: dc=0, age=NULL, no deploy_block file before patch) |
| patch NULL to RED/UNKNOWN_BLOCKED according to policy | ✅ (UNKNOWN_BLOCKED for cold-start, RED for regression) |
| add regression test | ✅ (9 tests, including explicit false-green prevention test) |
| verify no deploy blocker bypass | ✅ (`test_b3_no_bypass_path_for_zero_deployable` exhaustively checks dc=0 with various age values) |
| verify no false green | ✅ (`test_b3_false_green_prevention` + live integration check showing deploy_block file now appears) |
| forbidden: changing deployment policy except NULL-safety | ✅ unchanged: process-side semantics, worker grace, cron cadence all unchanged |
| forbidden: modifying alpha/CANARY/prod rollout | ✅ unchanged: no zangetsu/services touch beyond tests |
