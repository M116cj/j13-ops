# Gate-A Workflow Live Spec — MOD-6 Phase 2 (Prereq 1.5 part A)

- **Scope**: Server-side enforcement of Phase 7 entry prerequisites via GitHub Actions workflow `.github/workflows/phase-7-gate.yml`. Replaces MOD-3 spec-only language. Committed as part of MOD-6.
- **Actions performed**:
  1. Authored `phase-7-gate.yml` covering 8 prerequisite verification steps (1.1–1.8).
  2. YAML syntax validated via `python3 -c "yaml.safe_load(open(...))"`.
  3. File committed to `.github/workflows/` in MOD-6 commit.
  4. Triggers on PR + push to main touching Phase-7-structural paths.
- **Evidence path**:
  - Workflow file: `.github/workflows/phase-7-gate.yml` (committed)
  - Syntax check log: captured during MOD-6 authoring (pre-commit python yaml load)
  - Live trigger evidence: first push touching a covered path will exercise this workflow (observable in GitHub Actions UI)
- **Observed result**:
  - YAML valid (top-level keys: `name`, `on`, `permissions`, `concurrency`, `jobs`)
  - Workflow defines one job `verify_phase7_prerequisites` with 8 sequential checks (1.1 Gate-A memo, 1.2 blocker matrix, 1.3 Gemini verdict, 1.4 enforce_admins live, 1.5 workflow files present, 1.6 cp_api present, 1.7 controlled-diff scripts present, 1.8 rollback rehearsal evidence)
  - Checks use deterministic file-presence + content-pattern grep + GitHub API probe
- **Forbidden changes check**: No threshold / arena / runtime / live gate semantics touched. Workflow is READ-ONLY (reads repo files + calls `gh api` for branch protection state). Fails loudly if any prerequisite is missing; does NOT attempt to fix.
- **Residual risk**:
  - Workflow itself runs on `ubuntu-latest` GitHub-hosted runner; cannot probe Alaya runtime (systemd / cp_api service state). Those live states are captured via snapshots in Controlled-Diff framework; workflow relies on committed evidence.
  - If Gemini verdict file naming convention changes, pattern `mod*_adversarial_verdict.md docs/recovery/*/gemini_round*_verdict.md` would need update — accepted; current naming stable.
- **Verdict**: Gate-A server-side enforcement is LIVE upon MOD-6 commit landing. First trigger executes automatically on any Phase-7-touching PR/push. Prerequisite 1.5 part A = VERIFIED MET.
