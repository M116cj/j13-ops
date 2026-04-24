# Medium Findings Patchset — MOD-5 Phase 3

**Order**: `/home/j13/claude-inbox/0-7` Phase 3 deliverable
**Produced**: 2026-04-24T00:55Z
**Scope**: Authoritative amendment text for findings RESOLVED in MOD-5. Patchset format ready for Phase 7 YAML application.

---

## 1. R4b-F2 amendment — M9 cache_lookup hard cap

**Target file** (when Phase 7 writes concrete YAML): `zangetsu/module_contracts/cp_worker_bridge.yaml`

**Target section**: `outputs[0].rate_limit.cache_lookup`

**Authoritative replacement spec** (supersedes `amended_cp_worker_bridge_contract.md §1 outputs.rate_limit.cache_lookup`):

```yaml
rate_limit:
  cache_lookup:
    max_events_per_second: 20000
    max_events_per_minute: 1200000
    burst_size: 100000
    backpressure_policy: circuit_breaker
    circuit_breaker_threshold: "sustained > 18000/s for 3 consecutive seconds"
    circuit_breaker_open_duration: 1   # seconds; auto-close after
    circuit_breaker_recovery: half_open_probe (10% requests pass during recovery)
    enforcement: hard_client_side
    failure_mode: "rate_limit_rest_fetch_breach (already declared in MOD-3 failure_surface)"
```

Observability:
- `cp_worker_bridge_circuit_breaker_open_total{reason}` — counter
- `cp_worker_bridge_circuit_breaker_open_duration_seconds` — histogram

Tests (Phase 7):
- `zangetsu/tests/l1/cp_worker_bridge/test_cache_lookup_hard_cap.py`:
  - assert 20000 req/s sustained → no breaker trip
  - assert 19000 sustained 3s → breaker trips
  - assert 1s recovery window → half-open probe succeeds → close

## 2. R4b-F3 amendment — M9 thundering-herd mandatory

**Target file**: `zangetsu/module_contracts/cp_worker_bridge.yaml`

**Target section**: `responsibilities` + new mandatory functional_requirements subsection.

### 2.1 Added to responsibilities (authoritative)

```yaml
responsibilities:
  - fetch CP parameters on-demand via cp_api REST
  - subscribe to CP pg_notify / Redis pub/sub for parameter change events
  - cache last-known-good values locally (TTL + stale-flag)
  - emit stale-read warnings to obs_metrics
  - enforce fail-closed on parameter with `fail_closed_on_unreachable: true` flag
  # MOD-5 ADDITIONS (promoted from design intent to mandatory requirement)
  - coalesce concurrent rest_fetch requests per-key via single-flight pattern
  - apply jitter (0-500ms) before post-invalidation refetch
```

### 2.2 New `functional_requirements` section (MOD-5 addition)

```yaml
functional_requirements:
  single_flight:
    description: "Only one rest_fetch request per cache-miss key at any time; other concurrent callers piggyback on the in-flight request."
    implementation_note: "Use threading.Event per key; event set when response returns; callers wait on event."
    required_at: "MOD-5 → Phase 7 contract; validated at Gate-B.B.1"
    test: "zangetsu/tests/l1/cp_worker_bridge/test_thundering_herd_single_flight.py"

  jitter:
    description: "After receiving CPChangeEvent, delay local cache invalidation refetch by random 0-500ms."
    implementation_note: "time.sleep(random.random() * 0.5) before rest_fetch"
    required_at: "MOD-5 → Phase 7 contract; validated at Gate-B.B.1"
    test: "zangetsu/tests/l1/cp_worker_bridge/test_thundering_herd_jitter.py"
    configuration:
      - key: cp_bridge.rest_fetch.jitter_ms_max
        default: 500
        range: [0, 5000]
```

### 2.3 Gate-B.B.1 validation update

`validate_module_contract.py` (per `github_actions_gate_b_enforcement_spec.md §3` Phase 7 implementation):
- Assert `functional_requirements.single_flight.test` file exists + passes
- Assert `functional_requirements.jitter.test` file exists + passes
- Reject YAML if either missing

## 3. Blocker matrix update (reflected in `blocker_matrix_delta_mod5.md`)

After this patchset lands:
- R4b-F2: removed from open list (RESOLVED)
- R4b-F3: removed from open list (RESOLVED)
- Open MEDIUM: R4a-F1 (DEFERRED), R3a-F6 (PARTIAL) — see `remaining_findings_resolution_table.md §3`

## 4. Propagation checklist

This patchset amends (spec-level; Phase 7 applies to YAML):

| File | Section | Change |
|---|---|---|
| `docs/recovery/20260423-mod-4/amended_cp_worker_bridge_contract.md §1` | `outputs.rate_limit.cache_lookup` | MOD-5 hard-cap values (per §1 above) |
| `docs/recovery/20260423-mod-4/cp_worker_bridge_rate_limit_split.md §2.1` | cache_lookup row | Update description: "hard_client_side with circuit breaker" |
| `docs/recovery/20260423-mod-4/cp_worker_bridge_rate_limit_split.md §6.3` | Thundering-herd section | Move from "design intent" to "MOD-5 mandatory functional_requirement" |
| Future `zangetsu/module_contracts/cp_worker_bridge.yaml` | — | Apply §1 + §2 values |

Not changed:
- Any other field in M9 contract
- Any other module's contract
- Any governance / CQG / execution gate doc

## 5. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 1. No silent mutation | ✅ — patchset is explicit |
| 3. No live gate change | ✅ — spec-level only; no live contract yet |
| 8. No broad refactor | ✅ — limited to M9 fields |
| 10. Labels | ✅ |

## 6. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — both amendments precisely targeted |
| Silent failure | PASS — tests required at Gate-B.B.1 |
| External dep | PASS — circuit breaker standard pattern |
| Concurrency | PASS — single-flight is the thundering-herd answer |
| Scope creep | PASS — 2 fields, no cross-module |

## 7. Label per 0-7 rule 10

- §1 hard cap spec: **VERIFIED** (numeric + test)
- §2 thundering-herd spec: **VERIFIED** (mandatory functional_requirements with tests)
- §3 matrix impact: **VERIFIED**
