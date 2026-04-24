# gate_calcifer_bridge Resolution — MOD-4 Phase 1

**Order**: `/home/j13/claude-inbox/0-5` Phase 1 primary deliverable
**Produced**: 2026-04-23T09:30Z
**Resolves**: Gemini R3b-F1 CRITICAL — `gate_calcifer_bridge` depended on by M8 `gate_contract` but not in mandatory set
**Decision**: **FOLD** — `gate_calcifer_bridge` is folded into `gate_contract` (M8). No new mandatory module added.

---

## 1. Decision

**FOLD** — gate_calcifer_bridge ceases to exist as a separate sub-module. Its sole behavior (read `/tmp/calcifer_deploy_block.json`, publish state) is absorbed directly into M8 `gate_contract`.

Alternative considered: **PROMOTE** to 10th mandatory module. Rejected.

## 2. Rationale for FOLD vs PROMOTE

### 2.1 What gate_calcifer_bridge does today

Per MOD-1 `module_boundary_map.md §2` Ascension table:
> "gate_calcifer_bridge: Calcifer block file reader (scattered today); Upstream contract: calcifer block JSON; Downstream contract: GateOutcomeContract (veto)"

Scope: thin read wrapper around `/tmp/calcifer_deploy_block.json`. Publishes a boolean-veto signal into gate promotion logic.

### 2.2 FOLD arguments (chosen)

- **Simplicity**: the bridge is 50–100 lines of code at most. Creating a separate module + registry entry + contract review for 50 lines is overhead without benefit.
- **Cohesion**: reading Calcifer state is PART of gate decision logic. The gate needs to know "is deployable blocked?" — that IS a gate property, not a data-plane concern.
- **Consistency with existing pattern**: M8 `gate_contract` already absorbs 6 evaluators (admission / A2 / A3 / A4 / promote / calcifer). Separating one of them is arbitrary.
- **Smaller mandatory set**: staying at 9 mandatory modules is architecturally tighter than 10.
- **No loss of auditability**: M8 `failure_surface` already covers `calcifer_red_active` detection; folding makes this explicit rather than cross-module.

### 2.3 PROMOTE arguments (rejected)

- **Mirror cp_worker_bridge (M9)**: cp_worker_bridge was promoted because 6 modules depended on it universally. gate_calcifer_bridge is used by M8 ONLY. Different shape; different conclusion.
- **Explicit versioning**: a separate module could evolve independently. Not needed — Calcifer's block-file schema is fixed (see `calcifer/zangetsu_outcome.py` §17.3). No evolution pressure.
- **Register separate failure surface**: already covered in M8 `failure_surface.calcifer_red_active`.

### 2.4 Adversarial check

Q: "If folded, how does M8 avoid violating the `execution_environment.filesystem_read_paths` discipline?"
A: M8 Field 15 adds explicit `filesystem_read_paths: ["/tmp/calcifer_deploy_block.json"]`. Legitimate, declared, auditable. Not a hidden side channel.

Q: "Is there any failure mode where folding hides a bug that separating would have made visible?"
A: No. Folding changes the location of the code, not the observability. M8 metrics already include `gate_contract_calcifer_block_active_total` counter — this is already exposed.

Q: "Does folding make M8 responsibility count exceed the 2–7 rule?"
A: M8 pre-fold had 6 responsibilities. Folding does NOT add a responsibility — "evaluate Calcifer block state" is implicit within "evaluate promote gate" (per M8 original responsibilities). No count change.

## 3. Concrete changes to M8 gate_contract contract

### 3.1 `responsibilities` — unchanged
All 6 entries remain; "evaluate Calcifer block state" is sub-task of "evaluate final promotion gate".

### 3.2 `inputs` — change

Old (MOD-3):
```yaml
- contract_name: CalciferBlockState
  source_module: gate_calcifer_bridge (external sibling consumer of /tmp/calcifer_deploy_block.json)
  cardinality: stream
  frequency: polling_60_seconds
```

New (MOD-4):
```yaml
- contract_name: CalciferBlockFile
  source_module: filesystem (direct read of /tmp/calcifer_deploy_block.json)
  cardinality: on_demand_per_promote_decision
  frequency: event (read on every promote gate evaluation; bounded to ≤ 1/s given arena cadence)
```

### 3.3 `failure_surface` — strengthened

Add explicit failure mode:
```yaml
- name: calcifer_flag_missing_or_stale
  detection: "os.stat() reports mtime > 10min OR file missing OR json parse fail"
  recovery: "treat as RED (fail-closed — deny promotion; log to obs_metrics; emit audit row)"
  observable_via: gate_contract_calcifer_flag_stale_total
  alert_rule: "rate(gate_contract_calcifer_flag_stale_total[5m]) > 0 → WARN"
```

### 3.4 `execution_environment` (Field 15) — amended

Old:
```yaml
execution_environment:
  permitted_egress_hosts: []
  filesystem_write_paths: []
```

New:
```yaml
execution_environment:
  permitted_egress_hosts: []
  filesystem_read_paths:           # NEW MOD-4 addition
    - "/tmp/calcifer_deploy_block.json"
  filesystem_write_paths: []
  # other fields unchanged
```

Note: `filesystem_read_paths` is a NEW sub-field of Field 15 (see `amended_module_contract_template_v3.md`). Adds read allowlisting alongside the write-path allowlisting.

### 3.5 `metrics` — add 2

```yaml
- {name: gate_contract_calcifer_flag_stale_total, type: counter, unit: events, labels: [reason], cardinality_cap: 5, sample_sla: event}
- {name: gate_contract_calcifer_read_duration_seconds, type: histogram, unit: seconds, labels: [], cardinality_cap: 1, sample_sla: event}
```

## 4. Concrete changes to boundary map

### 4.1 `module_boundary_map.md §2` Ascension table row

Old:
```
| gate_calcifer_bridge | Calcifer block file reader (scattered today) | Calcifer daemon internals | calcifer block JSON | GateOutcomeContract (veto) |
```

New (MOD-4):
```
| gate_calcifer_bridge | FOLDED INTO gate_contract (MOD-4 Phase 1) | — | — | — |
```

Marked as FOLDED rather than removed — preserves historical trace.

### 4.2 `§MOD-1.C` mapping table row for M8

Old:
```
| gate_contract (NEW M8) | gate_admission + gate_a2 + gate_a3 + gate_a4 + gate_promote + gate_calcifer_bridge (execution side) | ADDED |
```

New (MOD-4):
```
| gate_contract (M8) | gate_admission + gate_a2 + gate_a3 + gate_a4 + gate_promote + gate_calcifer_bridge (ALL absorbed via FOLD) | ABSORBED gate_calcifer_bridge per MOD-4 Phase 1 |
```

## 5. Changes to modular_target_architecture

Per `modular_target_architecture_amendment.md §2` L6 Gate section — old:
> "gate_contract (M8, execution-plane: ...) — absorbs: gate_admission + gate_a2 + gate_a3 + gate_a4 + gate_promote + gate_calcifer_bridge (as internal evaluators)"

MOD-4 confirms this — previously ambiguous whether gate_calcifer_bridge was a sub-module or internal evaluator; MOD-4 FOLDS IT as INTERNAL EVALUATOR definitively. No external edge.

## 6. Non-negotiable rules compliance

| Rule | Compliance |
|---|---|
| 1. No silent production mutation | ✅ — MOD-4 is spec-level; no runtime change |
| 3. No live gate change | ✅ — Calcifer RED logic unchanged; only the MODULE boundary changes |
| 8. No broad refactor | ✅ — FOLD is the minimal-surface remediation |
| 9. No black-box control surface | ✅ — M8 absorbs Calcifer state visibly with declared Field 15 read path |

## 7. Impact on Phase 7 implementation plan

When Phase 7 builds M8 `gate_contract`:
- Implementation includes direct `json.load(open("/tmp/calcifer_deploy_block.json"))` (or mmap for perf)
- No separate `gate_calcifer_bridge/*.py` module files
- No `zangetsu/module_contracts/gate_calcifer_bridge.yaml`
- Single module test suite covers all 6 evaluators including Calcifer

Net LOC estimate: folding saves ~50–100 lines vs separate module (no duplicated contract scaffolding).

## 8. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — FOLD explicitly declares filesystem_read_paths; egress declaration unchanged |
| Silent failure | PASS — calcifer_flag_stale as explicit failure mode |
| External dep | PASS — only local filesystem read; no new network dep |
| Concurrency | PASS — read is on-demand per promote gate; no concurrent write |
| Scope creep | PASS — FOLD is the smaller-scope option |

## 9. Label per 0-5 rule 10

- §1 decision: **VERIFIED** (reasoned trade-off between FOLD vs PROMOTE)
- §2 rationale: **VERIFIED** (adversarial-checked)
- §3 M8 contract changes: **PROBABLE** (design; VERIFIED when Phase 7 yaml validates)
- §4 boundary map changes: **PROBABLE** (textual delta; landed in `amended_module_boundary_map_v3.md`)

## 10. Exit condition (0-5 §Phase 1)

"No mandatory-path dependency remains outside the mandatory-path definition." **MET** — M8 absorbs gate_calcifer_bridge; no external edge.
