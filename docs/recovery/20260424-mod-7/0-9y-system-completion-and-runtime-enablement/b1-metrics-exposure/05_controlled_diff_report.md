# 05 — Controlled Diff Report (Subprogram B1)

## `git diff --stat` (working tree at evidence write time)

```
 calcifer/maintenance.log                       |     ?? +
 calcifer/maintenance_last.json                 |     ?? +-
 calcifer/report_state.json                     |      2 +-
 zangetsu/logs/engine.jsonl.1                   |  ????  +-
 zangetsu/services/arena_pass_rate_telemetry.py |   20 +
 zangetsu/services/arena_pipeline.py            |  180 +
 zangetsu/tests/test_b1_aggregate_metrics_exposure.py |  ???? +
 7 files changed, ~200+ insertions(+), N deletions(-)
```

## Classification

| Path | Type | In B1 scope? |
|---|---|---|
| `calcifer/maintenance.log` | runtime log | NO (carry-forward dirty) |
| `calcifer/maintenance_last.json` | runtime state | NO (carry-forward dirty) |
| `calcifer/report_state.json` | runtime state | NO (carry-forward dirty) |
| `zangetsu/logs/engine.jsonl.1` | rotated log | NO (carry-forward dirty) |
| `zangetsu/services/arena_pass_rate_telemetry.py` | source code | YES — schema additive |
| `zangetsu/services/arena_pipeline.py` | source code | YES — accumulator + emit-call additive |
| `zangetsu/tests/test_b1_aggregate_metrics_exposure.py` | tests | YES — new test file |

The 4 dirty runtime artifacts are pre-existing (verified Subprogram A) and are NOT staged for this PR. Only the 3 source files (2 modified + 1 new test) are staged.

## Forbidden-action safety greps

### A2_MIN_TRADES = 25 unchanged

Canonical sites unchanged at:

```
zangetsu/config/settings.py:29: ARENA2_MIN_TRADES: int = 25  # Patch H1 ...
zangetsu/services/arena_gates.py:48: A2_MIN_TRADES: int = 25
zangetsu/services/arena_gates.py:54: if n < A2_MIN_TRADES:
zangetsu/services/feedback_decision_record.py:38: "A2_MIN_TRADES_UNCHANGED",
```

Saved: `/tmp/0_9y_b1_a2_min_trades_check.txt`

### alpha_zoo write-guard intact

```
237:    "--no-db-write", action="store_true", default=True,
241:    "--confirm-write", action="store_true", default=False,
```

Defense-in-depth ladder + default-deny abort branches at lines 142, 149, 153 unchanged.

Saved: `/tmp/0_9y_b1_alpha_zoo_safety_check.txt`

### APPLY / runtime-switchable check

Two hits, both test/tool scaffolding (no runtime APPLY enable):

```
zangetsu/tools/sparse_canary_readiness_check.py:115: "apply_budget",
zangetsu/tests/test_generation_profile_identity_and_scoring.py:409: "apply_budget",
```

Saved: `/tmp/0_9y_b1_apply_path_check.txt`

## Required B1 classification

| Field | Status |
|---|---|
| docs evidence | `EXPLAINED_DOCS_ONLY` (under `docs/recovery/20260424-mod-7/0-9y-system-completion-and-runtime-enablement/b1-metrics-exposure/`) |
| /tmp parsers | `NOT_COMMITTED` (`/tmp/0_9y_b1_*.txt` outputs not staged) |
| source diff | **2 source files changed (additive)** + **1 new test file** — telemetry exposure scope only |
| validation threshold diff | `NONE` |
| Arena pass/fail diff | `NONE` |
| BacktestResult schema | `NONE` |
| cost model | `NONE` |
| reject gate logic | `NONE` |
| capital / risk / order_router | `NONE` |

## STOP-condition check

| Condition | Triggered |
|---|---|
| validation threshold modified | NO |
| Arena pass/fail semantics modified | NO |
| champion promotion modified | NO |
| cost model modified | NO |
| deployable_count semantics modified | NO |
| A2_MIN_TRADES changed | NO |
| alpha_zoo DB write enabled | NO |
| CANARY started | NO |
| production rollout started | NO |
| force-push | NO |
| logs wiped | NO |
| validator behavior changed | NO |

**No STOP triggered.**
