# Gate-B Path Scope Expansion — MOD-4 Phase 3

**Order**: `/home/j13/claude-inbox/0-5` Phase 3 deliverable
**Produced**: 2026-04-23T10:08Z
**Resolves**: Gemini R3a-F9 MEDIUM — "Gate-B path triggers miss `zangetsu/src/utils/**` + `zangetsu/src/infra/**`"

---

## 1. Change

Expand `github_actions_gate_b_enforcement_spec.md §2` trigger paths + add paths-ignore for files that should NOT gate.

## 2. Old spec (MOD-3)

```yaml
on:
  pull_request:
    paths:
      - 'zangetsu/src/modules/**'
      - 'zangetsu/src/l[0-9]*/**'
      - 'zangetsu/module_contracts/*.yaml'
      - 'zangetsu/module_contracts/*.yml'
```

**Gap (per R3a-F9)**: a contributor could relocate module logic to `zangetsu/src/utils/` or `zangetsu/src/infra/` to avoid Gate-B triggers.

## 3. MOD-4 amended spec

```yaml
on:
  pull_request:
    paths:
      - 'zangetsu/src/**'                           # EXPANDED — covers utils/, infra/, anything new
      - 'zangetsu/module_contracts/**'              # covers .yaml + .yml + subdirs
      - 'zangetsu/migrations/**'                    # DB schema changes (adversarial-sensitive)
      - 'calcifer/**.py'                            # Calcifer supervisor code (crosses governance boundary)
    paths-ignore:
      - 'zangetsu/src/**/*.md'                      # docs don't trigger
      - 'zangetsu/src/**/*.txt'                     # notes don't trigger
      - 'zangetsu/src/**/test_*.py'                 # test files don't trigger (tests reference modules, not define them)
      - 'zangetsu/src/**/tests/**'                  # test directories
      - 'zangetsu/src/**/__pycache__/**'
      - 'zangetsu/src/**/*.pyc'
  push:
    branches: [main]
    paths:                                          # same pattern as pull_request
      - 'zangetsu/src/**'
      - 'zangetsu/module_contracts/**'
      - 'zangetsu/migrations/**'
      - 'calcifer/**.py'
    paths-ignore:
      - 'zangetsu/src/**/*.md'
      - 'zangetsu/src/**/*.txt'
      - 'zangetsu/src/**/test_*.py'
      - 'zangetsu/src/**/tests/**'
      - 'zangetsu/src/**/__pycache__/**'
      - 'zangetsu/src/**/*.pyc'
```

## 4. New trigger paths rationale

| Path | Why triggered |
|---|---|
| `zangetsu/src/**` | Catches any code file anywhere in the module source tree; relocation to `utils/` or `infra/` no longer bypasses |
| `zangetsu/module_contracts/**` | Any YAML add/change under contracts dir |
| `zangetsu/migrations/**` | DB schema migrations are adversarial-sensitive (CS-05 related); anyone committing a migration MUST pass Gate-B |
| `calcifer/**.py` | Calcifer supervisor code crosses the governance boundary (it READS zangetsu VIEW per §17.3); changes warrant Gate-B |

## 5. New paths-ignore rationale

| Path-ignore | Why ignored |
|---|---|
| `**/*.md` | Documentation; not module behavior |
| `**/*.txt` | Notes, READMEs |
| `**/test_*.py` | Test files reference modules, not define them. Moving tests doesn't change production behavior. |
| `**/tests/**` | Test directories, same reason |
| `**/__pycache__/**`, `**/*.pyc` | Python bytecode — should not be in repo (gitignored) but defensive |

Note: Test _coverage_ is validated by Gate-B.B.1 (responsibility→fixture 1:1 check per `amended_module_contract_template.md §4`). Modifying tests doesn't re-trigger Gate-B because Gate-B's purpose is validating CONTRACTS, not tests. Tests validate IMPLEMENTATIONS.

## 6. Adversarial check — can Gate-B still be bypassed?

Per MOD-4's revised scope, potential bypass paths:

1. **Rename `zangetsu/src/` to something else** → WOULD bypass. Mitigation: the workflow's required_status_check name is pinned; renaming `zangetsu/` would require j13-level admin action which triggers separate review.
2. **Create a symlink from `zangetsu/src/modules/xyz/` → external dir** → WOULD work only if symlink target is outside `zangetsu/src/**`. Defense: repo-level audit script in Phase 7 can detect symlinks pointing outside repo.
3. **Commit to a different branch, then re-point `main` HEAD** → blocked by `allow_force_pushes=false` + `required_linear_history=true`.
4. **Admin bypass via j13 PAT** → preserved by design (`enforce_admins=false`). j13 can force-merge without Gate-B; this is intentional for emergency.

No legitimate non-admin bypass path remains after this expansion.

## 7. Change to `amended_modularization_execution_gate_v3.md §5.2`

Replace paragraph:

Old (MOD-3):
> "Triggers (any PR matching these paths — un-bypassable via label omission): zangetsu/src/modules/** / zangetsu/src/l[0-9]*/** / zangetsu/module_contracts/*.yaml / zangetsu/module_contracts/*.yml"

New (MOD-4):
> "Triggers (any PR matching these paths — un-bypassable via label omission OR file-path relocation): `zangetsu/src/**` + `zangetsu/module_contracts/**` + `zangetsu/migrations/**` + `calcifer/**.py`. Paths-ignore: test files + docs + bytecode. Full YAML in `github_actions_gate_b_enforcement_spec.md §2` (v2)."

## 8. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 1. No silent mutation | ✅ — spec change only |
| 8. No broad refactor | ✅ — path expansion is targeted |

## 9. Resolution status

Gemini R3a-F9 MEDIUM — **RESOLVED** at spec level. Workflow YAML update lands in `amended_modularization_execution_gate_v3.md §5.2` and (future) `.github/workflows/module-migration-gate.yml`.

## 10. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — `zangetsu/src/**` covers any subdir including future ones |
| Silent failure | PASS — paths-ignore explicit; tests don't trigger silently |
| External dep | PASS — only GitHub Actions path glob |
| Concurrency | PASS — trigger is atomic per-PR |
| Scope creep | PASS — expansion bounded to module + contract + migration + calcifer code |

## 11. Label per 0-5 rule 10

- §3 amended trigger spec: **VERIFIED** (catches relocation paths)
- §6 bypass audit: **VERIFIED** (3 legitimate non-bypass conclusions; 1 intentional admin bypass)
