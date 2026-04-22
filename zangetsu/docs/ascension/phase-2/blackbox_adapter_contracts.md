# Zangetsu — Black-Box Adapter Contracts (Phase 2)

**Program:** Ascension v1 Phase 2
**Date:** 2026-04-23
**Status:** DESIGN.
**Scope change note (from v2):** L10 was demoted from top-level layer to pattern (`modular_target_architecture.md §L9 pattern`). This doc specifies the pattern's contract shape.

---

## §1 — Purpose

When ≥1 black-box component (LGBM model, external LLM agent, external strategy signal, etc.) is wrapped into Zangetsu, the adapter MUST expose explicit contracts so that the system remains **white-box controllable** even when the model itself is opaque (Ascension §3.6).

---

## §2 — Mandatory contract fields

Every adapter MUST expose:

```
adapter:
  id: <canonical_name>
  target_module: <which L4/L5 module this adapter is applied inside>
  blackbox_kind: ml_model | external_agent | external_signal | external_service
  blackbox_identity:
    name: <model_name or service_id>
    version: <semver or hash>
    provenance: <how obtained>
    integrity_hash: <sha256 of weights / binary / api response schema>

  # Input
  input_schema: <Contract ref> # must match upstream producer's contract
  input_validation: <rule spec>

  # Output
  output_schema: <Contract ref> # must match downstream consumer's contract
  output_validation: <rule spec>

  # Config surface
  config_schema: <yaml schema>
  config_defaults: <map>
  config_via_CP: bool # true if CP is source

  # State surface
  state_schema: <yaml schema>
  state_location: <where persisted — Postgres / Redis / file>

  # Health
  health_endpoint: <url or probe fn>
  health_timeout_ms: <int>
  expected_latency_p95_ms: <int>

  # Version identity
  version_visible_via: <CP read path>
  bump_policy: <how to upgrade — ADR required>

  # Failure modes
  failure_modes:
    - name: <failure>
      detection: <how caught>
      recovery: <what happens>

  # Rollback surface
  rollback_path: <command or runbook>
  rollback_time_estimate: <duration>

  # Observability
  metrics_emitted: [<list>]
  logs_emitted: <structure>

  # Auth / isolation
  isolation_boundary: process | container | vm | none
  auth_required: bool
  secrets_referenced: [<env names>]
```

---

## §3 — Acceptance rules

An adapter is ACCEPTED into registry iff:

1. All fields above are populated with non-placeholder values.
2. Input + output contracts match the upstream / downstream module's declared contracts.
3. Integrity hash is verifiable at load time.
4. Failure modes listed cover: upstream-unreachable, malformed-response, rate-limited, authentication-failure, schema-drift, latency-blowup, **non-determinism_detected** (v2 per Gemini §F.2 — replay-fixture divergence), **resource_exhaustion** (v2 — RSS / CPU thresholds).
5. Rollback path is tested in shadow-mode before going CANARY.
6. Health endpoint is queried by L8.O freshness monitor.
7. Adapter is registered in `module_registry_spec.md` entry with `blackbox_pattern_applied: true` + `adapter_contract_ref: <path>`.
8. Gemini adversarial has signed off.
9. ADR exists.

---

## §4 — Example scaffold (illustrative only, no implementation)

For an LGBM adapter (addressing D-07 single-search):

```yaml
adapter:
  id: search_lgbm
  target_module: search.lgbm
  blackbox_kind: ml_model
  blackbox_identity:
    name: lightgbm
    version: 4.6.0
    provenance: pip install lightgbm==4.6.0
    integrity_hash: sha256:<pinned-wheel-hash>
  input_schema: CandidateFeaturesContract
  output_schema: CandidateContract
  config_schema:
    n_estimators: {type: int, default: 500, range: [50, 5000]}
    learning_rate: {type: float, default: 0.05, range: [0.001, 0.3]}
    max_depth: {type: int, default: 6, range: [3, 15]}
    early_stopping_rounds: {type: int, default: 50}
  config_via_CP: true
  state_schema:
    training_fingerprint: sha256
    last_trained_at: timestamp
  health_endpoint: internal probe fn returning {ready, last_predict_latency_ms}
  failure_modes:
    - {name: upstream_data_unavailable, detection: data_provider health probe, recovery: skip cycle}
    - {name: model_not_loaded, detection: predict() throws, recovery: reload from last checkpoint}
    - {name: latency_blowup, detection: p95 > 5s, recovery: circuit-breaker open for 60s}
    - {name: schema_drift, detection: input shape mismatch, recovery: fail-closed}
    # v2 — added per Gemini §F.2:
    - {name: non_determinism_detected, detection: replay N (default 50) predictions on fixed-input fixture at startup + every 1h; flag if any two runs diverge beyond float-epsilon, recovery: freeze adapter to last-known-good checkpoint + RED Telegram}
    - {name: resource_exhaustion, detection: process RSS > config.max_rss_mb OR CPU sustained > config.max_cpu_pct for 60s, recovery: circuit-breaker + degrade to peer search path + RED Telegram}
  rollback_path: "CP: set rollout_tier=OFF; remove module from L4 search_engine registry"
  metrics_emitted: [predict_latency_ms, prediction_count, null_rate, feature_coverage]
```

---

## §5 — When the pattern should NOT be used

- If the wrapped component has full source accessible + is internally modifiable, it's not a black-box — use regular module shape.
- For experimental shadow probes (shorter than 14 days), use `.claude/scratch/` workflow without formal adapter.
- If the component's contract fields can't be enumerated, DO NOT wrap — refuse integration.

---

## §6 — Consumer responsibilities

When an L4/L5 module registers `blackbox_pattern_applied: true`:
- L8.O monitors the `health_endpoint` at the declared cadence
- gov_reconciler checks integrity_hash matches pinned value on load
- gov_contract_engine refuses mutation if adapter_contract is missing fields
- pub_alert wires any adapter failure_mode alert

---

## §7 — Relationship to Ascension §3.6

The adapter pattern is the ONLY way to have a black-box in Zangetsu per charter §3.6:
> "Black-box internal engines are allowed. Black-box control surfaces are forbidden."

The adapter turns a black-box into a white-box-controllable component.

---

## §8 — Non-goals

- NOT wrapping every existing module — only true black-boxes need this.
- NOT specifying specific ML frameworks (that's implementation).
- NOT a model versioning service — adapter refers to external versioning.
