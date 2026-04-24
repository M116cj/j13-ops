# Modular Target Architecture — Zangetsu MOD-1

**Order**: `/home/j13/claude-inbox/0-2` Phase 5 deliverable
**Produced**: 2026-04-23T03:25Z
**Author**: Claude (Lead)
**Base authoritative source**: `zangetsu/docs/ascension/phase-2/modular_target_architecture.md` (Gemini round-2 ACCEPTED v2.1).
**Status**: MOD-1 Phase 5 exit criterion MET — one coherent target engine architecture (not a list of ideas).

---

## §MOD-1.A — Envelope

Phase 5 asks: what will Zangetsu look like after modularization? How do modules communicate? Which layers own which state? How is recovery isolated from discovery? How does governance stay ABOVE the engine?

Answers in the authoritative doc below (§1–§9) plus these MOD-1 cross-links:

---

## §MOD-1.B — State / config / control ownership pointers

Per 0-2 Phase 5 required contents:
- **state ownership model** — see `state_ownership_matrix.md`
- **config ownership model** — CP is the canonical store per `control_plane_blueprint.md §2 req 1`; reads via `cp_worker_bridge`; fallbacks warn
- **control ownership model** — see `control_surface_matrix.md` (59 surfaces × 6 classes × decision-rights matrix)
- **recovery/discovery separation** — recovery lives in Track R (L2 kernel + L6 gates enforcing honest rejection); discovery lives in Track 3 (L4 search_contract with pluggable peers behind L9 adapter pattern when black-box). Neither depends on the other's module runtime state. Gate-B forbids migration PRs that mix both.
- **black-box adapter model** — see `module_boundary_map §MOD-1.B Module 7 adapter_contract` + `phase-2/blackbox_adapter_contracts.md`
- **rollout / migration principles** — see `modularization_execution_gate.md §2-§4` (Gate-A/B/C) + `phase-2/migration_plan_to_modular_engine.md`

---

## §MOD-1.C — Label per 0-2 rule 10

- §1-§8 target architecture: **PROBABLE** (Ascension-accepted design; becomes VERIFIED module-by-module as Phase 7 migrations land + Gate-B passes)
- §4 process consolidation table: **PROBABLE** (concrete process layout is Phase 7 decision)
- §7 identity preservation: **VERIFIED** (A1→A5 arena, broad/semi-random search, gates remain explicit — all preserved per Charter §2.3)

---

## §MOD-1.D — Exit criterion

MOD-1 Phase 5 exit: *"The team has one coherent target engine architecture, not a list of ideas."*

Met by: §2 module topology diagram + §3 module list per layer + §4 process consolidation + §5 data stores + §6 cross-module contracts + §7 identity preservation + state/config/control ownership cross-links (§MOD-1.B above).

Proceed to Phase 6 (`control_plane_blueprint.md` + `modularization_execution_gate.md`).

---

## §MOD-1.E — Authoritative content (preserved from Ascension Phase-2 v2.1)

---

# Zangetsu — Modular Target Architecture (Phase 2)

**Program:** Ascension v1 Phase 2
**Date:** 2026-04-23
**Author:** Claude Lead
**Status:** DESIGN. Implementation is Phase 7.
**Zero-intrusion:** planning-only.

---

## §1 — Purpose

Refine Phase 1's `intended_architecture.md` 9-layer model into concrete, compose-able **modules**. Each module has an explicit contract, lives in a specific repo location, and integrates with the Control Plane (from `control_plane_blueprint.md`).

---

## §2 — Module topology

```
                   ┌───────────────────────────┐
                   │    L1 Control Plane       │
                   │  (Postgres + Redis + API) │
                   └─────────┬─────────────────┘
                             │
            ┌────────────────┼─────────────────────────────┐
            │ reads params   │ publishes state             │ writes audit
            ▼                ▼                             ▼
  ┌──────────────┐  ┌──────────────────┐         ┌─────────────────────┐
  │ L2 Kernel    │  │ L3 Data Input    │         │ L8 Integrity & Gov  │
  │  (engine     │  │ (data_collector  │         │  (observability +   │
  │   core)      │  │  + parquet +     │         │   governance)       │
  └──────────────┘  │  schema registry)│         └─────────────────────┘
         │          └──────────────────┘                  ▲
         │                    │                           │
         ▼                    ▼                           │
  ┌──────────────────────────────────────────────────────┘
  │ L4 Research (pluggable SearchEngine)   L5 Evaluation   L6 Gate    L7 Output
  │ GP | LGBM | factor-zoo (behind contract)
  │
  │          L9 Black-box Adapter Pattern — applied inside L4/L5 when needed
```

---

## §3 — Modules (by layer)

### L1 Control Plane
- **cp_api** — FastAPI service exposing `/api/control/*` endpoints
- **cp_storage** — Postgres `control_plane.*` schema + Redis caches
- **cp_audit** — append-only audit log writer
- **cp_notifier** — `pg_notify` + Redis pub/sub fan-out
- **cp_cli** — `zctl` command-line client
- **cp_worker_bridge** — library consumed by workers to pull/subscribe

### L2 Engine Kernel
- **kernel_state** — single atomic state-machine; owns arena transitions
- **kernel_lease** — lease manager (acquire + reap)
- **kernel_dispatcher** — routes work to L4/L5/L6 based on state
- **kernel_logger** — structured event emit to L8.O

### L3 Data Input
- **data_provider** — `DataProvider` contract implementations (Binance now; pluggable)
- **data_schema_registry** — per-source schema + version + hash manifest
- **data_health** — per-source freshness/health endpoint
- **data_store** — parquet-backed read layer

### L4 Research (pluggable SearchEngine)
- **search_contract** — abstract `SearchEngine` interface
- **search_gp** — DEAP-based GP implementation (current default)
- **search_lgbm** — LGBM implementation (currently offline; Phase 4+ re-integration)
- **search_factor_zoo** — legacy factor discovery (DEPRECATED, flag-guarded)
- **search_hand_seed** — cold-start + hand-seed workflow (needs re-scoping; D-23 symptom)
- **primitive_registry** — indicator + operator + pset catalogue (replaces `alpha_primitives.py` sprawl)

### L5 Evaluation
- **eval_contract** — `Evaluator` interface (input = candidate, output = Metrics)
- **eval_a1** — A1 (in-evolution) fitness compute
- **eval_a2_holdout** — A2 OOS holdout (CD-14 as contract, not hotfix)
- **eval_a3_train** — A3 legacy train evaluation
- **eval_a4_gate** — A4 multi-metric gate
- **eval_a5_tournament** — A5 tournament + ELO
- **backtester** — backtester engine (kept internal; has contract on bt.run)
- **cost_model** — per-tier cost lookup (single source from CP)

### L6 Gate
- **gate_registry** — consolidated threshold registry (all 6 distinct active values unified)
- **gate_contract** — abstract `Gate` interface
- **gate_admission** — admission_validator wrapper (PL/pgSQL body + prosrc hash attest)
- **gate_a2/a3/a4/promote** — individual gate implementations
- **gate_calcifer_bridge** — consumes Calcifer RED/GREEN state

### L7 Output
- **publish_contract** — `Publisher` interface
- **pub_db** — DB-table writer (champion_pipeline_fresh)
- **pub_view** — `zangetsu_status` VIEW as versioned artefact
- **pub_snapshot** — `/tmp/zangetsu_live.json` writer (consolidated from cron + snapshot.sh)
- **pub_telegram** — Telegram sink (wraps calcifer/notifier.py)
- **pub_akasha** — AKASHA memory writer
- **pub_alert** — alert bus

### L8 Integrity & Governance
- **L8.O observe**:
  - **obs_metrics** — Prometheus-compatible exporter
  - **obs_logs** — structured log pipeline
  - **obs_view** — zangetsu_status VIEW + derived views
  - **obs_reports** — hourly report generators
  - **obs_freshness** — cross-process file freshness monitors (XPD-01/02)
- **L8.G govern**:
  - **gov_contract_engine** — charter §17 + mutation_blocklist v2 runtime enforcement
  - **gov_reconciler** — POST-violation detection crons (per blocklist `detection` field)
  - **gov_audit_stream** — consumes cp_audit
  - **gov_rollout** — rollout tier state machine
  - **gov_ci_hooks** — pre-commit + pre-receive integrations

### L9 Black-box Adapter Pattern
- applied INSIDE L4/L5 modules when a black-box peer lands
- **adapter_contract** — mandatory wrapper schema (input/output/config/state/health/version/failure/rollback)

---

## §4 — Processes (deployment units)

Consolidation from current 6+ workers → explicit process boundaries:

| Process | Modules hosted | Replaces |
|---|---|---|
| `cp_service` | cp_api, cp_storage binding, cp_audit, cp_notifier | (new) |
| `zangetsu_engine` | kernel_state, kernel_dispatcher, kernel_lease | arena_pipeline, arena23_orchestrator, arena45_orchestrator main loops consolidated |
| `zangetsu_worker_A1` × N | eval_a1 + search_gp (or configured via CP) | arena_pipeline.py workers |
| `zangetsu_worker_A23` × 1 | eval_a2_holdout + eval_a3_train | arena23_orchestrator.py |
| `zangetsu_worker_A45` × 1 | eval_a4_gate + eval_a5_tournament + pub_db DEPLOYABLE writes | arena45_orchestrator.py |
| `data_collector` | data_provider + data_schema_registry + data_health | current data_collector.py cron |
| `observer` | obs_metrics + obs_freshness + obs_reports + gov_reconciler | zangetsu_snapshot cron + hourly reports + r2_n4_watchdog pattern generalized |
| `gov_service` | gov_contract_engine + gov_audit_stream + gov_ci_hooks | Calcifer supervisor (extended) |

---

## §5 — Data stores (consolidated)

| Store | Use |
|---|---|
| Postgres `zangetsu` schema | champion_pipeline_* tables, admission_validator, VIEWs |
| Postgres `control_plane` schema | CP params, audit, rollout, decision-rights |
| Redis | sessions, activity, shortcuts, task queue, job status, heartbeats, TTL locks, pub/sub |
| Parquet `data/` | OHLCV, funding, OI |
| AKASHA | cross-session memory chunks + compact operations |
| JSON files `/tmp/*.json` | ephemeral snapshots only (zangetsu_live, calcifer block); no critical state |

---

## §6 — Cross-module contracts (category names only; concrete in Phase 7)

- `DataProviderContract`
- `CandidateContract` (L4 → L6/L2)
- `MetricsContract` (L5 → L6)
- `GateOutcomeContract`
- `ChampionStateContract` (L2 internal)
- `PublisherContract`
- `AlertContract`
- `AuditContract`
- `AdapterContract` (for L9 pattern)
- `OrderExecutionContract` (future, OUT-06)

---

## §7 — Identity preservation checklist

Per Ascension §2:
- ✅ Arena pipeline (A1→A5) preserved as L2 kernel state machine
- ✅ Broad / semi-random search preserved (GP is primary; LGBM / factor-zoo are peers behind contract)
- ✅ NOT hand-crafted strategy framework (gates remain explicit)
- ✅ NOT static factor ranking (discovery pressure retained in search_* modules)

---

## §8 — Success metric for target architecture

Each module must reach Ascension §3.4 completeness (10/10 fields). Migration plan in `migration_plan_to_modular_engine.md` defines how each current subsystem gets there.

Currently average is 5.8/10 (Phase 1 §3 rollup). Target: average ≥ 8/10 after Phase 7, weighted-by-criticality per L8.G scheme.

---

## §9 — Non-goals

- NOT implementing any module here.
- NOT selecting specific libraries (FastAPI vs Flask; asyncpg vs psycopg; etc.) — Phase 7.
- NOT listing concrete filenames — `module_registry_spec.md` does that at structure level only.
- NOT a port assignment plan — Phase 7.
