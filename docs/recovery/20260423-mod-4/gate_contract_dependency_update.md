# gate_contract (M8) Dependency Update — MOD-4 Phase 1

**Order**: `/home/j13/claude-inbox/0-5` Phase 1 deliverable
**Produced**: 2026-04-23T09:38Z
**Supersedes**: `gate_contract_module_spec.md §2` (MOD-3) inputs + failure_surface + execution_environment sections
**Resolves**: Gemini R3b-F1 CRITICAL via FOLD (see `gate_calcifer_bridge_resolution.md`)

---

## 1. Complete amended M8 contract (drop-in replacement for Phase 7 YAML)

```yaml
module:
  module_name: gate_contract
  purpose: "Execution engine for every L6 gate; consumes MetricsContract from eval_contract + ThresholdLookup from gate_registry + Calcifer block state from filesystem; produces GateOutcomeContract for kernel_dispatcher."
  responsibilities:
    - evaluate admission gate (3 checks: min_trades / pos_count / improvement OR economic-viability)
    - evaluate A2 OOS holdout gate (CD-14: hard-fail on missing holdout)
    - evaluate A3 train-slice gate (legacy V9 path)
    - evaluate A4 multi-metric promotion gate
    - evaluate final promotion gate (PROMOTE_WILSON_LB + PROMOTE_MIN_TRADES + Calcifer block check)
    - emit GateOutcomeContract for each gate decision including decisive-reason code
  inputs:
    - contract_name: MetricsContract
      source_module: eval_contract
      cardinality: one_per_evaluation
      frequency: event
    - contract_name: ThresholdLookup
      source_module: gate_registry
      cardinality: n_per_request
      frequency: on_demand (cached 60s)
    - contract_name: CalciferBlockFile
      source_module: filesystem (direct read of /tmp/calcifer_deploy_block.json)
      cardinality: on_demand_per_promote_decision
      frequency: event (read on every promote gate evaluation; bounded to ≤ 1/s given arena cadence)
  outputs:
    - contract_name: GateOutcomeContract
      consumer_modules: [engine_kernel (via kernel_dispatcher), obs_metrics, gov_audit_stream]
      cardinality: one_per_input_metrics_event
      guarantees:
        delivery: exactly_once
        ordering: total_per_champion_per_gate
        idempotency: true (keyed by champion_id + gate_id + metrics_hash)
      rate_limit:   # MOD-4 addition
        max_events_per_second: 100
        max_events_per_minute: 5000
        burst_size: 500
        backpressure_policy: drop_newest (with audit)
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
      - gate.promote.calcifer_stale_max_seconds  # MOD-4 addition
      - gate.enforcement.strictness_mode
  state_schema:
    - name: gate_decision_cache
      type: keyed_cache
      storage: in_memory
      ownership: EXCLUSIVE
      lifecycle: session
    - name: gate_decision_audit
      type: row
      storage: postgres.pipeline_audit_log
      ownership: SHARED[kernel_dispatcher, gate_contract]
      lifecycle: persistent
    - name: calcifer_flag_cache  # MOD-4 addition
      type: json
      storage: in_memory (single record; refreshed per promote-gate read)
      ownership: EXCLUSIVE
      lifecycle: request
  metrics:
    # unchanged from MOD-3 + 2 new (calcifer-specific)
    - {name: gate_contract_up, type: gauge, unit: bool, labels: [version], cardinality_cap: 10, sample_sla: 1s}
    - {name: gate_contract_decisions_total, type: counter, unit: events, labels: [gate_id, outcome, decisive_reason], cardinality_cap: 300, sample_sla: event}
    - {name: gate_contract_decision_duration_seconds, type: histogram, unit: seconds, labels: [gate_id], cardinality_cap: 30, sample_sla: event}
    - {name: gate_contract_threshold_miss_rate, type: gauge, unit: ratio, labels: [gate_id], cardinality_cap: 20, sample_sla: 5min}
    - {name: gate_contract_calcifer_block_active_total, type: counter, unit: events, labels: [], cardinality_cap: 1, sample_sla: event}
    - {name: gate_contract_calcifer_flag_stale_total, type: counter, unit: events, labels: [reason], cardinality_cap: 5, sample_sla: event}  # MOD-4 addition
    - {name: gate_contract_calcifer_read_duration_seconds, type: histogram, unit: seconds, labels: [], cardinality_cap: 1, sample_sla: event}  # MOD-4 addition
  failure_surface:
    - {name: upstream_missing_metrics, detection: MetricsContract schema violation, recovery: reject_input + audit}
    - {name: threshold_lookup_unavailable, detection: gate_registry stale or down > config.max_stale_s, recovery: fail_closed (deny all promotions) + RED Telegram}
    - {name: holdout_hard_fail, detection: A2 gate receives MetricsContract without holdout slice attribution, recovery: reject_champion + RED Telegram}
    - {name: calcifer_red_active, detection: /tmp/calcifer_deploy_block.json.status == RED (read on promote gate), recovery: block_promote_gate_only (other gates still run for evidence collection)}
    - {name: calcifer_flag_missing_or_stale, detection: "os.stat() mtime > config.gate.promote.calcifer_stale_max_seconds (default 600) OR file missing OR json parse fail", recovery: fail_closed (treat as RED; deny promotion; log + audit row; emit alert)}  # MOD-4 addition per FOLD
    - {name: decision_timeout, detection: gate decision > 10s, recovery: timeout_as_deny + audit + alert}
    - {name: resource_exhaustion, detection: gate_decision_cache > config.max_cache_mb, recovery: evict_oldest + degrade}
    - {name: non_deterministic_output, detection: same (champion_id, gate_id, metrics_hash) produces different outcomes across workers, recovery: freeze_gate + RED Telegram}
  rollback_surface:
    # unchanged from MOD-3
    code_rollback: git-revert to prior gate_contract SHA
    state_rollback: "pipeline_audit_log entries are append-only; no retroactive change. In-memory cache discarded on restart."
    downstream_effect: "kernel_dispatcher sees gate decisions from reverted version; in-flight decisions complete with new version; no re-evaluation of historical champions"
    rollback_time_estimate_p50: 30 seconds
    rollback_time_estimate_p95: 90 seconds
    rollback_rehearsal: (scheduled pre-Phase-7 per execution_gate §B.2)
  test_boundary:
    unit: zangetsu/tests/l6/gate_contract/test_unit.py
    contract: zangetsu/tests/l6/gate_contract/test_contract.py + golden_fixtures/{admission,a2,a3,a4,promote,calcifer}/*.json  # MOD-4: added calcifer/ fixtures
    coverage_target_pct: 90
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: restart_after_swap
    downstream_impact: "kernel queues gate-awaiting champions during swap"
    shadow_required: true
  blackbox_allowed: false
  blackbox_rationale: "Gate decisions must be fully auditable per Charter §3.3 'every rejection layer has explicit meaning'. Folding gate_calcifer_bridge does not introduce opacity — Calcifer state is a JSON file read with declared filesystem_read_paths."
  console_controls:
    - {surface_key: "gate.enforcement.strictness_mode", class: parameter, decision_rights_ref: "control_plane_blueprint.md#validation-controls", audit_tier: high}
    - {surface_key: "gate.a2.holdout_hard_fail", class: parameter, decision_rights_ref: same, audit_tier: high}
    - {surface_key: "gate.promote.*", class: parameter, decision_rights_ref: "control_plane_blueprint.md#gate-thresholds", audit_tier: high_for_major}
    - {surface_key: "gate.promote.calcifer_stale_max_seconds", class: parameter, decision_rights_ref: same, audit_tier: high}  # MOD-4 addition
    - {surface_key: system.kill.gate_contract, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
    - {surface_key: system.mode.gate_shadow, class: mode_change, decision_rights_ref: "control_plane_blueprint.md#system-mode", audit_tier: high}
  # Field 15 (MOD-4 amended with filesystem_read_paths sub-field)
  execution_environment:
    permitted_egress_hosts: []  # pure local compute
    subprocess_spawn_allowed: false
    subprocess_permitted_binaries: []
    filesystem_read_paths:       # MOD-4 addition for FOLD
      - "/tmp/calcifer_deploy_block.json"
    filesystem_write_paths: []
    max_rss_mb: 512
    max_cpu_pct_sustained: 40
    requires_root: false
    requires_docker_group: false
    requires_sudo: false
```

## 2. Delta summary vs MOD-3 M8 contract

| Section | MOD-3 | MOD-4 | Reason |
|---|---|---|---|
| inputs[2] | CalciferBlockState from gate_calcifer_bridge | CalciferBlockFile from filesystem | FOLD |
| outputs rate_limit | absent | present (100/s) | MOD-3 template addition, now applied |
| config_schema cp_params | 9 keys | 10 keys (added gate.promote.calcifer_stale_max_seconds) | FOLD requires staleness threshold |
| state_schema | 2 states | 3 states (calcifer_flag_cache added) | FOLD internal state |
| metrics | 5 | 7 (calcifer_flag_stale + calcifer_read_duration added) | FOLD observability |
| failure_surface | 7 modes | 8 modes (calcifer_flag_missing_or_stale added) | FOLD error path |
| test_boundary | 5 fixture dirs | 6 fixture dirs (calcifer added) | FOLD test coverage |
| execution_environment | no filesystem_read_paths field | filesystem_read_paths: [calcifer_flag] | FOLD declaration |
| console_controls | 5 entries | 6 entries (calcifer_stale_max_seconds added) | FOLD governance surface |

Total: 9 sections amended. No removal of existing MOD-3 behavior.

## 3. Verification M8 is now self-contained

Post-FOLD, M8 has no dependency on gate_calcifer_bridge because gate_calcifer_bridge no longer exists as a separate module. All Calcifer-related logic is:
- Input: direct filesystem read (declared)
- Processing: inside M8
- Output: part of GateOutcomeContract (same as other gate outcomes)
- State: M8 internal
- Metrics: M8-prefixed
- Failure: M8 failure_surface entry

No external seam remains.

## 4. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 1. No silent mutation | ✅ — every delta explicit |
| 3. No live gate change | ✅ — Calcifer RED logic preserved (behavior identical; implementation location changed) |
| 9. No black-box control surface | ✅ — filesystem_read_paths declared |

## 5. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — FOLD inputs declared; mtime-staleness bounded |
| Silent failure | PASS — calcifer_flag_missing_or_stale fails closed with audit |
| External dep | PASS — single filesystem path declared |
| Concurrency | PASS — read is on-demand per promote-gate; no race with Calcifer writer (os.replace atomic) |
| Scope creep | PASS — delta is minimal FOLD; no new responsibilities |

## 6. Label per 0-5 rule 10

- §1 full amended contract: **PROBABLE** (design-time; VERIFIED when Phase 7 YAML validates)
- §2 delta summary: **VERIFIED** (each change traced to FOLD rationale)
- §3 self-containment: **VERIFIED** (no external module edge)
