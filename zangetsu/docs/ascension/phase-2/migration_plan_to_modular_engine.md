# Zangetsu — Migration Plan to Modular Engine (Phase 2)

**Program:** Ascension v1 Phase 2
**Date:** 2026-04-23
**Status:** DESIGN.
**Scope:** strategy only. Concrete per-patch queue is Phase 7.

---

## §1 — Prerequisites (must be done before any migration patch)

1. **D-01 BLOCKER**: Control Plane skeleton LIVE (at least read-API + Postgres schema).
2. **CS-05 BLOCKER mitigations**: pg_stat_statements audit + schema-hash attestation cron.
3. **Baseline snapshots**: current production metrics captured for before/after diff.
4. **Rollback discipline**: each migration patch carries a verified rollback.
5. **Gemini + Codex team ready** for per-patch adversarial + implementation.

---

## §2 — Staging (high-level phases)

| Stage | Name | Goal | Exit |
|---|---|---|---|
| S0 | Control Plane bootstrap | CP read-API + param-registry live in SHADOW | all params readable via CP; no writes yet |
| S1 | Parameter consolidation | Merge Cluster A thresholds into one registry | §D-03 drift closed; shim consumers |
| S2 | Kernel extraction | Kernel module consolidated from 3 orchestrators | D-02 drift closed |
| S3 | Gate registry | Unify §4 gate authors | D-08 drift closed |
| S4 | Search pluggability | search_gp behind SearchEngine contract; stub LGBM peer | D-07 drift closed at interface level |
| S5 | Evaluation contracts | Evaluators behind contract | D-05 CD-14 becomes contract |
| S6 | Output contracts | Publishers behind contract | D-09 drift closed |
| S7 | Observability | Metric export + reconciler crons live | D-10, D-11 drift closed |
| S8 | Data layer | Schema registry + integrity attestation | D-13, D-21 drift closed |
| S9 | Test coverage | Unit tests per module; contract conformance | D-14 drift closed |
| S10 | Cleanup | D-04 Policy wiring (or retirement), D-20 cron removal, D-22 Numba versioning | hygiene drift closed |

Each stage has its own ADR + rollback + before/after evidence.

---

## §3 — Ordering rules

1. S0 must land first — everything else depends on CP.
2. S1 and S2 may run in parallel once S0 is SHADOW.
3. S3 blocks S4 (search needs gate outcomes).
4. S5 blocks S6 (publisher needs metrics schema).
5. S7 runs as soon as S0 finishes (observability hardens every step).
6. S8 can run parallel to any of S1-S5 (data is a leaf).
7. S9 runs continuously from S1 onwards.
8. S10 runs last.

---

## §4 — Migration tactics

### §4.1 Shim pattern
For each subsystem being migrated, write a shim that exposes the NEW contract interface on top of the CURRENT implementation. Downstream consumers migrate to contract; upstream impl unchanged. Then swap impl.

### §4.2 Dual-write during cutover
For state-holding subsystems (DB tables, Redis keys), dual-write OLD + NEW format during migration window. Once consumers stabilized on NEW, drop OLD.

### §4.3 Tier advancement
Per subsystem: OFF → SHADOW → CANARY → FULL. Minimum durations:
- SHADOW: 24h of clean behavior + Gemini pass
- CANARY: 72h with metric parity +/- 2%
- FULL: only after j13 sign-off

### §4.4 Rollback first
Every patch proof:
1. Define rollback command.
2. Test rollback in shadow worktree.
3. Only then apply.

---

## §5 — Per-stage detail (summary; Phase 7 owns concrete patches)

### S0 — Control Plane bootstrap
- Create Postgres schema `control_plane.*`
- Create CP service (FastAPI, Postgres + Redis backends)
- Expose read-only endpoints
- Seed registry from scattered_config_map.md
- Acceptance: `GET /api/control/params` returns N entries matching known scattered config

### S1 — Parameter consolidation
- For each parameter in `scattered_config_map.md`:
  - Ensure CP holds canonical value + lineage
  - Add shim in code to consult CP with fallback to current behavior
  - Warn on fallback usage
- Acceptance: 7 days with zero fallback warnings → canonical is sole source

### S2 — Kernel extraction
- Move `claim_champion`/`release_champion`/`reap_expired_leases` into `kernel_state` module
- Orchestrators import from kernel_state instead of shared_utils
- Consolidate main loops into kernel_dispatcher
- Acceptance: all 3 orchestrators run under kernel_dispatcher without behavior change

### S3 — Gate registry
- Extract gate_a2/a3/a4/promote into gate_contract-conforming implementations
- admission_validator kept in DB but wrapped by gate_admission
- Calcifer bridge becomes gate module
- Acceptance: GateOutcomeContract emitted for every rejection with reason_code + decisive_gate

### S4 — Search pluggability
- SearchEngine interface defined
- search_gp becomes contract-conforming peer
- search_lgbm scaffold with adapter contract (no live results yet)
- Acceptance: CP config can route to search_gp or search_lgbm; shadow runs show parity

### S5 — Evaluation contracts
- Evaluator interface
- eval_a2_holdout made explicit (no more hardcoded `"holdout"` key assumption)
- cost_model consolidated
- Acceptance: MetricsContract populated for every eval path

### S6 — Output contracts
- Publisher interface
- pub_db + pub_snapshot + pub_telegram as contract-conforming sinks
- `zangetsu_status` VIEW versioned
- Acceptance: all output paths accept AlertContract / PublisherContract envelopes

### S7 — Observability
- obs_metrics (Prometheus endpoint)
- obs_freshness for XPD-01/02 + /tmp/*.md consumption
- gov_reconciler crons for every BL-F-### detection
- Acceptance: `detection_coverage.rules_with_active_detection` advances from 0 to N

### S8 — Data layer
- DataProvider contract
- data_schema_registry
- Schema-hash attestation cron (D-21)
- Acceptance: D-13, D-21 detection signals arm

### S9 — Test coverage
- Unit tests per module (contract conformance)
- Golden fixtures for evaluators
- Regression suite per migration patch
- Acceptance: coverage ≥ target per module

### S10 — Cleanup
- Wire Policy Layer v0 (or retire)
- Remove deprecated cron entries (D-20)
- Add Numba cache versioning (D-22)
- Remove shims from S1

---

## §6 — Blocking gates (end-of-Phase-2)

Phase 2 is considered complete when:
- Control Plane blueprint approved
- Modular target architecture approved
- Module boundary map agreed with Codex (implementation lead)
- Module registry schema committed
- Console capability spec agreed with j13
- Black-box adapter contract approved
- Migration plan (this doc) approved

All design docs, all ACCEPT-ed by Gemini, committed to GitHub under `zangetsu/docs/ascension/phase-2/`.

---

## §7 — Success criteria (end-of-migration)

Per Ascension §14:
1. Zangetsu scientific truth verified end-to-end (addressed across S2+S5+Phase 4)
2. System can explain why candidates are rejected (S3 gate registry + S7 observability)
3. Deployable path trustworthy (S6 + S7)
4. Architecture is coherent modular engine (all S stages done)
5. Parameters governable from single CP (S0+S1)
6. Black-box wrapped with contracts (Phase 4+ when peers land; pattern ready)
7. Top hotspots improved (Phase 5 intersects)
8. Monitoring covers health / pipeline / truth (S7)
9. Migration concrete, staged, rollback-safe (this doc + Phase 7)
10. Minimal human micromanagement (S0 CP + S3 gates + S7 reconcilers)

---

## §8 — Non-goals

- NOT a per-patch schedule (Phase 7 owns).
- NOT specifying calendar dates (depends on R2-N4 outcome + Phase 4 verdict).
- NOT dictating code layout within modules (implementation).
