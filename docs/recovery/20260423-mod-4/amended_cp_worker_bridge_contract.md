# Amended cp_worker_bridge Contract — MOD-4 Phase 2B

**Order**: `/home/j13/claude-inbox/0-5` Phase 2B deliverable
**Produced**: 2026-04-23T09:55Z
**Supersedes**: `cp_worker_bridge_promotion_spec.md §2` (MOD-3) rate_limit block and metrics
**Changes summary**: Rate-limit split per `cp_worker_bridge_rate_limit_split.md`; metrics expanded per channel.

---

## 1. Full amended M9 contract (drop-in replacement for Phase 7 YAML)

```yaml
module:
  module_name: cp_worker_bridge
  purpose: "Worker-side library for reading + subscribing to Control Plane parameters; the canonical data-plane bridge every L2/L4/L5/L6 worker uses to consume CP config."
  responsibilities:
    - fetch CP parameters on-demand via cp_api REST
    - subscribe to CP pg_notify / Redis pub/sub for parameter change events
    - cache last-known-good values locally (TTL + stale-flag)
    - emit stale-read warnings to obs_metrics
    - enforce fail-closed on parameter with `fail_closed_on_unreachable: true` flag
  inputs:
    - contract_name: CPParameterQuery
      source_module: <consuming module> (in-process library call)
      cardinality: on_demand
      frequency: any
    - contract_name: CPChangeEvent
      source_module: cp_notifier (pg_notify or Redis pub/sub stream)
      cardinality: stream
      frequency: event
  outputs:
    - contract_name: ParameterValue
      consumer_modules: [engine_kernel, gate_registry, gate_contract, obs_metrics, gov_contract_engine, search_contract, eval_contract, adapter_contract, and ANY L3/L7 module]
      cardinality: one_per_query
      guarantees:
        delivery: exactly_once (per query)
        ordering: none (each query independent)
        idempotency: true (pure read)
      # MOD-4: multi-channel rate_limit (supersedes MOD-3 single-channel)
      rate_limit:
        cache_lookup:
          max_events_per_second: 10000
          max_events_per_minute: 600000
          burst_size: 50000
          backpressure_policy: not_applicable
          enforcement: soft_metric_only
        rest_fetch:
          max_events_per_second: 10       # per-worker hard cap
          max_events_per_minute: 300
          burst_size: 50
          backpressure_policy: drop_newest + fall_back_to_cache (if TTL-fresh)
          enforcement: hard_client_side (cp_api also enforces API gateway limits)
        subscribe_event:
          max_events_per_second: 100
          max_events_per_minute: 2000
          burst_size: 500
          backpressure_policy: drop_newest (bounded by pg_notify / Redis buffer)
          enforcement: soft_monitor
  config_schema:
    ref: zangetsu/module_contracts/cp_worker_bridge.yaml
    cp_params:
      - cp_bridge.cache.ttl_seconds
      - cp_bridge.stale.max_age_seconds
      - cp_bridge.fail_closed_default
      - cp_bridge.pubsub.backend  # pg_notify | redis
      - cp_bridge.query.timeout_ms
      - cp_bridge.rest_fetch.single_flight_enabled  # MOD-4 addition (thundering-herd protection)
      - cp_bridge.rest_fetch.jitter_ms              # MOD-4 addition
  state_schema:
    - name: local_param_cache
      type: keyed_cache
      storage: in_memory (per worker process)
      ownership: EXCLUSIVE
      lifecycle: session
    - name: cache_metrics
      type: counters
      storage: in_memory
      ownership: EXCLUSIVE
      lifecycle: session
    - name: inflight_rest_requests  # MOD-4 addition (single-flight tracking)
      type: keyed_set
      storage: in_memory
      ownership: EXCLUSIVE
      lifecycle: session
  metrics:
    - {name: cp_worker_bridge_up, type: gauge, unit: bool, labels: [worker_id], cardinality_cap: 50, sample_sla: 1s}
    - {name: cp_worker_bridge_queries_total, type: counter, unit: events, labels: [param_key, cache_hit, channel], cardinality_cap: 300, sample_sla: event}
    # MOD-4: per-channel metrics
    - {name: cp_worker_bridge_cache_lookup_duration_seconds, type: histogram, unit: seconds, labels: [], cardinality_cap: 1, sample_sla: event}
    - {name: cp_worker_bridge_rest_fetch_total, type: counter, unit: events, labels: [outcome], cardinality_cap: 5, sample_sla: event}
    - {name: cp_worker_bridge_rest_fetch_duration_seconds, type: histogram, unit: seconds, labels: [outcome], cardinality_cap: 5, sample_sla: event}
    - {name: cp_worker_bridge_subscribe_event_total, type: counter, unit: events, labels: [param_key, outcome], cardinality_cap: 100, sample_sla: event}
    - {name: cp_worker_bridge_rate_limit_drop_total, type: counter, unit: events, labels: [channel, reason], cardinality_cap: 9, sample_sla: event}
    - {name: cp_worker_bridge_single_flight_coalesce_total, type: counter, unit: events, labels: [], cardinality_cap: 1, sample_sla: event}  # MOD-4
    # unchanged from MOD-3
    - {name: cp_worker_bridge_query_duration_seconds, type: histogram, unit: seconds, labels: [cache_hit], cardinality_cap: 4, sample_sla: event}
    - {name: cp_worker_bridge_stale_read_total, type: counter, unit: events, labels: [reason], cardinality_cap: 10, sample_sla: event}
    - {name: cp_worker_bridge_fail_closed_total, type: counter, unit: events, labels: [param_key], cardinality_cap: 50, sample_sla: event}
  failure_surface:
    # unchanged from MOD-3 (7 modes)
    - {name: cp_api_unreachable, detection: HTTP error or timeout, recovery: "use local cache if TTL-fresh; otherwise per-param fail_closed flag"}
    - {name: pg_notify_disconnect, detection: stream gap detected, recovery: reconnect + refresh cache}
    - {name: stale_cache_read, detection: cached value older than max_age_seconds, recovery: emit warning + refetch (block caller)}
    - {name: param_not_found, detection: cp_api returns 404, recovery: fail_closed (caller decides)}
    - {name: schema_drift, detection: cp returns value with unexpected type, recovery: fail_closed + alert}
    - {name: resource_exhaustion_cache, detection: cache entries > max_cache_entries, recovery: LRU eviction}
    - {name: malformed_input, detection: query param key invalid, recovery: reject at API boundary + log}
    # MOD-4 additions
    - {name: rate_limit_rest_fetch_breach, detection: rest_fetch count > 10/s per worker, recovery: drop_newest + stale-fallback + audit}
    - {name: rate_limit_subscribe_burst, detection: subscribe_event burst > 500, recovery: drop_oldest (ring buffer) + alert}
    - {name: thundering_herd_detected, detection: >10 workers refetching same key within 500ms window, recovery: single_flight_coalesce + jitter}
  rollback_surface:
    code_rollback: git-revert (library — consumers auto-pick-up on next restart)
    state_rollback: "caches are ephemeral; no persistent rollback"
    downstream_effect: "consumers see old cached values during restart window (< 60s); subsequent queries refresh"
    rollback_time_estimate_p50: immediate (library)
    rollback_time_estimate_p95: 60 seconds
    rollback_rehearsal: (scheduled pre-Phase-7)
  test_boundary:
    unit: zangetsu/tests/l1/cp_worker_bridge/test_unit.py
    contract: zangetsu/tests/l1/cp_worker_bridge/test_contract.py + fixtures/cp_stub/
    # MOD-4: added per-channel test fixtures
    channel_tests:
      - zangetsu/tests/l1/cp_worker_bridge/test_cache_lookup.py
      - zangetsu/tests/l1/cp_worker_bridge/test_rest_fetch.py
      - zangetsu/tests/l1/cp_worker_bridge/test_subscribe_event.py
      - zangetsu/tests/l1/cp_worker_bridge/test_thundering_herd.py
    coverage_target_pct: 95
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: hot_swap
    downstream_impact: "consumers restart to pick up new library"
    shadow_required: false
  blackbox_allowed: false
  blackbox_rationale: "cp_worker_bridge is the universal data-plane; opaque behavior here would hide parameter drift across every consumer. Must be fully auditable."
  console_controls:
    - {surface_key: "cp_bridge.cache.ttl_seconds", class: parameter, decision_rights_ref: "control_plane_blueprint.md#system-controls", audit_tier: standard}
    - {surface_key: "cp_bridge.stale.max_age_seconds", class: parameter, decision_rights_ref: same, audit_tier: standard}
    - {surface_key: "cp_bridge.fail_closed_default", class: parameter, decision_rights_ref: same, audit_tier: high}
    - {surface_key: "cp_bridge.rest_fetch.single_flight_enabled", class: parameter, decision_rights_ref: same, audit_tier: standard}  # MOD-4
    - {surface_key: system.kill.cp_worker_bridge, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
  execution_environment:
    permitted_egress_hosts:
      - "localhost:8773"
      - "127.0.0.1:6380"
      - "127.0.0.1:5432"
    subprocess_spawn_allowed: false
    subprocess_permitted_binaries: []
    filesystem_read_paths: []   # MOD-4: new sub-field, N/A for M9
    filesystem_write_paths: []
    max_rss_mb: 128
    max_cpu_pct_sustained: 10
    requires_root: false
    requires_docker_group: false
    requires_sudo: false
```

## 2. Delta summary vs MOD-3 contract

| Section | MOD-3 | MOD-4 |
|---|---|---|
| outputs.rate_limit | single-channel {500/s max, 10000/min} | three-channel {cache_lookup, rest_fetch, subscribe_event} |
| config_schema.cp_params | 5 keys | 7 keys (+ single_flight_enabled, jitter_ms) |
| state_schema | 2 entries | 3 entries (+ inflight_rest_requests) |
| metrics | 5 | 11 (added per-channel + single_flight) |
| failure_surface | 7 | 10 (added rate_limit_rest_fetch_breach, rate_limit_subscribe_burst, thundering_herd_detected) |
| test_boundary | 1 unit + 1 contract | + 4 channel-specific tests |
| console_controls | 4 | 5 (+ single_flight_enabled) |
| execution_environment filesystem_read_paths | absent | present (empty) per MOD-4 template v3 |

## 3. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 1. No silent mutation | ✅ — delta explicit |
| 8. No broad refactor | ✅ — backward-compatible extension |

## 4. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — per-channel rate_limit removes conflation |
| Silent failure | PASS — 3 new failure modes for rate-limit breach |
| External dep | PASS — same network deps, declared |
| Concurrency | PASS — single_flight addresses thundering herd |
| Scope creep | PASS — targeted at M9; no cross-module changes |

## 5. Resolution status

Gemini R3b-F2 HIGH — **RESOLVED** at contract level.

## 6. Label per 0-5 rule 10

- §1 full amended contract: **PROBABLE** (design-time; VERIFIED when Phase 7 YAML validates)
- §2 delta summary: **VERIFIED**
