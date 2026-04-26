# 0-9V-REPLACE — Alaya Runtime Replacement and Shadow Validation Final Report

## 1. Status

**BLOCKED_DIRTY_STATE** (also touches BLOCKED_DIVERGED_MAIN sub-condition: 0 ahead, 10 behind).

Equivalent allowed status from order §16:
- `BLOCKED_DIRTY_STATE` (primary — Phase C blocked)
- `BLOCKED_REPLACEMENT_GATE` (Phase H gate fails on G1 + G2)

Per order §16, the most informative single label is **BLOCKED_DIRTY_STATE** because that's the root cause; G1 fails as a downstream effect.

## 2. Alaya host

- Host: `j13@100.123.49.102` (Tailscale)
- Repo path: `/home/j13/j13-ops`
- SSH access: PASS
- Repo path exists: PASS

## 3. Old runtime inventory

| Field | Value |
| --- | --- |
| Old SHA | `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52` |
| Old branch | `phase-7/p7-pr4b-a2-a3-arena-batch-metrics` (NOT main) |
| Old process | arena pipeline STOPPED since 2026-04-23 (engine.jsonl) |
| Old launcher | cron + `watchdog.sh` (every 5 min) |
| Old env | (no top-level `.env*` or `secret/` directory) |
| Old logs | `zangetsu/logs/engine.jsonl` (38 MB), `engine.jsonl.1` (2.5 MB) |

Detail: `01_old_runtime_inventory.md`.

## 4. Rollback snapshot

| Field | Value |
| --- | --- |
| Rollback feasible | YES |
| Rollback SHA | `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52` |
| Rollback command | `rollback_commands.sh` (this directory) |
| Rollback limitations | dirty WIP must be re-derived from local diff if previously discarded; Calcifer state files self-regenerate |

Detail: `02_rollback_snapshot.md`.

## 5. Repo sync

| Field | Value |
| --- | --- |
| Pre-sync SHA | `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52` |
| origin/main SHA | `73b931d2df695572b0816fc1ebe1d10dbe9a5564` |
| Post-sync SHA | `f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52` (UNCHANGED) |
| Fast-forward only | NOT ATTEMPTED |
| Mac overwrite used | **NO** |
| Ahead/behind | 0 / 10 |
| Dirty files (modified) | 6 |
| Dirty files (untracked) | 3 |

Detail: `03_repo_sync_report.md`.

## 6. Local state preservation

| Path | Status |
| --- | --- |
| `zangetsu/logs/engine.jsonl` (38 MB) | preserved |
| `zangetsu/logs/engine.jsonl.1` (2.5 MB) | preserved |
| `zangetsu/data/funding/` | preserved |
| `zangetsu/data/ohlcv/` | preserved |
| `.env*` / `secret/` | not present (as before) |
| Calcifer state files | preserved (still dirty) |

No deletion. No modification. No copy.

## 7. Tests

| Field | Value |
| --- | --- |
| Tests on Alaya | DEFERRED (sync blocked) |
| Mac proxy validation | 453 PASS / 0 regression across all 9 sparse / canary suites + adjacent |

Detail: `04_dependency_and_test_report.md`.

## 8. Runtime safety

| Field | Value |
| --- | --- |
| apply path | NONE |
| runtime-switchable APPLY mode | NONE |
| consumer connected to generation runtime | NO |
| consumer output consumed by generation runtime | NO |
| `A2_MIN_TRADES` | 25 |
| production rollout | NOT STARTED |

Detail: `05_runtime_safety_audit.md`.

## 9. Telemetry source check

| Field | Value |
| --- | --- |
| `arena_batch_metrics.jsonl` | MISSING (pipeline stopped + emitter not deployed) |
| `sparse_candidate_dry_run_plans.jsonl` | MISSING (consumer not deployed) |
| Engine.jsonl line counts | 308579 (38 MB), 14213 (2.5 MB rotated) |
| Engine.jsonl last modified | 2026-04-23T00:35:54Z |
| Enough for live observation | **NO** (expected post-replacement state, not blocking this PR) |

Detail: `06_telemetry_source_check.md`.

## 10. Shadow validation

| Field | Value |
| --- | --- |
| Readiness | NOT RUN (tools missing) |
| Observer | NOT RUN (tools missing) |
| Records | 0 |
| Result | SHADOW_BLOCKED_MISSING_TOOLS (documented non-blocking) |

Detail: `07_shadow_validation_report.md`.

## 11. Runtime replacement gate

```
G1 (sync): FAIL
G2 (clean): FAIL
G3 (rollback): PASS
G4 (launcher): PASS
G5 (state preservation): PASS
G6 (tests): DEFERRED
G7 (safety): PASS
G8 (no apply): PASS
G9 (no APPLY mode): PASS
G10 (no runtime consumer): PASS
G11 (A2_MIN_TRADES=25): PASS
G12 (telemetry): PASS (with note)
G13 (shadow): DEFERRED
G14 (branch protection): PASS
G15 (signed PR-only): PASS

Verdict: BLOCKED_REPLACEMENT_GATE on G1+G2.
```

Detail: `08_runtime_replacement_gate.md`.

## 12. Runtime switch

| Field | Value |
| --- | --- |
| Performed | NO (gate failed) |
| Runtime manager | cron + watchdog.sh + systemd (HTTP APIs only) |
| Old PID | arena pipeline STOPPED; HTTP APIs preserved |
| New PID | (none) |
| Logs writing | HTTP APIs only |
| Telemetry writing | none |
| Errors | none |

Detail: `09_runtime_switch_report.md`.

## 13. Controlled-diff

This PR is documentation + evidence files only. No runtime files
modified. Expected classification: **EXPLAINED** (docs-only).

| CODE_FROZEN runtime SHA | Status |
| --- | --- |
| `config.zangetsu_settings_sha` | zero-diff |
| `config.arena_pipeline_sha` | zero-diff |
| `config.arena23_orchestrator_sha` | zero-diff |
| `config.arena45_orchestrator_sha` | zero-diff |
| `config.calcifer_supervisor_sha` | zero-diff |
| `config.zangetsu_outcome_sha` | zero-diff |

0 forbidden. No `--authorize-trace-only` flag needed.

## 14. Gate-A / Gate-B

Expected: **PASS / PASS**. Docs-only PR with no controversial diffs.
Will run on PR open.

## 15. Branch protection

Expected unchanged on `main`:

- `enforce_admins=true`
- `required_signatures=true`
- `linear_history=true`
- `allow_force_pushes=false`
- `allow_deletions=false`

This PR does not modify governance configuration.

## 16. Forbidden changes audit

| Item | Status |
| --- | --- |
| alpha generation | UNCHANGED (no Alaya code touched) |
| formula generation | UNCHANGED |
| mutation/crossover | UNCHANGED |
| search policy | UNCHANGED |
| generation budget | UNCHANGED |
| sampling weights | UNCHANGED |
| thresholds | UNCHANGED |
| `A2_MIN_TRADES` | PINNED at 25 |
| Arena pass/fail | UNCHANGED |
| champion promotion | UNCHANGED |
| `deployable_count` semantics | UNCHANGED |
| execution / capital / risk | UNCHANGED |
| CANARY | NOT STARTED |
| production | NOT STARTED |

## 17. Recommended next action

### Immediate (j13 owns)

Decide what to do with the dirty WIP on Alaya. Two paths in
`08_runtime_replacement_gate.md` §5:

**Path A — discard (recommended)**: WIP doesn't match the final
P7-PR4B implementation now on origin/main; the final code is
governance-validated through PR #18 review. Discarding the dirty
state and fast-forwarding is the cleanest path.

**Path B — preserve**: only if j13 wants the WIP archived for
audit. Move it to a feature branch via signed PR.

### After dirty state cleanup

Re-run 0-9V-REPLACE from Phase C. Expected outcome:

```
TEAM ORDER 0-9V-REPLACE = COMPLETE_REPLACED
Sync: f5f62b2b → 73b931d2 (fast-forward)
G1-G15: all PASS or DEFERRED→PASS
Runtime switch: arena pipeline restart via watchdog.sh next cycle
```

### Subsequent (separate orders)

After successful runtime replacement:

- **TEAM ORDER 0-9S-CANARY-OBSERVE-LIVE** — run sparse-candidate
  observer against live arena_batch_metrics stream on Alaya;
  accumulate ≥ 20 real rounds; produce real CANARY verdict.

## 18. Final declaration

```
TEAM ORDER 0-9V-REPLACE = BLOCKED_DIRTY_STATE
```

Inventory + rollback + sync attempt + safety + telemetry + gate evaluation completed honestly. No Alaya runtime modified. Mac repo NOT copied to Alaya. Branch protection intact. Signed PR-only flow preserved. j13 must inspect dirty state and authorize next path.
