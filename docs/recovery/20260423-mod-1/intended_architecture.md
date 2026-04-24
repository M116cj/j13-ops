# Intended Architecture — Zangetsu MOD-1

**Order**: `/home/j13/claude-inbox/0-2` Phase 1 deliverable
**Produced**: 2026-04-23T03:05Z
**Author**: Claude (Lead)
**Base authoritative source**: `zangetsu/docs/ascension/phase-1/intended_architecture.md` (Gemini round-2 ACCEPTED v2.1).
**Status**: MOD-1 Phase 1 exit criterion MET — complete-form Zangetsu is explicit, without ambiguity.

---

## §MOD-1.A — Envelope

MOD-1 Phase 1 asks:
- What is the system supposed to do?
- What are its non-negotiable identities?
- What are its permanent preserved cores?
- What layers must exist in the complete engine?

The authoritative answers live in the embedded full content below (§1–§9), preserved verbatim from the Ascension Phase-1 v2.1 document that Gemini ACCEPTED after round-2 review. This MOD-1 wrapper adds:

- §MOD-1.B — mapping from MOD-1's 10-layer spec to the v2 9-layer merge
- §MOD-1.C — post-0-1 state confirmation (freeze held, R2 authoritative, Calcifer outcome-watch committed)
- §MOD-1.D — label per 0-2 non-negotiable rule 10

---

## §MOD-1.B — Mapping 0-2's 10-layer spec to the chosen 9-layer target

0-2 Phase 1 enumerates 10 layers. The intended architecture below uses 9, explicitly merging 0-2's L8 Observability + L9 Governance into `L8 Integrity & Governance` (sub-modules L8.O + L8.G), and demoting 0-2's L10 Black-Box Adapter from top-level layer to applied pattern `L9 pattern`.

| 0-2 spec layer | Target layer | Rationale |
|---|---|---|
| 1 Control Plane | **L1 Control Plane** | 1:1 |
| 2 Engine Kernel | **L2 Engine Kernel** | 1:1 |
| 3 Data Input | **L3 Data Input** | 1:1 |
| 4 Research / Search | **L4 Research** | 1:1 |
| 5 Evaluation | **L5 Evaluation** | 1:1 |
| 6 Gate | **L6 Gate** | 1:1 |
| 7 Output | **L7 Output** | 1:1 |
| 8 Observability | **L8.O (sub-module of L8)** | merged with 0-2.L9 — governance IS applied policy on observability signals; two layers created an artificial boundary forcing constant rule-engine cross-calls |
| 9 Governance | **L8.G (sub-module of L8)** | merged — see above |
| 10 Black-Box Adapter | **L9 pattern** (applied inside L4/L5) | only GP is active today (D-07 single-search); pattern rather than layer avoids a "ghost layer" (Gemini §A.3) |

All 10 0-2 spec concerns are present. The merge is a structural choice Gemini ACCEPTED; it can be re-split if ≥2 peer black-boxes exist (re-promotion criterion).

Deviation label: **PROBABLE acceptable** — design choice; re-visit at Gate-A.1 review.

---

## §MOD-1.C — Post-0-1 state confirmation

As of 2026-04-23T02:30Z (MOD-1 launch time):

- **Freeze holds**: 0 arena processes running, engine.jsonl static, VIEW deployable_count=0 (unchanged since 2026-04-21 pipeline freeze)
- **R2 authoritative**: commit `bd91face` remains on main HEAD-lineage; no rollback performed
- **Calcifer outcome-watch formalized**: commit `ae738e37` on main landed §17.3 deterministic gate
- **Non-negotiable rule 1 PASS**: no silent production mutation since 0-1 completion
- **Non-negotiable rule 7 PASS**: no recovery-path contamination from modularization work

These state facts establish the BASELINE against which the intended architecture below is aspirational.

---

## §MOD-1.D — Document classification per 0-2 rule 10

This document is INTENDED TARGET — the aspiration Zangetsu migrates toward. Labels VERIFIED/PROBABLE/INCONCLUSIVE/DISPROVEN apply to comparative docs (actual + drift + target architecture). This doc itself is design-time and labelled:

- §1 mission statement — **PROBABLE** (preserved from charter §1-2, accepted by Gemini + j13)
- §2 10-layer target — **PROBABLE** (design choice with v2 merge rationale; deviation acknowledged in §MOD-1.B)
- §3 arena state machine — **VERIFIED** (exists as DB-backed state enum today; target preserves it)
- §4 SLAs — **PROBABLE targets** (aspirational, not measured)
- §5-§7 contracts / non-goals — **PROBABLE design**

---

## §MOD-1.E — Exit criterion

MOD-1 Phase 1 exit condition: *"The team can explain what complete-form Zangetsu should be, without ambiguity."*

Met by: §1 purpose + §2 10-layer (9-in-design) target + §3 preserved arena pipeline + §4 SLA targets + §5 explicit controls. One coherent aspiration, not a list of ideas.

Proceed to Phase 2 (`actual_architecture.md`).

---

## §MOD-1.F — Authoritative content (preserved from Ascension Phase-1 v2.1)

The full authoritative document follows unchanged.

---

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

### L8 — Integrity & Governance Layer (merged v2 per Gemini §A.1)

**Scope change (v2):** L8 Observability and L9 Governance merged into a single layer. Rationale: governance IS applied policy on observability signals; two layers created an artificial boundary where metric-consumers had to cross-call rule-engines constantly. Sub-modules remain distinct.

**Sub-module L8.O — Observability signal collection**
- Purpose: collect metrics, logs, state from L2-L7; emit structured streams.
- Responsibilities: expose VIEWs (zangetsu_status); emit Prometheus-like streams; maintain alert-rule registry; run reconciliation crons per mutation_blocklist detection entries.
- Outputs: dashboards, alerts, status JSON snapshots, audit-source events.
- Metrics: alert lag, false-alert rate, retention compliance, metric cardinality.
- Failure modes: metrics pipeline down → fallback to log-based alerts.

**Sub-module L8.G — Governance enforcement**
- Purpose: apply charter §17 + mutation_blocklist rules to signals from L8.O and to commit events; produce allow/deny verdicts + rollback handles.
- Responsibilities: PR / commit gates, mutation blocklist runtime enforcement, rollout sign-off, decision-records authoring.
- Inputs: commit events, pipeline events, operator commands, observability signals.
- Outputs: audit log entries, allow/deny verdicts, rollback scripts.
- Configs: mutation_blocklist.yaml, charter rules, decision-rights matrix.
- States: current block state (Calcifer RED/GREEN), pending approvals.
- Failure modes: governance-stream down → block writes (fail-closed).

**Joint test boundary**: signal-replay tests + golden rule-outcome fixtures.
**Joint replacement boundary**: pluggable exporters (Prometheus/Loki/ClickHouse) + pluggable policy engines.

### L9 (was L10) — Black-Box Adapter Pattern (demoted scope v2 per Gemini §A.1)

**Scope change (v2):** demoted from top-level layer to **architectural pattern applied inside L4/L5** when needed. Rationale: today only GP is active (D-07 single-search); adapter pattern only materialises when D4 model-gate introduces a second peer (LGBM, transformer). Keeping as pattern not layer avoids a "ghost layer" per Gemini §A.3. Re-promoted to layer if/when ≥2 peer black-boxes exist.

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

## §6 — Contracts required at each boundary (v2 — scope-bleed fixed per Gemini §G)

For every cross-layer call, an explicit data schema + error schema + backward-compat policy is REQUIRED. Phase 1 only states this requirement and enumerates the **categories** of contract. **Concrete file names, paths, and canonical template are Phase 2 deliverables** (per Ascension §7 execution order, Phase 1 must not do Phase 2 work).

**Required contract categories** (Phase 2 owns names + layout):
- Data schema contract (L3 ↔ L4/L5)
- Candidate schema contract (L4 → L6 admission / L2)
- Metrics schema contract (L5 → L6)
- Gate outcome contract (L6 → L2)
- Champion state contract (L2 internal transitions)
- Alert contract (L8.O → consumers)
- Audit contract (L8.G append-only log format)
- Adapter contract (applied when black-box pattern materialises — see demoted L10→pattern §L9)
- Order-execution contract (future, for OUT-06 Binance order API — **added v2 per Gemini §E.3**: plan now to avoid ad-hoc Phase 7)

Phase 2 outputs will name + structure these. Phase 1 just records the requirement.

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
