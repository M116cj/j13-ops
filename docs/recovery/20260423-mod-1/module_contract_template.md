# Module Contract Template — Zangetsu MOD-1

**Order**: `/home/j13/claude-inbox/0-2` Phase 4 deliverable
**Produced**: 2026-04-23T02:45Z
**Author**: Claude (Lead)
**Status**: **CANONICAL TEMPLATE** — any new Zangetsu module MUST declare one instance of this contract before entering the Module Registry (§7 `module_registry_spec.md`). Any drift between declared contract and runtime = fail-closed (§MOD-1 rule 9).

---

## §1 — Purpose

Every module in Zangetsu's modular target architecture MUST self-declare a machine-readable contract that covers the 14 MOD-1 mandatory fields. This contract is:

- **The unit of modularity** — defines exactly where the module begins and ends
- **The unit of replacement** — another implementation can replace it iff the new impl honours this contract
- **The unit of review** — Gemini adversarial reviews happen at this grain
- **The unit of rollback** — rollback_surface is part of the contract, not ad-hoc

A module without a complete contract is **not a module**; it's a script.

---

## §2 — Mandatory fields (exactly 14 per MOD-1 Phase 4)

### Field 1 — `module_name`
Canonical identifier. Convention: `<layer_prefix>_<role>` (e.g. `kernel_state`, `gate_admission`, `search_gp`).
Naming rules: lowercase snake_case; no version suffix (version is separate field); unique within registry.

### Field 2 — `purpose`
One sentence. Answers "why does this module exist".
Anti-patterns to reject:
- "handles X" (vague)
- "manages Y and Z and also W" (multi-purpose = not a module)
- "contains the logic for" (what logic? rewrite with nouns not "logic")

### Field 3 — `responsibilities`
Enumerated list. Each entry = one verb + one noun. Typically 3–7 entries. **>7 entries = module too large, split.** **<2 entries = module too small, merge.**

### Field 4 — `inputs`
Each input = `{contract_name, source_module, cardinality, frequency}`.
- `contract_name`: must reference a declared Contract (e.g. `CandidateContract`, `MetricsContract`).
- `source_module`: which other module produces it.
- `cardinality`: one-per-request / one-per-champion / stream.
- `frequency`: event-driven / polling interval / on-demand.

Inputs MUST be typed — `any` is rejected. Inputs MUST come from another registered module — bare file reads or env-var polling are rejected (CP registry is the data-plane authority).

### Field 5 — `outputs`
Each output = `{contract_name, consumer_modules, cardinality, guarantees}`.
- `contract_name`: referenced Contract.
- `consumer_modules`: downstream modules that consume.
- `cardinality`: one-per-input / n-per-input / stream.
- `guarantees`: at-most-once / at-least-once / exactly-once; ordering (total / partition / none); idempotency.

### Field 6 — `config_schema`
Reference to a YAML/JSON-Schema file declaring all parameters the module reads at runtime, with:
- canonical key
- type
- default
- valid_range / enum
- rollout tier (OFF / SHADOW / CANARY / FULL) if any are gated
- consumed by: [list of dependent modules]

Config MUST come from the Control Plane (`cp_storage`). Hardcoded literals in module code are forbidden except as *fallback when CP unreachable* (and even then, emit warning per `control_plane_blueprint §2 rule 2`).

### Field 7 — `state_schema`
What persistent state the module owns. For each state component:
- name
- type
- storage (Postgres table / Redis key / in-memory)
- ownership (EXCLUSIVE — only this module writes / SHARED — name all other writers / READ-ONLY)
- lifecycle (persistent / session-scoped / request-scoped)

In-memory-only state must be reconstructable from persistent state on restart.

### Field 8 — `metrics`
Prometheus-compatible list. Each metric = `{name, type (counter/gauge/histogram/summary), unit, labels, cardinality_cap, sample_sla}`.
Minimum required metrics for every module:
- `<module>_up{version}` — gauge
- `<module>_requests_total{outcome}` — counter
- `<module>_request_duration_seconds` — histogram
- Module-specific domain metrics

### Field 9 — `failure_surface`
Enumerated failure modes. For each failure:
- `name`
- `detection`: how this module or an observer detects the failure
- `recovery`: what the module does automatically (retry / fallback / circuit-break / degrade / fail-closed)
- `observable_via`: metric name + alert rule

Minimum categories to cover (add more as needed):
- upstream unavailable
- malformed input (schema violation)
- timeout / latency blowup
- resource exhaustion (RAM / CPU / disk / file descriptors)
- dependency failure
- invariant violation
- non-determinism detected (if wrapped black-box)

### Field 10 — `rollback_surface`
Exactly what it takes to revert state changes this module has made, expressed as:
- `code_rollback`: git SHA to revert to OR "idempotent — no code rollback needed"
- `state_rollback`: SQL / Redis / file operations, OR "append-only, no rollback"
- `downstream_effect`: what other modules observe during rollback (reads may fail? reads return stale? no effect?)
- `rollback_time_estimate`: p50 / p95 wall-clock
- `rollback_rehearsal`: date last tested (refresh quarterly)

### Field 11 — `test_boundary`
Where unit + contract tests live. Each module MUST have:
- unit tests exercising its own logic (no cross-module dependencies)
- contract tests verifying input/output schemas
- golden fixtures for critical paths

Declared location: `zangetsu/tests/<layer>/<module_name>/`.
Coverage threshold: configurable per module criticality (gate / state-owning modules ≥80%, peripheral ≥40%).
Integration tests are a separate boundary; not owned by a single module.

### Field 12 — `replacement_boundary`
Exactly what it takes to swap this module for an alternative implementation:
- contract version required (min + max)
- migration mode (hot-swap / restart-after-swap / schema-migrate-first)
- downstream dependency impact
- shadow-mode prerequisite (mandatory for any L2/L4/L5/L6 module)
- data-retention implication

### Field 13 — `blackbox_allowed`
Boolean + rationale.
- `false` (default): module must be fully auditable; no ML models / external LLM calls / opaque binaries internally.
- `true`: module wraps a black-box via the Adapter Pattern (see `phase-2/blackbox_adapter_contracts.md`). When `true`, field 14 `console_controls` must include an adapter-health override + a force-disable switch.

### Field 14 — `console_controls`
Which parameters/actions this module exposes on the Control Plane (Phase 6 blueprint). Each entry:
- `surface_key` (parameter key or action id)
- `class` (parameter / kill_switch / rollout_advance / mode_change)
- `decision_rights` (reference to `control_plane_blueprint §5`)
- `audit_tier` (standard / high — standard writes audit row; high also emits Telegram)

Modules that expose ZERO console_controls are rejected — every module must be operator-introspectable.

---

## §3 — Machine-readable skeleton (YAML)

```yaml
module:
  module_name: <snake_case>
  purpose: <one-line>
  responsibilities:
    - <verb> <noun>
    - <verb> <noun>
  inputs:
    - contract_name: <ContractName>
      source_module: <module_id>
      cardinality: one_per_request | one_per_champion | stream
      frequency: event | polling_N_seconds | on_demand
  outputs:
    - contract_name: <ContractName>
      consumer_modules: [<module_id>, ...]
      cardinality: one_per_input | n_per_input | stream
      guarantees:
        delivery: at_most_once | at_least_once | exactly_once
        ordering: total | partition | none
        idempotency: true | false
  config_schema:
    ref: config_schemas/<module_name>.yaml
    cp_params: [<canonical_keys>]
  state_schema:
    - name: <state_name>
      type: <type>
      storage: postgres.<table> | redis.<key> | in_memory
      ownership: EXCLUSIVE | SHARED[<writers>] | READ_ONLY
      lifecycle: persistent | session | request
  metrics:
    - name: <module>_<metric>
      type: counter | gauge | histogram | summary
      unit: <unit>
      labels: [<label1>, <label2>]
      cardinality_cap: <int>
      sample_sla: <description>
  failure_surface:
    - name: <failure_mode>
      detection: <how>
      recovery: retry | fallback | circuit_break | degrade | fail_closed
      observable_via: <metric>
      alert_rule: <prometheus-expr or log pattern>
  rollback_surface:
    code_rollback: <git SHA or "idempotent">
    state_rollback: <SQL / Redis ops / "append-only">
    downstream_effect: <description>
    rollback_time_estimate_p50: <duration>
    rollback_time_estimate_p95: <duration>
    rollback_rehearsal: <YYYY-MM-DD>
  test_boundary:
    unit: zangetsu/tests/<layer>/<module>/test_unit.py
    contract: zangetsu/tests/<layer>/<module>/test_contract.py
    coverage_target_pct: <int>
  replacement_boundary:
    contract_version_min: <semver>
    contract_version_max: <semver>
    migration_mode: hot_swap | restart_after_swap | schema_first
    downstream_impact: <description>
    shadow_required: true | false
  blackbox_allowed: false | true
  blackbox_rationale: <if true, reference adapter contract ref>
  console_controls:
    - surface_key: <key>
      class: parameter | kill_switch | rollout_advance | mode_change
      decision_rights_ref: control_plane_blueprint.md#<anchor>
      audit_tier: standard | high
```

---

## §4 — Acceptance checklist (for module submission)

Before a module YAML is accepted into `control_plane.modules`:

- [ ] All 14 mandatory fields populated (no `TBD`, no placeholder strings)
- [ ] `purpose` passes the one-sentence rule (§2 field 2)
- [ ] `responsibilities` is 2–7 entries
- [ ] Every input and output references a declared Contract (not `any`, not raw type)
- [ ] `config_schema` exists as a file; CP canonical keys enumerated
- [ ] `state_schema` states ownership explicitly (no "multiple writers" without listing them)
- [ ] At minimum the 3 required metrics (`_up`, `_requests_total`, `_request_duration_seconds`) are declared
- [ ] `failure_surface` covers the 7 minimum categories
- [ ] `rollback_surface` is executable (not "TBD", not "manual intervention")
- [ ] `test_boundary` locations exist (file may be empty stub but path is declared)
- [ ] `replacement_boundary.migration_mode` is one of the 3 enums
- [ ] `blackbox_allowed` false OR adapter contract ref valid
- [ ] `console_controls` has at least one entry with `kill_switch` class
- [ ] Gemini adversarial review signed off
- [ ] ADR `docs/decisions/YYYYMMDD-module-<name>.md` exists and is committed
- [ ] CI (CP sync workflow) would accept this YAML (dry-run in PR)

If any item fails: **module rejected**; module code does not ship.

---

## §5 — Anti-patterns (reject at review)

| Pattern | Why rejected |
|---|---|
| "purpose: utilities for X" | Utilities = not a module. Split by responsibility. |
| Inputs from file paths rather than contracts | Data plane must be typed; file-based coupling is forbidden (D-16). |
| `config: env vars directly` | CP is the source of truth. Emit warning on fallback but don't declare env as canonical. |
| Multi-writer state without explicit SHARED[list] | Creates silent state drift (mutation_blocklist). |
| `metrics: []` | Violates observability requirement. |
| `failure_surface: []` | Module never fails = module never runs. Invalid. |
| `rollback: manual` | Rollback must be executable. If truly manual, document the exact runbook steps. |
| `blackbox_allowed: true` without adapter contract | Contradicts charter §3.6 white-box control surface. |
| `console_controls: []` | Module is not operator-introspectable. Violates MOD-1 rule 8 (no black-box control surface). |

---

## §6 — Versioning

- Contract version follows semver: `MAJOR.MINOR`
  - MAJOR: breaking input/output schema change; requires all consumers migration plan
  - MINOR: additive change (new optional field); consumers unaffected
- Module implementation version is independent: `MAJOR.MINOR.PATCH`
- A module may advance implementation version under same contract version (bug fixes, perf)
- Contract bump requires ADR + Gemini review + CP migration plan

---

## §7 — Relationship to other MOD-1 docs

| Source | Relationship |
|---|---|
| `module_boundary_map.md` | Lists WHICH modules exist; this template defines WHAT each module's contract looks like. |
| `module_registry_spec.md` | Defines WHERE contracts are stored + HOW they sync. This template defines the SHAPE of each entry. |
| `modular_target_architecture.md` | Defines module topology. Contracts are the edges. |
| `control_plane_blueprint.md` | Defines how `console_controls` surfaces wire to CP. |
| `architecture_drift_map.md` | Drift entries identify modules whose current form does NOT yet have a complete 14-field contract; they go in Phase 7 migration queue. |

---

## §8 — Q1 adversarial for this template

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | 14 fields cover MOD-1 Phase 4 mandatory list verbatim; each field has acceptance rule | PASS |
| Silent failure | Anti-patterns §5 catch the most common silent-coupling failures observed in current Zangetsu (D-16 cross-process file deps, D-08 5-gate-authors) | PASS |
| External dep | Template does not itself depend on any external system; it's pure spec | PASS |
| Concurrency | State ownership rule forces SHARED writers to be enumerated = race conditions become visible in contract review | PASS |
| Scope creep | Template specifies only fields + acceptance; does NOT dictate implementation language, framework, or storage backend | PASS |
