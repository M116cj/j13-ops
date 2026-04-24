# Modular Target Architecture — MOD-3 Amendment

**Order**: `/home/j13/claude-inbox/0-4` Phase 2 deliverable
**Produced**: 2026-04-23T07:44Z
**Supersedes**: N/A — this is a DELTA document against `docs/recovery/20260423-mod-1/modular_target_architecture.md`
**Amendment scope**: Update module topology to reflect 9-module mandatory set + L8.G sub-module split + rollout-gating move.

---

## 1. Changes to `modular_target_architecture.md §2 Module topology` diagram

Old topology diagram depicted 7-module mandatory + L1/L8 sub-clusters. New topology adds:

```
                   ┌───────────────────────────┐
                   │    L1 Control Plane       │
                   │  (cp_api + cp_storage +   │
                   │   cp_audit + cp_notifier +│
                   │   cp_cli)                 │
                   └─────────┬─────────────────┘
                             │
                             ▼
                   ┌───────────────────────────┐
                   │  cp_worker_bridge (L1,    │
                   │   MANDATORY M9) —         │
                   │   library consumed by     │
                   │   ALL L2/L4/L5/L6/L8      │
                   │   modules                 │
                   └─────────┬─────────────────┘
                             │ CP parameters
            ┌────────────────┼─────────────────────────────┐
            │                │                             │
            ▼                ▼                             ▼
  ┌──────────────┐  ┌──────────────────┐         ┌─────────────────────┐
  │ L2 Kernel    │  │ L3 Data Input    │         │ L8 Integrity & Gov  │
  │  consumes    │  │ (data_provider + │         │  L8.O obs_metrics   │
  │  PolicyVerdict│  │  schema registry)│         │  L8.G gov_contract_ │
  │  from gov    │  │                  │         │      engine +       │
  │              │  │                  │         │      gov_rollout_   │
  │              │  │                  │         │      authority      │
  └──────────────┘  └──────────────────┘         └──────────┬──────────┘
         │                    │                              │
         ▼                    ▼                              │
  ┌──────────────────────────────────────────────────────┐   │
  │ L4 Research   L5 Evaluation   L6 Gate Layer           │   │
  │ (search_*)    (eval_*)        (gate_registry +        │   │
  │                               gate_contract — M8)    │   │
  │                                                      │   │
  │          L9 Black-box Adapter Pattern — applied     │   │
  │          inside L4/L5 when needed                   │   │
  └──────────────────────────────────────────────────────┘   │
         ▲                                                    │
         │ PolicyVerdict                                      │
         └────────────────────────────────────────────────────┘
```

Key topology changes:
1. **cp_worker_bridge (M9) promoted** to a visible box, shown as the universal bus between L1 CP service and all other layers
2. **gate_contract (M8) added** to L6 alongside gate_registry (registry = data, contract = execution)
3. **PolicyVerdict edge** added from L8.G → L2 (formalizes the rollout-gating ownership move per R2-F2)
4. **gov_rollout_authority** added as L8.G sub-module (split from gov_contract_engine per §3 of `gov_contract_engine_boundary_update.md`)

## 2. Changes to `§3 Modules (by layer)`

### L1 Control Plane — unchanged list + M9 flag
```
- cp_api
- cp_storage
- cp_audit
- cp_notifier
- cp_cli
- **cp_worker_bridge** ← NOW MANDATORY M9 per MOD-3
```

### L6 Gate — SPLIT into data-plane + execution-plane
```
Old:
- gate_registry (with implicit gate-contract umbrella)
- gate_admission / gate_a2 / gate_a3 / gate_a4 / gate_promote / gate_calcifer_bridge

New (MOD-3):
- gate_registry (M2, data-plane: threshold store + version history)
- **gate_contract (M8, execution-plane: evaluates all gates against MetricsContract + ThresholdLookup)**
  — absorbs: gate_admission + gate_a2 + gate_a3 + gate_a4 + gate_promote + gate_calcifer_bridge (as internal evaluators)
```

### L8.G Governance — sub-module split
```
Old:
- gov_contract_engine (monolithic)
- gov_reconciler
- gov_audit_stream
- gov_rollout  ← was a sub-module but not distinguished in MOD-1 mandatory set
- gov_ci_hooks

New (MOD-3):
- **gov_contract_engine (M4, core: charter + blocklist evaluation + audit + alert)**
- **gov_rollout_authority (NEW sub, split from M4: rollout-advance authorization)**
- gov_reconciler
- gov_audit_stream
- gov_ci_hooks
```

Mandatory count: gov_contract_engine remains M4 (with scope tightened); gov_rollout_authority is an L8.G sub-module (not promoted to mandatory — same treatment as obs_logs, obs_view etc.).

### L2 Engine Kernel — unchanged list; behavioral change only
```
- kernel_state
- kernel_lease
- kernel_dispatcher
- kernel_logger
```

Behavioral change (per §3 of `gov_contract_engine_boundary_update.md`):
- kernel_dispatcher now consumes `PolicyVerdict` from `gov_contract_engine` before dispatching any rollout-sensitive transition
- No module additions; edge additions only

## 3. Changes to `§4 Processes (deployment units)`

Old process list:
| Process | Modules hosted |
|---|---|
| cp_service | cp_api, cp_storage, cp_audit, cp_notifier |
| zangetsu_engine | kernel_state, kernel_dispatcher, kernel_lease |
| zangetsu_worker_A1 × N | eval_a1 + search_gp |
| zangetsu_worker_A23 × 1 | eval_a2_holdout + eval_a3_train |
| zangetsu_worker_A45 × 1 | eval_a4_gate + eval_a5_tournament |
| data_collector | data_provider + data_schema_registry + data_health |
| observer | obs_metrics + obs_freshness + obs_reports + gov_reconciler |
| gov_service | gov_contract_engine + gov_audit_stream + gov_ci_hooks |

MOD-3 amendment:
| Process | MOD-3 change |
|---|---|
| cp_service | cp_worker_bridge is in-process library (not a separate process); consumers statically link/import |
| zangetsu_engine | unchanged; dispatcher consumes PolicyVerdict (CP edge) |
| zangetsu_workers_A1/A23/A45 | each worker imports cp_worker_bridge library |
| gov_service | hosts gov_contract_engine + gov_rollout_authority + gov_audit_stream + gov_ci_hooks (4 modules) |
| L6 gate process | NEW — hosts gate_contract as a long-running evaluator; may share process with zangetsu_worker_A23/A45 (per deployment choice) |

## 4. Changes to `§6 Cross-module contracts`

Add new contracts:
- `PolicyVerdict` (gov_rollout_authority → engine_kernel + cp_api + gov_ci_hooks)
- `ThresholdLookup` (gate_registry → gate_contract; formalized name)
- `ParameterValue` (cp_worker_bridge → every consumer)
- `CPChangeEvent` (cp_notifier → cp_worker_bridge subscribers)

Total contracts: 10 MOD-1 + 4 MOD-3 = 14 cross-module contracts.

## 5. Coherence check against other MOD-3 deliverables

| MOD-3 doc | Consistent? |
|---|---|
| `amended_module_boundary_map.md` §2 (9-module set) | ✅ |
| `gate_contract_module_spec.md` (M8 full contract) | ✅ |
| `cp_worker_bridge_promotion_spec.md` (M9 full contract) | ✅ |
| `gov_contract_engine_boundary_update.md` (rollout-gating move) | ✅ |
| `amended_module_contract_template.md` (Field 15 additive) | ✅ |
| `gate_b_trigger_correction.md` (path-based trigger) | ✅ |
| `github_actions_gate_b_enforcement_spec.md` (server-side enforcement) | ✅ |

No contradictions; single coherent amendment.

## 6. Label per 0-4 rule 10

- §1 topology amendment: **PROBABLE** (design; VERIFIED when Phase 7 lands modules)
- §2 per-layer module lists: **VERIFIED** (1:1 with boundary map + supporting MOD-3 deliverables)
- §4 process amendments: **PROBABLE** (deployment choice has freedom; spec describes minima)
- §5 coherence: **VERIFIED** in §5 check-table
