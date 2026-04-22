# Zangetsu — Mutation Surface Map (Phase 0)

**Program:** Zangetsu Engine Ascension v1
**Phase:** 0
**Date:** 2026-04-23
**Source:** Explore agent survey of `/home/j13/j13-ops/zangetsu/` 2026-04-22, cross-checked by Claude Lead against Ascension §3.1 truth-integrity rule.
**Scope:** Zangetsu proper (exclude calcifer/ sibling folder except where explicitly shared).

---

## §1 — Summary

| Class | Count | Blast range |
|---|---:|---|
| SQL write mutations | 42 | single-row → multi-table → multi-row-batch |
| File write mutations | 3 | shared file system |
| Process / signal mutations | 3 | process-local → all-of-pipeline |
| Outbound network writes | 0 | (read-only Binance ingress is not a mutation) |
| **TOTAL** | **48** | |

Zero outbound POST/PUT/DELETE from Zangetsu production workers. All external writes are channelled through wrapped intermediaries (AKASHA notifier → /memory, Telegram via calcifer/notifier.py).

---

## §2 — SQL write inventory (42)

Legend:
- `gate_status`: `WG5` = v0.7.1 governance rule #5 (verify_no_archive_reads), `ADM` = admission_validator trigger, `SKIP` = FOR UPDATE SKIP LOCKED + lease, `DEP` = deprecated-flag guard, `CNF` = confirm token / --dry-run, `ungated` = no explicit guard
- `blast`: `row` / `tab` / `mtab` / `batch` / `pipe`

### §2.1 arena_pipeline.py (A1, 5)
| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| SQL-001 | arena_pipeline.py:136 | engine_telemetry | periodic telemetry flush | ungated | idempotent | tab |
| SQL-002 | arena_pipeline.py:574–590 | round_checkpoints | regime transition checkpoint | ungated (`ON CONFLICT DO UPDATE`) | idempotent | tab |
| SQL-003 | arena_pipeline.py:873–900 | champion_pipeline_staging | A1 insert candidate | v0.7.1 staging gate + `ADM` next | reversible (→staging) | row |
| SQL-004 | arena_pipeline.py:915 | champion_pipeline_fresh | `SELECT admission_validator(id)` | ADM (3 gates) | gated move, atomic | mtab |
| SQL-005 | arena_pipeline.py:135–136 | engine_telemetry | batch flush | ungated | idempotent | tab |

### §2.2 arena23_orchestrator.py (A2/A3, 5)
| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| SQL-006 | arena23_orchestrator.py:352–362 | champion_pipeline_fresh | `pick_champion` FOR UPDATE SKIP LOCKED | SKIP + lease | revertible by reaper | row |
| SQL-007 | arena23_orchestrator.py:397–398 | champion_pipeline_fresh | `release_champion` dynamic UPDATE | status check | reversible | row |
| SQL-008 | arena23_orchestrator.py:1336 | champion_pipeline_fresh | ARENA2_COMPLETE on success (error recovery) | ungated | reversible | row |
| SQL-009 | arena23_orchestrator.py:1381 | champion_pipeline_fresh | revert ARENA1_COMPLETE on A2 failure | ungated | reversible | row |
| SQL-010 | services/db_audit.py:28 | pipeline_audit_log | log_transition audit trail | ungated (best-effort) | idempotent | row |

### §2.3 arena45_orchestrator.py (A4/A5, 9)
| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| SQL-011 | arena45_orchestrator.py:255–272 | champion_pipeline_fresh | `pick_arena3_complete` SKIP LOCKED | SKIP + lease | reversible | row |
| SQL-012 | arena45_orchestrator.py:283–298 | champion_pipeline_fresh | `arena4_pass` → CANDIDATE | code-internal A4 gate | reversible | row |
| SQL-013 | arena45_orchestrator.py:301–316 | champion_pipeline_fresh | `arena4_fail` → ARENA4_ELIMINATED | ungated | reversible | row |
| SQL-014 | arena45_orchestrator.py:397–398 | champion_pipeline_fresh | `promote_candidate` → DEPLOYABLE | `PROMOTE_WILSON_LB` + `PROMOTE_MIN_TRADES` | reversible | row |
| SQL-015 | arena45_orchestrator.py:669–671 | champion_pipeline_fresh | `sync_active_cards` → DEPLOYABLE_LIVE | ungated (sync op) | reversible | row |
| SQL-016 | arena45_orchestrator.py:677–679 | champion_pipeline_fresh | deactivation revert | ungated | reversible | row |
| SQL-017 | arena45_orchestrator.py:854–859 | champion_pipeline_fresh | `update_elo_rating` post-A5 match | ungated | reversible | row |
| SQL-018 | arena45_orchestrator.py:875–887 | champion_pipeline_fresh | passport JSONB upsert | ungated | reversible | row |
| SQL-019 | arena45_orchestrator.py:942–950 | champion_pipeline_fresh | `check_daily_reset` scheduled ELO reset | ungated | reversible | batch |

### §2.4 shared_utils.py (1, critical)
| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| SQL-020 | shared_utils.py:354–368 | champion_pipeline_fresh | `reap_expired_leases` atomic CTE | SKIP + `lease_minutes ≥ 1` clamp | reversible | batch |

### §2.5 Deprecated seed / discovery (6)
| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| SQL-021 | seed_101_alphas.py:242–258 | champion_pipeline | direct INSERT | DEP flag `--i-know-deprecated-v071` | reversible | row |
| SQL-022 | seed_101_alphas_batch2.py:847–861 | champion_pipeline | batch seed | DEP | reversible | batch |
| SQL-023 | factor_zoo.py:125 | champion_pipeline | GP discovery | DEP | reversible | row |
| SQL-024 | factor_zoo.py:244 | champion_pipeline | zoo metadata update | DEP | reversible | row |
| SQL-025 | alpha_discovery.py:155–176 | champion_pipeline | GP insert with ON CONFLICT | DEP + ON CONFLICT | idempotent | row |
| SQL-026 | alpha_discovery.py:(~155 continued) | champion_pipeline | dedup via `uniq_alpha_hash_v10` | DEP + ON CONFLICT DO NOTHING | idempotent | row |

### §2.6 Manual scripts (6, human-invoked)
| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| SQL-027 | seed_hand_alphas.py:276–290 | champion_pipeline_fresh (via staging) | seed hand-tuned alphas | ADM | reversible | row→batch |
| SQL-028 | cold_start_hand_alphas.py:250 | champion_pipeline_staging | cold-start seed | ADM + `--allow-dirty-tree` | reversible | batch |
| SQL-029 | scripts/rescan_legacy_with_new_gates.py | champion_pipeline_fresh | re-validate legacy | CNF (implicit) | reversible | batch |
| SQL-030 | scripts/reseed_from_legacy_top.py | champion_pipeline_fresh | reseed top performers | CNF (human review) | reversible | batch |
| SQL-031 | scripts/wilson_wr_rescore.py | champion_pipeline_fresh | batch Wilson LB rescore | CNF (manual) | reversible | batch |
| SQL-032 | scripts/valgate_counterfactual.py | champion_pipeline_fresh | val-gate counterfactual | CNF (manual) | reversible | batch |

### §2.7 Arena13 feedback + audit + reap (4)
| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| SQL-033 | arena13_feedback.py (guidance file) | `a13_guidance.json` | 5m refresh | env_guard + `MAX_WEIGHT_DELTA_PCT=50%` | reversible (file rewrite) | process |
| SQL-034 | arena13_feedback.py (gating file) | `a13_gating.json` | conditional update | env_guard | reversible | process |
| SQL-035 | arena13_feedback.py (soft guidance) | (read) → a1 weights | advisory only | ungated (read) | N/A | N/A |
| SQL-036 | zangetsu_ctl.sh (reap section) | champion_pipeline_fresh | `ctl.sh reap [--dry-run]` | CNF `--dry-run` available | reversible | batch |

---

## §3 — File write inventory (3)

| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| FILE-001 | data_collector.py:222 | `zangetsu/data/ohlcv/*.parquet` | `_save_merged` via daily cron | ungated (data pipeline) | idempotent merge | shared FS |
| FILE-002 | arena13_feedback.py (main loop) | `config/a13_guidance.json` | 5m cycle | env_guard | reversible (rewrite) | shared FS |
| FILE-003 | arena13_feedback.py (gating) | `config/a13_gating.json` | conditional | env_guard | reversible | shared FS |

Plus telemetry files at `/tmp/*.md` from hourly analysis crons (signal_quality, factor_zoo_report, alpha_ic_analysis, v8_vs_v9_metrics, zangetsu_snapshot) — classified as idempotent ungated outputs (not counted above; ephemeral reports).

---

## §4 — Process / signal mutations (3)

| ID | File:Line | Target | Path | Gate | Reversibility | Blast |
|---|---|---|---|---|---|---|
| PROC-001 | watchdog.sh:99–145 | worker PIDs | SIGTERM→10s→SIGKILL | fcntl.flock | reversible (respawn) | process |
| PROC-002 | pidlock.py:50 | `/tmp/zangetsu/*.lock` | acquire_lock / release_lock | fcntl LOCK_EX \| LOCK_NB | reversible (atexit) | process |
| PROC-003 | zangetsu_ctl.sh (start/stop) | systemd / lockfile | start_if_not_running, graceful stop | CNF (must invoke ctl) | reversible | pipe |

---

## §5 — Existing defensive gates cross-reference

1. **`verify_no_archive_reads.sh`** (v0.7.1 rule #5) — bundled into `zangetsu_ctl.sh start` pre-flight. Blocks bare `champion_pipeline` in FROM / UPDATE / JOIN / INTO.
2. **`admission_validator($staging_id)`** — PL/pgSQL gate: (a) alpha_hash 16-char hex format, (b) epoch must be `B_full_space`, (c) arena1_score finite + ON CONFLICT for uniq_alpha_hash. Failure routes to `pending_validator_error` exception state; dup collision → `admitted_duplicate` (added in v0.7.2.3).
3. **FOR UPDATE SKIP LOCKED + lease_until** — standard across pick_*/reap_* paths.
4. **ON CONFLICT DO NOTHING / DO UPDATE** — for dedup + idempotency.
5. **Deprecated flag guard** — `--i-know-deprecated-v071` refusal for legacy seeders.
6. **`--dry-run` reap** — `ctl.sh reap` supports preview mode.
7. **Governance thresholds** — config/settings.py (`PROMOTE_WILSON_LB`, `PROMOTE_MIN_TRADES`, `MAX_HOLD_BARS`, …).
8. **Soft guidance cap** — `MAX_WEIGHT_DELTA_PCT=50%` in arena13_feedback rejects sudden weight swings.
9. **§17.6 stale-service check** — hook enforced pre-"done" for every service restart claim.

---

## §6 — Mutation entry points (top-level)

### §6.1 Continuous workers (lockfile-managed)
- `services/arena_pipeline.py` — A1 GP evolution (4 × w0-w3)
- `services/arena23_orchestrator.py` — A2 / A3 evaluation
- `services/arena45_orchestrator.py` — A4 / A5 promotion + card state

### §6.2 Cron writers
- `*/5 * * * *` `watchdog.sh` — signal mutations
- `*/5 * * * *` `arena13_feedback.py` — guidance file
- `*/30 * * * *` `alpha_discovery.py` — **FROZEN by DEP flag**
- `0 */6 * * *` `daily_data_collect.sh` — parquet writes
- `* * * * *` `zangetsu_snapshot.sh` — `/tmp/zangetsu_live.json`
- `30/15/45 * * * *` — hourly report scripts (read-only outputs)

### §6.3 Human / CLI entry points
- `zangetsu_ctl.sh start|stop|restart|status|reap|health|logs`
- `scripts/seed_hand_alphas.py`
- `scripts/cold_start_hand_alphas.py`
- `scripts/rescan_legacy_with_new_gates.py`
- `scripts/reseed_from_legacy_top.py`
- `scripts/wilson_wr_rescore.py`
- `scripts/valgate_counterfactual.py`

---

## §7 — Candidate blocklist additions (carried into `mutation_blocklist.yaml`)

1. SQL-012 `arena4_pass()` — currently code-gated only; add `PROMOTE_MIN_TRADES`-like explicit gate at DB level.
2. SQL-019 `check_daily_reset()` — scheduled ELO reset is ungated; require ADR + cron-audit trail.
3. SQL-029 `rescan_legacy_with_new_gates.py` — undocumented gate semantics; add explicit `--allow-legacy-rescan` flag.
4. SQL-036 `zangetsu_ctl.sh reap` — default --dry-run when invoked by non-j13 owner.
5. `arena13_feedback` guidance file — expose age via API so the A1 consumer can drift-detect.
6. `alpha_discovery.py` cron — since the flag frozen, remove the cron entirely to prevent accidental lift (evidence-safe).

These are **proposals** for Ascension Phase 7; not applied in Phase 0.
