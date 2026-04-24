# Controlled-Diff Operationalization — MOD-6 Phase 4 (Prereq 1.7)

- **Scope**: Move Controlled-Diff from framework/spec (MOD-5) to runnable operational mechanism: snapshot capture script + diff comparison script + evidence artifact storage + freshness/ownership rules.
- **Actions performed**:
  1. Authored `scripts/governance/capture_snapshot.sh` (executes per `pre_post_snapshot_spec.md v1`).
  2. Authored `scripts/governance/diff_snapshots.py` (implements `state_diff_acceptance_rules.md §1` decision tree).
  3. Deployed both scripts to Alaya + marked executable.
  4. Created `docs/governance/snapshots/` + `docs/governance/diffs/` directories.
  5. Ran the scripts LIVE against current state; generated real artifacts.
- **Evidence path**:
  - Capture script: `scripts/governance/capture_snapshot.sh` (committed, executable)
  - Diff script: `scripts/governance/diff_snapshots.py` (committed, executable)
  - Snapshot artifacts: `docs/governance/snapshots/2026-04-24T01*Z-*-claude_mod6.json` (multiple, one per phase + one per rehearsal pre/post)
  - Diff artifact: `docs/governance/diffs/mod6_phase4_live_demo.md` (ZERO/EXPLAINED classification)
- **Observed result**:
  - `capture_snapshot.sh` exit 0; JSON file written; SHA256 manifest appended
  - `diff_snapshots.py` exit 0 on pre→post pair; classification = EXPLAINED (43 zero + 1 explained + 0 forbidden)
  - Scripts correctly categorized the 1 diff (`repo.git_status_porcelain_lines: 2 → 3`) as EXPLAINED (new untracked files from snapshot script itself — natural + catalogued)
- **Forbidden changes check**: Scripts are read-only probes. They never mutate:
  - branch protection state (only read via `gh api`)
  - code files (only hash them)
  - service state (only query via `systemctl is-active`)
  - database (not touched at all — VIEW data captured only if committed via prior snapshot; MOD-6 skeleton doesn't probe DB directly from capture script, avoiding state-change window)
  - Gate-A classification files (only grep from them)
- **Residual risk**:
  - Snapshots are taken by Claude Lead manually (on-demand) in MOD-6. No cron yet → snapshot freshness depends on operator discipline. Phase 7 adds cron (`gov_reconciler` responsibility).
  - Diff script's ALLOWED/EXPLAINABLE/FORBIDDEN catalog is hard-coded in Python. Expanding requires code edit (not a spec change); Gate-B on `scripts/governance/**` catches drift.
  - `git_status_porcelain_lines` increments naturally during script execution itself (temp output files) — categorized as EXPLAINED. A bad actor could hide under this — compensating: the MANIFEST sha256 catches file-content changes, not just line counts.
- **Verdict**: Controlled-Diff is now OPERATIONAL — not merely specified. Scripts run, artifacts land, classification is deterministic + verifiable. Prerequisite 1.7 = **VERIFIED LIVE MET**.
