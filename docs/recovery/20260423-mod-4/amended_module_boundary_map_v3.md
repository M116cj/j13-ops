# Amended Module Boundary Map v3 — MOD-4

**Order**: `/home/j13/claude-inbox/0-5` Phase 4 deliverable
**Produced**: 2026-04-23T10:25Z
**Supersedes**: `amended_module_boundary_map.md` (MOD-3 v1) via MOD-4 delta
**Scope**: Apply MOD-4 Phase 1+2+3 remediations to create v3 authoritative boundary map.

---

## 1. MOD-4 delta summary

| Module/concept | MOD-3 v1 | MOD-4 v3 |
|---|---|---|
| Mandatory set count | 9 | **9** (unchanged; gate_calcifer_bridge FOLDED into M8, not promoted) |
| M8 inputs | 3 edges (incl. external gate_calcifer_bridge) | 3 edges (CalciferBlockFile from filesystem, not external bridge) |
| M8 Field 15 | no filesystem_read_paths | **filesystem_read_paths: [/tmp/calcifer_deploy_block.json]** |
| M8 failure_surface | 7 modes | 8 modes (+ calcifer_flag_missing_or_stale) |
| M8 metrics | 5 | 7 (+ calcifer_flag_stale_total, calcifer_read_duration_seconds) |
| M9 rate_limit | single-channel (500/s) | **three-channel** (cache_lookup 10k/s / rest_fetch 10/s / subscribe_event 100/s) |
| M9 metrics | 5 | 11 (per-channel breakdown) |
| M9 failure_surface | 7 modes | 10 modes (+ rate_limit_rest_fetch_breach, rate_limit_subscribe_burst, thundering_herd_detected) |
| M1 engine_kernel responsibilities | "enforces rollout gating" removed (MOD-3) + "consumes PolicyVerdict" added | unchanged |
| M4 gov_contract_engine | split into core + gov_rollout_authority sub-module (MOD-3) | unchanged |
| M6 rollback | p50=90s p95=3min worst=30min (single mode) | **three modes (full / lean / cold)** with degraded_quality flag |
| gate_calcifer_bridge status | sub-module with external edge | **FOLDED INTO M8 (ceases to exist as separate)** |

## 2. Authoritative 9-module set (v3)

| # | Module | Layer | Brief |
|---|---|---|---|
| 1 | engine_kernel | L2 | arena state machine; dispatches work; consumes PolicyVerdict from gov |
| 2 | gate_registry | L6 data-plane | threshold store + version history; outputs ThresholdLookup |
| 3 | obs_metrics | L8.O | Prometheus-compatible metrics export |
| 4 | gov_contract_engine | L8.G | charter + blocklist evaluation; emits PolicyVerdict (rollout authority via gov_rollout_authority sub-module) |
| 5 | search_contract | L4 | pluggable SearchEngine interface |
| 6 | eval_contract | L5 | Evaluator interface + CD-14 slice + three-mode rollback |
| 7 | adapter_contract | L9 pattern | black-box wrapper contract |
| 8 | **gate_contract** | **L6 execution-plane** | **executes gates (admission/A2/A3/A4/promote, ABSORBS Calcifer state check via FOLD)** |
| 9 | cp_worker_bridge | L1 worker-side | universal CP data-plane library; three-channel rate-limit |

## 3. Per-module authoritative references

| Module | Full contract reference |
|---|---|
| M1 engine_kernel | `amended_module_boundary_map.md` (MOD-3) §3 — unchanged |
| M2 gate_registry | `amended_module_boundary_map.md` (MOD-3) §MOD-1.B Module 2 — unchanged |
| M3 obs_metrics | MOD-1 `module_boundary_map.md §MOD-1.B Module 3` — unchanged |
| M4 gov_contract_engine | MOD-3 `gov_contract_engine_boundary_update.md` — unchanged |
| M5 search_contract | MOD-1 `module_boundary_map.md §MOD-1.B Module 5` — unchanged |
| M6 eval_contract | MOD-1 + MOD-3 boundary map §5 + **MOD-4 `rollback_worst_case_note.md` three-mode rollback** |
| M7 adapter_contract | MOD-1 `module_boundary_map.md §MOD-1.B Module 7` — unchanged |
| M8 gate_contract | **MOD-4 `gate_contract_dependency_update.md` (full v3 contract)** |
| M9 cp_worker_bridge | **MOD-4 `amended_cp_worker_bridge_contract.md` (full v3 contract)** |

## 4. Cross-module contracts registry (updated post-MOD-4)

| Contract name | Producer | Consumer(s) |
|---|---|---|
| CandidateContract | M5 search_contract | M8 gate_contract (admission), M1 engine_kernel |
| MetricsContract | M6 eval_contract | M8 gate_contract, M3 obs_metrics |
| ThresholdLookup | M2 gate_registry | M8 gate_contract |
| GateOutcomeContract | M8 gate_contract | M1 engine_kernel, M3 obs_metrics, M4 gov_audit_stream |
| PolicyVerdict | M4 gov_rollout_authority sub | M1 engine_kernel |
| ChampionStateContract | M1 engine_kernel | publishers (pub_db, obs_view) |
| ParameterValue | M9 cp_worker_bridge | ALL modules |
| AuditContract | producers | M4 cp_audit |
| AdapterVerdict | M7 adapter_contract | M4 cp_api, gov_contract_engine |
| AlertContract | M3/alerts | pub_alert, pub_telegram, pub_akasha |
| **CalciferBlockFile** (NEW MOD-4) | **filesystem** (Calcifer daemon external write) | **M8 gate_contract** |

Total: 11 cross-module / cross-boundary contracts (added CalciferBlockFile per FOLD).

## 5. Forbidden boundary crossings (unchanged from MOD-3 + 1 MOD-4 addition)

1-7: unchanged from MOD-3 `amended_module_boundary_map.md`
8. **NEW MOD-4**: No module may read `/tmp/calcifer_deploy_block.json` except M8 (the FOLDed owner). gov_reconciler may read for integrity-monitoring but emits its own dedicated metrics (`gov_reconciler_calcifer_flag_age_seconds`).

## 6. L3 / L7 / L8-O (non-mandatory layers) — unchanged

`data_provider` (L3), publishers (L7), obs_logs + obs_freshness + obs_reports + obs_view (L8.O sub-modules) not mandatory per 0-5 / MOD-3 / MOD-4. They remain as designed in MOD-1 `modular_target_architecture.md §3`.

## 7. Resolution status recap

| Round-3 finding | Resolution |
|---|---|
| R3b-F1 CRITICAL | FOLD M8 ← v3 reflects |
| R3a-F8 HIGH | LIVE branch protection ← v3 exec_gate reflects |
| R3b-F2 HIGH | 3-channel rate_limit ← v3 M9 reflects |
| R3a-F6 MEDIUM | PARTIAL (spec-level) ← template v3 reflects |
| R3a-F7 MEDIUM | AST check ← template v3 reflects |
| R3a-F9 MEDIUM | path broadening ← exec_gate v3 reflects |
| R3b-F3 MEDIUM | 3-mode rollback ← v3 M6 reflects |
| R3b-F4 LOW INCONCLUSIVE | DISPROVEN via transitive rule ← template v3 reflects |

## 8. Label per 0-5 rule 10

- §1 delta summary: **VERIFIED** (each row cites MOD-4 file)
- §2 9-module set: **VERIFIED** (count unchanged)
- §4 contracts registry: **VERIFIED** (CalciferBlockFile added)
- §7 resolution recap: **VERIFIED** (maps to MOD-4 Phase 1-3 docs)
