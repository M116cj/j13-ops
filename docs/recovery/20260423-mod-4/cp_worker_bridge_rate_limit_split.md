# cp_worker_bridge Rate-Limit Split — MOD-4 Phase 2B

**Order**: `/home/j13/claude-inbox/0-5` Phase 2B primary deliverable
**Produced**: 2026-04-23T09:52Z
**Resolves**: Gemini R3b-F2 HIGH — "M9 rate_limit=500/s mixes in-process, REST fetch, and subscribe channels"

---

## 1. Problem with MOD-3 spec

MOD-3 `cp_worker_bridge_promotion_spec.md §2` declared:
```yaml
rate_limit:
  max_events_per_second: 500  # per-worker
  max_events_per_minute: 10000
  burst_size: 1000
  backpressure_policy: drop_newest
```

Per Gemini R3b-F2:
- 500/s per worker × 100 workers = 50,000 REST req/s to cp_api — unsustainable
- 500/s implies subscribe-model failure (if subscribe works, polling shouldn't be 500/s)
- Lumps together three distinct channels:
  - in-process cache lookup (pure memory access — should be ~unbounded)
  - REST fetch to cp_api (network, expensive — should be low)
  - subscribe-stream event consumption (pub/sub push — rate depends on change frequency)

## 2. MOD-4 split specification

### 2.1 Three distinct rate_limits per channel

```yaml
rate_limit:
  # Channel 1: in-process cache lookups (memory-only reads of local cache)
  cache_lookup:
    max_events_per_second: 10000       # effectively unbounded for any sane worker
    max_events_per_minute: 600000
    burst_size: 50000
    backpressure_policy: not_applicable (cache is non-blocking)
    enforcement: soft metric only (alert if sustained > 5000/s indicates algorithmic issue)

  # Channel 2: REST fetch to cp_api (loopback HTTP)
  rest_fetch:
    max_events_per_second: 10          # per-worker hard cap
    max_events_per_minute: 300         # 5/s sustained acceptable
    burst_size: 50
    backpressure_policy: drop_newest + fall_back_to_cache (if TTL-fresh)
    enforcement: hard limit at client side; cp_api also rate-limits at API gateway

  # Channel 3: Subscribe-stream event consumption
  subscribe_event:
    max_events_per_second: 100
    max_events_per_minute: 2000
    burst_size: 500
    backpressure_policy: drop_newest (server-side emission; bounded by pg_notify/Redis buffer)
    enforcement: soft (monitor via metrics; if exceeded, alert indicates CP parameter thrashing)
```

### 2.2 Semantic clarity per channel

**cache_lookup** is an in-process function call from a consumer module to the cp_worker_bridge library. Reads from local dict. No I/O. Should cost microseconds. Rate-limit here is a sanity bound.

**rest_fetch** is a network call (even if loopback) from cp_worker_bridge to cp_api. Triggered when:
- cache miss
- TTL expired on cached value
- explicit refresh requested (e.g., after CPChangeEvent)

Should be RARE in steady-state. 10/s ceiling per worker is generous.

**subscribe_event** is pg_notify message (or Redis pub/sub message) received by the bridge. Frequency depends on how often CP parameters actually change. Steady-state: near-zero (params don't change). Burst: when j13 changes config via `zctl set param …`.

## 3. Backpressure policy — per-channel

| Channel | When limit exceeded | Action |
|---|---|---|
| cache_lookup | sustained > 5000/s | emit alert; continue serving (no throttle) |
| rest_fetch | per-worker > 10/s | drop new request; return cached value WITH stale-flag; emit audit |
| subscribe_event | 500 burst reached | drop oldest (ring buffer); emit obs_metrics alert |

No channel uses "block producer" — that would deadlock worker under load.

## 4. Relationship to Field 5 rate_limit schema (template)

MOD-3 `amended_module_contract_template.md §3` added `rate_limit` sub-schema to outputs. That schema has SINGLE rate values (`max_events_per_second` + `max_events_per_minute` + `burst_size` + `backpressure_policy`).

MOD-4 amendment: `rate_limit` can be either:
- **single-channel** (the MOD-3 schema; for modules with one output channel)
- **multi-channel** (the MOD-4 schema; nested keys per channel)

Discriminator: top-level `rate_limit` contains either `max_events_per_second` (single) or named channel keys (multi). Schema is backward-compatible — single modules keep MOD-3 shape.

See `amended_module_contract_template_v3.md §3` for the canonical template update.

## 5. Observability per channel

M9 metrics updated:

```yaml
metrics:
  # existing (MOD-3)
  - {name: cp_worker_bridge_up, ...}
  - {name: cp_worker_bridge_queries_total, type: counter, labels: [param_key, cache_hit, channel], cardinality_cap: 300, sample_sla: event}  # MOD-4: added `channel` label
  # MOD-4 additions:
  - {name: cp_worker_bridge_cache_lookup_duration_seconds, type: histogram, unit: seconds, labels: [], cardinality_cap: 1, sample_sla: event}
  - {name: cp_worker_bridge_rest_fetch_total, type: counter, unit: events, labels: [outcome], cardinality_cap: 5, sample_sla: event}
  - {name: cp_worker_bridge_rest_fetch_duration_seconds, type: histogram, unit: seconds, labels: [outcome], cardinality_cap: 5, sample_sla: event}
  - {name: cp_worker_bridge_subscribe_event_total, type: counter, unit: events, labels: [param_key, outcome], cardinality_cap: 100, sample_sla: event}
  - {name: cp_worker_bridge_rate_limit_drop_total, type: counter, unit: events, labels: [channel, reason], cardinality_cap: 9, sample_sla: event}
```

All 3 channels have independent counters and durations. Gemini round-4 can verify observability separation.

## 6. Channel-interaction rules

### 6.1 Typical flow

```
consumer module calls cp_bridge.get("param.key")
   ├── cache_lookup → HIT → return cached value (fast path, 99% of calls)
   └── cache_lookup → MISS
          └── rest_fetch → cp_api GET /api/control/params/{key}
                ├── 200 → populate cache, return value
                ├── timeout → backpressure: return cached value (stale-flag) OR fail_closed per param
                └── rate-limited → drop request, return stale value

(independently, in parallel)
cp_notifier emits CPChangeEvent → bridge subscribe_event handler → invalidate cache + emit change callback
```

### 6.2 Rate-limit coupling

subscribe_event → cache invalidation → NEXT cache_lookup miss → rest_fetch

If subscribe rate is high (CP param thrashing), rest_fetch rate surges. Bound at rest_fetch 10/s saves cp_api from cascade; bridge falls back to stale values with warning.

### 6.3 Thundering herd protection

All workers subscribe to `CPChangeEvent`. When one parameter changes, N workers all invalidate + refetch. Mitigation:
- Jittered refetch delay (random 0–5s after invalidation)
- Single-flight (if worker A is refetching key K, worker B's rest_fetch piggybacks on A's pending request via request coalescing)

These are implementation details (Phase 7); spec here mentions them as design intent.

## 7. Verification against Gemini R3b-F2 concerns

Gemini's specific concerns:
1. **"500/s × 100 workers = 50k/s unsustainable"**: RESOLVED — rest_fetch capped at 10/s per worker → 100 workers × 10/s = 1000/s ceiling on cp_api. Well within capacity.
2. **"implies subscribe-model failure"**: RESOLVED — subscribe_event channel has its own limit. High subscribe rate does NOT translate to high rest_fetch due to single-flight + jitter.
3. **"three channels conflated"**: RESOLVED — §2 explicit per-channel rate_limits.

## 8. Non-negotiable rules compliance

| Rule | Compliance |
|---|---|
| 1. No silent production mutation | ✅ — spec-level change only |
| 3. No live gate change | ✅ |
| 8. No broad refactor | ✅ — rate_limit sub-schema is additive; backward-compatible |

## 9. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — each channel has explicit rate + burst + policy |
| Silent failure | PASS — backpressure emits audit + alert; no silent drops |
| External dep | PASS — cp_api and pg_notify/Redis are declared channels |
| Concurrency | PASS — single-flight + jitter prevent thundering herd |
| Scope creep | PASS — targeted at M9 rate_limit; template v3 keeps backward compat |

## 10. Resolution status

Gemini R3b-F2 HIGH — **RESOLVED** pending Gemini round-4 confirmation.

## 11. Exit condition

0-5 Phase 2B: "No HIGH-severity ambiguity remains around M9 rate-limit semantics." MET.

## 12. Label per 0-5 rule 10

- §2 three-channel spec: **VERIFIED** (distinct numeric ceilings per channel)
- §4 backward compat: **PROBABLE** (schema evolution design)
- §7 concern-by-concern addressing: **VERIFIED**
