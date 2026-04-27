# 04 — Controlled Diff / Forbidden Audit (Phase 5)

**Phase 5 Verdict:** `CONTROLLED_DIFF_PASS`, `FORBIDDEN_OPS=0`

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

| Path | Type | Source code? | Notes |
|---|---|---|---|
| `calcifer/maintenance.log` | runtime log | NO | Calcifer supervisor maintenance log; appended continuously by service |
| `calcifer/maintenance_last.json` | runtime state | NO | Calcifer last-cycle state snapshot |
| `calcifer/report_state.json` | runtime state | NO | Calcifer reporting cursor |
| `zangetsu/logs/engine.jsonl.1` | rotated log | NO | Previous rotation file; written by engine logger |

**No `*.py`, `*.sql`, `*.toml`, `*.yaml`, `*.yml`, `*.sh`, `*.json` config, or `Makefile` modifications.** All four diffs are runtime artifacts of services that ran during this evidence window (Calcifer + engine logger). They are pre-existing dirty paths and were NOT introduced by this verification order.

## Forbidden-action safety greps

### A2_MIN_TRADES = 25 unchanged

```
zangetsu/config/settings.py:29:    ARENA2_MIN_TRADES: int = 25  # Patch H1 ...
zangetsu/config/settings.py:168:    arena2_min_trades: int = ARENA2_MIN_TRADES
zangetsu/services/arena_gates.py:48:A2_MIN_TRADES: int = 25
zangetsu/services/arena_gates.py:54:    if n < A2_MIN_TRADES:
zangetsu/services/arena_gates.py:55:        return GateResult(False, "too_few_trades", {"trades": n, "min": A2_MIN_TRADES})
```

Threshold canonical sites confirm `A2_MIN_TRADES = 25`. Test files (`test_a2_a3_arena_batch_metrics.py`, `test_arena_pass_rate_telemetry.py`, `test_p7_pr2_behavior_invariance.py`, `test_feedback_budget_consumer.py`) reference the same constant. `feedback_decision_record.py` records `A2_MIN_TRADES_UNCHANGED` as a structural invariant. **Unchanged.**

Saved: `/tmp/0_9x_post_restart_a2_min_trades_check.txt`

### alpha_zoo write-guard intact

`zangetsu/scripts/alpha_zoo_injection.py` defense-in-depth ladder:

```
86:    # a defense-in-depth ladder: --inspect-only ⊂ --dry-run ⊂ --no-db-write ⊂ --confirm-write.
139:    # --no-db-write hard-block — same as default-deny for now ...
142:        log.error("ABORT: --no-db-write is in effect (default-on). Use --inspect-only or --dry-run for safe modes. ...")
147:    # Default-deny: any path that could write to DB is blocked unless --confirm-write.
149:        log.error("ABORT: --confirm-write was NOT set. Cold-start tooling refuses to ...")
237:        "--no-db-write", action="store_true", default=True,
241:        "--confirm-write", action="store_true", default=False,
```

`--no-db-write` defaults ON; `--confirm-write` defaults OFF; both abort branches present. **Write-guard intact.**

Saved: `/tmp/0_9x_post_restart_alpha_zoo_safety_check.txt`

### APPLY / runtime-switchable check

Only two hits, both in test/tool scaffolding:
```
zangetsu/tools/sparse_canary_readiness_check.py:115:        "apply_budget",
zangetsu/tests/test_generation_profile_identity_and_scoring.py:409:        "apply_budget",
```
No runtime APPLY-path enable; `runtime-switchable` token absent.

Saved: `/tmp/0_9x_post_restart_apply_path_check.txt`

## Required Phase 5 classification

| Field | Status |
|---|---|
| docs evidence | `EXPLAINED_DOCS_ONLY` (only files added are under `docs/recovery/20260424-mod-7/0-9x-post-restart-a1-telemetry-verification/`) |
| /tmp parsers | `NOT_COMMITTED` (parser scripts run inline via heredoc `python3 - <<'PYEOF'`; outputs at `/tmp/0_9x_post_restart_*` are not staged) |
| source diff | `NONE` |
| alpha / Arena / threshold / execution / risk / capital diff | `NONE` |

## STOP-condition check

| Condition | Triggered |
|---|---|
| source code changed | NO |
| forbidden diff exists | NO |
| alpha_zoo DB write enabled | NO (default-deny intact) |
| CANARY started | NO |
| production rollout started | NO |
| A2_MIN_TRADES changed | NO (== 25 at canonical sites) |
| validator behavior changed | NO (no `admission_validator` PL/pgSQL change) |

**No STOP condition triggered.**
