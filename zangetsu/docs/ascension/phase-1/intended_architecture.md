# Zangetsu — Intended Architecture

**Program:** Zangetsu Engine Ascension v1
**Phase:** 1
**Date:** 2026-04-23
**Author:** Claude Lead
**Status:** BASELINE — this is what Zangetsu SHOULD be once Ascension Phase 2 migration completes.
**Zero-intrusion:** pure documentation.

---

## §1 — Mission statement (preserved from Ascension spec §1-2)

Zangetsu is an **Alpha Operating System** that discovers, validates, and deploys trading strategies through an arena-based discovery pipeline with scientifically honest gates. The architecture must be:

- coherent engine platform (not a fragmented script collection)
- fully modular (every subsystem has explicit boundaries)
- control-plane-governed (not scattered env / yaml / literal drift)
- black-box compatible with white-box control surface
- observable, testable, rollback-safe

Identity to preserve (per §2):
- Arena-based discovery (A1 → A2 → A3 → A4 → A5 → Deployable)
- Broad / semi-randomized search (GP + bayesian + factor-zoo options remain)
- NOT a hand-crafted strategy framework
- NOT static factor ranking without discovery pressure

---

## §2 — Target layered architecture (10 layers per spec §6)

### L1 — Control Plane Layer
**Purpose**: single point of truth for every parameter, mode, schedule, kill switch, rollout state.
**Responsibilities**: serve console + bot + CLI reads/writes; enforce decision rights; hold distributed lock on writes.
**Inputs**: auth + command from miniapp / CLI / SDK.
**Outputs**: state mutations to L2-L10 subsystems + audit trail.
**Configs**: controls schema (engine mode, worker counts, budgets, schedules, kill switches, rollout tiers).
**States**: per-mode state machine (safe / shadow / canary / production), rollout progress, last-actor.
**Metrics**: command latency, conflict rate, approval queue depth.
**Failure modes**: distributed-lock failure → read-only; auth failure → reject.
**Test boundary**: mock the subsystems; verify correct dispatch + ordering.
**Replacement boundary**: pluggable auth providers, pluggable storage (Redis or SQL for state).

### L2 — Engine Kernel Layer
**Purpose**: the core orchestrator. Accepts control-plane directives, dispatches to research / evaluation / gate / output. Owns the arena state machine.
**Responsibilities**: arena progression (A1→A5→Deployable), lease management, reap expired leases, rollout gating.
**Inputs**: research-output + evaluation-output + gate-outcomes.
**Outputs**: champion transitions between states (ARENA1_COMPLETE / _PROCESSING / _REJECTED / _ELIMINATED / CANDIDATE / DEPLOYABLE / LIVE).
**Configs**: arena pipeline cadence, lease TTL, retry policies.
**States**: atomic per-champion state (FOR UPDATE SKIP LOCKED + lease_until).
**Metrics**: throughput (alphas/sec), latency per-arena, lease contention, reap frequency.
**Failure modes**: worker crash → lease reaper; DB disconnect → kernel halt + alert.
**Test boundary**: kernel unit tests with stubbed arenas.
**Replacement boundary**: pluggable arena implementations behind a contract.

### L3 — Data Input Layer
**Purpose**: all external data ingress (OHLCV, funding, OI, alt-data).
**Responsibilities**: fetch, validate, dedup, store, serve consumers.
**Inputs**: Binance API, future exchange APIs.
**Outputs**: parquet / arrow tables with schema + version.
**Configs**: source registry, schedule per source, retention policy.
**States**: per-source freshness timestamps, error counts.
**Metrics**: fetch success rate, rows/sec, data-hash collisions, staleness.
**Failure modes**: upstream outage → backoff + stale-flag; schema change → halt + alert.
**Test boundary**: recorded-replay against fixtures.
**Replacement boundary**: pluggable data sources behind DataProvider contract.

### L4 — Research / Search Layer
**Purpose**: produce candidate alphas via configurable search (GP / LGBM / bayesian / manual seed / archive replay).
**Responsibilities**: iterate primitives, propose formulas, evolve populations.
**Inputs**: data from L3; target specification from L5; primitive set from config; search params from L1.
**Outputs**: candidate alphas with provenance (engine, git_commit, config_hash, grammar_hash, fitness_version, seed, epoch, generation, parent_hash).
**Configs**: pset registry, fitness registry, target registry, horizon registry.
**States**: population state, generation counter, archive tier.
**Metrics**: search efficiency (unique candidates / hour), fitness distribution, operator diversity.
**Failure modes**: numeric explosion → circuit-breaker; pset corrupt → halt.
**Test boundary**: shadow-mode candidate generation replay.
**Replacement boundary**: pluggable search strategies behind SearchEngine contract (GP, LGBM, transformer, factor-zoo as peers).

### L5 — Evaluation Layer
**Purpose**: compute honest train/holdout/oos metrics on candidates.
**Responsibilities**: backtest, IC computation, direction-sign verification, cost-adjusted PnL.
**Inputs**: candidates from L4, data from L3.
**Outputs**: metrics vector (IC, PnL, Sharpe, Wilson, trade count, pos_count, direction_sign, regime slice) with explicit train/holdout attribution.
**Configs**: cost model (per-tier bps), slippage, time-slice policy.
**States**: evaluation worker health, cache hit rates.
**Metrics**: evaluation latency, cache hit rate, NaN/inf rate, divergence between worker instances.
**Failure modes**: backtester crash → skip row; holdout missing → hard-fail (CD-14 rule).
**Test boundary**: golden fixtures + IC regression tests.
**Replacement boundary**: pluggable evaluators per horizon / target.

### L6 — Gate Layer
**Purpose**: every rejection layer has explicit meaning; no black-box reject.
**Responsibilities**: signal quality gate / tradeability gate / out-of-sample gate / regime robustness gate / cost-adjusted utility gate / deployment gate.
**Inputs**: metrics from L5.
**Outputs**: pass/fail per gate + reason code + which gate was decisive.
**Configs**: threshold registry (per-gate, per-mode), regime partitioning.
**States**: gate version, threshold revision history.
**Metrics**: rejection distribution per gate, false-positive rate, gate fire frequency.
**Failure modes**: all gates pass → sanity check required (unexpected mass-pass); gate logic bug → freeze promotions.
**Test boundary**: golden pass/fail cases.
**Replacement boundary**: pluggable gates behind Gate contract.

### L7 — Output Layer
**Purpose**: surface champion outputs to consumers (deployable registry, reports, dashboards, alerts).
**Responsibilities**: maintain deployable / historical / live split; generate evidence bundles; publish to dashboard / telegram / miniapp.
**Inputs**: promoted alphas from L2 + metrics from L5.
**Outputs**: deployable card state, ranked tables, evidence JSONs, alert events.
**Configs**: publishing targets, alert thresholds, schema versions.
**States**: per-alpha card state, last-publish timestamp.
**Metrics**: publish latency, subscriber lag.
**Failure modes**: subscriber unreachable → backlog + retry (bounded); schema mismatch → quarantine.
**Test boundary**: fake subscribers + schema validation.
**Replacement boundary**: pluggable sinks.

### L8 — Observability Layer
**Purpose**: expose health / pipeline / truth / search signals; anomaly rules.
**Responsibilities**: collect metrics from L2-L7, expose VIEWs (zangetsu_status), emit Prometheus-like streams, run alert rules, run reconciliation crons (per mutation_blocklist detection entries).
**Inputs**: metrics, logs, state from all layers.
**Outputs**: dashboards, alerts, status JSON snapshots.
**Configs**: alert rule registry, dashboard registry, retention.
**States**: metric cardinality, alert state machine.
**Metrics**: alert lag, false-alert rate, retention compliance.
**Failure modes**: metrics pipeline down → fallback to log-based alerts.
**Test boundary**: replay recorded metric streams.
**Replacement boundary**: pluggable exporters (Prometheus, Loki, ClickHouse).

### L9 — Governance Layer
**Purpose**: enforce contracts at every boundary; audit log; rollback surface.
**Responsibilities**: PR / commit gates (charter §17), mutation blocklist runtime enforcement, rollout sign-off, decision records.
**Inputs**: commit events, pipeline events, operator commands.
**Outputs**: audit log entries, allow/deny verdicts, rollback scripts.
**Configs**: mutation_blocklist.yaml, charter rules, decision-rights matrix.
**States**: current block state (Calcifer RED/GREEN), pending approvals.
**Metrics**: block hits, approval latency, audit coverage.
**Failure modes**: audit down → block writes (fail-closed).
**Test boundary**: rule unit tests + integration via mocked events.
**Replacement boundary**: pluggable policy engines.

### L10 — Black-Box Adapter Layer
**Purpose**: wrap any black-box model / external agent with explicit contract (per spec §3.6).
**Responsibilities**: enforce input/output/config/state/health/version/failure/rollback schemas on wrapped components.
**Inputs**: black-box module reference + contract manifest.
**Outputs**: contract-compliant adapter exposing required surfaces.
**Configs**: per-adapter registration.
**States**: wrapped module version + health ping status.
**Metrics**: adapter overhead, contract violations detected.
**Failure modes**: missing contract field → refuse to register; contract mismatch → quarantine adapter.
**Test boundary**: contract conformance test-suite.
**Replacement boundary**: adapters are inherently pluggable.

---

## §3 — Arena pipeline as L2 kernel state machine (preserved)

```
[L4 research] ──(candidate)──▶ staging.admission_validator (L6 gate)
                                     │
                                     ├── reject → staging.rejected (L7)
                                     └── admit  ──▶ fresh(ARENA1_COMPLETE)
                                                      │
                                                      ▼
                                        L5 A2 eval (holdout OOS)
                                                      │
                                        [L6 A2 gates: few_trades / val_neg / val_sharpe / val_wr / pos_count]
                                                      │
                                 ┌────── reject (fresh.ARENA2_REJECTED)
                                 │
                                 └── pass ──▶ fresh(ARENA2_COMPLETE)
                                                      │
                                                      ▼
                                           L5 A3 eval (train slice legacy)
                                           [L6 A3 gates]
                                                      │
                                 ┌────── reject (fresh.ARENA3_REJECTED)
                                 │
                                 └── pass ──▶ fresh(ARENA3_COMPLETE)
                                                      │
                                                      ▼
                                           L5 A4 eval + [L6 A4 gates]
                                                      │
                                 ┌────── fail (fresh.ARENA4_ELIMINATED)
                                 │
                                 └── pass ──▶ fresh(CANDIDATE)
                                                      │
                                                      ▼
                                           L6 promotion gate (PROMOTE_WILSON_LB, PROMOTE_MIN_TRADES)
                                                      │
                                 ┌────── fail (remain CANDIDATE)
                                 │
                                 └── pass ──▶ fresh(DEPLOYABLE)
                                                      │
                                                      ▼
                                           L7 card activation + A5 tournament
                                                      │
                                                      ▼
                                 fresh(DEPLOYABLE_LIVE / DEPLOYABLE_HISTORICAL)
```

Every arrow has an explicit gate owner (L6) and metric source (L5). No arrow may mutate state without an audit row (L9).

---

## §4 — Required SLAs (for Ascension §6 module health contracts)

| Surface | Target |
|---|---|
| A1 candidate → admission verdict | < 200 ms p95 |
| A2 OOS evaluation | < 2 s per alpha per symbol |
| A3 train-slice evaluation | < 3 s per alpha per symbol |
| A4 gate | < 500 ms |
| Promotion decision | < 1 s |
| Lease reap cycle | every 60 s |
| State-of-truth refresh (zangetsu_status) | < 10 s freshness |
| Deploy block transition latency | < 30 s |

These are TARGETS for the Ascension end-state, not current values.

---

## §5 — Explicit controls (L1 Control Plane surface)

Per spec §5, the control plane must govern:

- **System**: engine mode, safe/shadow/production, worker counts, resource budgets, schedules, kill switches, rollout states
- **Search**: mutation rate, search depth, factor pools, pset selection, exploration/exploitation, horizon sweep, regime partitioning, promotion policy, tournament policy
- **Validation**: replay windows, OOS policies, gate thresholds, cost models, deployment conditions, validation versions, shadow policies
- **Input**: data sources, symbol universes, time windows, feature families, blacklists, whitelists, routing policies
- **Output**: schemas, ranking tables, champion reports, evidence bundles, dashboard feeds, alerts, export targets

None of these should live as hardcoded literals in `services/*.py`, scattered env vars, or orphan yaml files.

---

## §6 — Contracts required at each boundary

For every cross-layer call, an explicit data schema + error schema + backward-compat policy. Contracts live in `zangetsu/contracts/`:

```
zangetsu/contracts/
├── data_schema.yaml          # L3 ↔ L4/L5
├── candidate_schema.yaml     # L4 → L6 (admission) / L2
├── metrics_schema.yaml       # L5 → L6
├── gate_outcome_schema.yaml  # L6 → L2
├── champion_state_schema.yaml# L2 internal transitions
├── alert_schema.yaml         # L8 → L9 / consumers
├── audit_schema.yaml         # L9 append-only log format
└── adapter_contract.yaml     # L10 black-box wrapper schema
```

Phase 2 migration will produce these; Phase 1 lists them as intended artefacts only.

---

## §7 — Non-goals (what intended architecture is NOT)

- Not a monolith. L1-L10 are SEPARATE modules.
- Not a microservices-per-layer. Layers are logical; some can share a process (e.g., L2 + L6 + L9 in the kernel process), others must split (L3 dedicated, L8 external observer).
- Not an async-only framework. Sync where simple, async where warranted.
- Not dependent on Kubernetes / K8s. Lockfile + cron + systemd suffices unless explicitly upgraded.
- Not a dashboard-only improvement project (per Ascension §1).

---

## §8 — Confidence label for this intended architecture

This document is **INTENDED TARGET** (design-time). It is not VERIFIED / PROBABLE / INCONCLUSIVE — those labels apply to the actual-architecture doc. This doc is the aspiration against which drift is measured.

---

## §9 — Phase 1 exit criteria

- `intended_architecture.md` (this doc) ✅ drafted
- `actual_architecture.md` — sibling (forthcoming)
- `architecture_drift_map.md` — diff sibling (forthcoming)
- `subsystem_contracts.md` — per-subsystem purpose/inputs/outputs/config/state/metrics/errors/rollback/tests (forthcoming)
- `scattered_config_map.md` — where configs currently live + duplication (forthcoming)
- `uncontrolled_io_map.md` — IO paths not centrally governed (forthcoming)
- Gemini adversarial → integrate → re-accept

Only once Phase 1 is ACCEPTED does Phase 2 (Architectural Ascension + Modularization) begin.
