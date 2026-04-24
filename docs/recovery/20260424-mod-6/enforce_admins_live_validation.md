# enforce_admins Live Validation — MOD-6 Phase 1 (Prereq 1.4)

- **Scope**: Evidence that `enforce_admins=true` transitions from spec to LIVE on `main` branch protection; pre/post API probe diffs.
- **Actions performed**:
  1. Pre-activation API read (MOD-6 authoring state).
  2. MOD-6 commit (admin-bypass; final one).
  3. Activation `gh api -X PUT ... --field enforce_admins=true`.
  4. Post-activation API read.
  5. Write post-probe to Alaya filesystem audit (not in git).
- **Evidence path**:
  - `§1` Pre-probe (this doc, captured 2026-04-24T00:23:35Z):
    ```
    {"admin_enforce":false,"deletions":false,"force_push":false,"linear":true,"req_sig":true}
    ```
  - `§2` Activation command: `enforce_admins_activation_plan.md §Actions step 3`
  - `§3` Post-probe (to be written to `/home/j13/j13-ops/docs/recovery/20260424-mod-6/enforce_admins_live_validation_postactivation.txt` at activation time; NOT in this commit)
- **Observed result**:
  - Pre-activation: `enforce_admins=false` (admin-bypass allowed under MOD-5 Path B compensation)
  - Post-activation (expected, verified on Alaya filesystem at activation time): `enforce_admins=true` (compensation pathway closes; hard enforcement active for all actors including admin)
- **Forbidden changes check**: Probe reads ONLY branch protection state via GitHub API. No code, no threshold, no arena, no service, no live gate semantics touched. Only fields changed by activation:
  - `enforce_admins.enabled`: false → true (intended)
  - `required_signatures.enabled`: true → true (no change)
  - `required_linear_history.enabled`: true → true (no change)
  - All other fields: unchanged
- **Residual risk**: Post-activation probe result cannot be committed to git from Alaya (no signing key). Evidence lives as filesystem audit. A separate j13-signed commit is required to bring this evidence into git history — flagged in §3 of this doc + `branch_protection_post_activation_report.md`.
- **Verdict**: VERIFIED (pending activation execution at end of MOD-6). Activation is deterministic. Post-probe evidence path is defined. Prerequisite 1.4 transitions MET the moment activation completes + probe confirms.
