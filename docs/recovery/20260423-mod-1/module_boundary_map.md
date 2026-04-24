# Module Boundary Map — Zangetsu MOD-1

**Order**: `/home/j13/claude-inbox/0-2` Phase 4 deliverable (first output)
**Produced**: 2026-04-23T03:18Z
**Author**: Claude (Lead)
**Base authoritative source**: `zangetsu/docs/ascension/phase-2/module_boundary_map.md` (Gemini round-2 ACCEPTED v2.1) — absorbs-file table and forbidden-crossings section preserved below as §2.
**Status**: MOD-1 Phase 4 exit criterion MET — explicit module map + 7 mandatory per-module 14-field contracts + reusable contract template (`module_contract_template.md`).

---

## §MOD-1.A — Envelope

The Ascension boundary map (§2 in the preserved content) is a FULL 46-module cross-reference mapping current scattered code to target modules, with forbidden crossings and sanity map. This MOD-1 wrapper ADDS what 0-2 Phase 4 required that the base did not include: **per-module 14-field contracts for the 7 mandatory modules**.

Mandatory target modules per 0-2 Phase 4:
1. Engine Kernel
2. Gate Layer
3. Observability Layer
4. Governance Layer
5. Research/Search Layer
6. Evaluation Layer
7. Black-Box Adapter Layer

Each is specified below using the `module_contract_template.md` 14-field schema.

---

## §MOD-1.B — Seven mandatory module contracts

Format for each module: the 14-field canonical contract. Sub-module decomposition (where applicable) references the Ascension §2 boundary table rather than duplicating it.

### Module 1 — Engine Kernel (L2)

```yaml
module:
  module_name: engine_kernel
  purpose: "Owns the Zangetsu arena state machine; dispatches work to L4/L5/L6; manages leases and reap; enforces rollout gating."
  responsibilities:
    - transition champion status (ARENA1_COMPLETE → _PROCESSING → ... → DEPLOYABLE/_LIVE)
    - acquire and release per-champion leases (FOR UPDATE SKIP LOCKED + lease_until)
    - reap expired leases on a 60s cadence
    - route events to evaluator / gate / publisher modules via kernel_dispatcher
    - emit structured transition events to L8.O (obs_logs)
  inputs:
    - contract_name: CandidateContract
      source_module: search_gp | search_lgbm | search_hand_seed | search_factor_zoo
      cardinality: one_per_candidate
      frequency: event
    - contract_name: MetricsContract
      source_module: eval_a2_holdout | eval_a3_train | eval_a4_gate | eval_a5_tournament
      cardinality: one_per_evaluation
      frequency: event
    - contract_name: GateOutcomeContract
      source_module: gate_admission | gate_a2 | gate_a3 | gate_a4 | gate_promote | gate_calcifer_bridge
      cardinality: one_per_evaluation
      frequency: event
    - contract_name: CP ParameterRead
      source_module: cp_worker_bridge
      cardinality: on_demand
      frequency: polling_60_seconds
  outputs:
    - contract_name: ChampionStateContract
      consumer_modules: [pub_db, obs_metrics, obs_view, gov_audit_stream]
      cardinality: one_per_transition
      guarantees:
        delivery: exactly_once
        ordering: total_per_champion
        idempotency: true
    - contract_name: AuditContract
      consumer_modules: [cp_audit]
      cardinality: one_per_transition
      guarantees:
        delivery: at_least_once
        ordering: total
        idempotency: true
  config_schema:
    ref: zangetsu/module_contracts/engine_kernel.yaml
    cp_params:
      - kernel.lease.ttl_seconds
      - kernel.reap.interval_seconds
      - kernel.dispatch.max_inflight
      - kernel.retry.policy
  state_schema:
    - name: champion_state_row
      type: row reference
      storage: postgres.champion_pipeline_fresh
      ownership: EXCLUSIVE
      lifecycle: persistent
    - name: lease_table
      type: row
      storage: postgres.champion_pipeline_fresh (lease_until + worker_id columns)
      ownership: EXCLUSIVE
      lifecycle: persistent
  metrics:
    - {name: engine_kernel_up, type: gauge, unit: bool, labels: [version], cardinality_cap: 10, sample_sla: 1s}
    - {name: engine_kernel_transitions_total, type: counter, unit: events, labels: [from_status, to_status, outcome], cardinality_cap: 400, sample_sla: event}
    - {name: engine_kernel_transition_duration_seconds, type: histogram, unit: seconds, labels: [transition], cardinality_cap: 50, sample_sla: event}
    - {name: engine_kernel_lease_contention_total, type: counter, unit: events, labels: [], cardinality_cap: 1, sample_sla: event}
    - {name: engine_kernel_reap_expired_total, type: counter, unit: events, labels: [reason], cardinality_cap: 10, sample_sla: event}
  failure_surface:
    - {name: postgres_disconnect, detection: exception on claim_champion/release_champion, recovery: halt_kernel_with_alert, observable_via: engine_kernel_up, alert_rule: "up == 0 for 60s → RED"}
    - {name: lease_timeout_cascade, detection: lease_contention_total rate > threshold, recovery: degrade_to_serial, observable_via: engine_kernel_lease_contention_total}
    - {name: dispatch_deadlock, detection: inflight count > max_inflight for 5min, recovery: kill_oldest_lease_and_alert}
    - {name: invalid_transition, detection: state machine rejects target state, recovery: fail_closed_row + log + alert}
    - {name: audit_pipeline_down, detection: cp_audit write fails, recovery: fail_closed (block further transitions), observable_via: engine_kernel_transitions_total{outcome=blocked}}
    - {name: resource_exhaustion_memory, detection: process RSS > config.max_rss_mb, recovery: graceful_drain_and_restart}
    - {name: malformed_input, detection: contract validation throws, recovery: reject_with_reason_and_quarantine}
  rollback_surface:
    code_rollback: git-revert to parent SHA
    state_rollback: "in-flight transitions are durable (DB rows); no explicit rollback of completed transitions — rollback means halting + letting lease_reaper return rows to prior state"
    downstream_effect: "publishers receive no new events during halt; readers continue to read last-known state; VIEW is current"
    rollback_time_estimate_p50: 2 minutes
    rollback_time_estimate_p95: 5 minutes
    rollback_rehearsal: (must be scheduled pre-Phase-7 in `modularization_execution_gate.md §B.2`)
  test_boundary:
    unit: zangetsu/tests/l2/engine_kernel/test_unit.py
    contract: zangetsu/tests/l2/engine_kernel/test_contract.py
    coverage_target_pct: 85
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: restart_after_swap
    downstream_impact: "publishers + evaluators + gates pause during swap (estimated <30s); no DB-schema change"
    shadow_required: true
  blackbox_allowed: false
  blackbox_rationale: "Kernel is the state machine authority; must be fully auditable. Any opaque component would violate charter §3.6."
  console_controls:
    - {surface_key: kernel.lease.ttl_seconds, class: parameter, decision_rights_ref: "control_plane_blueprint.md#system-controls", audit_tier: standard}
    - {surface_key: kernel.reap.interval_seconds, class: parameter, decision_rights_ref: same, audit_tier: standard}
    - {surface_key: system.kill.engine_kernel, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
    - {surface_key: kernel.mode, class: mode_change, decision_rights_ref: "control_plane_blueprint.md#system-mode", audit_tier: high}
```

### Module 2 — Gate Layer (L6, umbrella)

L6 is a cluster of peer modules (`gate_admission`, `gate_a2`, `gate_a3`, `gate_a4`, `gate_promote`, `gate_calcifer_bridge`). Each follows `module_contract_template.md`. The umbrella `gate_registry` owns the threshold registry; each gate module provides logic.

```yaml
module:
  module_name: gate_registry
  purpose: "Single source of truth for every gate threshold consumed across L4/L5/L6; enforces version history, per-mode overrides, rollout-gated changes."
  responsibilities:
    - serve threshold lookups for every Gate
    - version every threshold mutation (rows in control_plane.parameters with audit)
    - enforce decision-rights matrix on threshold writes (major vs low-impact per CP §5)
    - emit deprecation warnings when thresholds outlive their consumer module version
  inputs:
    - contract_name: CP ParameterRead
      source_module: cp_worker_bridge
      cardinality: on_demand
      frequency: polling_60_seconds
  outputs:
    - contract_name: ThresholdLookup
      consumer_modules: [gate_admission, gate_a2, gate_a3, gate_a4, gate_promote, search_gp, eval_*]
      cardinality: n_per_request
      guarantees:
        delivery: exactly_once
        ordering: none
        idempotency: true
  config_schema:
    ref: zangetsu/module_contracts/gate_registry.yaml
    cp_params:
      - gate.threshold.alpha_entry
      - gate.threshold.alpha_exit
      - gate.threshold.a2.*
      - gate.threshold.a3.*
      - gate.threshold.a4.*
      - gate.promote.wilson_lb
      - gate.promote.min_trades
  state_schema:
    - name: threshold_registry
      type: table
      storage: postgres.control_plane.parameters (WHERE key LIKE 'gate.%')
      ownership: EXCLUSIVE
      lifecycle: persistent
  metrics:
    - {name: gate_registry_up, type: gauge, unit: bool, labels: [], cardinality_cap: 1, sample_sla: 1s}
    - {name: gate_registry_lookups_total, type: counter, unit: events, labels: [key], cardinality_cap: 50, sample_sla: event}
    - {name: gate_registry_stale_read_total, type: counter, unit: events, labels: [reason], cardinality_cap: 10, sample_sla: event}
  failure_surface:
    - {name: cp_unreachable, detection: cp_worker_bridge returns stale-flag, recovery: use_last_known_good_with_warning, observable_via: gate_registry_stale_read_total}
    - {name: threshold_out_of_valid_range, detection: value violates valid_range at read time, recovery: fail_closed + RED Telegram}
    - {name: version_drift, detection: consumer module's cached version < registry version for > 5min, recovery: emit_deprecation_warning}
    - {name: resource_exhaustion, detection: registry read latency p95 > 500ms, recovery: degrade_to_cache_only}
    - {name: malformed_input, detection: write attempt with invalid schema, recovery: reject + audit}
    - {name: upstream_unavailable, detection: postgres down, recovery: fail_closed on writes}
  rollback_surface:
    code_rollback: git-revert
    state_rollback: "threshold_registry rows have audit trail; use `zctl gate-registry revert <key> <to_version>` to re-activate prior value with new audit row"
    downstream_effect: "consumers see new value on next polling cycle (≤60s); in-flight evaluations complete with old value"
    rollback_time_estimate_p50: 30 seconds
    rollback_time_estimate_p95: 90 seconds
    rollback_rehearsal: (scheduled pre-Phase-7)
  test_boundary:
    unit: zangetsu/tests/l6/gate_registry/test_unit.py
    contract: zangetsu/tests/l6/gate_registry/test_contract.py
    coverage_target_pct: 85
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: hot_swap
    downstream_impact: "consumers pull via cp_worker_bridge; swap is transparent"
    shadow_required: true
  blackbox_allowed: false
  console_controls:
    - {surface_key: "gate.threshold.*", class: parameter, decision_rights_ref: "control_plane_blueprint.md#gate-thresholds", audit_tier: high_for_major_low_for_minor}
    - {surface_key: system.kill.gate_registry, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
```

### Module 3 — Observability Layer (L8.O — sub-module cluster)

Peer modules: `obs_metrics`, `obs_logs`, `obs_view`, `obs_reports`, `obs_freshness`. Umbrella contract:

```yaml
module:
  module_name: obs_metrics
  purpose: "Export Prometheus-compatible metrics stream for every engine module; the canonical observability data plane."
  responsibilities:
    - expose /metrics endpoint (Prometheus scrape)
    - enforce metric cardinality caps declared in per-module contracts
    - provide histogram aggregations
    - emit structured alerts via pub_alert when metric exceeds alert_rule
  inputs:
    - contract_name: MetricEmission
      source_module: "every module (via kernel_logger / cp_worker_bridge bridge)"
      cardinality: stream
      frequency: event
  outputs:
    - contract_name: PrometheusScrape
      consumer_modules: [external grafana, obs_freshness, pub_alert]
      cardinality: stream
      guarantees:
        delivery: best_effort
        ordering: none
        idempotency: true
  config_schema:
    ref: zangetsu/module_contracts/obs_metrics.yaml
    cp_params:
      - obs.metrics.retention_days
      - obs.metrics.scrape_port
      - obs.metrics.cardinality_enforcement_mode
  state_schema:
    - name: in_memory_histograms
      type: map
      storage: in_memory
      ownership: EXCLUSIVE
      lifecycle: session
    - name: cardinality_audit
      type: row
      storage: postgres.control_plane.obs_cardinality
      ownership: EXCLUSIVE
      lifecycle: persistent
  metrics:
    - {name: obs_metrics_up, type: gauge, unit: bool, labels: [], cardinality_cap: 1, sample_sla: 1s}
    - {name: obs_metrics_scrape_total, type: counter, unit: events, labels: [scraper_id], cardinality_cap: 10, sample_sla: event}
    - {name: obs_metrics_cardinality_violation_total, type: counter, unit: events, labels: [module], cardinality_cap: 50, sample_sla: event}
  failure_surface:
    - {name: upstream_module_silent, detection: no emissions in > config.max_silence_seconds, recovery: emit_module_silent_alert}
    - {name: cardinality_explosion, detection: labels cardinality exceeds per-metric cap, recovery: drop_metric + alert}
    - {name: scrape_endpoint_unreachable, detection: readiness probe fails, recovery: restart_supervised}
    - {name: malformed_input, detection: emission violates contract, recovery: drop + increment violation counter}
    - {name: resource_exhaustion, detection: in-memory histograms > config.max_memory_mb, recovery: flush + reset}
    - {name: upstream_unavailable, detection: cp_worker_bridge unreachable for params, recovery: use_local_defaults}
    - {name: dependency_failure, detection: postgres down for cardinality audit, recovery: continue_without_audit}
  rollback_surface:
    code_rollback: git-revert
    state_rollback: "in-memory histograms are ephemeral; cardinality audit is append-only"
    downstream_effect: "grafana shows gap during restart"
    rollback_time_estimate_p50: 10 seconds
    rollback_time_estimate_p95: 30 seconds
    rollback_rehearsal: (scheduled)
  test_boundary:
    unit: zangetsu/tests/l8/obs_metrics/test_unit.py
    contract: zangetsu/tests/l8/obs_metrics/test_contract.py
    coverage_target_pct: 70
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: hot_swap
    downstream_impact: "none (scrape endpoint remains at same port)"
    shadow_required: false
  blackbox_allowed: false
  console_controls:
    - {surface_key: "obs.metrics.*", class: parameter, decision_rights_ref: "control_plane_blueprint.md#governance-controls", audit_tier: standard}
    - {surface_key: system.kill.obs_metrics, class: kill_switch, decision_rights_ref: same, audit_tier: high}
```

### Module 4 — Governance Layer (L8.G — sub-module cluster)

Peer modules: `gov_contract_engine`, `gov_reconciler`, `gov_audit_stream`, `gov_rollout`, `gov_ci_hooks`. Umbrella:

```yaml
module:
  module_name: gov_contract_engine
  purpose: "Apply charter §17 + mutation_blocklist.yaml rules at runtime; produce allow/deny verdicts on commits and config writes; act as the policy engine atop obs_metrics."
  responsibilities:
    - consume commit + PR + CP write events
    - evaluate each against charter §17 rules and mutation_blocklist entries
    - emit allow/deny + audit + rollback-handle
    - post RED Telegram alert on any high-severity rule violation
    - sync decisions to cp_audit
  inputs:
    - contract_name: CommitEvent
      source_module: gov_ci_hooks
      cardinality: one_per_commit
      frequency: event
    - contract_name: CPWriteIntent
      source_module: cp_api
      cardinality: one_per_write
      frequency: event
    - contract_name: ObservabilitySignal
      source_module: obs_metrics
      cardinality: stream
      frequency: event
  outputs:
    - contract_name: PolicyVerdict
      consumer_modules: [cp_api, gov_ci_hooks, pub_alert]
      cardinality: one_per_input
      guarantees:
        delivery: exactly_once
        ordering: total
        idempotency: true
    - contract_name: AuditContract
      consumer_modules: [cp_audit]
      cardinality: one_per_verdict
      guarantees:
        delivery: at_least_once
        ordering: total
        idempotency: true
  config_schema:
    ref: zangetsu/module_contracts/gov_contract_engine.yaml
    cp_params:
      - gov.charter.rules_active
      - gov.mutation_blocklist.version
      - gov.reconciler.interval_s
      - gov.alerts.red_channel
  state_schema:
    - name: active_rules
      type: table
      storage: postgres.control_plane.gov_rules
      ownership: EXCLUSIVE
      lifecycle: persistent
    - name: pending_verdicts
      type: queue
      storage: redis
      ownership: EXCLUSIVE
      lifecycle: session
  metrics:
    - {name: gov_contract_engine_up, type: gauge, unit: bool, labels: [], cardinality_cap: 1, sample_sla: 1s}
    - {name: gov_contract_engine_verdicts_total, type: counter, unit: events, labels: [outcome, rule_id], cardinality_cap: 100, sample_sla: event}
    - {name: gov_contract_engine_verdict_duration_seconds, type: histogram, unit: seconds, labels: [rule_id], cardinality_cap: 30, sample_sla: event}
  failure_surface:
    - {name: upstream_unavailable, detection: no input for > config.max_silence_s, recovery: alert_and_continue}
    - {name: rule_corrupt, detection: schema violation on active_rules load, recovery: fail_closed + RED Telegram}
    - {name: cp_audit_down, detection: audit write timeout, recovery: fail_closed (refuse verdicts until audit restored)}
    - {name: malformed_input, detection: commit/CP write missing required fields, recovery: reject_input + audit}
    - {name: timeout, detection: verdict decision > 10s, recovery: timeout_as_deny + audit}
    - {name: resource_exhaustion, detection: pending verdicts queue > 1000, recovery: shed_lowest_priority + RED alert}
    - {name: dependency_failure, detection: postgres or redis down, recovery: fail_closed}
  rollback_surface:
    code_rollback: git-revert
    state_rollback: "active_rules table has audit trail; rollback = activate prior rule-set version"
    downstream_effect: "pending verdicts queue drains with old rules; new inputs queue until restart"
    rollback_time_estimate_p50: 30 seconds
    rollback_time_estimate_p95: 2 minutes
    rollback_rehearsal: (scheduled)
  test_boundary:
    unit: zangetsu/tests/l8g/gov_contract_engine/test_unit.py
    contract: zangetsu/tests/l8g/gov_contract_engine/test_contract.py
    coverage_target_pct: 85
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: restart_after_swap
    downstream_impact: "cp_api queues pending writes during swap"
    shadow_required: true
  blackbox_allowed: false
  console_controls:
    - {surface_key: gov.charter.rules_active, class: parameter, decision_rights_ref: "control_plane_blueprint.md#gov", audit_tier: high}
    - {surface_key: gov.mutation_blocklist.version, class: parameter, decision_rights_ref: same, audit_tier: high}
    - {surface_key: system.kill.gov_contract_engine, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
```

### Module 5 — Research / Search Layer (L4)

```yaml
module:
  module_name: search_contract
  purpose: "Abstract SearchEngine interface; every search implementation (GP/LGBM/factor-zoo/hand-seed) registers under this contract."
  responsibilities:
    - declare the CandidateContract schema producers must honor
    - route CP params to the currently-active search implementation
    - enforce peer-switching protocol (one active search per strategy-id at a time)
    - emit search-level metrics (candidates/sec, uniqueness, fitness distribution)
  inputs:
    - contract_name: CP ParameterRead
      source_module: cp_worker_bridge
      cardinality: on_demand
      frequency: polling_60_seconds
    - contract_name: DataProviderContract
      source_module: data_provider
      cardinality: one_per_cycle
      frequency: session-scoped
    - contract_name: GuidanceStream
      source_module: obs_metrics (a13 guidance producer)
      cardinality: stream
      frequency: every_5min
  outputs:
    - contract_name: CandidateContract
      consumer_modules: [gate_admission, kernel_dispatcher]
      cardinality: stream
      guarantees:
        delivery: at_least_once
        ordering: none
        idempotency: true (candidate alpha_hash is the dedup key)
  config_schema:
    ref: zangetsu/module_contracts/search_contract.yaml
    cp_params:
      - search.engine.active
      - search.gp.mutation_rate
      - search.gp.pop_size
      - search.gp.pset.active
      - search.target.horizon_bars
      - search.target.strategy_id
  state_schema:
    - name: active_engine_id
      type: string
      storage: postgres.control_plane.parameters (search.engine.active)
      ownership: EXCLUSIVE (cp_storage writes; search_contract reads)
      lifecycle: persistent
    - name: per_engine_population
      type: per_implementation
      storage: in_memory (rebuildable from candidate stream snapshot)
      ownership: EXCLUSIVE per implementation module
      lifecycle: session
  metrics:
    - {name: search_contract_up, type: gauge, unit: bool, labels: [engine_id], cardinality_cap: 10, sample_sla: 1s}
    - {name: search_candidates_total, type: counter, unit: events, labels: [engine_id, outcome], cardinality_cap: 50, sample_sla: event}
    - {name: search_uniqueness_ratio, type: gauge, unit: ratio, labels: [engine_id], cardinality_cap: 10, sample_sla: 5min}
  failure_surface:
    - {name: upstream_data_unavailable, detection: data_provider health fails, recovery: pause_search + alert}
    - {name: engine_module_dead, detection: implementation's _up metric == 0, recovery: fail_closed_engine + alert}
    - {name: candidate_duplicate_storm, detection: uniqueness_ratio < config.min_uniqueness for 10min, recovery: restart_engine}
    - {name: malformed_candidate, detection: schema validation throws, recovery: drop + increment violation counter}
    - {name: peer_switch_conflict, detection: two engines claim active for same strategy_id, recovery: fail_closed_both + RED alert}
    - {name: resource_exhaustion, detection: in-memory population > config.max_pop_size, recovery: shrink_population}
    - {name: dependency_failure, detection: CP unreachable, recovery: use_last_known_params}
  rollback_surface:
    code_rollback: git-revert
    state_rollback: "in-memory state lost on restart; CP params revert via gate_registry rollback mechanism"
    downstream_effect: "candidate stream pauses during restart"
    rollback_time_estimate_p50: 2 minutes
    rollback_time_estimate_p95: 5 minutes
    rollback_rehearsal: (scheduled)
  test_boundary:
    unit: zangetsu/tests/l4/search_contract/test_unit.py
    contract: zangetsu/tests/l4/search_contract/test_contract.py
    coverage_target_pct: 80
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: restart_after_swap
    downstream_impact: "candidate stream pause; gate_admission queues"
    shadow_required: true
  blackbox_allowed: false
  blackbox_rationale: "search_contract itself is pure orchestration. Specific implementations (e.g. search_lgbm) DO wrap black-boxes via the L9 adapter pattern; those modules declare blackbox_allowed: true with adapter_contract_ref."
  console_controls:
    - {surface_key: "search.engine.active", class: parameter, decision_rights_ref: "control_plane_blueprint.md#search-controls", audit_tier: high}
    - {surface_key: "search.gp.*", class: parameter, decision_rights_ref: same, audit_tier: standard}
    - {surface_key: system.kill.search_gp, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
```

### Module 6 — Evaluation Layer (L5)

```yaml
module:
  module_name: eval_contract
  purpose: "Abstract Evaluator interface; every evaluator (a1/a2_holdout/a3_train/a4_gate/a5_tournament) implements it with declared train/holdout/oos slice needs."
  responsibilities:
    - declare MetricsContract schema
    - enforce evaluator slice discipline (CD-14 hard-fail on missing holdout is a property of this contract, not a hotfix)
    - emit metrics per evaluation (latency, cache hit rate, divergence)
    - route metrics to consumers via kernel_dispatcher
  inputs:
    - contract_name: CandidateContract
      source_module: kernel_dispatcher
      cardinality: one_per_champion
      frequency: event
    - contract_name: DataProviderContract
      source_module: data_provider
      cardinality: on_demand
      frequency: lazy_load
    - contract_name: CP ParameterRead (cost model, TRAIN_SPLIT_RATIO, etc.)
      source_module: cp_worker_bridge
      cardinality: on_demand
      frequency: polling_60_seconds
  outputs:
    - contract_name: MetricsContract
      consumer_modules: [kernel_dispatcher, gate_a2, gate_a3, gate_a4, gate_promote, obs_metrics]
      cardinality: one_per_evaluation
      guarantees:
        delivery: exactly_once
        ordering: total_per_champion
        idempotency: true (keyed by champion_id + evaluator_id + slice)
  config_schema:
    ref: zangetsu/module_contracts/eval_contract.yaml
    cp_params:
      - validation.train_split_ratio
      - validation.holdout.required
      - validation.cost.bps_per_tier
  state_schema:
    - name: data_cache
      type: map<symbol, {train, holdout}>
      storage: in_memory (rebuilt from parquet at session start)
      ownership: EXCLUSIVE
      lifecycle: session
    - name: evaluation_cache
      type: row
      storage: postgres.champion_pipeline_fresh.passport JSONB
      ownership: SHARED[kernel_dispatcher writes via PATCH]
      lifecycle: persistent
  metrics:
    - {name: eval_contract_up, type: gauge, unit: bool, labels: [evaluator_id], cardinality_cap: 10, sample_sla: 1s}
    - {name: eval_latency_seconds, type: histogram, unit: seconds, labels: [evaluator_id, slice], cardinality_cap: 30, sample_sla: event}
    - {name: eval_cache_hit_ratio, type: gauge, unit: ratio, labels: [evaluator_id], cardinality_cap: 10, sample_sla: 1min}
    - {name: eval_nan_rate, type: gauge, unit: ratio, labels: [evaluator_id, slice], cardinality_cap: 20, sample_sla: 1min}
    - {name: eval_worker_divergence, type: gauge, unit: ratio, labels: [pair], cardinality_cap: 20, sample_sla: 5min}
  failure_surface:
    - {name: holdout_slice_missing, detection: "data_cache[sym].get('holdout') is None", recovery: hard_fail_row + RED Telegram (CD-14 contract)}
    - {name: backtester_crash, detection: exception in backtester.run, recovery: skip_row + increment violation counter}
    - {name: data_provider_unreachable, detection: data_provider health fails, recovery: pause_new_evaluations + alert}
    - {name: metric_nan_spike, detection: nan_rate > threshold, recovery: drop_metric_with_warning}
    - {name: worker_divergence, detection: two evaluators of same kind disagree beyond epsilon, recovery: quarantine_row + alert}
    - {name: resource_exhaustion_memory, detection: data_cache > config.max_cache_mb, recovery: evict_oldest_symbol}
    - {name: malformed_input, detection: CandidateContract schema violation, recovery: reject + increment violation counter}
  rollback_surface:
    code_rollback: git-revert
    state_rollback: "data_cache rebuilt from parquet on restart; champion passport patches are additive, no revert needed unless explicitly requested"
    downstream_effect: "gates pause during restart; kernel queues"
    rollback_time_estimate_p50: 3 minutes (includes data_cache rebuild)
    rollback_time_estimate_p95: 8 minutes
    rollback_rehearsal: (scheduled)
  test_boundary:
    unit: zangetsu/tests/l5/eval_contract/test_unit.py
    contract: zangetsu/tests/l5/eval_contract/test_contract.py + golden_fixtures/
    coverage_target_pct: 85
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: restart_after_swap
    downstream_impact: "kernel queues during swap"
    shadow_required: true (contract change in eval slice policy is a Phase 4 / D1-territory decision)
  blackbox_allowed: false
  blackbox_rationale: "eval_contract itself is the orchestrator. Specific evaluators implementing ML-based scoring (rare; not in current roadmap) would wrap their model via L9 adapter pattern."
  console_controls:
    - {surface_key: "validation.train_split_ratio", class: parameter, decision_rights_ref: "control_plane_blueprint.md#validation-controls", audit_tier: high}
    - {surface_key: "validation.cost.bps_per_tier", class: parameter, decision_rights_ref: same, audit_tier: high}
    - {surface_key: system.kill.eval_a2_holdout, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
```

### Module 7 — Black-Box Adapter Layer (L9 pattern)

```yaml
module:
  module_name: adapter_contract
  purpose: "Pattern (not a top-level layer) applied INSIDE L4/L5 modules when wrapping a black-box component (ML model, external LLM, external strategy signal); exposes the 13 mandatory adapter fields so a black-box internal engine can be governed via a white-box control surface."
  responsibilities:
    - define adapter fields (per `phase-2/blackbox_adapter_contracts.md §2`)
    - require integrity_hash verification at load
    - enforce health_endpoint polling from obs_freshness
    - force registry entry with blackbox_pattern_applied: true
    - mandate adversarial review + ADR
    - catch non-determinism (replay-fixture divergence) per Gemini §F.2 v2
    - catch resource_exhaustion per Gemini §F.2 v2
  inputs:
    - contract_name: AdapterRegistration
      source_module: any L4/L5 module with blackbox_allowed: true
      cardinality: one_per_adapter
      frequency: on_demand
    - contract_name: HealthPoll
      source_module: obs_freshness
      cardinality: stream
      frequency: polling_per_adapter_declared_cadence
  outputs:
    - contract_name: AdapterVerdict (pass/fail registration; pass/fail health)
      consumer_modules: [cp_api, gov_contract_engine, obs_metrics]
      cardinality: one_per_input
      guarantees:
        delivery: exactly_once
        ordering: total
        idempotency: true
  config_schema:
    ref: zangetsu/module_contracts/adapter_contract.yaml
    cp_params:
      - adapter.replay.fixture_N_default
      - adapter.replay.interval_hours
      - adapter.resource.default_max_rss_mb
      - adapter.resource.default_max_cpu_pct
  state_schema:
    - name: registered_adapters
      type: table
      storage: postgres.control_plane.adapters
      ownership: EXCLUSIVE
      lifecycle: persistent
    - name: integrity_hashes
      type: table
      storage: postgres.control_plane.adapter_hashes
      ownership: EXCLUSIVE
      lifecycle: persistent
  metrics:
    - {name: adapter_contract_up, type: gauge, unit: bool, labels: [], cardinality_cap: 1, sample_sla: 1s}
    - {name: adapter_registrations_total, type: counter, unit: events, labels: [outcome], cardinality_cap: 5, sample_sla: event}
    - {name: adapter_health_total, type: counter, unit: events, labels: [adapter_id, outcome], cardinality_cap: 40, sample_sla: event}
    - {name: adapter_integrity_violation_total, type: counter, unit: events, labels: [adapter_id], cardinality_cap: 20, sample_sla: event}
    - {name: adapter_nondeterminism_detected_total, type: counter, unit: events, labels: [adapter_id], cardinality_cap: 20, sample_sla: event}
  failure_surface:
    - {name: integrity_hash_mismatch, detection: load-time sha256 != registered hash, recovery: refuse_load + RED Telegram}
    - {name: health_endpoint_dead, detection: 3 consecutive failures, recovery: mark_adapter_degraded + alert}
    - {name: non_determinism_detected, detection: replay N fixture predictions diverge > float-epsilon, recovery: freeze_adapter + RED Telegram (Gemini §F.2)}
    - {name: resource_exhaustion, detection: RSS > max OR CPU > max for 60s, recovery: circuit_break + degrade_to_peer_search + RED}
    - {name: schema_drift, detection: adapter input/output violates declared contract, recovery: fail_closed + quarantine}
    - {name: auth_failure, detection: external auth returns 401/403, recovery: alert_and_disable_adapter}
    - {name: rate_limited, detection: upstream returns 429, recovery: exponential_backoff}
  rollback_surface:
    code_rollback: git-revert
    state_rollback: "adapter registration row has audit trail; rollback = deregister adapter"
    downstream_effect: "consuming L4/L5 module falls back to peer (non-adapter) implementation per its own failure_surface"
    rollback_time_estimate_p50: 15 seconds
    rollback_time_estimate_p95: 60 seconds
    rollback_rehearsal: (scheduled — Phase 7 when first real adapter lands)
  test_boundary:
    unit: zangetsu/tests/l9/adapter_contract/test_unit.py
    contract: zangetsu/tests/l9/adapter_contract/test_contract.py + fixtures/*_replay.json
    coverage_target_pct: 90
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: hot_swap
    downstream_impact: "none (no current adapter registered; pattern is pre-deployed)"
    shadow_required: true
  blackbox_allowed: false
  blackbox_rationale: "adapter_contract itself is the governance pattern — pure orchestration. Adapter INSTANCES wrap black-boxes."
  console_controls:
    - {surface_key: "adapter.replay.interval_hours", class: parameter, decision_rights_ref: "control_plane_blueprint.md#adapter-controls", audit_tier: standard}
    - {surface_key: "adapter.resource.default_max_rss_mb", class: parameter, decision_rights_ref: same, audit_tier: standard}
    - {surface_key: system.kill.adapter_contract, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
```

---

## §MOD-1.C — Mapping these 7 to the Ascension §2 boundary table below

| MOD-1 module | Ascension §2 boundary entries absorbed |
|---|---|
| engine_kernel | kernel_state + kernel_lease + kernel_dispatcher + kernel_logger |
| gate_registry | gate_registry + gate_contract (umbrella) |
| obs_metrics | obs_metrics + obs_logs + obs_view + obs_reports + obs_freshness |
| gov_contract_engine | gov_contract_engine + gov_reconciler + gov_audit_stream + gov_rollout + gov_ci_hooks |
| search_contract | search_contract + search_gp + search_lgbm + search_factor_zoo + search_hand_seed + primitive_registry |
| eval_contract | eval_contract + eval_a1 + eval_a2_holdout + eval_a3_train + eval_a4_gate + eval_a5_tournament + backtester + cost_model |
| adapter_contract | L9 pattern umbrella (applies inside L4/L5 modules) |

The full 46-module boundary table below (preserved from Ascension §2) sub-decomposes each of these into per-role modules. MOD-1 contracts here define the UMBRELLA obligations; sub-module contracts inherit and specialize.

---

## §MOD-1.D — Label per 0-2 rule 10

- §MOD-1.B contracts — **PROBABLE** (design-time spec; will be VERIFIED once each module lands in Phase 7 with runtime metrics matching declared schema)
- §2 boundary table (below, preserved) — **PROBABLE** (Ascension-accepted design)
- §3 forbidden crossings (below, preserved) — **PROBABLE**

---

## §MOD-1.E — Exit criterion

MOD-1 Phase 4 exit: *"The team has an explicit module map and a reusable contract template."*

Met by: 7 full 14-field contracts above + 46-module cross-reference table below + `module_contract_template.md` (reusable template). Combined, Phase 7 migration can proceed module-by-module with Gate-B enforcement on each.

Proceed to Phase 5 (`modular_target_architecture.md`).

---

## §MOD-1.F — Authoritative content (preserved from Ascension Phase-2 v2.1)

---

# Zangetsu — Module Boundary Map (Phase 2)

**Program:** Ascension v1 Phase 2
**Date:** 2026-04-23
**Status:** DESIGN.

---

## §1 — Purpose

Given the `modular_target_architecture.md` module list, define for EACH module:
- which current file(s) it absorbs
- which files it does NOT touch (explicit exclusion)
- what responsibility crosses its boundary TO and FROM neighbouring modules

Every boundary has a contract named in `modular_target_architecture.md §6`.

---

## §2 — Boundary table

| Module | Absorbs (current file) | Does NOT touch | Upstream contract | Downstream contract |
|---|---|---|---|---|
| cp_api | (new) | zangetsu/services/* | n/a | CP read/write API consumed by all layers |
| cp_storage | (new) | admission_validator function body | n/a | Postgres `control_plane.*` schema |
| cp_audit | (new) | `pipeline_audit_log` (L8 owns that) | CP writes | Audit API to L8.G |
| cp_notifier | (new) | zangetsu_notifier / calcifer notifier | CP state | `pg_notify` + Redis pub/sub |
| cp_cli | `zangetsu_ctl.sh` (shim layer) | direct worker spawn logic | user input | CP API |
| cp_worker_bridge | (new) — library | `claim_champion` internals | CP read API | in-process config cache |
| kernel_state | `shared_utils.claim_champion/release_champion/reap_expired_leases` + orchestrator main loops | A1 GP primitives, backtester | CP params | DB champion_pipeline_fresh + pg_notify state events |
| kernel_lease | `shared_utils.py` reaper | evaluator internals | CP params | DB leases |
| kernel_dispatcher | new integration layer | evaluator internals | kernel_state events | L4/L5/L6 call routing |
| kernel_logger | (new) | business log content | kernel events | obs_logs |
| data_provider | `data_collector.py` | parquet consumers directly | external APIs | DataProviderContract |
| data_schema_registry | (new) | content of parquet | data_provider | schema API to consumers |
| data_health | (new) | data content | data_schema_registry | health API to L8 |
| data_store | parquet read helpers (scattered in workers today) | DB writes | data layout | read-only parquet API |
| search_contract | (new) | GP primitives, pset config | candidate producer role | CandidateContract |
| search_gp | `arena_pipeline.py::main GP loop` + `alpha_engine.py` + `alpha_primitives.py` | DB writes (use kernel_dispatcher) | CP params + data | CandidateContract |
| search_lgbm | (new scaffold) | — | CP params + data | CandidateContract |
| search_factor_zoo | `scripts/factor_zoo.py` | — | CP deprecated flag | CandidateContract |
| search_hand_seed | `scripts/cold_start_hand_alphas.py`, `scripts/seed_hand_alphas.py`, `scripts/seed_101_alphas*.py` | — | CP + operator | CandidateContract |
| primitive_registry | consolidated from alpha_primitives.py + pset_lean_config.py | signal generation (stays in alpha_signal.py) | CP | pset lookup |
| eval_contract | (new) | candidates | MetricsContract | MetricsContract |
| eval_a1 | `alpha_engine._forward_returns`, fitness fn | DB | data + candidate | MetricsContract |
| eval_a2_holdout | `arena23_orchestrator.process_arena2` | DB writes (use kernel_dispatcher) | data + candidate + cost_model | MetricsContract |
| eval_a3_train | `arena23_orchestrator.process_arena3` | DB writes | data + candidate | MetricsContract |
| eval_a4_gate | `arena45_orchestrator.arena4_*` | promotion decision (gate_promote owns) | MetricsContract | GateOutcomeContract |
| eval_a5_tournament | `arena45_orchestrator.arena5_*` | card state updates (pub_db owns) | MetricsContract + ELO state | ELO update events |
| backtester | (existing) | signal generation (alpha_signal.py) | candidate + data + cost | MetricsContract fields |
| cost_model | `settings.py` per-tier bps | literals in orchestrator | CP | cost_per_symbol lookup |
| gate_registry | consolidated threshold registry | individual gate logic | CP params | threshold lookup |
| gate_contract | (new) | — | MetricsContract | GateOutcomeContract |
| gate_admission | wraps admission_validator PL/pgSQL | kernel state transitions | staging row | GateOutcomeContract |
| gate_a2 | hardcoded checks in arena23_orchestrator | eval_a2_holdout | MetricsContract | GateOutcomeContract |
| gate_a3 | hardcoded in arena23 | eval_a3_train | MetricsContract | GateOutcomeContract |
| gate_a4 | hardcoded in arena45 | eval_a4_gate | MetricsContract | GateOutcomeContract |
| gate_promote | `PROMOTE_WILSON_LB` + `PROMOTE_MIN_TRADES` in settings.py | — | MetricsContract | GateOutcomeContract |
| gate_calcifer_bridge | Calcifer block file reader (scattered today) | Calcifer daemon internals | calcifer block JSON | GateOutcomeContract (veto) |
| publish_contract | (new) | — | state events | PublisherContract |
| pub_db | kernel_dispatcher's DB writes + release_champion | DB reads (obs_view) | ChampionStateContract | DB rows |
| pub_view | `zangetsu_status` VIEW (SQL) | VIEW consumers | DB rows | versioned SQL artefact |
| pub_snapshot | `scripts/zangetsu_snapshot.sh` | VIEW implementation | VIEW + worker telemetry | `/tmp/zangetsu_live.json` |
| pub_telegram | wraps `calcifer/notifier.py::notify_telegram` | Telegram API directly | AlertContract | Telegram message |
| pub_akasha | wraps `notifier.py::write_to_akasha_sync` | AKASHA server | AlertContract | AKASHA memory chunk |
| pub_alert | (new) | specific channels | MetricsContract + thresholds | AlertContract |
| obs_metrics | (new) | log content | kernel_logger + per-worker metric emit | Prometheus endpoint |
| obs_logs | (new) | business logs (just routes) | kernel_logger + worker stdout | structured log sink |
| obs_view | `zangetsu_status` SQL | pub_view | DB rows | SQL VIEW |
| obs_reports | `scripts/signal_quality_report.py`, `v10_*`, `v8_vs_v9_metrics.py` | DB writes | DB + parquet | `/tmp/*.md` |
| obs_freshness | (new; pattern from `r2_n4_watchdog.py`) | log content | file mtimes + proc list | alert emit |
| gov_contract_engine | `verify_no_archive_reads.sh` + pre-bash hook | CP writes (only checks) | commit events + CP writes | allow/deny |
| gov_reconciler | (new; cron suite matching `mutation_blocklist.yaml detection` fields) | CP state | DB + files + CP | alert emit |
| gov_audit_stream | (new) | CP internals | cp_audit | audit queries |
| gov_rollout | (new) | per-feature implementation | CP rollout table | state events |
| gov_ci_hooks | pre-commit + pre-receive + `~/.claude/hooks/*` | actual code change | commit / push events | allow/deny |

---

## §3 — Forbidden boundary crossings

Avoid these patterns (they will be caught in code review / migration):

1. A worker module writes directly to DB without going through **kernel_dispatcher** (forbids hidden state machine).
2. A search / eval module reads CP params without going through **cp_worker_bridge** (forbids stale cached constants).
3. An output sink accepts messages without an **AlertContract** envelope (forbids ad-hoc formats).
4. Any module logs raw secrets / credentials / tokens.
5. A gate module writes back to state without emitting a **GateOutcomeContract** record.
6. A data_provider module caches in a location other than `data_store`.
7. CP writes bypass the audit pipeline.

---

## §4 — Sanity map: current scattered code → target module

| Current file / function | Absorbed by target module | Phase 7 migration |
|---|---|---|
| `zangetsu_ctl.sh` | cp_cli + gov_ci_hooks | wrap existing behavior; publish as shim |
| `services/arena_pipeline.py` main loop | kernel_dispatcher + kernel_state (portion) + search_gp + eval_a1 | major refactor P1 |
| `services/arena23_orchestrator.py` | kernel_dispatcher + eval_a2_holdout + eval_a3_train + gate_a2 + gate_a3 | P1 |
| `services/arena45_orchestrator.py` | kernel_dispatcher + eval_a4_gate + eval_a5_tournament + gate_a4 + gate_promote + pub_db | P1 |
| `services/arena13_feedback.py` | obs_metrics (produces guidance events) + gov_contract_engine (consumes weight delta cap) | P2 |
| `services/alpha_discovery.py` | search_factor_zoo (frozen) | rename + clean |
| `services/shared_utils.py` | kernel_lease + kernel_state | P1 |
| `services/db_audit.py` | cp_audit + gov_audit_stream | P1 |
| `engine/components/alpha_engine.py` | search_gp + primitive_registry + eval_a1 | P2 (after kernel exists) |
| `engine/components/alpha_signal.py` | search_gp signal-side helper | P2 |
| `engine/components/alpha_primitives.py` | primitive_registry | P2 |
| `engine/components/indicator_bridge.py` | primitive_registry + data_store integration | P2 (D-22 cache invalidation also) |
| `engine/components/pset_lean_config.py` | primitive_registry (variant) | P2 |
| `config/settings.py` | CP parameter registry + gate_registry + cost_model | P1 |
| `config/family_strategy_policy_v0.yaml` | gate_registry (family routing) | P3 wiring |
| `scripts/zangetsu_snapshot.sh` | pub_snapshot + obs_view | P2 |
| `scripts/watchdog.sh` | obs_freshness + gov_reconciler | P2 |
| `scripts/r2_n4_watchdog.py` | reference pattern for obs_freshness + pub_alert | P2 template |
| `scripts/signal_quality_report.py`, `v10_*`, `v8_vs_v9_metrics.py` | obs_reports | P3 |
| `scripts/verify_no_archive_reads.sh` | gov_contract_engine | P2 |
| `scripts/seed_*.py`, `cold_start_hand_alphas.py` | search_hand_seed | P3 |
| Calcifer block file + supervisor | gate_calcifer_bridge (reads) + gov_service (writes) | coordinate with sibling |
| `~/.claude/hooks/*` | gov_ci_hooks | small move |

---

## §5 — Out-of-scope for boundary map

- Implementation details within a module (Phase 7).
- Specific Python package layout (`zangetsu/l4/search/gp.py` vs `zangetsu/search/gp.py`) — Phase 7.
- Database schema migrations (Phase 7).
- Backwards-compat shims (Phase 7 migration plan).
