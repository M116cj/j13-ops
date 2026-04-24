# enforce_admins Activation Plan — MOD-6 Phase 1 (Prereq 1.4)

- **Scope**: Move `enforce_admins` on `main` branch protection from `false` to `true`. Sole change. Executed as the VERY LAST MOD-6 action, AFTER the MOD-6 commit lands (MOD-6 commit is the final admin-bypass commit; see `enforce_admins_live_validation.md` §3).
- **Actions performed**:
  1. Pre-activation probe: `gh api /repos/M116cj/j13-ops/branches/main/protection --jq '{req_sig: .required_signatures.enabled, linear: .required_linear_history.enabled, admin_enforce: .enforce_admins.enabled}'`
  2. Commit MOD-6 deliverables (admin-bypass used; `[BYPASS_WARNING]` token in commit message; compensating controls G21/G22/G24 cited)
  3. Execute activation: `gh api -X PUT /repos/M116cj/j13-ops/branches/main/protection --field required_signatures=true --field required_linear_history=true --field enforce_admins=true --field required_status_checks=null --field required_pull_request_reviews=null --field restrictions=null --field allow_force_pushes=false --field allow_deletions=false`
  4. Post-activation probe: same query as step 1.
  5. Write probe output to `/home/j13/j13-ops/docs/recovery/20260424-mod-6/enforce_admins_live_validation_postactivation.txt` on Alaya filesystem (NOT committed to main — Alaya lacks signing key).
- **Evidence path**:
  - Pre-probe: captured inline in `enforce_admins_live_validation.md §1` (MOD-4 state = `enforce_admins=false`)
  - Activation command trace: `enforce_admins_live_validation.md §2`
  - Post-probe: `/home/j13/j13-ops/docs/recovery/20260424-mod-6/enforce_admins_live_validation_postactivation.txt` (filesystem audit; not in git until later signed commit)
- **Observed result**: TO BE RECORDED in `enforce_admins_live_validation.md §4` immediately after activation. Expected: `enforce_admins.enabled: true`.
- **Forbidden changes check**: No changes to `required_pull_request_reviews`, `required_status_checks`, `restrictions`, `allow_force_pushes`, `allow_deletions` beyond their prior values (`null/false`). No thresholds, no arena, no gate semantics, no runtime change.
- **Residual risk**:
  - After activation, `j13` PAT on Alaya can NO LONGER push unsigned commits. Post-activation probe result cannot be committed by this session; it lives on Alaya filesystem only.
  - j13 must register a GPG/SSH key + configure signing before the next commit to `main` from Alaya (or use GitHub web UI for direct edit with automatic signing).
  - Emergency bypass: j13 can `DELETE /repos/.../branches/main/protection/enforce_admins` if absolutely required, but that itself requires GitHub UI or admin API call.
- **Verdict**: PLAN VERIFIED. Activation is a single-field toggle with known behavior (GitHub docs). Post-activation verification path is defined. Residual risks are disclosed, bounded, and accepted — they are the exact friction the activation intends to introduce.
