# Zangetsu — Architecture Drift Map

**Program:** Ascension v1 Phase 1
**Date:** 2026-04-23
**Scope:** diff between `intended_architecture.md` and `actual_architecture.md`.
**Zero-intrusion:** pure documentation.

---

## §1 — How to read this doc

Each drift entry:
- **D-ID** — Drift identifier
- **Layer / Contract** — intended architecture element
- **Intended** — what the intended arch says
- **Actual** — what the code does today
- **Severity** — BLOCKER / HIGH / MEDIUM / LOW (for Ascension migration)
- **Root cause** — why drift happened
- **Remediation** — Phase 2/3/5/7 target

Drift entries are evidence, not tasks. Tasks are generated in Phase 7 patch queue.

---

## §2 — Drift entries

### D-01 — Control Plane missing entirely
| Field | Value |
|---|---|
| Layer / Contract | L1 Control Plane |
| Intended | Single authoritative store for every parameter, mode, schedule, kill switch, rollout state. Decision rights enforced. Distributed lock on writes. |
| Actual | No such layer. Parameters scattered across env vars, `config/settings.py`, `config/*.yaml`, `zangetsu_ctl.sh` flags, DB function bodies, orchestrator hardcoded literals. No decision-rights enforcement. No rollout-state machine. |
| Severity | **BLOCKER** for Ascension §5 success criterion "Major parameters governable from single control plane." |
| Root cause | Organic script-centric growth; each author added configs where convenient. |
| Remediation | Phase 2 control_plane_blueprint.md + Phase 7 migration P1 priority. |

### D-02 — Engine Kernel is implicit, not a module
| Field | Value |
|---|---|
| Layer / Contract | L2 Engine Kernel |
| Intended | Single kernel object owns arena state machine, lease TTL, reap, rollout gating. |
| Actual | State-machine logic duplicated across `arena_pipeline.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py`, `shared_utils.py`. `reap_expired_leases` is in `shared_utils` but called from 3 different main loops with subtle differences. |
| Severity | HIGH — creates subtle drift opportunities (e.g. different retry policies per orchestrator). |
| Root cause | No kernel contract defined. Each orchestrator owns its main loop end-to-end. |
| Remediation | Phase 2 subsystem_contracts.md designs Kernel contract; Phase 7 migration P2. |

### D-03 — Five thresholds mean the same thing
| Field | Value |
|---|---|
| Layer / Contract | L6 Gate threshold registry |
| Intended | Single registry of threshold constants with version history, per-mode overrides, consumed by all gates/search uniformly. |
| Actual | Per N1.3 threshold-semantic map: five sites hold the same `entry/exit rank-cutoff` semantic — `arena_pipeline.py:561-562`, `arena23_orchestrator.py:174-175`, `alpha_signal.py:19,90`, `config/family_strategy_policy_v0.yaml`, `arena23_orchestrator.py:156-157` grid lists. Three sites default to 0.80/0.50; one to 0.95/0.65 (post-R2-hotfix revert); yaml declares 0.90/0.50 but is INERT. |
| Severity | HIGH — split-brain in production when env vars unset. |
| Root cause | f098ead5 changed one site only (v0.7.2.2); N1.3 documented but never consolidated. |
| Remediation | Phase 2 threshold registry design; Phase 7 migration P1 (touches all 5 sites + adds ADR). |

### D-04 — Policy Layer v0 is inert
| Field | Value |
|---|---|
| Layer / Contract | L6 family-aware routing + L7 output routing |
| Intended | Family-aware policy registry drives both signal generation and output routing. |
| Actual | `config/family_strategy_policy_v0.yaml` exists + 6 ADRs + playbooks + 191-line exception overlay test. But `family_tag` column in `champion_pipeline_fresh` is NULL on all 89 rows. `generate_alpha_signals` never reads the registry. |
| Severity | MEDIUM (code is in place, wiring incomplete). |
| Root cause | Landed as a coherent design package but kernel-side integration deferred. |
| Remediation | Phase 2 identifies wire-up; Phase 7 patch wires signal path (tested in shadow before canary). |

### D-05 — CD-14 holdout is file-level code not gate contract
| Field | Value |
|---|---|
| Layer / Contract | L6 OOS gate contract |
| Intended | OOS slice is a gate-registry property; any evaluator declares its train/holdout/oos needs. |
| Actual | `process_arena2` in `arena23_orchestrator.py:452-457` asserts `"holdout" in data_cache[symbol]` and hard-fails. Data cache `main()` builds holdout slice at line 1221. Hard-coded knowledge of `"holdout"` key spread across function bodies. A3/A4/A5 use separate slicing policies duplicated in their own functions. |
| Severity | MEDIUM. |
| Root cause | Landed as a hotfix (R2-N2) rather than a contract redesign — necessary trade-off. |
| Remediation | Phase 2 add `evaluation_slice_contract` to every evaluator; Phase 7 migrate per-gate. |

### D-06 — Admission_validator is the only DB-level gate; but it's mutable code
| Field | Value |
|---|---|
| Layer / Contract | L6 + L9 gate enforcement integrity |
| Intended | Gate logic is versioned + hash-attested + testable in isolation. |
| Actual | `admission_validator(bigint)` PL/pgSQL body is stored in pg_proc; version is migration-file-based but there is no runtime hash attestation (Gemini Phase 0 §D.3 caught this and BL-F-018 now lists it). |
| Severity | HIGH (stealth replacement = silent bypass of F3). |
| Root cause | Migration v0.7.1/v0.7.2.3 pattern never included prosrc hash check. |
| Remediation | Phase 7 add migration with hash attestation + Phase 6 observability adds SHA cron. |

### D-07 — Search is GP-only
| Field | Value |
|---|---|
| Layer / Contract | L4 pluggable search strategies |
| Intended | `SearchEngine` contract with pluggable implementations (GP, LGBM, transformer, factor-zoo as peers). |
| Actual | GP via DEAP is the only active search. LGBM baseline was one-off (Phase 4A), never productionised. Factor-zoo / alpha-discovery are frozen by deprecated-flag. |
| Severity | MEDIUM (single-formulation risk per charter §2.2). |
| Root cause | Historical mono-approach. |
| Remediation | Phase 2 design SearchEngine contract; Phase 7 re-introduce LGBM as peer once D4 (Model Gate) validates feasibility. |

### D-08 — Five gate authors
| Field | Value |
|---|---|
| Layer / Contract | L6 unified gate registry |
| Intended | Gate registry is a module; each gate implements `Gate` contract; thresholds in one registry. |
| Actual | Gates live in (a) admission_validator PL/pgSQL, (b) orchestrator code per-arena, (c) `settings.py` PROMOTE_* constants, (d) `family_strategy_policy_v0.yaml` (inert), (e) `/tmp/calcifer_deploy_block.json` (runtime flag). Five authors, no common interface. |
| Severity | HIGH (charter §3.3 violation: "Every rejection layer must have explicit meaning"). |
| Root cause | Each gate added by a different session/intent. |
| Remediation | Phase 2 gate registry design; Phase 7 migration P1 (centralizes threshold + adds gate_outcome_schema). |

### D-09 — Output path is mainly "DB + ad-hoc sinks"
| Field | Value |
|---|---|
| Layer / Contract | L7 output contract |
| Intended | Publish contract + versioned schemas + pluggable sinks. |
| Actual | `champion_pipeline_fresh` is both store and publication channel. Downstream readers (miniapp, telegram, dashboards) poll it directly or read `/tmp/*.json` snapshots. No publish contract, no schema versioning for consumers. |
| Severity | MEDIUM. |
| Root cause | Incremental consumer addition. |
| Remediation | Phase 2 output contract; Phase 7 standardise consumer reads via a typed API. |

### D-10 — Observability is static reports + one VIEW
| Field | Value |
|---|---|
| Layer / Contract | L8 metrics export + alert rules |
| Intended | Metrics exporter + alert rule engine + reconciliation crons (per mutation_blocklist detection). |
| Actual | `zangetsu_status` VIEW does most aggregation. Hourly cron writes `/tmp/*.md`. Alert logic spread across `watchdog.sh`, `Calcifer supervisor.py`, `r2_n4_watchdog.py`, `arena13_feedback` guidance file. No structured metric export (Prometheus/OTel). |
| Severity | HIGH (Phase 6 observability is a pillar). |
| Root cause | Files-first culture; metric registry deferred. |
| Remediation | Phase 2 monitoring_spec; Phase 6 observability expansion. |

### D-11 — Governance rules live in HUMAN discipline, not code
| Field | Value |
|---|---|
| Layer / Contract | L9 governance |
| Intended | Charter §17 rules enforced by code at runtime where possible; post-violation reconciler catches what pre-gates miss. |
| Actual | §17.3 / §17.4 / §17.7 partially enforced (pre-bash hook, pre-done-stale-check, CI regex). §17.1 / §17.2 / §17.5 / §17.8 largely HUMAN discipline. Post-violation detection missing (DISPROVEN in Phase 0 v2 §8). |
| Severity | HIGH (charter + mutation_blocklist both depend on detection for credibility). |
| Root cause | Early pre-only gates were cheapest to add. |
| Remediation | Phase 6 reconciler cron suite per mutation_blocklist detection fields. |

### D-12 — Black-box adapter layer absent
| Field | Value |
|---|---|
| Layer / Contract | L10 |
| Intended | Wrapper contract with input/output/config/state/health/version/failure/rollback schemas for every black-box (LGBM, external agents, future ML models). |
| Actual | No such layer. LGBM baseline Phase 4A ran as ad-hoc harness. External agent integrations (Gemini/Codex/Markl/Calcifer) are bash-CLI wrapped, not code-contract wrapped. |
| Severity | HIGH (charter §3.6: "black-box internal engines allowed; black-box control surfaces forbidden"). |
| Root cause | Black-boxes haven't been integrated as prod-path components yet; but Phase 4+ will require this. |
| Remediation | Phase 2 adapter_contract.yaml; Phase 7 add wrapper for first black-box (likely LGBM D4 Model Gate). |

### D-13 — Data layer lacks schema registry + integrity attestation
| Field | Value |
|---|---|
| Layer / Contract | L3 Data Input |
| Intended | Data sources registered with schema + version + integrity hash; per-source health. |
| Actual | `data_collector.py` merges parquet; `_save_merged` is idempotent but no schema registry, no per-source health endpoint, no integrity attestation on downstream loads. Phase 0 v2 §9 added ingress data integrity as explicit non-goal for Phase 0 but Phase 1 exposes this as a Layer 3 gap. |
| Severity | HIGH if upstream is tampered; MEDIUM under normal conditions. |
| Root cause | Data layer grown organically with research. |
| Remediation | Phase 2 data_schema.yaml contract; Phase 6 per-source health + integrity cron; Phase 7 migrate data_collector to contract. |

### D-14 — Tests cover only policy layer
| Field | Value |
|---|---|
| Layer / Contract | All layers test boundaries |
| Intended | Each module has unit tests (contract tests + golden fixtures). |
| Actual | `zangetsu/tests/policy/` has 2 files (test_exception_overlay.py + test_resolver_abcd.py, 290 lines total). services/ + engine/ + data/ have no unit coverage (smoke tests exist as retrospective artifacts). |
| Severity | HIGH (charter §3.4: "explicit test boundary"). |
| Root cause | Script-centric growth; tests added reactively. |
| Remediation | Phase 2 subsystem_contracts define test boundaries; Phase 7 migration creates unit-test scaffolding. |

### D-15 — Process management lockfile-only, no systemd/supervisord
| Field | Value |
|---|---|
| Layer / Contract | L2 kernel process lifecycle |
| Intended | Worker lifecycle owned by a service manager with auto-restart + resource caps + log rotation. |
| Actual | `pidlock.py` + `watchdog.sh` cron handle both lifecycle and liveness. No cgroup / memory caps / CPU affinity (touched only via `nice -n 10` for alpha_discovery). Zangetsu does not use systemd unit despite plist examples elsewhere. |
| Severity | MEDIUM. |
| Root cause | Simplicity choice; works under current load. |
| Remediation | Phase 5 compute_topology_map should score whether systemd migration is worth it. |

### D-16 — Cross-process file dependency (XPD)
| Field | Value |
|---|---|
| Layer / Contract | L7/L8 output contract |
| Intended | Cross-process state via a typed event stream (DB table / Redis pub/sub / AKASHA memory). |
| Actual | `/tmp/zangetsu_live.json` writer (snapshot cron) → multiple readers (miniapp, potentially A1/a13_feedback). `/tmp/j13-current-task.md` writer (Mac Claude CLI hook) → miniapp reader. Stale-read risk not monitored. |
| Severity | MEDIUM. |
| Root cause | Files are cheapest. |
| Remediation | Phase 2 cross-process contract; Phase 6 freshness monitor; Phase 7 migrate to typed bus if needed. |

### D-17 — Hooks / plist as mutation surfaces without integrity check
| Field | Value |
|---|---|
| Layer / Contract | L9 governance integrity |
| Intended | Any governance tool (hook, plist, ctl script) carries integrity hash; any silent edit is detected. |
| Actual | `~/.claude/hooks/*.sh` + launchd plists are edited directly. `.integrity` file does not exist. Phase 0 v2 BL-R-012 added the requirement but it is not yet implemented. |
| Severity | HIGH (silent bypass of the safety contract). |
| Root cause | Not considered until Gemini Phase 0 review. |
| Remediation | Phase 7 add `.claude/hooks/.integrity` + check on CLI launch. |

### D-18 — Admission validator + fresh table = same component, different enforcement models
| Field | Value |
|---|---|
| Layer / Contract | L6 gate + L2 kernel |
| Intended | Admission is a gate (L6) feeding the kernel (L2); boundary is clear. |
| Actual | Admission validator is a DB function directly INSERT-ing to fresh. It's acting as both gate AND kernel-writer. The orchestrator later UPDATE-s the same row. Two owners, one row. |
| Severity | MEDIUM. |
| Root cause | v0.7.1 governance split staging/fresh but kept admission as DB-side for atomic move — good choice, but the kernel doesn't model it. |
| Remediation | Phase 2 clarify ownership; kernel contract treats admission as a gate-producing insert-handler. |

### D-19 — Reports and dashboards have no contract with the VIEW they read
| Field | Value |
|---|---|
| Layer / Contract | L7 output consumer contract |
| Intended | `zangetsu_status` VIEW is versioned; consumers declare which fields they expect; VIEW change requires consumer audit. |
| Actual | The VIEW is schema-less from consumers' perspective. Miniapp reads `deployable_count`, `champions_last_1h`, `last_live_at_age_h`. Hourly report scripts compute their own things. Any VIEW column rename would silently break readers. |
| Severity | MEDIUM. |
| Root cause | Ad-hoc. |
| Remediation | Phase 2 VIEW as versioned artefact; Phase 7 add schema tests. |

### D-20 — DEPRECATED modules still have cron entries (or would, if unfrozen)
| Field | Value |
|---|---|
| Layer / Contract | L9 hygiene |
| Intended | Deprecated code deleted OR fenced behind explicit enable flag with loud startup warning AND no cron invocation. |
| Actual | `alpha_discovery.py` is flag-frozen, BUT crontab still has `*/30 * * * * alpha_discovery.py >> /tmp/alpha_discovery.log`. If someone removes the flag, cron lights up immediately. |
| Severity | LOW (currently frozen, just ugly). |
| Root cause | Cron entries live separately from deprecation metadata. |
| Remediation | Phase 7 remove cron OR add guard in script. |

---

## §3 — Drift severity roll-up

| Severity | Count | Layers hit |
|---|---:|---|
| BLOCKER | 1 | L1 (D-01) |
| HIGH | 9 | L2/L4/L5/L6/L8/L9/L10/L3/L9 |
| MEDIUM | 8 | L4/L5/L6/L7/L10/L2/L7/L7 |
| LOW | 2 | L9 hygiene |

**Blocker count = 1** → confirms Ascension can proceed after L1 control-plane design (Phase 2 control_plane_blueprint.md is the first prerequisite before any migration).

---

## §4 — Confidence

- **VERIFIED**: drift entries D-01 through D-20 are backed by Phase 0 evidence + repo reads + session history.
- **PROBABLE**: severity labels are current-best-judgement; Gemini adversarial can challenge.
- **INCONCLUSIVE**: whether D-15 (lockfile vs systemd) is worth migrating — depends on Phase 5 compute_topology_map.

---

## §5 — Non-goals

- Not proposing migration order — that's Phase 2 migration_plan_to_modular_engine.md.
- Not writing code to fix drift — that's Phase 7.
- Not auditing correctness of gates per-se — that's Phase 4.
