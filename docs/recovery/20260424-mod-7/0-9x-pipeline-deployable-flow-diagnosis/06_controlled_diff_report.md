# 06 — Controlled Diff / Forbidden Audit (Phase 6)

**Phase 6 Verdict:** `CONTROLLED_DIFF_PASS`, `FORBIDDEN_OPS=0`

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

Same four runtime / log artifacts as the prior two orders. Pre-existing dirty paths.

| Path | Type | Source code? | Origin |
|---|---|---|---|
| `calcifer/maintenance.log` | runtime log | NO | Calcifer supervisor |
| `calcifer/maintenance_last.json` | runtime state | NO | Calcifer last-cycle snapshot |
| `calcifer/report_state.json` | runtime state | NO | Calcifer reporting cursor |
| `zangetsu/logs/engine.jsonl.1` | rotated log | NO | engine logger rotation at 17:02 restart |

**No source code (`*.py` / `*.sql` / `*.toml` / `*.yaml` / `*.yml` / `*.sh` / `Makefile`) modification.**

## Forbidden-action safety greps

### A2_MIN_TRADES = 25 unchanged

Canonical sites:
```
zangetsu/config/settings.py:29: ARENA2_MIN_TRADES: int = 25
zangetsu/services/arena_gates.py:48: A2_MIN_TRADES: int = 25
zangetsu/services/arena_gates.py:54: if n < A2_MIN_TRADES:
```

`feedback_decision_record.py` records `A2_MIN_TRADES_UNCHANGED` as a tracked structural invariant.

Saved: `/tmp/0_9x_deployable_flow_a2_min_trades_check.txt`

### alpha_zoo write-guard intact

```
237: "--no-db-write", action="store_true", default=True,
241: "--confirm-write", action="store_true", default=False,
```

Plus default-deny abort branches at lines 142, 149, 153. Defense-in-depth ladder `--inspect-only ⊂ --dry-run ⊂ --no-db-write ⊂ --confirm-write` intact.

Saved: `/tmp/0_9x_deployable_flow_alpha_zoo_safety_check.txt`

### APPLY / runtime-switchable check

Two hits, both test/tool scaffolding (no runtime APPLY enable):

```
zangetsu/tools/sparse_canary_readiness_check.py:115: "apply_budget",
zangetsu/tests/test_generation_profile_identity_and_scoring.py:409: "apply_budget",
```

Saved: `/tmp/0_9x_deployable_flow_apply_path_check.txt`

## Required Phase 6 classification

| Field | Status |
|---|---|
| docs evidence | `EXPLAINED_DOCS_ONLY` (only files added are under `docs/recovery/20260424-mod-7/0-9x-pipeline-deployable-flow-diagnosis/`) |
| /tmp parsers | `NOT_COMMITTED` (parsers run via inline heredoc; `/tmp/0_9x_dfd_*` outputs not staged) |
| source diff | `NONE` |
| runtime / config diff | `NONE` |
| alpha / Arena / threshold / execution / risk / capital diff | `NONE` |

## STOP-condition check

| Condition | Triggered |
|---|---|
| source code changed | NO |
| DB schema changed | NO |
| forbidden diff exists | NO |
| alpha_zoo DB write enabled | NO |
| CANARY started | NO |
| production rollout started | NO |
| A2_MIN_TRADES changed | NO |
| validator behavior changed | NO |

**No STOP triggered.**
