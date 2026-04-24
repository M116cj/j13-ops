# Gate-B Trigger Correction — Path-Based Enforcement

**Order**: `/home/j13/claude-inbox/0-4` Phase 1 deliverable
**Produced**: 2026-04-23T07:20Z
**Supersedes**: `docs/recovery/20260423-mod-1/modularization_execution_gate.md §5.2` (label-based trigger) via amendment
**Resolves**: Gemini R1a-F1 CRITICAL + R1a-F2 HIGH

---

## 1. Amendment summary

**Change Gate-B trigger mechanism** from label-based (omittable) to **path-based (un-omittable)** AND add server-side GitHub Actions workflow that mirrors Gate-A hook logic, so local `--no-verify` cannot bypass.

## 2. Old specification (MOD-1 §5.2)

```
Location: GitHub Actions workflow `module-migration-gate.yml`
Trigger: any PR with label `module-migration/<module_id>`
Action: verify §B.1 CP registry entry exists; verify §B.2 rollout tier logs in
        `control_plane.rollout_audit`; verify §B.3 rollback doc exists
```

**Vulnerability (Gemini R1a-F1)**: A PR author who omits the `module-migration/<module_id>` label entirely triggers no Gate-B workflow. Migration slips through.

## 3. New specification (MOD-3)

### 3.1 Path-based trigger

```yaml
# .github/workflows/module-migration-gate.yml (MOD-3 AMENDMENT)
name: Module Migration Gate (Gate-B)

on:
  pull_request:
    paths:
      - 'zangetsu/src/modules/**'
      - 'zangetsu/src/l[0-9]*/**'
      - 'zangetsu/module_contracts/*.yaml'
      - 'zangetsu/module_contracts/*.yml'
  push:
    branches: [main]
    paths:
      - 'zangetsu/src/modules/**'
      - 'zangetsu/src/l[0-9]*/**'
      - 'zangetsu/module_contracts/*.yaml'

permissions:
  contents: read
  pull-requests: write

jobs:
  gate_b:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Identify affected modules from changed paths
        id: affected
        run: |
          # Extract module_ids from paths under zangetsu/src/modules/*
          # and zangetsu/module_contracts/*.yaml
          # (concrete implementation in Phase 7)
      - name: Verify B.1 — module has complete contract registered
        run: |
          # For each affected module_id:
          #   - assert zangetsu/module_contracts/<id>.yaml exists
          #   - assert YAML passes module_contract_template schema validation
          #   - assert control_plane.modules CP-registered (via CP API health check)
          #   - assert Gemini adversarial sign-off ADR present
      - name: Verify B.2 — shadow + CANARY rehearsal evidence
        run: |
          # - assert rollout_audit has SHADOW + CANARY entries ≥ 72h each
          # - assert no alert threshold fired in either window
          # - assert rollback_surface.rollout_rehearsal was executed
      - name: Verify B.3 — rollback + forward-compat signed
        run: |
          # - assert docs/rollback/<module_id>.md exists
          # - assert rollback p95 empirically measured (not just documented)
          # - assert consumer modules have compatible contract_version_max
```

### 3.2 Label is ADDITIVE, not gating

```
If a PR has label `module-migration/<module_id>` → same workflow runs (no harm)
If a PR lacks the label BUT touches one of the path patterns → workflow STILL runs
If a PR has the label but touches NO module path → workflow runs with no-op (early exit)
```

**Label-based omission cannot bypass**; path-based inclusion cannot be forgotten.

### 3.3 Explicit un-omittable patterns

| Path pattern | What it means |
|---|---|
| `zangetsu/src/modules/**` | Any module implementation code |
| `zangetsu/src/l[0-9]*/**` | Layer-structured module organization (l2_kernel/ l4_search/ l5_eval/ etc.) |
| `zangetsu/module_contracts/*.yaml` | Contract YAML file additions/changes |
| `zangetsu/module_contracts/*.yml` | Same, alternate extension |

**Design intent**: Any structural change touching module code OR contract YAML triggers Gate-B. A sloppy PR author who refactors `zangetsu/src/modules/gate_contract/` WITHOUT adding the label still gets gated.

## 4. Branch protection backup (belt-and-suspenders)

GitHub branch protection on `main`:
- Require `gate_b` status check to pass before merge
- Require linear history (no merge commits that might bypass)
- Require signed commits for `gate-override` ADRs (per R1a-F5 — Phase 2 scope)

These are repository-level settings (not YAML); to be configured via `gh api repos/M116cj/j13-ops/branches/main/protection` when Phase 7 nears.

## 5. Local hook relationship (per R1a-F2 HIGH)

Local `~/.claude/hooks/pre-phase-7-gate.sh` remains but is **non-authoritative**:
- Local hook = convenience (fast feedback during local dev)
- Server-side workflow = ground truth (un-bypassable on merge)

Local hook bypass via `git commit --no-verify` has NO effect on the merge gate.

## 6. Enforcement-location summary (MOD-3 amendment to execution_gate §5)

| Gate | Location | Un-bypassable? |
|---|---|---|
| Gate-A (pre-Phase-7) | GitHub Actions `phase-7-gate.yml` (server-side, runs on PRs labeled `phase-7-start` OR touching `zangetsu/src/<new modular paths>`) | YES |
| Gate-B (per module migration) | GitHub Actions `module-migration-gate.yml` (path-based per §3.1) | YES |
| Gate-C (CP takeover) | cp_api API-level check before accepting scatter-site removal PRs (per MOD-1 §5.3) | YES (API-enforced) |

Local `~/.claude/hooks/pre-phase-7-gate.sh` = optional convenience only.

## 7. Resolution status

| Finding | Status |
|---|---|
| R1a-F1 CRITICAL (label bypass) | **RESOLVED** — path-based trigger un-omittable |
| R1a-F2 HIGH (local hook bypass) | **RESOLVED** — server-side workflow is ground truth |

## 8. Label per 0-4 rule 10

- §3.1 path-based trigger spec: **PROBABLE** (design; VERIFIED when workflow lands on main)
- §3.3 path patterns: **VERIFIED** (exhaustively cover modular refactor paths per `modular_target_architecture.md §4 process map`)
- §6 enforcement-location summary: **PROBABLE**
- §7 resolution: **PROBABLE** pending Gemini round-3

## 9. Related MOD-3 deliverables

- `github_actions_gate_b_enforcement_spec.md` — full workflow YAML skeleton
- `amended_modularization_execution_gate.md` — incorporates this correction + MOD-3 amendments
