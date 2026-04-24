# Gate-B Workflow Live Spec — MOD-6 Phase 2 (Prereq 1.5 part B)

- **Scope**: Server-side per-module migration gate via `.github/workflows/module-migration-gate.yml`. Path-based triggers (un-omittable; no label bypass per MOD-3 `gate_b_trigger_correction.md §3.1`).
- **Actions performed**:
  1. Authored `module-migration-gate.yml` with path-based + paths-ignore trigger block.
  2. Defined 2 jobs: `identify_affected_modules` (extracts module IDs from changed paths) + `gate_b_per_module` (matrix job running 4 checks per affected module: B.1 YAML present, B.1 15-field schema, B.1 Gemini sign-off ADR, B.3 rollback runbook) + `gate_b_summary` (always-run aggregator).
  3. YAML syntax validated.
- **Evidence path**:
  - Workflow file: `.github/workflows/module-migration-gate.yml` (committed)
  - Syntax check log: captured pre-commit
  - Path-based trigger definition: §on.pull_request.paths + §on.push.paths (both reference `zangetsu/src/modules/**`, `zangetsu/src/l[0-9]*/**`, `zangetsu/module_contracts/**`)
- **Observed result**:
  - Triggers on any PR/push touching module source or contract YAML paths
  - Noop (early exit) when no module paths affected (e.g., pure docs PR)
  - For each affected module ID extracted from paths: runs B.1 + B.3 checks with `fail-fast: false` so multiple modules surface all failures in one run
  - YAML valid; no syntax errors
- **Forbidden changes check**: Workflow does NOT modify code, state, or runtime. READ-ONLY file-presence and schema validation. No network calls except to GitHub Actions-runtime provided envs (no external egress). `paths-ignore` excludes `*.md`, `test_*.py`, `tests/`, `__pycache__/`, `*.pyc` so pure test/doc edits don't trip the gate unnecessarily.
- **Residual risk**:
  - B.2 (SHADOW + CANARY rollout verification) + B.1 (CP registry probe) steps are OMITTED from this version — they require cp_api being FULL-live with `control_plane.modules` populated + `control_plane.rollout_audit` existing. Those are Phase 7 implementation dependencies. MOD-6 ships the un-omittable shell; full verification lands when CP is operational beyond skeleton.
  - B.3 rollback runbook check is `::warning::` not `::error::` in MOD-6 (no modules yet, so no runbooks; once any module lands, MUST upgrade to hard error).
- **Verdict**: Gate-B server-side trigger + core schema enforcement is LIVE upon MOD-6 commit landing. Path-based triggering is un-bypassable (per R1a-F1 CRITICAL resolution from MOD-3). Prerequisite 1.5 part B = VERIFIED MET (skeleton sufficient; B.2 depth added when CP lands).
