# Zangetsu — State of Truth (Phase 0 Lock)

**Program:** Zangetsu Engine Ascension v1
**Phase:** 0 — State of Truth Lock
**Date:** 2026-04-23 (Asia/Taipei)
**Author:** Claude Lead (synthesis from Explore survey + charter §17 + Recovery Program v1 evidence)
**Status:** BASELINE — becomes authoritative snapshot once approved by j13.
**Zero-intrusion:** pure documentation; no prod code changed.

---

## §1 — Purpose

This document locks the current, verified reality of the Zangetsu production system so that every subsequent Ascension action (Phase 1 reconstruction, Phase 2 modularization, Phase 3 defect seizure, Phase 4 truth audit, Phase 5 compute topology, Phase 6 observability, Phase 7 patches, Phase 8 operating model) has one authoritative baseline to diff against.

No future proposal may claim "this is how it works today" without citing this doc.

---

## §2 — System Identity (explicitly preserved)

Per Ascension spec §2, the identity to preserve:

- **Arena-based discovery architecture** (A1 → A2 → A3 → A4 → A5 → Deployable).
- **Broad / semi-random search** as primary alpha discovery mechanism (GP via DEAP PrimitiveSet + j01/j02 fitness).
- Zangetsu is NOT a hand-crafted strategy framework. It is NOT a static factor-ranking pipeline. Neither direction is acceptable as a "simplification."

---

## §3 — Current operating modes

| Mode | How entered | What runs | Current state 2026-04-22T19:05Z |
|---|---|---|---|
| **Production (A1 evolution)** | `zangetsu_ctl.sh start` spawns 4 × `arena_pipeline.py` workers w0-w3 keyed by `STRATEGY_ID=j01/j02` | GP evolution on 14-symbol × 15m with TRAIN slice | **RUNNING** — PIDs 2385765/88/812/904, since 17:52:30Z |
| **Production (A2/A3)** | Same ctl script spawns `arena23_orchestrator.py` | Processes ARENA1_COMPLETE rows via holdout (v0.7.2.3) / train slice | **RUNNING** — PID 2385996 since 17:52:32Z, CD-14 holdout path active |
| **Production (A4/A5)** | Same ctl script spawns `arena45_orchestrator.py` | Arena 4 / 5 gates + card state management | **RUNNING** — PID 2386067 |
| **Production (validator)** | DB trigger `admission_validator($staging_id)` called synchronously by A1 after INSERT into staging | PL/pgSQL: 3 gates (alpha_hash format / epoch / arena1_score finite) + dedup via `ON CONFLICT` | Live (function body contains admitted_duplicate handling from v0.7.2.3) |
| **Telemetry + outcome** | Cron `* * * * * zangetsu_snapshot.sh` every minute | Dumps `/tmp/zangetsu_live.json` + engine_telemetry batch flush | Writing every 60s; 2339 bytes last observed |
| **Watchdog** | Cron `*/5 * * * * watchdog.sh` | PID liveness check + restart dead workers | Running |
| **A13 feedback** | Cron `*/5 * * * * arena13_feedback.py` | Writes `a13_guidance.json` for A1 weight guidance | Running |
| **Data collector** | Cron `0 */6 daily_data_collect.sh` | Merges OHLCV/funding/OI parquet | Running |
| **Calcifer RED gate** | File `/tmp/calcifer_deploy_block.json` presence | `feat(zangetsu/vN)` commits blocked per §17.3 | RED (dc=0, last_live=null) since ~2026-04-22 morning |
| **R2-N4 observation window** | `r2_n4_watchdog.py` nohup process | Polls VIEW + alerts on 3 conditions; logs snapshot every 10 min | Running until 2026-04-22T19:56:47Z |

---

## §4 — Verified system state (2026-04-22T19:05Z)

### §4.1 Production database (zangetsu on `deploy-postgres-1`)

| Metric | Value |
|---|---|
| `zangetsu_status.deployable_count` | **0** |
| `deployable_historical / fresh / live_proven` | 0 / 0 / 0 |
| `active_count` / `candidate_count` | 0 / 0 |
| `champions_last_1h` | 0 |
| `last_live_at_age_h` | NULL |
| `champion_pipeline_fresh` — 89 rows, 100% ARENA2_REJECTED / INACTIVE |
| `champion_pipeline_staging` — 95 admitted_duplicate + 89 admitted |
| `champion_pipeline_rejected` — 0 rows |

### §4.2 Live Calcifer deploy block
```
status=RED  deployable_count=0  last_live_at_age_h=null
ts=2026-04-22T17:29:40Z
reason="deployable_count==0 AND age=None>6.0h"
```
Per §17.3, any `feat(zangetsu/vN)` commit is BLOCKED.

### §4.3 Repo / GitHub
- Repo: `/home/j13/j13-ops/` (Alaya) + `github.com/M116cj/j13-ops` (origin)
- Main SHA (local = origin): `a9572d8e` (full backup confirmed 2026-04-22T19:01Z as precondition for this Phase 0)
- Zangetsu scope HEAD commits (newest→oldest):
  - `a9572d8e chore(zangetsu/results): 20260422 7-task experiment outputs`
  - `3ad7c6ae chore(zangetsu/doe-session): DOE probe + lean-pset scaffolding`
  - `af6e8172 chore(zangetsu/r2): R2-N4 observation watchdog`
  - `bd91face fix(zangetsu/r2-hotfix): v0.7.2.2 threshold revert + CD-14 holdout`
  - `480976c1 docs(zangetsu/policy-layer): path fix`
  - `14da62c5 feat(zangetsu/policy-layer): Family-Aware Policy + Exception Overlay`
  - `f098ead5 fix(zangetsu/v0.7.2.2): signal threshold 0.80→0.95`
- Uncommitted (out of this scope lock): calcifer/* state files only

### §4.4 Mutation surfaces (summary; full detail in `mutation_surface_map.md` v2)
**54 total** in v2 (was 48 in v1 — **6 surfaces added** after Gemini Phase 0 review):
- **42 SQL writes** (unchanged count, but note one flagged for spam risk: `engine_telemetry` flush in SQL-001/005)
- **3 file writes**
- **3 process / signal mutations**
- **+2 external-service mutations** added v2: AKASHA `POST /memory` (write via `write_to_akasha_sync`), AKASHA `POST /compact` (ungated chunk-deletion surface — **HIGH BLAST**)
- **+3 hook / launchd surfaces** added v2: `~/.claude/hooks/pre-bash.sh`, `~/.claude/hooks/pre-done-stale-check.sh`, `com.j13.d-mail.v2.plist` (launchd Mac→Alaya auth sync)
- **+1 cross-process dependency** added v2: `/tmp/zangetsu_live.json` writer → A1 / arena13_feedback reader (state leaks from snapshot into live workers)

By subsystem:
| Subsystem | SQL writes | File | Process | Notes |
|---|---|---|---|---|
| arena_pipeline (A1) | 5 | — | — | Double-gated: staging + admission_validator |
| arena23_orchestrator (A2/A3) | 5 | — | — | FOR UPDATE SKIP LOCKED + lease |
| arena45_orchestrator (A4/A5) | 9 | — | — | ELO + card state + promotion gate |
| shared_utils (reap) | 1 | — | — | Atomic CTE + lease_minutes floor |
| Seed + discovery (**DEPRECATED**) | 6 | — | — | Requires `--i-know-deprecated-v071` flag |
| Manual scripts (CLI) | 6 | — | — | Human-invoked, admission_validator gated |
| Arena13 feedback | 1 | 2 | — | Soft guidance + gating JSON |
| DB audit trail | 1 | — | — | Best-effort, non-blocking |
| Maintenance (ctl reap) | 1 | — | — | `--dry-run` available |
| Data collector | — | 1 | — | Parquet append-merge |
| Pidlock + signals | — | 1 | 1 | fcntl.flock + SIGTERM/SIGKILL chain |
| Process control (ctl) | — | — | 2 | start/stop/restart |

Zero outbound network POST/PUT/DELETE from Zangetsu workers. Only read-only ingress (Binance data collector).

---

## §5 — Gates currently in force

### §5.1 DB-level
- **`admission_validator($staging_id)` trigger / function** — 3 gates + ON CONFLICT + staged atomic move
- **`uniq_alpha_hash_v10`** — partial unique index on fresh
- **`valid_admission_state` CHECK constraint** — extended in v0.7.2.3 to include `admitted_duplicate`
- **`FOR UPDATE SKIP LOCKED`** — used by pick_champion / pick_arena3_complete / reap_expired_leases

### §5.2 Process-level
- **`pidlock.py` fcntl.flock** — advisory exclusive lock per worker role (prevents double-spawn)
- **`lease_until` reaping** — stuck ARENA*_PROCESSING reverted by `reap_expired_leases` atomic CTE (min 1 min floor)
- **§17.6 stale-service check** — pre-commit hook `~/.claude/hooks/pre-done-stale-check.sh` enforces process_start > source mtime before declaring "done"

### §5.3 Governance-level (charter §17)
- **§17.1 Single truth** — `zangetsu_status` VIEW is the outcome oracle
- **§17.2 Mandatory witness** — AKASHA independent-agent signing for feat() version bumps
- **§17.3 Calcifer outcome watch** — deployable_count==0 & age>6h → RED → commit block
- **§17.4 Auto-regression revert** — deployable_count drop OR age>12h with new feat() → auto `git revert`
- **§17.5 Version bump is bot action** — only `bin/bump_version.py` may emit `feat(<proj>/vX.X)`
- **§17.6 Stale-service check** — running process must be ≥ source mtime before "done"
- **§17.7 Decision record CI gate** — PR blocks if commit matches `^(feat|fix|refactor)\(.*/v` without matching docs/decisions/YYYYMMDD-*.md
- **§17.8 Scratch → tests integration** — smoke tests in `.claude/scratch/*-smoke.py` aged >3d alert, >7d auto-delete

### §5.4 Code-level
- **`verify_no_archive_reads.sh`** — pre-start governance (rule #5): blocks bare `champion_pipeline` in SQL (enforces the staging/fresh/rejected/legacy split)
- **Deprecated flag guard** — `--i-know-deprecated-v071` required for seed_*, alpha_discovery, factor_zoo
- **`--allow-dirty-tree`** — override flag for `cold_start_hand_alphas.py` (operator ad-hoc)
- **Soft guidance cap** — `MAX_WEIGHT_DELTA_PCT=50%` in A13 feedback (rejects sudden large weight swings)

---

## §6 — Architecture assumptions (explicit)

Assumptions currently held by the codebase — these become the baseline the Ascension program must either preserve or formally change via ADR:

1. **Data window**: 200,000 bars per symbol × 14 symbols, stratified TRAIN_SPLIT_RATIO=0.7 (train 140k / holdout 60k).
2. **Forecast horizon**: `ALPHA_FORWARD_HORIZON=60` bars (env-configurable default). Current fitness + A2 evaluate signed forward return at this horizon.
3. **Signal convention**: `alpha_signal.py` converts rolling-rank to signal via `size = 2 × |rank - 0.5|`. Long-on-high-rank hardcoded (phase-3B signed-bug fix is partial — remaining Phase 3C direction-sign patch applied).
4. **Primitive set (pset_v0)**: 126 indicators × 6 periods + 35 operators = 166 primitives. pset_v2 (55) prototyped offline, not active.
5. **Cost model**: per-tier round-trip 11.5 / 14.5 / 23 bps (Stable / Diversified / High-Vol). Source: Binance Futures taker rates + slippage estimate.
6. **Workers**: 4 × A1 (2 × j01 + 2 × j02) + 1 × A23 + 1 × A45. All lockfile-managed.
7. **DB table model** (v0.7.1 governance split):
   - `champion_pipeline_staging` (pending → admitted / admitted_duplicate / pending_validator_error)
   - `champion_pipeline_fresh` (live: ARENA1_COMPLETE / _PROCESSING / _REJECTED up through DEPLOYABLE / DEPLOYABLE_LIVE)
   - `champion_pipeline_rejected` (terminal failure archive)
   - `champion_legacy_archive` (pre-v0.7.1 alphas, read-only)
8. **AKASHA**: `http://100.123.49.102:8769` is the session / memory / compact hub. GET /context, POST /memory, POST /compact.
9. **Telegram**: @Alaya13jbot publishing channel + @macmini13bot CLI bot + two miniapps (`d-mail-miniapp` :8771, `calcifer-miniapp` :8772).
10. **Control surface**: scattered. No central control-plane yet. Parameters live across:
    - env vars (ALPHA_FORWARD_HORIZON, ALPHA_ENTRY_THR, STRATEGY_ID, …)
    - `zangetsu/config/settings.py` (promotion gates)
    - `zangetsu/config/family_strategy_policy_v0.yaml` (policy registry — **INERT** per N1.4)
    - `zangetsu_ctl.sh` (worker counts)
    - DB function bodies (admission_validator gate logic)
    - Hardcoded literals in orchestrator (A2 grid thresholds, baseline 0.55/0.30)

Assumption (10) is explicitly targeted by Ascension Phase 2 (control-plane blueprint).

---

## §7 — Evidence that the system is currently "honest-but-no-edge" (critical)

Per R2-N4 observation (T+70min at time of writing) + prior investigation chain:

- Phase 3A: random-GP gross edge median ≈ 0 bps / trade (cost-dominant)
- Phase 3B: 63% of alphas traded wrong direction (system bug) — direction-sign patch applied in Phase 3C
- Phase 3D-a: 638 archive champions, 0 survive current conditions (90% were always false positives)
- Phase 3E: GP re-architecture, 4 arms `inserted=0` offline
- Phase 4A: LGBM baseline, 14/14 symbols reject_val_neg, y_hat Spearman ≈ 0
- **R2 (today)**: CD-14 holdout revealed 89 cold-start alphas all fail at `pos_count=0` — net_pnl ≤ 0 AND sharpe ≤ 0 AND pnl_per_trade ≤ 0 on OOS. 100%.

Current interpretation (hypothesis labeled **PROBABLE**): market efficiency at 60-bar forward return on 15m OHLCV+126-indicator space is near R²≈0. Pipeline exposes this truth rather than hiding it.

Alternative hypotheses not yet ruled out (labeled **INCONCLUSIVE** — will be addressed by Phase 4 signal-truth + gate-truth audit):
- H2 primitive-layer collapse (pset too narrow / wrong inductive bias)
- H3 regime-conditional edge (current holdout sits in low-edge regime)
- H4 residual signal-path bug (Phase 3B fix incomplete)
- H5 horizon mismatch (edge at 5-bar or 200-bar, not 60)
- H6 search efficiency (GP fitness too noisy for navigation) — added by Gemini pre-review

Ascension Phase 4 will disambiguate with VERIFIED / PROBABLE / INCONCLUSIVE / DISPROVEN labels.

---

## §8 — Confidence labels (per Ascension §4 rule; downgraded v2 after Gemini review)

| Claim | Label | Caveat |
|---|---|---|
| Workers running from bd91face / services mtime 17:52:14Z | **PROBABLE** (downgraded from VERIFIED) | `ps` + `stat` can be true while live Python runs stale bytecode via `imp.reload` / `exec()`. Upgrade to VERIFIED requires in-process bytecode hash probe (Phase 6 observability). |
| 54 mutation surfaces catalogued (v2) | **PROBABLE** (downgraded from VERIFIED) | Single-agent Explore survey is survey-limited. Exhaustive verification requires multi-agent cross-check (Gemini + Codex + manual diff) — Phase 3. |
| Admission validator gates correctness | **PROBABLE** (downgraded from VERIFIED) | Function body read from `pg_proc` matches migration source, but DB-side triggers / cascades / side-effects (pg_notify / plpython) not yet fully audited. |
| 89 ARENA2_REJECTED under CD-14 all pos_count=0 | **PROBABLE** (downgraded from VERIFIED) | `engine.jsonl` parsing assumed 100% reliable; async logging / rotation / disk-full can lose lines. Gemini §B caveat accepted. |
| Calcifer RED reflects real outcome absence | VERIFIED (file content + VIEW match) | |
| "No OOS edge at 60-bar 15m OHLCV+indicator" | PROBABLE (multiple phases of offline + R2 live all converge, but not exhaustive hypothesis ruling) | |
| "Archive champions would survive different horizon" | INCONCLUSIVE (not tested) | |
| pset_v0 is insufficient | INCONCLUSIVE (D1-D horizon-swept SNR needed) | |
| AKASHA/telegram/miniapp surfaces are REAL | VERIFIED (live endpoint probe + Gemini audit adjusted for v0.5.5 truth) | |
| Control plane exists | DISPROVEN (scattered per §6-10) | |
| **Safety-contract rules have POST-violation detection** (added v2) | **DISPROVEN** | Gemini §D — rules are PRE-commit / PRE-execution only. No reconciler cron currently audits DB/files against contract rules. Phase 6 observability must add. |
| **Ingress data integrity (Binance OHLCV) verified** (added v2) | **INCONCLUSIVE** (added as non-goal §9) | Phase 0 assumes data_collector output is trustworthy. Corruption/tamper not in Phase 0 scope. |

---

## §9 — Non-goals for Phase 0

- NOT fixing any defect here — that's Phase 3.
- NOT designing the modular target architecture — that's Phase 2.
- NOT deciding whether to change horizon / target / pset — that's Phase 4 + D1.
- NOT touching production — zero mutation.
- NOT promoting any optimization — Phase 5.
- **NOT verifying ingress data integrity** (added v2 per Gemini §E): Phase 0 treats Binance OHLCV + funding + OI parquet as authoritative input. If the `daily_data_collect.sh` pipeline or upstream exchange API is tampered with, the entire state-of-truth is built on corrupt evidence. Ingress integrity is explicitly OUT-OF-SCOPE for Phase 0 — no attempt to protect against it here. Phase 6 observability may add content-hash attestation and Phase 7 patch plan may add a deterministic replay audit, but neither is promised by Phase 0.
- **NOT attesting multi-owner commit races** (added v2 per Gemini §C.4): Phase 0 assumes a single `j13` identity. If Mac + Alaya submit `feat(…/vN)` simultaneously, `bin/bump_version.py` is not protected by distributed locking. Explicit non-goal here; a fix is Phase 7 backlog.

---

## §10 — Phase 0 exit criteria

- ✅ `state_of_truth.md` (this doc) approved by j13
- ✅ `production_safety_contract.md` — binding rules (sibling doc)
- ✅ `mutation_surface_map.md` — full file:line table (sibling doc)
- ✅ `mutation_blocklist.yaml` — machine-readable blocklist (sibling doc)
- ✅ Gemini adversarial review integrated
- ✅ All changes markdown/yaml only; zero prod touch

Once signed off: Phase 1 (System Reconstruction) begins. Phase 1 output: intended vs actual architecture diff + drift map + scattered-config map + IO-path map.
