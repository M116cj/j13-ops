# Amended Mandatory Module Set v2 — MOD-4 Phase 1

**Order**: `/home/j13/claude-inbox/0-5` Phase 1 deliverable
**Produced**: 2026-04-23T09:35Z
**Supersedes**: `amended_module_boundary_map.md §2` (MOD-3 v1) via delta
**Version**: v2 (post-MOD-4 FOLD decision)

---

## 1. The 9-module mandatory set (UNCHANGED count from MOD-3)

MOD-4 preserves the 9-module count. gate_calcifer_bridge is FOLDED into M8, NOT promoted to M10.

| # | Module | Layer | MOD-4 status |
|---|---|---|---|
| 1 | engine_kernel | L2 | unchanged |
| 2 | gate_registry | L6 data-plane | unchanged |
| 3 | obs_metrics | L8.O | unchanged |
| 4 | gov_contract_engine | L8.G | unchanged (MOD-3 rollout-authority split stays) |
| 5 | search_contract | L4 | unchanged |
| 6 | eval_contract | L5 | unchanged (MOD-3 snapshot amendments stay) |
| 7 | adapter_contract | L9 pattern | unchanged |
| 8 | gate_contract | L6 execution | **absorbs gate_calcifer_bridge via FOLD (MOD-4 Phase 1)** |
| 9 | cp_worker_bridge | L1 worker-side | unchanged (MOD-3 M9 contract; rate_limit split coming in MOD-4 Phase 2B) |

No new mandatory modules. No removed modules. One module (M8) gets wider scope via FOLD.

## 2. What changed vs MOD-3

| Aspect | MOD-3 (v1) | MOD-4 (v2) |
|---|---|---|
| Mandatory count | 9 | 9 (no change) |
| M8 inputs | 3 edges incl. CalciferBlockState from gate_calcifer_bridge | 3 edges incl. CalciferBlockFile from filesystem (no external bridge) |
| M8 Field 15 filesystem_read_paths | absent | `["/tmp/calcifer_deploy_block.json"]` added |
| M8 failure_surface | 7 modes | 8 modes (calcifer_flag_missing_or_stale added) |
| gate_calcifer_bridge status | sub-module with implicit dependency | FOLDED INTO M8; no separate existence |

## 3. Mandatory path coherence check

0-5 §Phase 1 exit: "No mandatory-path dependency remains outside the mandatory-path definition."

Verification — for each mandatory module, every declared input source_module:

| Module | Inputs' source_modules | All in mandatory? |
|---|---|---|
| M1 engine_kernel | search_*, eval_*, gate_* (via kernel_dispatcher), cp_worker_bridge, gov_contract_engine | ✅ all M2-M9 |
| M2 gate_registry | cp_worker_bridge | ✅ M9 |
| M3 obs_metrics | every module (via kernel_logger) | ✅ all |
| M4 gov_contract_engine | gov_ci_hooks (sub-module), cp_api (sub-module of L1), obs_metrics, cp_api, engine_kernel | ✅ (sub-modules are inside L1 CP umbrella or M4 itself) |
| M5 search_contract | cp_worker_bridge, data_provider (L3 sub), obs_metrics | ✅ (data_provider is L3 sub-module of main architecture — see note below) |
| M6 eval_contract | kernel_dispatcher (inside M1), data_provider (L3), cp_worker_bridge | ✅ |
| M7 adapter_contract | L4/L5 modules with blackbox_allowed=true, obs_freshness | ✅ |
| M8 gate_contract | eval_contract (M6), gate_registry (M2), **filesystem** (MOD-4 FOLD) | ✅ (no external module dep; filesystem is declared in Field 15) |
| M9 cp_worker_bridge | cp_notifier (L1 sub) | ✅ (L1 umbrella) |

Cross-module deps: all resolved within the 9-module set OR within clearly-named sub-modules of L1/L3/L8 umbrellas.

## 4. Hidden-dependency scan

0-5 spirit: no mandatory-path component can have upstream deps outside the mandatory set. Per-module `inputs` field audit:

| Module | External deps flagged | Resolution |
|---|---|---|
| M1 | Postgres (DB) | acceptable — infrastructure dependency, not a module |
| M3 | Prometheus scrapers | external consumer, not module |
| M4 | AKASHA endpoint | external service; declared in Field 15 egress |
| M4 | Telegram api | external service; declared in Field 15 egress |
| M8 | /tmp/calcifer_deploy_block.json | declared in Field 15 filesystem_read_paths (MOD-4 FOLD) ✅ |
| M9 | cp_api | internal L1 sub-module; declared in Field 15 |

All external deps are DECLARED in Field 15 `execution_environment`. None are hidden. The pattern R2-F3 (hidden cp_worker_bridge) and R3b-F1 (hidden gate_calcifer_bridge) are both closed by:
- R2-F3: promote to M9
- R3b-F1: fold + Field 15 declaration

## 5. L3 data_provider status

Note from §3: `search_contract` (M5) + `eval_contract` (M6) both list `data_provider` as input source. Is this a hidden dependency like gate_calcifer_bridge was?

**Analysis**: data_provider is L3 Data Input layer — explicitly part of the 10-layer intended architecture (per MOD-1 `intended_architecture.md §2`). It's a SUB-MODULE of L3, not mandatory-path. Missing from mandatory doesn't create ambiguity because L3 is a declared peer layer.

**Decision**: data_provider does NOT need promotion. Different shape from R2-F3 / R3b-F1:
- R2-F3 / R3b-F1: dependency was cross-referenced by multiple mandatory modules but had NO layer home
- data_provider: has a home layer (L3) and is architecturally obvious

Gemini round-4 may challenge this; if so, MOD-5 resolution.

## 6. Relationship to amended_module_boundary_map_v3.md

MOD-4 Phase 4 will produce `amended_module_boundary_map_v3.md` — the FULL replacement with all MOD-4 amendments applied. This v2 file specifies the MOD-4 DELTA against MOD-3's v1. The v3 full file is the readable authoritative document.

## 7. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 1. No silent mutation | ✅ — delta explicit |
| 8. No broad refactor | ✅ — FOLD preserves 9-count |
| 10. Labels applied | ✅ |

## 8. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — every input edge resolved to mandatory OR sub-module OR declared external |
| Silent failure | PASS — hidden-dep scan §4 enumerates |
| External dep | PASS — AKASHA / Telegram / filesystem all declared in Field 15 |
| Concurrency | PASS — static spec |
| Scope creep | PASS — maintains 9-module discipline |

## 9. Label per 0-5 rule 10

- §1 module set: **VERIFIED** (9 modules, FOLD confirmed in `gate_calcifer_bridge_resolution.md`)
- §3 coherence check: **VERIFIED** (per-module edge audit)
- §4 hidden-dep scan: **VERIFIED** (all remaining deps declared)
- §5 data_provider decision: **PROBABLE** (Gemini round-4 may revisit)

## 10. Exit condition

Mandatory-path coherence verified. Phase 1 succeeds.
