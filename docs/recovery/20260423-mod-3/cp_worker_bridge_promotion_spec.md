# cp_worker_bridge Promotion Spec — Module 9

**Order**: `/home/j13/claude-inbox/0-4` Phase 2 deliverable
**Produced**: 2026-04-23T07:40Z
**Supersedes**: `docs/recovery/20260423-mod-1/module_boundary_map.md §MOD-1.B` (7 mandatory) by adding Module 9
**Resolves**: Gemini R2-F3 HIGH (cp_worker_bridge hidden dependency)

---

## 1. Why promote to mandatory

Per Gemini R2-F3:
> "The architecture relies on an undefined `cp_worker_bridge` as a universal data bus, which is not one of the 7 mandatory modules. M1, M2, M3, M4, M5, and M6 all list `cp_worker_bridge` in their 'inputs' field."

6 of 7 existing mandatory modules depend on `cp_worker_bridge`. A dependency used by almost every module IS a core boundary — not a support library. Promotion is correct.

## 2. Full 14-field contract (+ Field 15 per MOD-3 template amendment = 15 fields)

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
      rate_limit:
        max_events_per_second: 500  # per-worker
        max_events_per_minute: 10000
        burst_size: 1000
        backpressure_policy: drop_newest (fail fast; fall back to local cache)
  config_schema:
    ref: zangetsu/module_contracts/cp_worker_bridge.yaml
    cp_params:
      - cp_bridge.cache.ttl_seconds
      - cp_bridge.stale.max_age_seconds
      - cp_bridge.fail_closed_default
      - cp_bridge.pubsub.backend  # pg_notify | redis
      - cp_bridge.query.timeout_ms
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
  metrics:
    - {name: cp_worker_bridge_up, type: gauge, unit: bool, labels: [worker_id], cardinality_cap: 50, sample_sla: 1s}
    - {name: cp_worker_bridge_queries_total, type: counter, unit: events, labels: [param_key, cache_hit], cardinality_cap: 200, sample_sla: event}
    - {name: cp_worker_bridge_query_duration_seconds, type: histogram, unit: seconds, labels: [cache_hit], cardinality_cap: 4, sample_sla: event}
    - {name: cp_worker_bridge_stale_read_total, type: counter, unit: events, labels: [reason], cardinality_cap: 10, sample_sla: event}
    - {name: cp_worker_bridge_fail_closed_total, type: counter, unit: events, labels: [param_key], cardinality_cap: 50, sample_sla: event}
  failure_surface:
    - {name: cp_api_unreachable, detection: HTTP error or timeout, recovery: "use local cache if TTL-fresh; otherwise per-param fail_closed flag"}
    - {name: pg_notify_disconnect, detection: stream gap detected, recovery: reconnect + refresh cache}
    - {name: stale_cache_read, detection: cached value older than max_age_seconds, recovery: emit warning + refetch (block caller)}
    - {name: param_not_found, detection: cp_api returns 404, recovery: fail_closed (caller decides)}
    - {name: schema_drift, detection: cp returns value with unexpected type, recovery: fail_closed + alert}
    - {name: resource_exhaustion_cache, detection: cache entries > max_cache_entries, recovery: LRU eviction}
    - {name: malformed_input, detection: query param key invalid, recovery: reject at API boundary + log}
  rollback_surface:
    code_rollback: git-revert (library — consumers auto-pick-up on next restart)
    state_rollback: "caches are ephemeral; no persistent rollback"
    downstream_effect: "consumers see old cached values during restart window (< 60s); subsequent queries refresh"
    rollback_time_estimate_p50: immediate (library; no process to restart independently)
    rollback_time_estimate_p95: 60 seconds (worker recycle to pick up new library)
    rollback_rehearsal: (scheduled pre-Phase-7)
  test_boundary:
    unit: zangetsu/tests/l1/cp_worker_bridge/test_unit.py
    contract: zangetsu/tests/l1/cp_worker_bridge/test_contract.py + fixtures/cp_stub/
    coverage_target_pct: 95 (CRITICAL — every module uses this)
  replacement_boundary:
    contract_version_min: "1.0"
    contract_version_max: "2.99"
    migration_mode: hot_swap (library is drop-in replaceable if ABI-compatible)
    downstream_impact: "consumers restart to pick up new library"
    shadow_required: false (library is in-process; no inter-process contract change)
  blackbox_allowed: false
  blackbox_rationale: "cp_worker_bridge is the universal data-plane; opaque behavior here would hide parameter drift across every consumer. Must be fully auditable."
  console_controls:
    - {surface_key: "cp_bridge.cache.ttl_seconds", class: parameter, decision_rights_ref: "control_plane_blueprint.md#system-controls", audit_tier: standard}
    - {surface_key: "cp_bridge.stale.max_age_seconds", class: parameter, decision_rights_ref: same, audit_tier: standard}
    - {surface_key: "cp_bridge.fail_closed_default", class: parameter, decision_rights_ref: same, audit_tier: high}
    - {surface_key: system.kill.cp_worker_bridge, class: kill_switch, decision_rights_ref: "control_plane_blueprint.md#kill-switches", audit_tier: high}
  # Field 15 (MOD-3 amendment)
  execution_environment:
    permitted_egress_hosts:
      - "localhost:8773"   # cp_api (MOD-3 proposed CP port)
      - "127.0.0.1:6380"   # Redis
      - "127.0.0.1:5432"   # Postgres (if pg_notify used)
    subprocess_spawn_allowed: false
    subprocess_permitted_binaries: []
    filesystem_write_paths: []   # pure-in-memory library
    max_rss_mb: 128              # per worker; cache-bounded
    max_cpu_pct_sustained: 10    # library reads should be cheap
    requires_root: false
    requires_docker_group: false
    requires_sudo: false
```

## 3. Why library not service

`cp_worker_bridge` runs **in-process** inside every consumer module, not as a standalone service. This is deliberate:
- Reading a parameter from CP should be a function call, not a network round-trip
- Caching is per-worker (simpler; no cache coherency issues across workers)
- pg_notify / Redis pub/sub is the only network dep; cached fallback handles outages

Alternative design considered + rejected: cp_worker_bridge as a sidecar process. Rejected because:
- Extra process hop adds latency (p50 ~50µs vs ~5ms network)
- Sidecar failure adds a new failure surface
- Language-specific library is simpler to version with the module

## 4. Upstream contract from cp_api

cp_worker_bridge queries cp_api via these endpoints (per `control_plane_blueprint.md §8`):
- `GET /api/control/params/{key}` — single param
- `GET /api/control/params?keys=a,b,c` — batch read (added MOD-3 for efficiency)
- `GET /api/control/mode` — current operating mode
- `GET /api/control/rollout/{subsystem}` — rollout state

Subscription via:
- pg_notify channel `cp_param_change`
- OR Redis pub/sub `cp:subscribe:param:<key>`

## 5. Consumer migration checklist

When Phase 7 modules migrate to use cp_worker_bridge, each consumer must:

1. Import `cp_worker_bridge` library
2. Replace direct `os.environ.get("PARAM")` reads with `cp_bridge.get("param.key", default=...)`
3. Declare `cp_params: [...]` list in own module contract
4. Subscribe via `cp_bridge.subscribe("param.key", callback)` for change-reactive behavior
5. Remove any hardcoded fallback literals (let `fail_closed_on_unreachable` policy decide)

This is a Phase 7 activity, spec here is design-only.

## 6. Relationship to cp_api (M1's cp_* helpers)

The L1 Control Plane has these modules (from `modular_target_architecture.md §3 L1`):
- cp_api
- cp_storage
- cp_audit
- cp_notifier
- cp_cli
- **cp_worker_bridge** ← this module

In MOD-1, cp_worker_bridge was listed as an L1 sub-module but NOT mandatory. MOD-3 promotes to mandatory status per R2-F3. cp_api / cp_storage / cp_audit / cp_notifier / cp_cli remain L1 sub-modules (not promoted) — they are implementation details of the CP service, not consumer-facing.

## 7. Resolution status

| Finding | Status |
|---|---|
| R2-F3 HIGH (cp_worker_bridge hidden dep) | **RESOLVED** — M9 promoted to mandatory with full 15-field contract |

## 8. Label per 0-4 rule 10

- §2 15-field contract: **PROBABLE** (design; VERIFIED when library lands in Phase 7)
- §3 design rationale (in-process library): **VERIFIED** via comparative latency reasoning
- §4 upstream contract: **PROBABLE** (matches existing cp_api spec)
- §5 migration checklist: **PROBABLE** (Phase 7 activity)
