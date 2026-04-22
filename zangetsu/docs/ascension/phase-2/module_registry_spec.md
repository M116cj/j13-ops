# Zangetsu — Module Registry Spec (Phase 2)

**Program:** Ascension v1 Phase 2
**Date:** 2026-04-23
**Status:** DESIGN.

---

## §1 — Purpose

Define WHAT a module registry is in Zangetsu and HOW modules register. This is a specification, not an implementation.

---

## §2 — Requirements

1. Every runtime module self-declares its contract (per Ascension §3.4 ten fields).
2. Registry is queryable at runtime from CP.
3. Module version is bound to its contract version; contract breaking change = major version.
4. Health is reported to L8.O.
5. Replacement is possible without rebuilding the world.

---

## §3 — Registration entry schema

```
module:
  id: <canonical name — matches modular_target_architecture.md>
  layer: L1|L2|L3|L4|L5|L6|L7|L8.O|L8.G|L9(pattern)
  version: <semver>
  contract_version: <major.minor>
  repo_path: <path/to/module>
  owner: <agent or team — claude_lead | gemini | codex | markl | calcifer | j13>

  # Ascension §3.4 fields
  purpose: <one-line>
  responsibilities: [<list>]
  inputs:
    - contract: <ContractName>
      description: <text>
  outputs:
    - contract: <ContractName>
      description: <text>
  config_schema: <ref or inline>
  state_schema: <ref or inline>
  metrics: [<metric name + unit>]
  error_surface: [<failure mode>]
  rollback_surface: <how to revert changes this module made>
  test_boundary: <test suite location>
  replacement_boundary: <what replacing this module entails>

  # Operational
  blackbox_pattern_applied: bool
  adapter_contract_ref: <path if blackbox>
  rollout_tier: OFF|SHADOW|CANARY|FULL
  health_endpoint: <url or internal probe>
  dependencies: [<module ids>]
  dependents: [<module ids>]
```

---

## §4 — Registry storage

- Canonical registry lives in Postgres `control_plane.modules` table.
- Human-editable YAMLs under `zangetsu/module_contracts/<module_id>.yaml` are the source of truth for each module's contract; CP sync job reads + upserts.
- On worker startup, worker self-registers OR verifies its declared contract against registry; mismatch = fail-closed.

---

## §5 — Registration workflow

### §5.1 New module
1. Author writes YAML contract at `zangetsu/module_contracts/<id>.yaml`.
2. Gemini adversarial review.
3. Claude Lead approves.
4. ADR `docs/decisions/YYYYMMDD-module-<id>.md` committed.
5. CP sync job picks it up on next cron; module becomes SHADOW tier.
6. Rollout tier advances per operational policy.

### §5.2 Existing module contract change
1. Diff PR against `<id>.yaml`.
2. Determine semver impact (patch / minor / major).
3. If breaking: consumer migration plan attached.
4. Gemini adversarial + ADR.
5. CP accepts new version; old dependents warned.

---

## §6 — Queries

- `GET /api/control/modules` — all registered modules
- `GET /api/control/modules/{id}` — single entry + lineage + health
- `GET /api/control/modules/by-layer/{L}` — all modules in a layer
- `GET /api/control/modules/contract-mismatches` — modules whose runtime doesn't match declared contract

---

## §7 — Relationship to mutation_blocklist.yaml

Every module entry references which `mutation_blocklist` rules it is subject to (e.g. `BL-F-003 applies` for anything writing fresh). Reconciler crons (gov_reconciler) consult this mapping.

---

## §8 — Non-goals

- NOT a package manager.
- NOT handling secret storage.
- NOT bundling/build system.
