# Amended Module Boundary Map — Zangetsu MOD-3

**Order**: `/home/j13/claude-inbox/0-4` Phase 1 deliverable
**Produced**: 2026-04-23T07:15Z
**Supersedes**: `docs/recovery/20260423-mod-1/module_boundary_map.md §MOD-1.B` (7 mandatory modules) via amendment
**Amendment scope**: Add Module 8 `gate_contract` + Module 9 `cp_worker_bridge` (from Phase 2 HIGH fix) to mandatory set; resolve R2-F1 CRITICAL + R2-F3 HIGH.

---

## 1. Amendment summary

| Change | Source finding | Severity |
|---|---|---|
| **Add Module 8 gate_contract** (L6 execution engine) | Gemini R2-F1 | CRITICAL |
| **Add Module 9 cp_worker_bridge** (CP data-plane bridge) | Gemini R2-F3 | HIGH |
| Change engine_kernel responsibility: remove "enforces rollout gating"; add "consumes PolicyVerdict from gov_contract_engine" | Gemini R2-F2 | HIGH |
| Add rollout-gating ownership to gov_contract_engine responsibilities | Gemini R2-F2 | HIGH |
| Add L9-adapter-disclaimer to eval_contract (M6) | Gemini R2-F5 | LOW |
| Downgrade M6 rollback_time p95 from 8min to 30min OR add persistent data_cache snapshot | Gemini R2-F4 | MEDIUM |

## 2. Amended mandatory module set (now 9, was 7)

| # | Module | Layer | Role |
|---|---|---|---|
| 1 | `engine_kernel` | L2 | Arena state machine; dispatch; lease mgmt |
| 2 | `gate_registry` | L6 data-plane | Threshold store + version history |
| 3 | `obs_metrics` | L8.O | Metrics export + cardinality enforcement |
| 4 | `gov_contract_engine` | L8.G | Charter §17 + blocklist rule engine + **rollout gating (moved from M1)** |
| 5 | `search_contract` | L4 | SearchEngine interface abstraction |
| 6 | `eval_contract` | L5 | Evaluator interface + CD-14 slice discipline |
| 7 | `adapter_contract` | L9 pattern | Black-box wrapper contract |
| **8** | **`gate_contract`** | **L6 execution-plane** | **Gate decisions: admission / A2 / A3 / A4 / promote** |
| **9** | **`cp_worker_bridge`** | **L1 worker-side** | **CP param read / subscribe library consumed by all workers** |

Full 14-field contracts:
- M1–M7: see MOD-1 `module_boundary_map.md §MOD-1.B` (M6 + M1 amendments noted below)
- **M8**: `gate_contract_module_spec.md` (this MOD-3 deliverable)
- **M9**: `cp_worker_bridge_promotion_spec.md` (this MOD-3 deliverable)

## 3. M1 engine_kernel — amended responsibilities

Old (MOD-1):
> "enforces rollout gating"

New (MOD-3 per R2-F2):
> "consumes PolicyVerdict from gov_contract_engine; if verdict=deny for a transition, halts that transition"

Full amended engine_kernel contract differs only in §2 `responsibilities` and adds one input edge:
```yaml
inputs:
  # ... existing inputs ...
  - contract_name: PolicyVerdict
    source_module: gov_contract_engine
    cardinality: one_per_transition_attempt
    frequency: event
```

## 4. M4 gov_contract_engine — amended responsibilities

Old (MOD-1):
> "consume commit + PR + CP write events; evaluate each against charter §17 rules + mutation_blocklist; emit allow/deny + audit + rollback-handle; post RED Telegram; sync to cp_audit"

New (MOD-3 per R2-F2):
Same 5 responsibilities PLUS:
> "authorize rollout tier advances (OFF → SHADOW → CANARY → FULL); consume rollout advance requests from cp_api; emit PolicyVerdict to engine_kernel on transition-attempt eligibility"

Input edge added:
```yaml
inputs:
  # ... existing inputs ...
  - contract_name: RolloutAdvanceRequest
    source_module: cp_api (operator-originated)
    cardinality: event
    frequency: on_demand
  - contract_name: TransitionAttemptEvent
    source_module: engine_kernel
    cardinality: one_per_transition_attempt
    frequency: event
```

Output edge added:
```yaml
outputs:
  # ... existing outputs ...
  - contract_name: PolicyVerdict
    consumer_modules: [engine_kernel, cp_api, gov_ci_hooks]
    cardinality: one_per_input
    guarantees:
      delivery: exactly_once
      ordering: total
      idempotency: true
```

## 5. M6 eval_contract — amended fields

### 5.1 blackbox_allowed rationale (per R2-F5 LOW, now consistent with M5)

Old:
> "blackbox_allowed: false"

New:
```yaml
blackbox_allowed: false
blackbox_rationale: "eval_contract itself is the orchestrator. Specific evaluator implementations using ML-based scoring (e.g., a future ML-based A4 gate evaluator) would wrap their model via L9 adapter pattern; those sub-modules declare blackbox_allowed: true with adapter_contract_ref."
```

### 5.2 rollback_surface (per R2-F4 MEDIUM)

Old:
> "p50=3 minutes p95=8 minutes (includes data_cache rebuild)"

New (persistent snapshot added):
```yaml
rollback_surface:
  code_rollback: git-revert
  state_rollback: "data_cache has persistent last-known-good snapshot at zangetsu/data/eval_cache_snapshot/*.parquet (refreshed every 1h by obs_freshness sidecar); rollback restores from snapshot → restart data_cache in <90s instead of cold rebuild"
  downstream_effect: "gates pause during restart; kernel queues"
  rollback_time_estimate_p50: 90 seconds (WITH snapshot)
  rollback_time_estimate_p95: 3 minutes (WITH snapshot)
  rollback_time_estimate_p95_worst_case: 30 minutes (IF snapshot missing — cold rebuild from parquet)
  rollback_rehearsal: (scheduled pre-Phase-7, both paths tested)
```

## 6. Updated cross-reference (supersedes MOD-1 `module_boundary_map.md §MOD-1.C`)

| MOD-1 module | Ascension §2 absorbs | MOD-3 status |
|---|---|---|
| engine_kernel | kernel_state + kernel_lease + kernel_dispatcher + kernel_logger | amended (rollout gating removed) |
| gate_registry | gate_registry + gate_contract umbrella (SPLIT in MOD-3 — see below) | amended |
| **gate_contract (NEW M8)** | gate_admission + gate_a2 + gate_a3 + gate_a4 + gate_promote + gate_calcifer_bridge (execution side) | ADDED |
| obs_metrics | obs_metrics + obs_logs + obs_view + obs_reports + obs_freshness | unchanged |
| gov_contract_engine | gov_contract_engine + gov_reconciler + gov_audit_stream + gov_rollout + gov_ci_hooks | amended (rollout gating moved here) |
| search_contract | search_contract + search_gp + search_lgbm + search_factor_zoo + search_hand_seed + primitive_registry | unchanged |
| eval_contract | eval_contract + eval_a1 + eval_a2_holdout + eval_a3_train + eval_a4_gate + eval_a5_tournament + backtester + cost_model | amended (rollback snapshot added, L9 disclaimer added) |
| adapter_contract | L9 pattern (no sub-modules) | unchanged |
| **cp_worker_bridge (NEW M9)** | CP worker-side read/subscribe library | ADDED |

## 7. Resolution status

| Gemini finding | MOD-3 resolution |
|---|---|
| R2-F1 CRITICAL (missing gate_contract) | **RESOLVED** — M8 added in §2 + full contract in `gate_contract_module_spec.md` |
| R2-F2 HIGH (kernel vs gov split-brain) | **RESOLVED** — rollout gating moved to M4 in §4; M1 amendment in §3 |
| R2-F3 HIGH (hidden cp_worker_bridge dep) | **RESOLVED** — M9 promoted to mandatory in §2 + full contract in `cp_worker_bridge_promotion_spec.md` |
| R2-F4 MEDIUM (M6 rollback wishful) | **RESOLVED** — persistent snapshot added in §5.2 |
| R2-F5 LOW (M6 missing L9 disclaimer) | **RESOLVED** — disclaimer added in §5.1 |

## 8. Forward compatibility with execution gate

The 9-module mandatory set is a superset of the 7-module set. Gate-B enforcement (per `amended_modularization_execution_gate.md`) applies to all 9 uniformly. No breaking change to gate logic beyond counting check.

## 9. Label per 0-4 rule 10

- §2 9-module set: **PROBABLE** (design; VERIFIED when Phase 7 implementation lands)
- §3/§4 responsibility moves: **VERIFIED** (in response to Gemini round-2 findings)
- §5 M6 amendments: **PROBABLE** (snapshot path is design commitment; empirical timing pending Phase 7)
- §7 resolution status: **PROBABLE** pending Gemini round-3
