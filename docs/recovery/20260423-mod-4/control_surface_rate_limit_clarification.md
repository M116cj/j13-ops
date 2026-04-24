# Control Surface Rate-Limit Clarification — MOD-4 Phase 2B

**Order**: `/home/j13/claude-inbox/0-5` Phase 2B deliverable
**Produced**: 2026-04-23T09:58Z
**Purpose**: Update `control_surface_matrix.md` + `control_plane_blueprint.md` references to reflect M9 three-channel rate-limit split.

---

## 1. Changes to `control_surface_matrix.md`

Existing §3 Validation / gate controls list does NOT include rate-limit surfaces (those live in consumer module contracts, not CP). No change.

Existing §4 Search controls: unchanged.

**New additions to §3 System controls** (per MOD-4 M9 updates):

| Surface key | Class | Owner module | Decision rights (§5 row) | Audit tier |
|---|---|---|---|---|
| `cp_bridge.rest_fetch.single_flight_enabled` | P (bool) | cp_worker_bridge | "System" (auxiliary) | standard |
| `cp_bridge.rest_fetch.jitter_ms` | P (int) | cp_worker_bridge | "System" | standard |

Existing `cp_bridge.cache.ttl_seconds` + `cp_bridge.stale.max_age_seconds` + `cp_bridge.fail_closed_default` already covered.

## 2. Changes to `control_plane_blueprint.md` §4 Functional scope

§4.1 System controls — add:
- cp_bridge rest_fetch single-flight toggle (default true)
- cp_bridge rest_fetch jitter_ms (default 500)

§5 Decision-rights matrix — no new rows; `cp_bridge.*` keys already under "Worker counts" adjacent authority (gov_contract_engine).

## 3. Rate-limit governance boundary

**Important distinction**: Rate-limits themselves are not CP parameters; they are declared in the module contract (M9's `outputs.rate_limit` sub-schema). They are:
- **Committed at Gate-B.B.1 schema validation time** (not runtime-tunable)
- **Revised via contract_version bump** (requires ADR + Gemini review)

CP surfaces EXPOSE observability of rate-limit breaches (via `cp_worker_bridge_rate_limit_drop_total` metric) but do NOT expose tuning controls. This is deliberate:
- If rate limits were CP-tunable, an operator could accidentally raise a limit and overwhelm cp_api
- Making them contract-bound forces code review + adversarial review before change

## 4. Observability surface

Via obs_metrics (dashboards, alerts):
- `cp_worker_bridge_rate_limit_drop_total{channel, reason}` — sourced from M9
- `cp_worker_bridge_rest_fetch_total{outcome}` — enables per-channel throughput tracking
- `cp_worker_bridge_single_flight_coalesce_total` — efficiency metric

Alert rules (to be authored in obs_metrics Phase 7):
- `rate(cp_worker_bridge_rate_limit_drop_total{channel="rest_fetch"}[5m]) > 0.5` → WARN
- `rate(cp_worker_bridge_rate_limit_drop_total{channel="subscribe_event"}[5m]) > 1` → WARN (subscribe drops are usually benign but warrant visibility)

## 5. Cross-reference updates

Files referencing M9 rate_limit:
- `amended_cp_worker_bridge_contract.md` (MOD-4) — authoritative new shape
- `control_plane_blueprint.md §7.1` parameter_entry schema — single_flight + jitter keys added to the existing `cp_bridge.*` namespace (see `amended_control_plane_blueprint_v3.md` for full patch)
- `modular_target_architecture.md §6` cross-module contracts — `ParameterValue` contract now implicitly multi-channel; contract NAME is unchanged (semantics unchanged from consumer's perspective)

No README/consumer-facing change — the rate-limit split is internal to M9's library implementation; consumers still call `cp_bridge.get()` normally.

## 6. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 9. No black-box control surface | ✅ — rate-limits are contract-bound, not hidden |
| 10. Labels applied | ✅ |

## 7. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — observability surfaces enumerated |
| Silent failure | PASS — rate-limit breaches emit metrics + alerts |
| External dep | PASS — no new external dep |
| Concurrency | PASS — single-flight prevents thundering herd |
| Scope creep | PASS — cross-doc updates only |

## 8. Label per 0-5 rule 10

- §1-§2 matrix additions: **VERIFIED**
- §3 governance boundary: **VERIFIED** (deliberate design choice)
- §4 observability: **PROBABLE** (alert rules Phase 7)
- §5 cross-refs: **VERIFIED**
