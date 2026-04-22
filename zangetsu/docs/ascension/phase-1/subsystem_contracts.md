# Zangetsu — Subsystem Contracts (Phase 1 draft)

**Program:** Ascension v1 Phase 1
**Date:** 2026-04-23
**Scope:** per-subsystem checklist of the Ascension §3.4 "explicit module" criteria. For each subsystem: purpose, inputs, outputs, config schema, state schema, metrics, error surface, rollback surface, test boundary, replacement boundary.
**Status:** **BASELINE** draft. Where a field is missing today, it is labelled **GAP** — these become Phase 2 migration targets.
**Zero-intrusion:** documentation.

---

## §1 — How to read a contract entry

Each subsystem gets a row under each of 10 fields. Where the field exists today, the cell shows current reality. Where it doesn't, **GAP** + remediation phase.

---

## §2 — Subsystems

### §2.1 A1 Worker — `services/arena_pipeline.py` × 4

| Field | Current | Phase to fix if GAP |
|---|---|---|
| purpose | GP evolution loop: generate candidate alphas per STRATEGY_ID, insert to staging | — |
| inputs | Data from `data/` parquet, env params (ENTRY_THR / FORWARD_HORIZON / pop / gen / top_K), DB state via `claim_champion` | **GAP** — input schema not declared; no typed DataProvider boundary. Phase 2 L3 contract. |
| outputs | Rows in `champion_pipeline_staging`; admission_validator call returns verdict | **GAP** — candidate schema not externalised. Phase 2 candidate_schema.yaml. |
| config schema | scattered (env + settings.py + hardcoded) | **GAP** — Phase 2 control plane param registry. |
| state schema | worker population (in-memory), A1 round log | **GAP** — not inspectable externally. Phase 6 observability expose. |
| metrics | `engine_telemetry` batch flushes + `rejects:` round log counters (after R2-N2) | partial — exporter gap; Phase 6 adds prometheus-like stream. |
| error surface | try/except around GP + DB; rejects logged by type | partial — dedicated error taxonomy missing; Phase 2 define. |
| rollback surface | stop worker via `zangetsu_ctl.sh stop` + lease reaper | **GAP** — no per-alpha rollback; Phase 7 adds. |
| test boundary | no unit tests in `tests/` for this file | **GAP** — Phase 2 test boundary spec; Phase 7 add. |
| replacement boundary | STRATEGY_ID env acts as rough pluggability (j01 vs j02) | **GAP** — Phase 2 SearchEngine contract. |

### §2.2 A2/A3 Orchestrator — `services/arena23_orchestrator.py`

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Poll ARENA1_COMPLETE from fresh; evaluate on holdout (A2) and train (A3); transition state | — |
| inputs | DB `claim_champion`; data_cache built at startup; cost_model; backtester; strategy config (max_hold) | **GAP** — implicit, not contract. Phase 2 evaluator contract. |
| outputs | `release_champion` row update (status + passport patch); `pipeline_audit_log` append | partial — passport JSONB is free-form. Phase 2 metrics_schema. |
| config schema | thresholds hardcoded (156-157 grid, 580-581 pos_count, 517 min trades, 174-175 _V10 thr) | **GAP** — D-03 + D-08 drift. Phase 2 gate registry. |
| state schema | per-champion lease + status enum | OK (DB-backed) |
| metrics | logged reject reasons; no structured export | **GAP** — Phase 6. |
| error surface | try/except per champion; failures revert to ARENA1_COMPLETE / ARENA2_COMPLETE | OK under single-row; no circuit breaker |
| rollback surface | lease reaper + explicit --reenqueue UPDATE | OK |
| test boundary | **GAP** — no unit tests | Phase 7 |
| replacement boundary | evaluator is monolithic | Phase 2 pluggable evaluator per horizon/target |

### §2.3 A4/A5 Orchestrator — `services/arena45_orchestrator.py`

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Promote ARENA3_COMPLETE through A4 / A5 / card-state machine | — |
| inputs | DB state + settings.py PROMOTE_* | **GAP** — same as §2.2 |
| outputs | status + card_status + elo_rating + passport | **GAP** — schema-less |
| config | PROMOTE_WILSON_LB / PROMOTE_MIN_TRADES (settings.py) | OK (single source for these) but D-08 still present |
| state | DB-backed | OK |
| metrics | ELO distribution, promotion count / day | **GAP** — not exposed |
| error surface | per-row try/except | OK under single-row |
| rollback | revert card_status via sync_active_cards | partial — no explicit rollback command |
| test boundary | **GAP** | Phase 7 |
| replacement boundary | promotion policy hardcoded in code | Phase 2 policy contract |

### §2.4 Admission Validator (PL/pgSQL)

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Move staging→fresh with 3 structural gates + ON CONFLICT handling | — |
| inputs | `_staging_id bigint` | OK |
| outputs | verdict string ('admitted' / 'admitted_duplicate' / 'rejected:<reason>' / 'error:<sqlerrm>') | OK |
| config | embedded gate logic + CHECK constraint enum | **GAP** — gates are part of function body, no registry. D-06 drift. |
| state | DB-side only | OK |
| metrics | none (only return value) | **GAP** — no DB-side counter; operators read staging state to infer |
| error surface | EXCEPTION block routes to pending_validator_error | OK |
| rollback | `rollback_v0.7.2.3.sql` pair | OK |
| test boundary | **GAP** — no SQL-level unit tests | Phase 7 |
| replacement boundary | new function-version in migration | OK (migration-based) |

### §2.5 Arena13 Feedback — `services/arena13_feedback.py`

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Compute per-indicator soft guidance weights; write config JSON for A1 consumers | — |
| inputs | DB read on fresh metrics + engine telemetry | **GAP** — input schema undeclared |
| outputs | `config/a13_guidance.json` + `config/a13_gating.json` | OK (file path defined) |
| config | `MAX_WEIGHT_DELTA_PCT=50%` cap + others | **GAP** — scattered |
| state | file state | OK |
| metrics | none exposed | **GAP** — Phase 6 |
| error surface | writes partial or none; readers tolerate | OK (soft) |
| rollback | previous JSON restorable if backup retained | **GAP** — no automatic backup; Phase 7 |
| test boundary | **GAP** | Phase 7 |
| replacement boundary | weight function is module-level | Phase 2 weight strategy contract |

### §2.6 Data Collector — `services/data_collector.py` + `scripts/daily_data_collect.sh`

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Fetch Binance OHLCV / funding / OI and merge to parquet | — |
| inputs | Binance API + existing parquet | OK per file |
| outputs | `data/ohlcv/*.parquet` + funding + oi | OK |
| config | source list + schedule (cron) | **GAP** — sources are hardcoded |
| state | per-source last-fetch timestamp implicit in file mtime | **GAP** — no explicit health record |
| metrics | log lines only | **GAP** — Phase 6 per-source health |
| error surface | retry w/ backoff | OK |
| rollback | parquet backup (manual) | **GAP** — no automatic backup |
| test boundary | **GAP** | Phase 7 |
| replacement boundary | DataProvider contract | Phase 2 L3 contract |

### §2.7 Snapshot Cron — `scripts/zangetsu_snapshot.sh`

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Compose `/tmp/zangetsu_live.json` snapshot of system state | — |
| inputs | DB reads + worker heartbeat files + VIEW | OK (read-only) |
| outputs | single JSON file with documented (in code) structure | **GAP** — schema not versioned |
| config | hard-coded queries | **GAP** |
| state | atomic write via temp file rename (presumed) | needs verification |
| metrics | none | **GAP** |
| error surface | silent on error in cron mode | **GAP** — Phase 6 add freshness alert |
| rollback | not applicable (read-only producer) | OK |
| test boundary | **GAP** | Phase 7 |
| replacement boundary | could be replaced by a VIEW that materialises the JSON | Phase 2 consideration |

### §2.8 Watchdog — `scripts/watchdog.sh`

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Restart dead workers + advisory lock reclaim | — |
| inputs | PID files + `kill -0` | OK |
| outputs | signals (SIGTERM/SIGKILL) + respawn | OK |
| config | embedded in script (service names, paths, timeouts) | **GAP** — externalise to control plane |
| state | lockfiles | OK |
| metrics | log lines | **GAP** |
| error surface | if respawn fails, logs and loops | OK (cron will re-run) |
| rollback | not applicable | OK |
| test boundary | **GAP** | Phase 7 |
| replacement boundary | could be systemd unit; Phase 5 analyse | — |

### §2.9 r2_n4_watchdog — `scripts/r2_n4_watchdog.py`

Already implements a newer pattern (JSONL snapshot log + structured alerts + explicit deadline). Treat as **REFERENCE** for Phase 6 alert watchdogs.

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | 2h observation window for R2 recovery | — |
| inputs | DB VIEW + fresh table + engine.jsonl tail | OK |
| outputs | JSONL snapshots + Telegram alerts | OK |
| config | inline constants (R2N3_T0, DEADLINE, POLL_INTERVAL, thresholds) | partial — could be externalised |
| state | in-process FIRED dict (fires-once gates) | OK (intentional) |
| metrics | JSONL log with T+min + dc + fresh_hist + reasons | OK — structured |
| error surface | psql error → error dict in snapshot | OK |
| rollback | watchdog exits at deadline | OK |
| test boundary | **GAP** — no unit test, but code is short | Phase 7 if generalised |
| replacement boundary | pattern re-usable for Phase 6 | **PROMOTE** to reference in Phase 2 |

### §2.10 Policy Layer v0 — `config/family_strategy_policy_v0.yaml` + `zangetsu/services/policy/*`

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Family-aware routing (Volume / Breakout / Meanrev / fallback) + exception overlay | — |
| inputs | alpha's family_tag + yaml registry + exception list | wired in policy code but NOT wired in signal generation (D-04) |
| outputs | resolver verdict (family → thresholds / gates) | OK in tests (2 test files, 290 lines) |
| config | YAML registry + exception overlay YAML | OK (well-structured) |
| state | inert at runtime | **GAP** — not wired |
| metrics | none | **GAP** |
| error surface | test coverage decent | OK |
| rollback | delete YAML → falls back to default thresholds | OK |
| test boundary | **EXEMPLARY** — 2 test files committed | — |
| replacement boundary | policy model pluggable (registry is data, not code) | OK |

### §2.11 Pidlock + Shared Utils — `pidlock.py` + `shared_utils.py`

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Advisory fcntl lock + claim/release/reap kernel primitives | — |
| inputs | service name + cwd | OK |
| outputs | lock handle; claimed champion; reap count | OK |
| config | lease minutes floor clamp | OK |
| state | lockfile + DB leases | OK |
| metrics | log only | **GAP** |
| error surface | atexit + SIGTERM/SIGINT handlers | OK |
| rollback | reaper on stale leases | OK |
| test boundary | **GAP** | Phase 7 |
| replacement boundary | could be migrated to asyncio / trio lock if needed | — |

### §2.12 Calcifer (sibling)

Out of primary Zangetsu scope; listed as external dependency. Calcifer owns:
- Calcifer block file (`/tmp/calcifer_deploy_block.json`)
- Notifier (`calcifer/notifier.py` — shared by Zangetsu through `from notifier import notify_telegram`)
- Supervisor
- Systemd service `calcifer-supervisor.service`

Contract obligations from Zangetsu's perspective:
- Zangetsu READS Calcifer block file; Calcifer owns writes.
- Zangetsu imports `notifier.py` — treat as shared library; changes require both-side ADR.

### §2.13 d-mail miniapp v0.5.5 (partner service, runs on Alaya)

Out of this ascension's direct scope but listed as consumer of Zangetsu outputs (via `/api/zangetsu/live`, `/api/current-task`, Telegram, Redis activity).

### §2.14 Deprecated path — alpha_discovery.py / factor_zoo.py / seed_101_alphas*.py

| Field | Current | Gap / Phase |
|---|---|---|
| purpose | Legacy alpha discovery / seeding | FROZEN |
| state | `--i-know-deprecated-v071` guard | OK |
| gap | cron still scheduled (D-20) | Phase 7 remove |
| replacement | supersede by L4 SearchEngine pluggable | Phase 2 design |

---

## §3 — Contract coverage roll-up

Per `subsystem × 10 fields`:

| Subsystem | Fields with current evidence | GAP count | Priority |
|---|---:|---:|---|
| A1 Worker | 5 / 10 | 5 | HIGH |
| A2/A3 Orchestrator | 5 / 10 | 5 | HIGH |
| A4/A5 Orchestrator | 5 / 10 | 5 | HIGH |
| Admission Validator | 7 / 10 | 3 | MEDIUM |
| Arena13 Feedback | 4 / 10 | 6 | MEDIUM |
| Data Collector | 5 / 10 | 5 | HIGH (ingress) |
| Snapshot Cron | 4 / 10 | 6 | MEDIUM |
| Watchdog | 5 / 10 | 5 | MEDIUM |
| r2_n4_watchdog | 9 / 10 | 1 | REFERENCE pattern |
| Policy Layer v0 | 8 / 10 | 2 | MEDIUM (wiring) |
| Pidlock + shared_utils | 7 / 10 | 3 | LOW |

**Average**: 5.8 / 10 fields populated — **note v2 (Gemini §F.1): this is a VANITY METRIC**. Uniform-weighted averaging is misleading — "replacement boundary" for a read-only snapshot (§2.7) is noise; "replacement boundary" for admission_validator (§2.4) is load-bearing. Phase 2 must define **criticality-weighted** contract metrics before using this as a priority signal.

**r2_n4_watchdog as template — caveat (added v2 per Gemini §F.2)**: it scores 9/10 for **alerting-shape** subsystems but only ~2/10 for **kernel-state-shape** or **research-engine-shape**. Use as reference ONLY for the alert/observability family. L2 kernel + L4 research need their own shape templates — Phase 2 work.

**Policy Layer v0 rated 8/10 but INERT — correction (added v2 per Gemini §F.3)**: tabular view is 8/10 for design-completeness. But because the design is never wired, the operational rating is more like 4/10 (contract exists, contract is lies). Effective rating = **-6 wiring penalty**, i.e. 8 design / 2 operational / net 4 for decision purposes.

---

## §4 — What Phase 2 must produce from this (v2 — scope-bleed fixed per Gemini §G)

Phase 1 only STATES requirements; Phase 2 designs + produces the deliverables. Phase 1 must not propose concrete templates.

Required Phase 2 inputs (from Phase 1):
- This subsystem-contract gap inventory (14 subsystems × 10 fields)
- `architecture_drift_map.md` severity roll-up
- `scattered_config_map.md` canonical-registry requirement
- `uncontrolled_io_map.md` governance-surface list

Required Phase 2 outputs (Phase 2's scope, not Phase 1's):
- Contract template shape (whatever Phase 2 decides — may or may not resemble r2_n4_watchdog)
- Concrete per-subsystem contract artifacts
- Migration plan from current gap coverage to target
- Module registry design

Phase 1 deliberately refuses to specify these.

---

## §5 — Confidence

- **VERIFIED**: presence/absence of fields per subsystem (file reads + repo grep)
- **PROBABLE**: gap priorities (may shift after Phase 2 blueprint)
- **INCONCLUSIVE**: whether policy layer wiring is Phase 2 scope or Phase 7 task

---

## §6 — Non-goals

- Not designing the target contract template here — Phase 2.
- Not filling the gaps — Phase 7.
- Not auditing correctness of existing code — Phase 4.
