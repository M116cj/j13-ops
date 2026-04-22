# Zangetsu — Module Boundary Map (Phase 2)

**Program:** Ascension v1 Phase 2
**Date:** 2026-04-23
**Status:** DESIGN.

---

## §1 — Purpose

Given the `modular_target_architecture.md` module list, define for EACH module:
- which current file(s) it absorbs
- which files it does NOT touch (explicit exclusion)
- what responsibility crosses its boundary TO and FROM neighbouring modules

Every boundary has a contract named in `modular_target_architecture.md §6`.

---

## §2 — Boundary table

| Module | Absorbs (current file) | Does NOT touch | Upstream contract | Downstream contract |
|---|---|---|---|---|
| cp_api | (new) | zangetsu/services/* | n/a | CP read/write API consumed by all layers |
| cp_storage | (new) | admission_validator function body | n/a | Postgres `control_plane.*` schema |
| cp_audit | (new) | `pipeline_audit_log` (L8 owns that) | CP writes | Audit API to L8.G |
| cp_notifier | (new) | zangetsu_notifier / calcifer notifier | CP state | `pg_notify` + Redis pub/sub |
| cp_cli | `zangetsu_ctl.sh` (shim layer) | direct worker spawn logic | user input | CP API |
| cp_worker_bridge | (new) — library | `claim_champion` internals | CP read API | in-process config cache |
| kernel_state | `shared_utils.claim_champion/release_champion/reap_expired_leases` + orchestrator main loops | A1 GP primitives, backtester | CP params | DB champion_pipeline_fresh + pg_notify state events |
| kernel_lease | `shared_utils.py` reaper | evaluator internals | CP params | DB leases |
| kernel_dispatcher | new integration layer | evaluator internals | kernel_state events | L4/L5/L6 call routing |
| kernel_logger | (new) | business log content | kernel events | obs_logs |
| data_provider | `data_collector.py` | parquet consumers directly | external APIs | DataProviderContract |
| data_schema_registry | (new) | content of parquet | data_provider | schema API to consumers |
| data_health | (new) | data content | data_schema_registry | health API to L8 |
| data_store | parquet read helpers (scattered in workers today) | DB writes | data layout | read-only parquet API |
| search_contract | (new) | GP primitives, pset config | candidate producer role | CandidateContract |
| search_gp | `arena_pipeline.py::main GP loop` + `alpha_engine.py` + `alpha_primitives.py` | DB writes (use kernel_dispatcher) | CP params + data | CandidateContract |
| search_lgbm | (new scaffold) | — | CP params + data | CandidateContract |
| search_factor_zoo | `scripts/factor_zoo.py` | — | CP deprecated flag | CandidateContract |
| search_hand_seed | `scripts/cold_start_hand_alphas.py`, `scripts/seed_hand_alphas.py`, `scripts/seed_101_alphas*.py` | — | CP + operator | CandidateContract |
| primitive_registry | consolidated from alpha_primitives.py + pset_lean_config.py | signal generation (stays in alpha_signal.py) | CP | pset lookup |
| eval_contract | (new) | candidates | MetricsContract | MetricsContract |
| eval_a1 | `alpha_engine._forward_returns`, fitness fn | DB | data + candidate | MetricsContract |
| eval_a2_holdout | `arena23_orchestrator.process_arena2` | DB writes (use kernel_dispatcher) | data + candidate + cost_model | MetricsContract |
| eval_a3_train | `arena23_orchestrator.process_arena3` | DB writes | data + candidate | MetricsContract |
| eval_a4_gate | `arena45_orchestrator.arena4_*` | promotion decision (gate_promote owns) | MetricsContract | GateOutcomeContract |
| eval_a5_tournament | `arena45_orchestrator.arena5_*` | card state updates (pub_db owns) | MetricsContract + ELO state | ELO update events |
| backtester | (existing) | signal generation (alpha_signal.py) | candidate + data + cost | MetricsContract fields |
| cost_model | `settings.py` per-tier bps | literals in orchestrator | CP | cost_per_symbol lookup |
| gate_registry | consolidated threshold registry | individual gate logic | CP params | threshold lookup |
| gate_contract | (new) | — | MetricsContract | GateOutcomeContract |
| gate_admission | wraps admission_validator PL/pgSQL | kernel state transitions | staging row | GateOutcomeContract |
| gate_a2 | hardcoded checks in arena23_orchestrator | eval_a2_holdout | MetricsContract | GateOutcomeContract |
| gate_a3 | hardcoded in arena23 | eval_a3_train | MetricsContract | GateOutcomeContract |
| gate_a4 | hardcoded in arena45 | eval_a4_gate | MetricsContract | GateOutcomeContract |
| gate_promote | `PROMOTE_WILSON_LB` + `PROMOTE_MIN_TRADES` in settings.py | — | MetricsContract | GateOutcomeContract |
| gate_calcifer_bridge | Calcifer block file reader (scattered today) | Calcifer daemon internals | calcifer block JSON | GateOutcomeContract (veto) |
| publish_contract | (new) | — | state events | PublisherContract |
| pub_db | kernel_dispatcher's DB writes + release_champion | DB reads (obs_view) | ChampionStateContract | DB rows |
| pub_view | `zangetsu_status` VIEW (SQL) | VIEW consumers | DB rows | versioned SQL artefact |
| pub_snapshot | `scripts/zangetsu_snapshot.sh` | VIEW implementation | VIEW + worker telemetry | `/tmp/zangetsu_live.json` |
| pub_telegram | wraps `calcifer/notifier.py::notify_telegram` | Telegram API directly | AlertContract | Telegram message |
| pub_akasha | wraps `notifier.py::write_to_akasha_sync` | AKASHA server | AlertContract | AKASHA memory chunk |
| pub_alert | (new) | specific channels | MetricsContract + thresholds | AlertContract |
| obs_metrics | (new) | log content | kernel_logger + per-worker metric emit | Prometheus endpoint |
| obs_logs | (new) | business logs (just routes) | kernel_logger + worker stdout | structured log sink |
| obs_view | `zangetsu_status` SQL | pub_view | DB rows | SQL VIEW |
| obs_reports | `scripts/signal_quality_report.py`, `v10_*`, `v8_vs_v9_metrics.py` | DB writes | DB + parquet | `/tmp/*.md` |
| obs_freshness | (new; pattern from `r2_n4_watchdog.py`) | log content | file mtimes + proc list | alert emit |
| gov_contract_engine | `verify_no_archive_reads.sh` + pre-bash hook | CP writes (only checks) | commit events + CP writes | allow/deny |
| gov_reconciler | (new; cron suite matching `mutation_blocklist.yaml detection` fields) | CP state | DB + files + CP | alert emit |
| gov_audit_stream | (new) | CP internals | cp_audit | audit queries |
| gov_rollout | (new) | per-feature implementation | CP rollout table | state events |
| gov_ci_hooks | pre-commit + pre-receive + `~/.claude/hooks/*` | actual code change | commit / push events | allow/deny |

---

## §3 — Forbidden boundary crossings

Avoid these patterns (they will be caught in code review / migration):

1. A worker module writes directly to DB without going through **kernel_dispatcher** (forbids hidden state machine).
2. A search / eval module reads CP params without going through **cp_worker_bridge** (forbids stale cached constants).
3. An output sink accepts messages without an **AlertContract** envelope (forbids ad-hoc formats).
4. Any module logs raw secrets / credentials / tokens.
5. A gate module writes back to state without emitting a **GateOutcomeContract** record.
6. A data_provider module caches in a location other than `data_store`.
7. CP writes bypass the audit pipeline.

---

## §4 — Sanity map: current scattered code → target module

| Current file / function | Absorbed by target module | Phase 7 migration |
|---|---|---|
| `zangetsu_ctl.sh` | cp_cli + gov_ci_hooks | wrap existing behavior; publish as shim |
| `services/arena_pipeline.py` main loop | kernel_dispatcher + kernel_state (portion) + search_gp + eval_a1 | major refactor P1 |
| `services/arena23_orchestrator.py` | kernel_dispatcher + eval_a2_holdout + eval_a3_train + gate_a2 + gate_a3 | P1 |
| `services/arena45_orchestrator.py` | kernel_dispatcher + eval_a4_gate + eval_a5_tournament + gate_a4 + gate_promote + pub_db | P1 |
| `services/arena13_feedback.py` | obs_metrics (produces guidance events) + gov_contract_engine (consumes weight delta cap) | P2 |
| `services/alpha_discovery.py` | search_factor_zoo (frozen) | rename + clean |
| `services/shared_utils.py` | kernel_lease + kernel_state | P1 |
| `services/db_audit.py` | cp_audit + gov_audit_stream | P1 |
| `engine/components/alpha_engine.py` | search_gp + primitive_registry + eval_a1 | P2 (after kernel exists) |
| `engine/components/alpha_signal.py` | search_gp signal-side helper | P2 |
| `engine/components/alpha_primitives.py` | primitive_registry | P2 |
| `engine/components/indicator_bridge.py` | primitive_registry + data_store integration | P2 (D-22 cache invalidation also) |
| `engine/components/pset_lean_config.py` | primitive_registry (variant) | P2 |
| `config/settings.py` | CP parameter registry + gate_registry + cost_model | P1 |
| `config/family_strategy_policy_v0.yaml` | gate_registry (family routing) | P3 wiring |
| `scripts/zangetsu_snapshot.sh` | pub_snapshot + obs_view | P2 |
| `scripts/watchdog.sh` | obs_freshness + gov_reconciler | P2 |
| `scripts/r2_n4_watchdog.py` | reference pattern for obs_freshness + pub_alert | P2 template |
| `scripts/signal_quality_report.py`, `v10_*`, `v8_vs_v9_metrics.py` | obs_reports | P3 |
| `scripts/verify_no_archive_reads.sh` | gov_contract_engine | P2 |
| `scripts/seed_*.py`, `cold_start_hand_alphas.py` | search_hand_seed | P3 |
| Calcifer block file + supervisor | gate_calcifer_bridge (reads) + gov_service (writes) | coordinate with sibling |
| `~/.claude/hooks/*` | gov_ci_hooks | small move |

---

## §5 — Out-of-scope for boundary map

- Implementation details within a module (Phase 7).
- Specific Python package layout (`zangetsu/l4/search/gp.py` vs `zangetsu/search/gp.py`) — Phase 7.
- Database schema migrations (Phase 7).
- Backwards-compat shims (Phase 7 migration plan).
