# State Ownership Matrix — Zangetsu MOD-1 (optional)

**Order**: `/home/j13/claude-inbox/0-2` optional deliverable
**Produced**: 2026-04-23T02:55Z
**Author**: Claude (Lead)
**Status**: DESIGN — evidence-backed matrix of where every meaningful piece of persistent state lives today, who writes it, who reads it, and which target module will own it post-migration.

---

## §1 — Purpose

A pre-requisite for clean modularization is knowing **who owns each state element**. Drift entry D-18 ("two writers, one row") shows the current system has silent multi-writer state. This matrix makes ownership explicit before migration so that Phase 7 cannot introduce new shared-writer patterns without violating the contract.

---

## §2 — State elements and ownership

Grouped by storage backend. Every row asserts one owning module (post-migration) and enumerates all current writers.

### §2.1 Postgres (zangetsu schema)

| State element | Current writers | Current readers | Target owner (module) | Ownership kind | Contract |
|---|---|---|---|---|---|
| `champion_pipeline_staging` | admission_validator (DB fn) | A23 orchestrator (claim), admission_validator | `gate_admission` | EXCLUSIVE write | GateOutcomeContract |
| `champion_pipeline_fresh.status` | admission_validator, arena23_orchestrator, arena45_orchestrator, scripts/*.py | all orchestrators + miniapp + VIEW | `kernel_state` | EXCLUSIVE write | ChampionStateContract |
| `champion_pipeline_fresh.passport` (JSONB) | arena23/45_orchestrator, R2-N3 scripts | same | `kernel_state` (for status/IDs) + evaluators (metrics patch via kernel_dispatcher) | SHARED but kernel mediates | MetricsContract + ChampionStateContract |
| `champion_pipeline_fresh.card_status` | arena45_orchestrator `sync_active_cards` | miniapp reader | `eval_a5_tournament` (via pub_db) | EXCLUSIVE | ChampionStateContract |
| `champion_pipeline_rejected` | admission_validator (reject path) | reports, miniapp | `gate_admission` | EXCLUSIVE | GateOutcomeContract |
| `champion_legacy_archive` | release cycle (manual), migration scripts | replay scripts | `pub_db` (archive side) | EXCLUSIVE | ChampionStateContract |
| `pipeline_audit_log` | every orchestrator via `db_audit.log_transition` | L8.G gov_audit_stream | `cp_audit` (post-migration); `kernel_logger` today | SHARED today → EXCLUSIVE post-migration | AuditContract |
| `pipeline_errors` | orchestrators on exception | reports, r2_n4_watchdog | `kernel_logger` | EXCLUSIVE | (engineering log; no consumer contract) |
| `engine_telemetry` | A1 batch flushes | reports | `obs_metrics` (post-migration) | EXCLUSIVE | (metrics stream) |
| `paper_trades` | (scripts only — not production) | research | `eval_*` for paper-trade mode | SHARED experimental | n/a |
| `trials` / `trial_*` / `studies` | Optuna optimisation (scripts) | reports | separate experiment tooling (not engine) | experimental-only | n/a |
| `rotation_log` | rotation cron | reports | `obs_metrics` | EXCLUSIVE | n/a |
| `runtime_status` | heartbeat writer (scripts/watchdog.sh?) | reports | `obs_freshness` | EXCLUSIVE | n/a |

### §2.2 Postgres (planned `control_plane` schema — does not exist yet)

| State element | Planned writer | Planned reader | Owner | Contract |
|---|---|---|---|---|
| `control_plane.parameters` | `cp_api` write endpoints | all workers via `cp_worker_bridge` | `cp_storage` | ParameterContract |
| `control_plane.audit` | `cp_api` on every write | `gov_audit_stream`, operator | `cp_audit` | AuditContract |
| `control_plane.modules` | CI/CD sync workflow | `cp_api`, gov_reconciler | `cp_storage` | ModuleContract |
| `control_plane.rollout` | rollout advance API | `cp_worker_bridge` | `cp_storage` | RolloutContract |
| `control_plane.decision_rights` | j13 manual via ADR process | cp_api | `cp_storage` (read-heavy) | (matrix schema from CP blueprint §5) |

### §2.3 Redis

| Key pattern | Current writer | Current reader | Target owner | Contract |
|---|---|---|---|---|
| `miniapp:session:*` | d-mail-miniapp `create_or_refresh_session` | same | miniapp (external — not in engine scope) | out of MOD-1 scope |
| `miniapp:jobs:*` | miniapp `_run_job` | miniapp + operator via `/api/jobs` | miniapp (external) | out of MOD-1 scope |
| `akasha:*` | AKASHA service | AKASHA service | AKASHA (external) | out of MOD-1 scope |
| planned `cp:subscribe:*` (pub/sub) | `cp_notifier` | `cp_worker_bridge` | `cp_notifier` | NotifyContract |
| planned `cp:lock:*` (write-lock) | `cp_api` | `cp_api` | `cp_api` (DLM) | (internal) |
| planned `cp:cache:params` | `cp_api` | `cp_worker_bridge` | `cp_api` | (cache) |

### §2.4 Parquet files (`zangetsu/data/`)

| Path | Writer | Reader | Target owner | Contract |
|---|---|---|---|---|
| `data/ohlcv/<SYM>.parquet` | `scripts/daily_data_collect.sh` cron → data_collector.py | A1 worker, orchestrators | `data_provider` | DataProviderContract |
| `data/funding/<SYM>.parquet` | same | same | `data_provider` | same |
| `data/oi/<SYM>.parquet` | same | same | `data_provider` | same |
| `data/regimes/<SYM>.parquet` | regime-computation script | A1/A23 | `data_provider` (with regime computation as `data_enrichment` sub-module) | same |

Ownership rule: NO worker writes parquet directly. Data-layer writes go through `data_provider` per DataProviderContract. This rule is new post-migration; today `data_collector.py` is ad-hoc-called.

### §2.5 Filesystem artifacts (`/tmp/`)

| Path | Writer | Reader | Target owner | Disposition |
|---|---|---|---|---|
| `/tmp/zangetsu_live.json` | `scripts/zangetsu_snapshot.sh` cron | d-mail-miniapp, operator | `pub_snapshot` | EXCLUSIVE write post-migration |
| `/tmp/calcifer_deploy_block.json` | `calcifer/zangetsu_outcome.py` (ae738e37) | `bin/bump_version.py`, operator checks, §17.3 hooks | `gate_calcifer_bridge` owns READ; Calcifer external owns WRITE | READ-only from engine; external writer |
| `/tmp/zangetsu_watchdog.log` | `scripts/watchdog.sh` | operator | `obs_freshness` (absorb) | — |
| `/tmp/zangetsu_a13fb.log` | `services/arena13_feedback.py` (currently failing — B5) | operator | `obs_freshness` | — |
| `/tmp/v9_metrics_latest.md`, `/tmp/v9_signal_quality_latest.md` | hourly cron scripts | operator, miniapp | `obs_reports` | EXCLUSIVE write |
| `/tmp/zangetsu-recovery-*.md` | manual work | operator | (non-persistent; do not migrate) | ephemeral |

### §2.6 Config files (single-source-of-truth targets)

| File | Current semantic | Migration target |
|---|---|---|
| `zangetsu/config/settings.py` | PROMOTE_* constants, TRAIN_SPLIT_RATIO, cost model | MIGRATE to `control_plane.parameters`; keep as read-only shim with deprecation warning |
| `zangetsu/config/family_strategy_policy_v0.yaml` | INERT | MIGRATE to `gate_registry` entries when policy wiring lands |
| `zangetsu/config/volume_c6_exception_overlay.yaml` | INERT | same |
| `zangetsu/config/j01_strategy.py`, `j02_strategy.py` | per-strategy fitness | MIGRATE to `search_gp` config per-strategy block |
| `zangetsu/config/a13_guidance.json` | written by (failing) `arena13_feedback.py`, consumed by A1 | MIGRATE to `obs_metrics` guidance stream + `search_gp` consumer |

### §2.7 Ephemeral in-memory state (deliberate call-out)

| Module | In-memory state | Persistent backing | Re-synth on restart |
|---|---|---|---|
| A1 worker | population, generation counter, archive tier | none (pure in-memory) | restart = cold-start from DB + data |
| A23/45 orchestrator | data_cache (train+holdout slices) | parquet | rebuilt on start |
| backtester | indicator cache | numba cache | rebuilt; D-22 invalidation risk |

Rule: in-memory state MUST be reconstructable from persistent state. Any exception is an explicit failure mode in the module's `failure_surface` (e.g. "population lost on restart; target cold-start time < 5min").

---

## §3 — Multi-writer state flagged for resolution

These are CURRENT multi-writer patterns; migration MUST resolve to single writer:

| State | Today | Resolution |
|---|---|---|
| `champion_pipeline_fresh.status` | admission_validator + 3 orchestrators + scripts | POST: `kernel_state` is SOLE writer; all others call via `kernel_dispatcher` |
| `champion_pipeline_fresh.passport` | 3 orchestrators | POST: evaluators PATCH passport via `kernel_dispatcher.patch_metrics(champion_id, metrics)` |
| `pipeline_audit_log` | every orchestrator | POST: `cp_audit` single writer |

Until resolved, these are BLOCKER items on Gate-C.C.2.

---

## §4 — Read-ownership rules

| Pattern | Rule |
|---|---|
| Reading DB directly | Allowed only for `pub_view`; others use typed client APIs |
| Reading `/tmp/*.json` state | Allowed only for `obs_freshness` and `gate_calcifer_bridge`; others go through CP registry |
| Reading env vars for parameters | Forbidden in normal path; `cp_worker_bridge` is the only reader (for bootstrap / fallback) |
| Reading config YAML files | Allowed only for registry seeders (CI sync workflow); runtime reads go through CP |

---

## §5 — State migration order (preview; detail in `migration_plan_to_modular_engine.md`)

Recommended order to minimise rollback surface:

1. **cp_storage + cp_audit** (skeleton, read-only)
2. **Seed `control_plane.parameters`** from current settings.py + scattered config
3. **Introduce `cp_worker_bridge`** in workers (read only, fall-back to current env)
4. **Phase-cut** each parameter class:
   - thresholds first (Cluster A — D-03 / D-08 / D-11 mitigations together)
   - cost model
   - promotion policy
   - data sources
   - cron schedules (last — cron is system-wide)
5. **kernel_state** extracted from orchestrators
6. **kernel_dispatcher** extracted; orchestrators call into it
7. **Evaluators** decoupled into modules
8. **Gates** consolidated into `gate_registry`
9. **L7 publishers** unified
10. **L8 observability** exporter added
11. **L8.G reconcilers** deployed
12. **Scatter-site removal** (Gate-C.C.3 triggers)

---

## §6 — Q1 adversarial

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | Every storage backend + every concrete state element enumerated from code inspection of current repo | PASS |
| Silent failure | §3 multi-writer list makes hidden contention visible | PASS |
| External dep | Redis/Postgres/parquet paths cross-referenced with `actual_architecture.md §3.1` | PASS |
| Concurrency | Ownership kind is either EXCLUSIVE or SHARED[enumerated list]; no implicit shared state | PASS |
| Scope creep | Matrix does not propose code; only ownership assignments | PASS |
