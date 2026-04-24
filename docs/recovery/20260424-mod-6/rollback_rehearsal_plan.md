# Rollback Rehearsal Plan — MOD-6 Phase 5 (Prereq 1.8)

- **Scope**: Design of the single bounded rollback rehearsal to satisfy prerequisite 1.8. Chosen scenario: calcifer-supervisor service stop + restore — simple, reversible, involves no runtime threshold or arena change.
- **Actions performed**:
  1. Evaluated candidate rehearsal targets. Selected calcifer-supervisor because:
     - Already running + easily observable (block-file write cadence)
     - Rollback action (systemctl start) is trivially reversible
     - No risk of threshold / arena / live-gate impact
     - Matches MOD-2 Phase 1 restart pattern already proven safe
  2. Defined trigger / steps / owner / artifacts / restore-confirmation fields.
  3. Validated scenario pre-execution: cp-api service already running uses same restart mechanism; successful there = acceptable here.
- **Evidence path**:
  - This doc (plan)
  - `rollback_rehearsal_execution_report.md` (execution trace)
  - `docs/recovery/20260424-mod-6/rollback_rehearsal/execution_trace.txt` (raw trace)
  - `docs/recovery/20260424-mod-6/rollback_rehearsal/snapshot_diff.md` (controlled-diff pre/post)
- **Observed result — plan specification**:

| Field | Value |
|---|---|
| Trigger | "calcifer-supervisor service failure" simulated by `sudo systemctl stop calcifer-supervisor` |
| Steps | 1) PRE snapshot → 2) capture calcifer pre-state → 3) `systemctl stop` → 4) wait 30s + verify block-file stops updating → 5) `systemctl start` (rollback action) → 6) wait 60s + verify block-file resumes updating → 7) POST snapshot → 8) diff |
| Owner | `claude@mod6` (executing actor); j13 approves (authorization via 0-8 order) |
| Artifacts | `execution_trace.txt` (full stdout), pre/post snapshot JSONs, snapshot_diff.md |
| Restore confirmation | Two tests: `systemctl is-active calcifer-supervisor = active` AND `stat /tmp/calcifer_deploy_block.json mtime` advances after restart |
| Expected rollback duration | p50 ≈ 3s (service start time); full steady-state ≈ 63s (includes block-file resumption verification) |
| Risk bound | Zero — calcifer block-file goes stale for ≤60s during simulated-failure phase; no downstream consumers treat 60s staleness as a problem |

- **Forbidden changes check**: Plan ONLY exercises a calcifer service stop/start. No threshold change, no arena restart, no code change, no gate semantics change, no runtime logic modification.
- **Residual risk**:
  - During the ~2min stop window, any external consumer that polled `/tmp/calcifer_deploy_block.json` would see stale data (but status remained `RED` so semantics safe).
  - If `systemctl start` had failed, calcifer would remain down until operator intervention — mitigation: Claude Lead is executing actor, immediately aware.
- **Verdict**: PLAN APPROVED — bounded, reversible, no-side-effect scenario satisfies 0-8 Phase 5 requirements.
