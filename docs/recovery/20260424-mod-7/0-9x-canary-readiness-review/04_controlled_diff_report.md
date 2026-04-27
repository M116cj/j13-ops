# 04 — Controlled Diff / Forbidden Audit (Phase 4)

**Phase 4 Verdict:** `CONTROLLED_DIFF_PASS`, `FORBIDDEN_OPS=0`

## `git diff --stat` (working tree at evidence write time)

```
 calcifer/maintenance.log       |    10 +
 calcifer/maintenance_last.json |    26 +-
 calcifer/report_state.json     |     2 +-
 zangetsu/logs/engine.jsonl.1   | 45299 +++++++++++++++++++++++++++------------
 4 files changed, 31110 insertions(+), 14227 deletions(-)
```

`git diff --name-only`:

```
calcifer/maintenance.log
calcifer/maintenance_last.json
calcifer/report_state.json
zangetsu/logs/engine.jsonl.1
```

### Classification of working-tree changes

Identical to the prior order's Phase 5: the same four runtime / log artifacts. Carried forward from before this verification began.

| Path | Type | Source code? | Origin |
|---|---|---|---|
| `calcifer/maintenance.log` | runtime log | NO | Calcifer supervisor (pid 885335) |
| `calcifer/maintenance_last.json` | runtime state | NO | Calcifer last-cycle snapshot |
| `calcifer/report_state.json` | runtime state | NO | Calcifer reporting cursor |
| `zangetsu/logs/engine.jsonl.1` | rotated log | NO | engine logger rotation at 17:02 restart |

**No `*.py` / `*.sql` / `*.toml` / `*.yaml` / `*.yml` / `*.sh` / `Makefile` modification.**

## Forbidden-action safety greps

### A2_MIN_TRADES = 25 unchanged

```
zangetsu/config/settings.py:29:    ARENA2_MIN_TRADES: int = 25  # Patch H1 ...
zangetsu/config/settings.py:168:    arena2_min_trades: int = ARENA2_MIN_TRADES
zangetsu/services/arena_gates.py:48:A2_MIN_TRADES: int = 25
zangetsu/services/arena_gates.py:54:    if n < A2_MIN_TRADES:
zangetsu/services/arena_gates.py:55:        return GateResult(False, "too_few_trades", {"trades": n, "min": A2_MIN_TRADES})
zangetsu/services/feedback_decision_record.py:38:    "A2_MIN_TRADES_UNCHANGED",
```

Threshold canonical sites unchanged. `feedback_decision_record` even records `A2_MIN_TRADES_UNCHANGED` as a tracked structural invariant.

Saved: `/tmp/0_9x_canary_readiness_a2_min_trades_check.txt`

### alpha_zoo write-guard intact

```
86:    # a defense-in-depth ladder: --inspect-only ⊂ --dry-run ⊂ --no-db-write ⊂ --confirm-write.
139:    # --no-db-write hard-block — same as default-deny for now ...
142:        log.error("ABORT: --no-db-write is in effect (default-on). ...")
147:    # Default-deny: any path that could write to DB is blocked unless --confirm-write.
149:        log.error("ABORT: --confirm-write was NOT set. ...")
237:        "--no-db-write", action="store_true", default=True,
241:        "--confirm-write", action="store_true", default=False,
```

`--no-db-write` defaults ON; `--confirm-write` defaults OFF; both abort branches present. **Write-guard intact.**

Saved: `/tmp/0_9x_canary_readiness_alpha_zoo_safety_check.txt`

### APPLY / runtime-switchable check

Two hits, both test/tool scaffolding:

```
zangetsu/tools/sparse_canary_readiness_check.py:115:        "apply_budget",
zangetsu/tests/test_generation_profile_identity_and_scoring.py:409:        "apply_budget",
```

No runtime APPLY-path activation; `runtime-switchable` token absent.

Saved: `/tmp/0_9x_canary_readiness_apply_path_check.txt`

### order_router / kill_switch / capital alloc / live_trading probe

`grep -RIn 'order_router|kill_switch|emergency_stop|capital_alloc|live_trading' zangetsu`:

| Hit | Source |
|---|---|
| `risk_manager_check_kill_switch` (multiple edges) | `zangetsu/graphify-out/graph.json` (AST graph artifact only) |
| `test_v5_verification_test_10_risk_manager_kill_switch` | `graphify-out/graph.json` (test graph artifact) |

The `graph.json` artifact reflects existing dependency graph; not source. The actual implementation at `zangetsu/live/risk_manager.py` exists (4.4 kB). It was inspected read-only in Phase 2 and **not modified** by this order.

No `order_router`, no `emergency_stop`, no `capital_alloc`, no `live_trading` enable hits. ✅

## Required Phase 4 classification

| Field | Status |
|---|---|
| docs evidence | `EXPLAINED_DOCS_ONLY` (only files added are under `docs/recovery/20260424-mod-7/0-9x-canary-readiness-review/`) |
| /tmp parsers | `NOT_COMMITTED` (parser scripts were inline heredoc; outputs at `/tmp/0_9x_canary_*` are not staged) |
| source diff | `NONE` |
| runtime / config diff | `NONE` |
| alpha / Arena / threshold / execution / risk / capital diff | `NONE` |

## STOP-condition check

| Condition | Triggered |
|---|---|
| source code changed | NO |
| DB schema changed | NO |
| forbidden diff exists | NO |
| alpha_zoo DB write enabled | NO (default-deny intact) |
| CANARY started | NO |
| production rollout started | NO |
| A2_MIN_TRADES changed | NO |
| validator behavior changed | NO |

**No STOP condition triggered.**
