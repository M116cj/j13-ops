# Actual Architecture — Zangetsu MOD-1

**Order**: `/home/j13/claude-inbox/0-2` Phase 2 deliverable
**Produced**: 2026-04-23T03:08Z
**Author**: Claude (Lead)
**Base authoritative source**: `zangetsu/docs/ascension/phase-1/actual_architecture.md` (Gemini round-2 ACCEPTED v2.1).
**Status**: MOD-1 Phase 2 exit criterion MET — current Zangetsu reality is mapped as an evidence-backed system map.

---

## §MOD-1.A — Envelope

MOD-1 Phase 2 asks for an evidence-backed map of:
- current live / frozen / deferred / experimental / local-only components
- current repos / worktrees / assets
- current governance / monitoring / recovery / discovery surfaces
- local-only and off-repo risks

The authoritative snapshot is preserved below. This MOD-1 wrapper adds post-0-1 state deltas.

---

## §MOD-1.B — Post-0-1 updates (deltas vs Ascension v2.1 snapshot 2026-04-22)

| Delta | Change | Source |
|---|---|---|
| Arena processes | were RUNNING → **now FROZEN** (0 processes; killed 2026-04-23T00:35:57Z) | `docs/recovery/20260423/phaseA_kill_trace.txt` |
| `calcifer/zangetsu_outcome.py` | was UNTRACKED → **now TRACKED + LIVE** (commit `ae738e37`) | `docs/recovery/20260423/calcifer_state_formalization.md` |
| `calcifer/maintenance.log` + `maintenance_last.json` + `report_state.json` | were TRACKED runtime-state (polluting diffs) → **now gitignored + untracked from HEAD** (commit `ae738e37`) | same |
| `arena13_feedback.py` | previously presumed LIVE → **VERIFIED silently failing** (KeyError on ZV5_DB_PASSWORD env every 5min since unknown date) | `docs/recovery/20260423/freeze_failed_formulation_report.md §6` + `infra_blocker_report.md §2 B5` |
| `d-mail-miniapp/` | listed as LIVE → **VERIFIED NOT under version control** (critical infra blocker B3) | `docs/recovery/20260423/infra_blocker_report.md §2 B3` |
| `calcifer-miniapp/` | same | `infra_blocker_report.md §2 B4` |
| Alaya GPU | previously unknown → **VERIFIED driver never installed** (CUDA user-space libs only; no nvidia-driver-* package; no nvidia.ko loaded) | `docs/recovery/20260423/gpu_driver_repair_report.md` |
| main HEAD | `fd7cc34e` (docs) → **`ae738e37`** (calcifer fix) → **`f3151220`** (recovery docs) → **new HEAD after MOD-1 commit** | git log |
| docs/recovery/ directory | did not exist → **NOW EXISTS** with 17-file 0-1 paper trail | `docs/recovery/20260423/` |

Everything else in the base actual_architecture.md snapshot remains accurate; the base doc was Ascension-authored at ~2026-04-22T19:30Z, shortly before 0-1 freeze.

---

## §MOD-1.C — Live/frozen/deferred/experimental/local-only classification (post-0-1)

Adding the MOD-1-required dimension:

### LIVE (running, version-controlled, healthy)
- `calcifer-supervisor.service` (systemd, running supervisor.py — but STALE binary until B10 restart — see blocker)
- `calcifer-miniapp.service` (external repo risk per B4)
- `console-api.service` (zangetsu console :9900)
- `dashboard-api.service` (zangetsu dashboard :9901)
- `d-mail-miniapp.service` (external repo risk per B3)
- Docker: `deploy-postgres-1`, `akasha-postgres`, `akasha-redis`, `akasha-harness`, `obs-postgres-exporter`
- cron: `zangetsu_snapshot.sh`, `daily_data_collect.sh`, `watchdog.sh`, hourly reports, arena13_feedback (but crashing — §MOD-1.B)

### FROZEN (intentionally stopped, authoritative state)
- arena_pipeline.py × 2
- arena23_orchestrator.py
- arena45_orchestrator.py
- (frozen under 0-1 Phase A; restart blocked until r2_patch_validation_plan §2 triggers A/B/C)

### DEFERRED (explicitly not-yet-implemented per 0-1 Phase D)
- systemd formalization for arena (see `systemd_deferral_memo.md`)
- Track 3 discovery restart (see `track3_restart_memo.md`)
- Phase3e branch merge
- full modular engine migration (MOD-1 plans it; Phase 7 implements)
- control-plane runtime rollout
- ascension architectural implementation

### EXPERIMENTAL / ACTIVE-RESTRICTED
- DOE probe scripts under `scripts/` (operator-only invocations; see Ascension §3.3.1)
- `/home/j13/zangetsu-phase3e/` worktree (latent shadow)

### LOCAL-ONLY / OFF-REPO RISK
- `/home/j13/d-mail-miniapp/` — NO .git (B3 CRITICAL)
- `/home/j13/calcifer-miniapp/` — NO .git (B4 HIGH)
- `/tmp/*.json` state files — ephemeral, acceptable
- `/tmp/*.md` report artifacts — ephemeral, acceptable
- `~/.claude/hooks/*.sh` — local to Mac; tracked in separate `M116cj/claude-os` backup per §13

### CRITICAL BLOCKERS OPEN
- B1 GPU driver missing (pending j13 presence)
- B3 d-mail-miniapp off git (pending repo owner decision)
- B4 calcifer-miniapp off git (pending repo owner decision)
- B5 arena13_feedback cron env (pending arena restart trigger)
- B7 Gemini CLI Mac-side broken (pending Mac session)
- B10 calcifer supervisor stale binary (pending sudo)

---

## §MOD-1.D — Label per 0-2 rule 10

- §1 current shape statement: **VERIFIED** (ssh + docker exec + git + filesystem probes)
- §2 mapping to 9-layer target: **PROBABLE** (interpretive — Gemini round-2 accepted)
- §3 subsystem inventory: **VERIFIED** (live state minus the §MOD-1.B deltas above)
- §4 data flow: **VERIFIED**
- §5 drift concrete examples: **VERIFIED** (backed by N1.1/N1.3/N1.4 evidence)
- §6 confidence labels: already scoped per Phase 0 scheme

---

## §MOD-1.E — Exit criterion

MOD-1 Phase 2 exit: *"The team can explain current Zangetsu reality as an evidence-backed system map."*

Met by: §1 current shape + §2 layer mapping + §3 active/frozen/inert/active-restricted inventory + §4 data flow + §5 drift examples + §MOD-1.B post-0-1 deltas + §MOD-1.C classified subsystem list.

Proceed to Phase 3 (`architecture_drift_map.md`).

---

## §MOD-1.F — Authoritative content (preserved from Ascension Phase-1 v2.1)

The full snapshot follows unchanged.

---

# Zangetsu — Actual Architecture

**Program:** Zangetsu Engine Ascension v1
**Phase:** 1
**Date:** 2026-04-23
**Author:** Claude Lead
**Status:** BASELINE SNAPSHOT — what Zangetsu currently is. Not what it should be.
**Zero-intrusion:** pure documentation from Phase 0 evidence + repo read.

---

## §1 — Current shape (honest)

Zangetsu today is a **script-centric pipeline with embedded arena logic**. It has most of the right components but they are not layered; responsibilities are mixed, controls are scattered, and there is no explicit control-plane.

Key layout on Alaya:

```
/home/j13/j13-ops/           (git root, github.com/M116cj/j13-ops)
├── zangetsu/
│   ├── services/
│   │   ├── arena_pipeline.py           # A1 GP evolution loop (924 WITH R2 patch)
│   │   ├── arena23_orchestrator.py     # A2 + A3 evaluation (1800+ lines including CD-14)
│   │   ├── arena45_orchestrator.py     # A4 + A5 + card state + ELO
│   │   ├── arena13_feedback.py         # guidance feedback writer (every 5 min)
│   │   ├── alpha_discovery.py          # FROZEN (deprecated-flag guard)
│   │   ├── db_audit.py                 # log_transition helper
│   │   └── shared_utils.py             # claim_champion / release_champion / reap_expired_leases
│   ├── engine/
│   │   └── components/
│   │       ├── alpha_engine.py         # DEAP GP primitive registration + fitness call
│   │       ├── alpha_signal.py         # rank-to-signal conversion (size = 2*|rank-0.5|)
│   │       ├── alpha_primitives.py     # indicator + operator catalog
│   │       ├── indicator_bridge.py     # bridge between numpy / numba / signal
│   │       ├── pset_lean_config.py     # lean-pset probe (48 terminals) — in WIP
│   │       └── [other primitives + fitness fns]
│   ├── config/
│   │   ├── settings.py                 # PROMOTE_* constants, TRAIN_SPLIT_RATIO, etc.
│   │   ├── family_strategy_policy_v0.yaml  # INERT (N1.4 — not wired)
│   │   ├── j01_strategy.py / j02_strategy.py  # per-strategy fitness definitions
│   │   └── …
│   ├── scripts/
│   │   ├── zangetsu_ctl.sh             # start/stop/status/reap/logs/health
│   │   ├── zangetsu_snapshot.sh        # cron every 1 min → /tmp/zangetsu_live.json
│   │   ├── daily_data_collect.sh       # cron 6h
│   │   ├── watchdog.sh                 # cron 5 min
│   │   ├── verify_no_archive_reads.sh  # governance §17 rule #5
│   │   ├── seed_*.py                   # manual seeders
│   │   ├── cold_start_hand_alphas.py   # cold-start seed
│   │   ├── rescan_legacy_with_new_gates.py
│   │   ├── reseed_from_legacy_top.py
│   │   ├── wilson_wr_rescore.py
│   │   ├── valgate_counterfactual.py
│   │   ├── r2_n4_watchdog.py           # observation watchdog (R2-N4)
│   │   ├── alpha_zoo_injection.py      # DOE probe (WIP)
│   │   ├── validate_lean_pset.py       # DOE probe (WIP)
│   │   ├── zangetsu_combo_run.py       # DOE probe (WIP)
│   │   ├── zangetsu_zoo_run.py         # DOE probe (WIP)
│   │   ├── signal_quality_report.py    # hourly report
│   │   ├── v10_alpha_ic_analysis.py    # hourly report
│   │   ├── v10_factor_zoo_report.py    # hourly report
│   │   └── v8_vs_v9_metrics.py         # hourly report
│   ├── data/
│   │   ├── ohlcv/*.parquet
│   │   ├── funding/*.parquet
│   │   └── oi/*.parquet
│   ├── tests/
│   │   └── policy/…  (only policy-layer tests; services + engine not broadly tested)
│   ├── docs/
│   │   ├── decisions/
│   │   ├── retros/
│   │   └── ascension/phase-0/ + phase-1/
│   ├── results/                        # experiment-output archive
│   └── VERSION_LOG.md
├── calcifer/                           # separate process (Alaya infra guardian)
│   ├── notifier.py                     # shared Telegram + AKASHA write helper
│   ├── supervisor.py
│   └── … (sibling; out of Zangetsu scope except as dependency)
├── infra/
│   └── magi/                           # docker-compose, litellm_config, etc.
└── .gitignore
```

Deployed elsewhere on Alaya:
- `/home/j13/d-mail-miniapp/server.py` — v0.5.5 miniapp (1241 lines, port 8771)
- `/home/j13/calcifer-miniapp/` — port 8772
- AKASHA at `:8769`, Claude Inbox at `:8765`, Redis `localhost:6379` (native)
- Docker: `deploy-postgres-1` (Postgres for zangetsu DB)

**Added v2 per Gemini §B (paths previously missed)**:
- `/home/j13/zangetsu-reports/` — **permanent report artifacts** archive (not transient `/tmp/*.md`). Git-tracked separate checkout; distinct from the zangetsu source tree.
- `/home/j13/strategic-research/` — **white-box control surface for human intent**; research artifacts codifying what we *want* Zangetsu to do. Not yet integrated into control plane.
- `/home/j13/zangetsu-phase3e/` — **latent shadow worktree** of `feat/zangetsu-phase3e-rearch` branch. Not "stashed" — present on disk, invokeable if someone cds into it. Treat as L4 peer-shadow until explicitly removed.
- **Claude Inbox backchannel** (`:8765`) — not merely a "queue". Per Gemini §B.1: this is the primary L1 bypass for the Claude CLI. When Claude CLI pulls from Inbox, it bypasses the `@macmini13bot` auth + miniapp owner-fresh layers. Needs explicit control-plane mapping in Phase 2.

---

## §2 — How responsibilities map to (the absence of) the 10 intended layers

| Intended layer (v2 numbering) | Actual location | Problem |
|---|---|---|
| L1 Control Plane | **DOES NOT EXIST as a layer.** Closest thing is `zangetsu_ctl.sh` + `@macmini13bot` + v0.5.5 miniapp. But: no central authoritative store for parameters; no decision-rights enforcement; no rollout-state machine. | Configs scattered across env / settings.py / yaml / ctl / DB function bodies / orchestrator hardcoded literals. |
| L2 Engine Kernel | Split across `shared_utils.claim_champion/release_champion/reap_expired_leases` + per-orchestrator main loops | No single "kernel" object; state-machine logic duplicated in orchestrators. |
| L3 Data Input | `data_collector.py` + `data/*/parquet` | Works (cron, parquet merge), but no schema registry, no per-source health endpoint, no integrity attestation. |
| L4 Research | `arena_pipeline.py` + `engine/components/alpha_*.py` + pset config | Monolithic: GP loop, primitive registration, fitness call, DB IO all mixed in single file. Lean-pset probe lives next to full pset without registry. |
| L5 Evaluation | Embedded inside `arena23_orchestrator.py::process_arena2/3` + `arena45_orchestrator.py::arena4_pass/arena5_*` + `backtester.run` | No unified evaluator; train/holdout/oos split is per-orchestrator-defined; cost model lives in `settings.py` + hardcoded literals. |
| L6 Gate | Mixed: `admission_validator` PL/pgSQL + orchestrator per-arena gates (hardcoded thresholds) + `PROMOTE_*` in `settings.py` + Calcifer block file | Five different gate authors, no unified registry, no version history. |
| L7 Output | `champion_pipeline_fresh` table + `/api/zangetsu/live` file snapshot + miniapp + Telegram via calcifer | Output targets are wired ad-hoc; no publish contract; no schema versioning. |
| **L8 Integrity & Governance** (merged v2: was L8 + L9) | L8.O: `zangetsu_status` VIEW + `/tmp/*.md` reports + engine.jsonl + Calcifer block file. L8.G: `verify_no_archive_reads.sh` + charter §17 + pre-bash hook + decision records + CI (partially). | L8.O: no metric export; L8.G: most rules are HUMAN disciplines, not code-enforced. Post-violation detection absent. |
| **L9 Black-box Adapter Pattern** (demoted v2: was L10) | **DOES NOT EXIST.** | LGBM / future transformer / external agents have no wrapper contract. Demoted from layer to pattern because only GP is active today (D-07). |

---

## §3 — Subsystem inventory (actual)

### §3.1 Active (running) subsystems
| Name | Files | Role | State |
|---|---|---|---|
| **A1 worker** | `services/arena_pipeline.py` × 4 (w0-w3, STRATEGY_ID=j01/j02) | GP evolution loop, writes candidates to staging | RUNNING |
| **A2/A3 orchestrator** | `services/arena23_orchestrator.py` × 1 | Polls ARENA1_COMPLETE from fresh, runs A2 (holdout via CD-14), A3 (train) | RUNNING |
| **A4/A5 orchestrator** | `services/arena45_orchestrator.py` × 1 | A4 promotion gate, A5 tournament, card state | RUNNING |
| **admission_validator** (PL/pgSQL) | DB function, synchronously called by A1 | 3 gates + dup handling | LIVE |
| **zangetsu_snapshot cron** | `scripts/zangetsu_snapshot.sh` every 1 min | Writes `/tmp/zangetsu_live.json` | LIVE |
| **arena13_feedback cron** | `services/arena13_feedback.py` every 5 min | Writes guidance JSON | LIVE |
| **watchdog cron** | `scripts/watchdog.sh` every 5 min | Worker liveness + restart | LIVE |
| **daily_data_collect cron** | `scripts/daily_data_collect.sh` every 6h | Binance → parquet | LIVE |
| **hourly reports** | `scripts/{signal_quality,v10_alpha_ic_analysis,v10_factor_zoo_report,v8_vs_v9_metrics}.py` | Write `/tmp/*.md` reports | LIVE |
| **r2_n4_watchdog** (R2 observation) | `scripts/r2_n4_watchdog.py` | Nohup background, 2h observation | LIVE (this session) |
| **Calcifer daemon** | `/home/j13/j13-ops/calcifer/supervisor.py` | Writes `/tmp/calcifer_deploy_block.json`, runs maintenance | LIVE (sibling) |
| **d-mail miniapp** | `/home/j13/d-mail-miniapp/server.py` (v0.5.5) | FastAPI on :8771, telegram webapp | LIVE |
| **@macmini13bot agent** | `/Users/a13/dev/d-mail/agent_v2.py` | Mac-side Telegram bot | LIVE via launchd |
| **AKASHA** | `:8769` endpoint (sibling service) | Session memory + compact | LIVE |
| **Claude Inbox** | `:8765` endpoint | User input queue | LIVE |

### §3.2 Frozen / deprecated subsystems
| Name | Why frozen |
|---|---|
| `services/alpha_discovery.py` | v0.7.1 deprecation, `--i-know-deprecated-v071` flag guard |
| `scripts/factor_zoo.py` | same flag guard |
| `scripts/seed_101_alphas*.py` | same flag guard |
| pset_v2 probe (offline Phase 3E) | stashed worktree `feat/zangetsu-phase3e-rearch` |

### §3.3 Inert subsystems (present in code, not wired)
| Name | Evidence |
|---|---|
| Policy Layer v0 (`config/family_strategy_policy_v0.yaml`) | N1.4 said "family_tag is NULL on all 89 fresh rows — not wired into signal generation" |
| Exception Overlay (`config/volume_c6_exception_overlay.yaml`) | part of Policy Layer; same inert status |
| Lean pset (`engine/components/pset_lean_config.py`) | env-gated by `PSET_MODE=lean`; currently disabled in production |

### §3.3.1 Active-Restricted subsystems (reclassified v2 per Gemini §B.2)
Previously labelled "inert" but actually invokeable by operator during DOE probes. Classification change: **Active-Restricted** means "production workers don't touch it, but operator CLI can invoke it during authorized sessions."

| Name | Status | Activation trigger |
|---|---|---|
| `scripts/alpha_zoo_injection.py` | Active-Restricted | operator invocation for zoo probes (seen Apr 22 DOE session) |
| `scripts/zangetsu_combo_run.py` | Active-Restricted | operator invocation for DOE combo runs |
| `scripts/zangetsu_zoo_run.py` | Active-Restricted | operator invocation |
| `scripts/validate_lean_pset.py` | Active-Restricted | operator invocation to sanity-check lean pset |
| `scripts/rescan_legacy_with_new_gates.py` | Active-Restricted | manual re-evaluation runs |
| `scripts/reseed_from_legacy_top.py` | Active-Restricted | manual reseed |
| `scripts/wilson_wr_rescore.py` | Active-Restricted | manual rescore batch |
| `scripts/valgate_counterfactual.py` | Active-Restricted | manual counterfactual runs |
| `scripts/cold_start_hand_alphas.py` | Active-Restricted + **workaround-turned-default risk** (see drift D-23) | operator invocation; `--allow-dirty-tree` guard |

---

## §4 — Data flow (actual, high-level)

```
Binance API ──cron(6h)──▶ data/*/parquet
                              │
                              ▼
                     load at A1 worker startup
                              │
                              ▼
      A1 GP loop ──candidate──▶ admission_validator (DB function)
                              │
                (gates) ──admit──▶ staging → fresh(ARENA1_COMPLETE)
                              │
                 (admitted_duplicate / pending_validator_error → terminal)
                              ▼
                A23 orchestrator claim_champion
                              │
                              ▼
                    process_arena2 on holdout
                              │
              [hardcoded A2 grid: 7 entry×3 exit pairs]
                              │
         (pos_count < 2 OR trades < 25 → ARENA2_REJECTED)
                              ▼
                            fresh
                              │
                              ▼
                       process_arena3 on train
                              │
                              ▼
                A45 orchestrator claim_arena3_complete
                              │
                              ▼
                    process_arena4 + A4 gates
                              │
                              ▼
               promote_candidate (PROMOTE_WILSON_LB gate)
                              │
                              ▼
                fresh(DEPLOYABLE)
                              │
                              ▼
              sync_active_cards → DEPLOYABLE_LIVE / _HISTORICAL
                              │
                              ▼
               A5 tournament + ELO update (passport JSONB)
```

Parallel observability:
- `zangetsu_status` VIEW ← aggregated fresh table state
- `/tmp/zangetsu_live.json` ← snapshot cron
- `/tmp/calcifer_deploy_block.json` ← Calcifer daemon
- `engine.jsonl` ← A1/A23/A45 worker stdout unified

---

## §5 — Where architecture has explicitly drifted (concrete examples)

1. **No kernel**: arena state machine logic duplicated in 3 orchestrators' main loops with subtle differences (lease TTL, retry policy).
2. **Hardcoded thresholds**: `services/arena23_orchestrator.py:156-157` has grid lists `ENTRY_THRESHOLDS=[0.60..0.95]` baked into the file; `:568, :578, :632, :869, :877, :914` have baseline 0.55/0.30 hardcoded.
3. **Split-brain env vars**: N1.3 documented 5 storage sites for the same threshold semantic across arena_pipeline / arena23 / alpha_signal / yaml / grid-list.
4. **Policy registry unused**: family_strategy_policy_v0.yaml declared but never wired into generate_alpha_signals. family_tag is NULL on every fresh row.
5. **CD-14 landed via patch, not kernel contract**: the holdout OOS for A2 is file-level code (`process_arena2` asserts `"holdout" in data_cache`), not a gate-registry property.
6. **Search uses one implementation**: GP via DEAP is the only search path; LGBM baseline was a one-off offline probe. No pluggable search interface.
7. **Five gate authors**: admission_validator / orchestrator code / settings.py constants / yaml registry (inert) / Calcifer block file — no single gate registry.
8. **Output is mainly the DB**: `champion_pipeline_fresh` is the register; dashboards/miniapp/telegram all read from it ad-hoc; no publish contract.
9. **Observability = VIEW + reports**: `zangetsu_status` VIEW does most of the aggregation work; no structured metric export; alert rules spread across watchdog / Calcifer / r2_n4_watchdog.
10. **Black-box adapter layer absent**: LGBM baseline run in Phase 4A had ad-hoc harness; no contract registry.

(Detailed drift entries go in `architecture_drift_map.md`.)

---

## §6 — Confidence on this snapshot

Per Ascension §4 labels:
- **VERIFIED**: list of live workers + cron writers + DB tables (from `state_of_truth.md` v2 + Phase 0 mutation map)
- **PROBABLE**: mapping from actual subsystems to intended layers (interpretation may shift after Gemini review)
- **INCONCLUSIVE**: subsystem boundaries where code is mixed (e.g., is `alpha_signal.py` part of L4 or L5? Currently both)
- **DISPROVEN**: "control plane exists" (confirmed absent)

---

## §7 — Non-goals for this doc

- Not claiming any intended layer is OK to merge into actual — Phase 2 decides.
- Not recommending refactors here — Phase 7 patch queue.
- Not auditing correctness of gates — Phase 4.
- Not optimising compute — Phase 5.
