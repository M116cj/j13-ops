# Module 8 — gate_contract (L6 execution) — Full 14-Field Contract

**Order**: `/home/j13/claude-inbox/0-4` Phase 1 deliverable
**Produced**: 2026-04-23T07:10Z
**Purpose**: Resolve Gemini round-2 CRITICAL finding R2-F1 — missing gate_contract execution engine from the 7-mandatory-module set. This spec adds Module 8 with a complete 14-field contract per `module_contract_template.md`.

---

## 1. Why this module is mandatory (context)

Per Gemini round-2 R2-F1 (CRITICAL):

> Module 1 (Kernel) lists `GateOutcomeContract` as an input from `gate_*`, but no module in the mandatory set is responsible for calculating those outcomes. `gate_registry` (M2) is a *threshold store*, not an execution engine.

Without `gate_contract`:
- engine_kernel cannot receive gate decisions (no producer)
- gate_registry lookups have no consumer
- the system cannot promote candidates through A1 → A2 → A3 → A4 → Deployable

This is an architectural hole. Module 8 fills it.

## 2. Full 14-field contract (per `module_contract_template.md §2`)

```yaml
module:
  module_name: gate_contract
  purpose: "Execution engine for every L6 gate; consumes MetricsContract from eval_contract + ThresholdLookup from gate_registry; produces GateOutcomeContract for kernel_dispatcher."
  responsibilities:
    - evaluate admission gate (3 checks: min_trades / pos_count / improvement OR economic-viability)
    - evaluate A2 OOS holdout gate (CD-14: hard-fail on missing holdout)
    - evaluate A3 train-slice gate (legacy V9 path)
    - evaluate A4 multi-metric promotion gate
    - evaluate final promotion gate (PROMOTE_WILSON_LB + PROMOTE_MIN_TRADES)
    - emit GateOutcomeContract for each gate decision including decisive-reason code
  inputs:
    - contract_name: MetricsContract
      source_module: eval_contract
      cardinality: one_per_evaluation
      frequency: event
    - contract_name: ThresholdLookup
      source_module: gate_registry
      cardinality: n_per_request (one lookup per threshold key)
      frequency: on_demand (cached 60s)
    - contract_name: CalciferBlockState
      source_module: gate_calcifer_bridge (external sibling consumer of /tmp/calcifer_deploy_block.json)
      cardinality: stream
      frequency: polling_60_seconds
  outputs:
    - contract_name: GateOutcomeContract
      consumer_modules: [engine_kernel (via kernel_dispatcher), obs_metrics, gov_audit_stream]
      cardinality: one_per_input_metrics_event
      guarantees:
        delivery: exactly_once
        ordering: total_per_champion_per_gate
        idempotency: true (keyed by champion_id + gate_id + metrics_hash)
  config_schema:
    ref: zangetsu/module_contracts/gate_contract.yaml
    cp_params:
      - gate.admission.min_trades_required
      - gate.admission.pos_count_required
      - gate.admission.improvement_required
      - gate.a2.holdout_hard_fail
      - gate.a3.train_slice_policy
      - gate.a4.multi_metric_weights
      - gate.promote.wilson_lb
      - gate.promote.min_trades
      - gate.enforcement.strictness_mode (strict / permissive / shadow)
  state_schema:
    - name: gate_decision_cache
      type: keyed_cache
      storage: in_memory (ephemeral; rebuilt on restart)
      ownership: EXCLUSIVE
      lifecycle: session
    - name: gate_decision_audit
      type: row
      storage: postgres.pipeline_audit_log
      ownership: SHARED[kernel_dispatcher, gate_contract] — appended by gate, read by kernel + gov_audit
      lifecycle: persistent
  metrics:
    - {name: gate_contract_up, type: gauge, unit: bool, labels: [version], cardinality_cap: 10, sample_sla: 1s}
    - {name: gate_contract_decisions_total, type: counter, unit: events, labels: [gate_id, outcome, decisive_reason], cardinality_cap: 300, sample_sla: event}
    - {name: gate_contract_decision_duration_seconds, type: histogram, unit: seconds, labels: [gate_id], cardinality_cap: 30, sample_sla: event}
    - {name: gate_contract_threshold_miss_rate, type: gauge, unit: ratio, labels: [gate_id], cardinality_cap: 20, sample_sla: 5min}
    - {name: gate_contract_calcifer_block_active_total, type: counter, unit: events, labels: [], cardinality_cap: 1, sample_sla: event}
  failure_surface:
    - {name: upstream_missing_metrics, detection: MetricsContract schema violation, recovery: reject_input + audit}
    - {name: threshold_lookup_unavailable, detection: gate_registry stale or down > config.max_stale_s, recovery: fail_closed (deny all promotions) + RED Telegram}
    - {name: holdout_hard_fail (CD-14), detection: A2 gate receives MetricsContract without holdout slice attribution, recovery: reject_champion + RED Telegram (preserves post-R2 invariant)}
    - {name: calcifer_red_active, detection: /tmp/calcifer_deploy_block.json.status == RED, recovery: block_promote_gate_only (other gates still run for evidence collection)}
    - {name: decision_timeout, detection: gate decision > 10s, recovery: timeout_as_deny + audit + alert}
    - {name: resource_exhaustion, detection: gate_decision_cache > config.max_cache_mb, recovery: evict_oldest + degrade}
    - {name: non_deterministic_output, detection: same (champion_id, gate_id, metrics_hash) produces different outcomes across workers, recovery: freeze_gate + RED Telegram (major structural bug)}
  rollback_surface:
    code_rollback: git-revert to prior gate_contract SHA
    state_rollback: "pipeline_audit_log entries are append-only; no retroactive change. In-memory cache discarded on restart."
    downstream_effect: "kernel_dispatcher sees gate decisions from reverted version; in-flight decisions complete with new version; no re-evaluation of historical champions (they remain in their decided-state)"
    rollback_time_estimate_p50: 30 seconds
    rollback_time_estimate_p95: 90 seconds
    rollback_rehearsal: (scheduled pre-Phase-7 per execution_gate §B.2)
  test_boundary:
    unit: zangetsu/tests/l6/gate_contract/test_unit.py
    contract: zangetsu/tests/l6/gate_contract/test_contract.py + golden_fixtures/{admission,a2,a3,a4,promote}/*.json
    coverage_target_pct: 90 (HIGH — gate decisions are production-decisive)
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: restart_after_swap
    downstream_impact: "kernel queues gate-awaiting champions during swap; no decision loss"
    shadow_required: true
  blackbox_allowed: false
  blackbox_rationale: "Gate decisions must be fully auditable per Charter §3.3 'every rejection layer has explicit meaning'. Any opaque gate would violate white-box-control requirement."
  console_controls:
    - {surface_key: "gate.enforcement.strictness_mode", class: parameter, decision_rights_ref: "control_plane_blueprint.md#validation-controls", audit_tier: high}
    - {surface_key: "gate.a2.holdout_hard_fail", class: parameter, decision_rights_ref: same, audit_tier: high (downgrading breaks CD-14 R2 invariant)}
    - {surface_key: "gate.promote.*", class: parameter, decision_rights_ref: "control_plane_blueprint.md#gate-thresholds", audit_tier: high_for_major}
    - {surface_key: system.kill.gate_contract, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
    - {surface_key: system.mode.gate_shadow, class: mode_change, decision_rights_ref: "control_plane_blueprint.md#system-mode", audit_tier: high}
```

## 3. Relationship to other mandatory modules

| Module | Relationship |
|---|---|
| M1 engine_kernel | consumes gate_contract's GateOutcomeContract output (Module 1 responsibility updated — see `gov_contract_engine_boundary_update.md`) |
| M2 gate_registry | gate_contract is the sole consumer of ThresholdLookup; gate_registry is read-only data-plane, gate_contract is execution-plane |
| M3 obs_metrics | consumes `gate_contract_*` metrics; alerts on missing rates / timeout spikes |
| M4 gov_contract_engine | reads gate_contract_decisions_total for charter §17 compliance (honest rejection rate monitoring) |
| M5 search_contract | NOT a direct edge; gate decisions feed kernel which routes to/from search |
| M6 eval_contract | produces MetricsContract → gate_contract input edge |
| M7 adapter_contract | N/A (gate_contract is never black-box) |
| **M9 cp_worker_bridge** (post-MOD-3 promotion) | provides CP parameter reads; gate_contract subscribes to threshold + config keys |

## 4. Why not fold into gate_registry (rejection of a simpler design)

Considered and rejected: merging gate_contract into gate_registry as a single "gate layer" module.

Reason for rejection:
- data-plane (thresholds as values) and execution-plane (gate logic as functions over metrics) have VERY different failure surfaces (threshold miss vs. decision timeout vs. holdout violation)
- rollback semantics differ: threshold rollback = change a value; execution rollback = change decision logic (touches more code paths)
- test coverage targets differ: execution-plane needs golden fixtures + adversarial cases; data-plane just needs schema + version tests
- the split is explicit enough to justify two modules (kernel + state_registry split is analogous)

## 5. Field 15 execution_environment (per HIGH amendment — see `amended_module_contract_template.md`)

Per Gemini R1b-F1, new Field 15 mandatory. gate_contract's values:

```yaml
execution_environment:
  permitted_egress_hosts: []  # empty — pure local compute
  subprocess_spawn_allowed: false
  filesystem_write_paths: []  # writes only via kernel_dispatcher + cp_audit
  max_rss_mb: 512
  max_cpu_pct_sustained: 40
```

gate_contract is a pure function of (MetricsContract, ThresholdLookup, CalciferBlockState) → GateOutcomeContract. No network, no subprocess, no filesystem writes.

## 6. Acceptance checklist (per `module_contract_template.md §4`)

- [x] All 14 mandatory fields populated (no TBD) — VERIFIED in §2
- [x] Purpose passes one-sentence rule
- [x] Responsibilities: 6 entries (within 2–7 range)
- [x] Every input references a declared Contract
- [x] state_schema states ownership explicitly
- [x] 3 required metrics declared (up / decisions_total / duration_seconds)
- [x] failure_surface covers the 7 minimum categories + CD-14 + non_determinism
- [x] rollback_surface is executable
- [x] test_boundary locations declared
- [x] replacement_boundary.migration_mode is enum-valid
- [x] blackbox_allowed=false with rationale
- [x] console_controls has kill_switch entry
- [x] Field 15 execution_environment per §5
- [ ] Gemini round-3 adversarial review signed off — PENDING (Phase 4 of this order)
- [ ] ADR `docs/decisions/YYYYMMDD-module-gate_contract.md` — PENDING (MOD-3 commit)

## 7. Label per 0-4 rule 10

- §2 contract content: **PROBABLE** (design-time spec; VERIFIED upon Phase 7 landing with runtime metrics matching declared schema)
- §3 relationships: **PROBABLE** (consistent with MOD-1 boundary map + amendments)
- §6 acceptance: **PROBABLE** complete; **INCONCLUSIVE** pending Gemini round-3

## 8. Resolution status of Gemini round-2 R2-F1

**RESOLVED pending Gemini round-3 confirmation.**

Missing-module hole filled. Architecture complete (modulo round-3 validation).
