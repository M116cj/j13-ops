# Rollback Rehearsal Artifact Index — MOD-6 Phase 5 (Prereq 1.8)

- **Scope**: Single index pointing to every artifact produced by the calcifer-supervisor rollback rehearsal.
- **Actions performed**: Enumerated artifact files + sha256/mtime pointers.
- **Evidence path**: see table below.
- **Observed result — artifact inventory**:

| # | Artifact | Location | Content |
|---|---|---|---|
| 1 | Plan | `docs/recovery/20260424-mod-6/rollback_rehearsal_plan.md` | Rehearsal design + expected outcome |
| 2 | Execution trace (raw stdout) | `docs/recovery/20260424-mod-6/rollback_rehearsal/execution_trace.txt` | Full trace of all 9 steps with timestamps |
| 3 | Pre snapshot JSON | `docs/governance/snapshots/2026-04-24T014039Z-rollback-rehearsal-pre-claude_mod6.json` | 5-surface state pre-stop; sha256_manifest `cc909a90d66f72aed203d603e3da1e99ed8c2fd272906d4688a23db9443b4740` |
| 4 | Post snapshot JSON | `docs/governance/snapshots/2026-04-24T014343Z-rollback-rehearsal-post-claude_mod6.json` | 5-surface state post-restore; sha256_manifest `9f38461c64ede7aec0d804b46b05b20cd518cafb07ef588e4e6e4673f4fe7fe1` |
| 5 | Snapshot diff | `docs/recovery/20260424-mod-6/rollback_rehearsal/snapshot_diff.md` | Classification: EXPLAINED (39 zero + 5 explained + 0 forbidden) |
| 6 | Execution report | `docs/recovery/20260424-mod-6/rollback_rehearsal_execution_report.md` | Step-by-step verification table; verdict = VERIFIED |
| 7 | This index | `docs/recovery/20260424-mod-6/rollback_rehearsal_artifact_index.md` | Single entry point to all above |

Total: 7 artifacts (plan + trace + 2 snapshots + diff + report + index).

- **Forbidden changes check**: Index only references files — no new state mutations. Snapshot content has been verified against controlled-diff rules (observed 0 forbidden diffs). Rehearsal did not introduce any unauthorized state beyond the simulated-failure + restore cycle.
- **Residual risk**:
  - Artifact index lives in repo — file paths pinned at MOD-6 commit. If snapshots are moved (e.g., 30-day rotation policy once Phase 7 cron runs), index must be updated.
  - For permanence of the rehearsal evidence, the AKASHA witness step (G22) would ideally include a snapshot sha reference — flagged for Phase 7 integration.
- **Verdict**: INDEX IS COMPLETE. Every artifact needed to reconstruct the rehearsal is pinned in git (except the execution_trace.txt which is in docs/recovery/ committed as-is). Prerequisite 1.8 artifact trail is AUDITABLE.
