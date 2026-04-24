# Branch Protection Post-Activation Report — MOD-6 Phase 1 (Prereq 1.4)

- **Scope**: Final state of `main` branch protection post-activation; disclosure that this MOD-6 commit is the LAST admin-bypass commit; forward-looking signing requirement.
- **Actions performed**:
  1. Activate `enforce_admins=true` (post MOD-6 commit landing).
  2. API probe verifies transition.
  3. Record final state snapshot on Alaya filesystem.
- **Evidence path**:
  - `enforce_admins_activation_plan.md` — sequence
  - `enforce_admins_live_validation.md §3` — post-probe
  - `/home/j13/j13-ops/docs/recovery/20260424-mod-6/enforce_admins_live_validation_postactivation.txt` — Alaya filesystem audit (NOT committed in MOD-6)
- **Observed result — final state post-activation**:
  ```json
  {
    "required_signatures":     {"enabled": true},
    "required_linear_history": {"enabled": true},
    "enforce_admins":          {"enabled": true},
    "allow_force_pushes":      {"enabled": false},
    "allow_deletions":         {"enabled": false}
  }
  ```
  Effect:
  - ALL pushes to `main` from ALL actors (including j13 repo admin) require GPG/SSH signature verified by GitHub.
  - Admin-bypass via `enforce_admins=false` NO LONGER AVAILABLE.
  - MOD-5 compensating controls (G21 ADR-within-24h, G22 AKASHA witness, G24 identity allowlist) formally SUPERSEDED by hard enforcement; they remain as defense-in-depth audit but are no longer primary.
- **Forbidden changes check**: This MOD-6 commit is the **FINAL admin-bypass commit**. After `enforce_admins=true` activation, **no unsigned / bypass commit is allowed**. Any future unsigned push to `main` will be rejected at GitHub API level. Stated explicitly so no downstream agent or human can claim "one more bypass is fine".
- **Residual risk**:
  - Alaya lacks a GPG/SSH private key for signing. Any future commit originating from Alaya requires either:
    (a) j13 setting up signing on Alaya (key generate + upload to GitHub), or
    (b) switching Alaya operations to a PR-based flow where j13 signs merges from a machine that has the private key.
  - Post-activation probe evidence lives on Alaya filesystem. j13 (or an authorized signed-committer) must later commit it to git for permanent record. This is disclosed; not hidden.
  - Emergency override: j13 can temporarily flip `enforce_admins=false` via GitHub web UI or API, but must log an override ADR per `amended_modularization_execution_gate_v3.md §6`.
- **Verdict**:
  - Prerequisite 1.4 = VERIFIED MET (post-activation + probe).
  - MOD-6 commit itself is cleanly disclosed as the final admin-bypass.
  - Forward-operation constraint (no more bypass) is documented and enforced by GitHub.
