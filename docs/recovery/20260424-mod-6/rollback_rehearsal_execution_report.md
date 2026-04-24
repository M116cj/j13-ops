# Rollback Rehearsal Execution Report — MOD-6 Phase 5 (Prereq 1.8)

- **Scope**: Execution trace of the calcifer-supervisor rollback rehearsal per `rollback_rehearsal_plan.md`. All steps ran on Alaya 2026-04-24T01:40:39Z → 01:43:44Z.
- **Actions performed**: All 9 steps from the plan executed sequentially; outputs captured to filesystem trace.
- **Evidence path**:
  - Full trace: `docs/recovery/20260424-mod-6/rollback_rehearsal/execution_trace.txt`
  - Pre snapshot: `docs/governance/snapshots/2026-04-24T014039Z-rollback-rehearsal-pre-claude_mod6.json` (sha256 `cc909a90d66f72aed203d603e3da1e99ed8c2fd272906d4688a23db9443b4740`)
  - Post snapshot: `docs/governance/snapshots/2026-04-24T014343Z-rollback-rehearsal-post-claude_mod6.json` (sha256 `9f38461c64ede7aec0d804b46b05b20cd518cafb07ef588e4e6e4673f4fe7fe1`)
  - Snapshot diff: `docs/recovery/20260424-mod-6/rollback_rehearsal/snapshot_diff.md`
- **Observed result — step-by-step**:

| Step | Expected | Observed | ✓ |
|---|---|---|---|
| 1. PRE snapshot captured | JSON written, manifest computed | Written; manifest cc909a... | ✓ |
| 2. Pre-stop state | calcifer-supervisor active, PID 3871492 | active, PID 3871492, ActiveEnter Thu 2026-04-23 06:19:51 UTC | ✓ |
| 3. `sudo systemctl stop` | exit 0, is-active → inactive | simulate_failure_ts 2026-04-24T01:40:40Z; is-active = inactive | ✓ |
| 4. Block file 30s static | mtime unchanged | 1776994842 → 1776994842 (VERIFIED) | ✓ |
| 5. `sudo systemctl start` (rollback) | exit 0, is-active → active, new PID | rollback_ts 2026-04-24T01:42:40Z; is-active active; new MainPID 1960230; new ActiveEnter Fri 2026-04-24 01:42:40 UTC | ✓ |
| 6. Block file 60s update | mtime advances | 1776994842 → 1776994964 (VERIFIED, +122s apparent but actual write cadence is internal Calcifer scheduler) | ✓ |
| 7. POST snapshot captured | JSON + manifest | Written; manifest 9f38461c... | ✓ |
| 8. Diff run | EXPLAINED, 0 forbidden | Classification EXPLAINED; 39 zero + 5 explained + 0 forbidden; exit 0 | ✓ |
| 9. Timing | p50 ≈ 3s restart | pure restore 3s; steady-state verification 63s | ✓ |

- **Forbidden changes check**:
  - No threshold touched
  - No arena change (arena remained frozen throughout)
  - No gate semantics change
  - Calcifer block-file resumed at status=RED (same as before); no misclassification
  - snapshot_diff.md lists exactly the EXPLAINED fields: calcifer_deploy_block_ts_iso, calcifer_deploy_block_file_sha, calcifer_state_file_sha (natural polling), calcifer-supervisor.active_since + main_pid (expected from restart)
- **Residual risk**:
  - During the 2min stop window, any hypothetical automated consumer of the block file would have seen stale data. No such consumer exists today (Calcifer block file is read by pre-done-stale-check + gov_reconciler, both manually triggered).
  - Rehearsal captured a single-sample p95. Multiple samples needed for statistical distribution — acceptable for prerequisite 1.8 which requires "at least one rehearsal recorded".
- **Verdict**: REHEARSAL EXECUTED SUCCESSFULLY. Every step VERIFIED. System returned cleanly to last legal state (calcifer running, block-file updating, RED status preserved). Prerequisite 1.8 = **VERIFIED LIVE MET**.
