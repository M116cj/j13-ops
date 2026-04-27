# 05 — Controlled Diff Report (Subprogram B3)

## `git diff --stat` (working tree at evidence write time)

```
 calcifer/calcifer_v071_watch.sh                              |  66 +
 calcifer/calcifer_outcome_predicate.py                       |  61 +  (new)
 zangetsu/tests/test_b3_calcifer_outcome_predicate.py         | 130 +  (new)
 calcifer/maintenance.log                                     | runtime artifact
 calcifer/maintenance_last.json                               | runtime artifact
 calcifer/report_state.json                                   | runtime artifact
 zangetsu/logs/engine.jsonl.1                                 | runtime artifact
```

## Classification

| Path | Type | In B3 scope? |
|---|---|---|
| `calcifer/calcifer_v071_watch.sh` | shell script | YES — additive deploy_block writer |
| `calcifer/calcifer_outcome_predicate.py` | python helper | YES — new pure-Python predicate mirror |
| `zangetsu/tests/test_b3_calcifer_outcome_predicate.py` | tests | YES — 9 unit tests |
| Calcifer runtime state files | runtime | NO (carry-forward dirty) |
| `engine.jsonl.1` | rotated log | NO (carry-forward dirty) |

## Forbidden-action safety greps

### A2_MIN_TRADES = 25 unchanged

Canonical sites unchanged at `zangetsu/services/arena_gates.py:48` and `zangetsu/config/settings.py:29`.

### alpha_zoo write-guard intact

`--no-db-write` default-on, `--confirm-write` default-off, default-deny abort branches unchanged.

### APPLY / runtime-switchable check

Two hits, both test/tool scaffolding (no runtime APPLY enable).

### Validation / Arena gates / cost model / BacktestResult

All unchanged — B3 does not touch `zangetsu/services/` source code, only `calcifer/` and `zangetsu/tests/`.

## Required B3 classification

| Field | Status |
|---|---|
| docs evidence | `EXPLAINED_DOCS_ONLY` |
| Source diff | 1 modified bash + 1 new Python helper + 1 new test file (additive only) |
| validation threshold diff | `NONE` |
| Arena pass/fail diff | `NONE` |
| BacktestResult schema | `NONE` |
| cost model | `NONE` |
| reject gate logic | `NONE` |
| capital / risk / order_router | `NONE` |
| Calcifer process-side semantics | `UNCHANGED` |
| Calcifer cron cadence | `UNCHANGED` |

## STOP-condition check

| Condition | Triggered |
|---|---|
| changing deployment policy except NULL-safety | NO (only the predicate now correctly handles NULL; everything else unchanged) |
| modifying alpha/CANARY/prod rollout | NO |
| weakening DB guards | NO |
| disabling kill switch | NO |
| altering execution/capital/risk | NO |
| force-push | NO |

**No STOP triggered.**
