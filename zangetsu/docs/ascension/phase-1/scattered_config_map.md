# Zangetsu — Scattered Config Map

**Program:** Ascension v1 Phase 1
**Date:** 2026-04-23
**Scope:** every location where a runtime parameter / threshold / mode / schedule lives today.
**Zero-intrusion:** documentation.

---

## §1 — Config storage taxonomy

| Storage class | Example | Binding time | Problem |
|---|---|---|---|
| **Env var** (process env) | `ALPHA_ENTRY_THR`, `STRATEGY_ID`, `TRAIN_SPLIT_RATIO`, `ALPHA_FORWARD_HORIZON`, `PSET_MODE`, `ZANGETSU_LIVE_PATH`, `CURRENT_TASK_PATH` | worker startup | scattered, per-invoker, no discovery |
| **Python module constant** | `settings.py::PROMOTE_WILSON_LB`, `settings.py::PROMOTE_MIN_TRADES`, `MAX_HOLD_BARS`, `LEASE_MINUTES` | import time | fine for infra constants, bad for policy parameters |
| **Hardcoded literal** | `arena23_orchestrator.py:156-157 ENTRY_THRESHOLDS [0.60..0.95]`, `:568, :578 baseline 0.55/0.30`, `arena_pipeline.py:561 default 0.95` | import time | invisible to ops; editable only by devs |
| **Function default** | `alpha_signal.py:19,90 entry_rank_threshold / exit_rank_threshold defaults` | call time | silent fallback when caller omits |
| **YAML declared but inert** | `config/family_strategy_policy_v0.yaml`, `config/volume_c6_exception_overlay.yaml` | N/A (not wired) | looks real but does nothing |
| **DB function body** | `admission_validator` PL/pgSQL gates | migration time | opaque to operators |
| **DB table / VIEW** | `zangetsu_status` VIEW, `champion_pipeline_fresh.status` enum | schema migration | versioned but not discoverable |
| **Cron line** | `* * * * * zangetsu_snapshot.sh` | crontab install | schedule lives outside code |
| **Shell script flag** | `zangetsu_ctl.sh reap --dry-run --age 30` | invocation | operator-driven |
| **File-based state** | `/tmp/calcifer_deploy_block.json`, `/tmp/zangetsu_live.json`, `/tmp/j13-current-task.md`, `config/a13_guidance.json` | file write | no ACL/versioning |
| **Git commit metadata** | charter §17 CI regex rules, decision record naming convention | git time | human discipline |
| **Runtime-computed literal** | A2 grid combinations from ENTRY_THRESHOLDS × EXIT_THRESHOLDS cross-product | import time | hidden multiplication |
| **Agent CLI alias** | `codex-akasha` → `codex`, `gemini-akasha` → `gemini` | shell init | cross-layer behavior change via shell alias |
| **Mac LaunchAgent plist** | `/Users/a13/Library/LaunchAgents/com.j13.d-mail.plist` | launchctl | controls bot process lifecycle from Mac |

13 storage classes — **no single source of truth**.

**Missing categories (added v2 per Gemini §D.1):**
- **Resource Budgets** — per-worker CPU quota, RAM limit, IO weight. Currently ZERO storage location; `nice -n 10` is the only resource knob in use (alpha_discovery cron).
- **Concurrency Scaling** — max total worker count across all strategy IDs. Currently unbounded by code; `zangetsu_ctl.sh start` picks hardcoded `A1_WORKERS=4`. No mechanism to scale up/down based on load or time-of-day.

These categories belong in the future L1 control plane.

---

## §2 — Per-parameter inventory

### §2.1 Signal generation
| Parameter | Locations | Current values |
|---|---|---|
| `ENTRY_THR` / `EXIT_THR` | `arena_pipeline.py:561-562` (env default) | HEAD after R2: 0.80 / 0.50 (reverted from 0.95/0.65) |
| `_V10_ENTRY_THR` / `_V10_EXIT_THR` | `arena23_orchestrator.py:174-175` | 0.80 / 0.50 (never changed by f098ead5) |
| `entry_rank_threshold` default | `alpha_signal.py:19` | 0.80 |
| `exit_rank_threshold` default | `alpha_signal.py:90` | 0.50 |
| Volume family | `family_strategy_policy_v0.yaml::volume` | entry=0.90, exit=0.50 (**INERT**) |
| Breakout family | `family_strategy_policy_v0.yaml::breakout` | entry=0.80, exit=0.50 (**INERT**) |
| Fallback family | `family_strategy_policy_v0.yaml::fallback` | entry=0.80, exit=0.50 (**INERT**) |
| AD3 baseline | `arena23_orchestrator.py:568,578,632,869,877,914` hardcoded literal | 0.55 / 0.30 |
| A2 grid | `arena23_orchestrator.py:156-157 ENTRY_THRESHOLDS/EXIT_THRESHOLDS` | [0.60,0.70,0.80,0.85,0.90,0.95] × [0.20,0.30,0.40,0.50] |

**Drift**: 9 locations hold the same semantic. **6 distinct active values (updated v2 per Gemini §D.2)**: 0.80/0.50 (three modules), 0.95/0.65 (HEAD arena_pipeline default), 0.55/0.30 (AD3 baseline), 0.90/0.50 (yaml volume, inert), 0.80/0.50 (yaml breakout, inert), 0.60..0.95 × 0.20..0.50 (grid lists, many points). Policy Layer v0 values are advertised but never reach production.

### §2.2 Data & slicing
| Parameter | Locations | Current |
|---|---|---|
| `TRAIN_SPLIT_RATIO` | `arena_pipeline.py:90`, `arena23_orchestrator.py:153` | 0.7 (in both; hardcoded) |
| `ALPHA_FORWARD_HORIZON` | `engine/components/alpha_engine.py:637` env + default | 60 bars |
| Data window size `w` | variable per call site | 200_000 bars typical |
| Holdout slice key | `arena23_orchestrator.py:452-457` | `"holdout"` dict key |

### §2.3 Gates
| Parameter | Locations | Current |
|---|---|---|
| `PROMOTE_WILSON_LB` | `config/settings.py` | 0.52 (from earlier notes) |
| `PROMOTE_MIN_TRADES` | `config/settings.py` | 25 |
| A2 `pos_count` threshold | `arena23_orchestrator.py:580-581` | `>= 2` |
| A2 `bt.total_trades` threshold | `arena23_orchestrator.py:517` | `>= 25` |
| A4 acceptance | `arena45_orchestrator.py:283-298` | code-gated |
| Admission validator gate 1 | DB function body | `alpha_hash !~ '^[0-9a-f]{16}$'` |
| Admission validator gate 2 | DB function body | `epoch IS DISTINCT FROM 'B_full_space'` |
| Admission validator gate 3 | DB function body | NaN / Inf / -Inf on arena1_score |
| Soft guidance cap | `arena13_feedback.py` | `MAX_WEIGHT_DELTA_PCT = 50%` |

### §2.4 Workers & scheduling
| Parameter | Locations | Current |
|---|---|---|
| A1 worker count | `zangetsu_ctl.sh start` | 4 (w0-w3) |
| A1 strategy split | `zangetsu_ctl.sh start STRATEGY_ID=j01/j02` | 2 × j01 + 2 × j02 |
| A1 lane | `zangetsu_ctl.sh start A1_LANE` | default |
| `LEASE_MINUTES` | `arena23_orchestrator.py::LEASE_MINUTES` | 15 |
| `lease_minutes` floor | `shared_utils.py:354` | `max(x, 1)` clamp |
| A1 generations | env `ALPHA_N_GEN` | default 20 |
| A1 pop size | env `ALPHA_POP_SIZE` | default 100 |
| A1 top K | env `ALPHA_TOP_K` | default 10 |
| MIN_HOLD / COOLDOWN | env `ALPHA_MIN_HOLD` / `ALPHA_COOLDOWN` | default 60 / 60 |
| MAX_HOLD_BARS | strategy config (j01/j02) | 120 (default after v0.7.2 horizon alignment) |

### §2.5 Cron schedules
| Job | Cadence | Location |
|---|---|---|
| zangetsu_snapshot | `* * * * *` | crontab (not in repo) |
| arena13_feedback | `*/5 * * * *` | crontab |
| watchdog | `*/5 * * * *` | crontab |
| alpha_discovery (**FROZEN**) | `*/30 * * * *` | crontab |
| daily_data_collect | `0 */6` | crontab |
| hourly reports (signal_quality / v10_* / v8_vs_v9) | `30 * * * *`, `15 * * * *`, `45 * * * *`, `0 * * * *` | crontab |
| log cleanup | `0 3 * * 0` | crontab |

**Drift**: cron schedules are operator-owned, not committed to repo. Changing them requires SSH access; history not in git.

### §2.6 External services
| Parameter | Location | Current |
|---|---|---|
| AKASHA_URL | env (Mac agent + miniapp) | `http://100.123.49.102:8769` |
| CLAUDE_INBOX_URL | miniapp env | `http://127.0.0.1:8765` (internal) |
| NEXUS_REDIS_URL | miniapp env | `redis://127.0.0.1:6379` |
| OPS_REDIS_URL | miniapp env | same as NEXUS_REDIS_URL |
| TELEGRAM_BOT_TOKEN | `~/dev/d-mail/.env` (bot) + `calcifer/notifier.py` default + env | various |
| TELEGRAM_CHAT_ID (publishing) | `CLAUDE.md §6` | `-1003601437444` |
| TELEGRAM_THREAD (publishing) | `CLAUDE.md §6` | `362` |
| DMAIL_MINIAPP_URL | launchd plist | `https://alaya.tail2522ad.ts.net/dmail/` |

**Drift**: mixed between env, plist, notifier-py default, CLAUDE.md documentation.

### §2.7 Charter rules + governance
| Rule | Location | Current |
|---|---|---|
| §17 constitution | `~/.claude/CLAUDE.md` | v3.0 |
| Decision rights | not in code | HUMAN discipline |
| Mutation blocklist v2 | `docs/ascension/phase-0/mutation_blocklist.yaml` | Phase 0 v2 |
| Pre-bash hook patterns | `~/.claude/hooks/pre-bash.sh` | v4.1 |
| Pre-done stale-check | `~/.claude/hooks/pre-done-stale-check.sh` | — |
| Auto skill suggest | `~/.claude/hooks/auto-skill-suggest.sh` | — |

### §2.8 Path constants
| Constant | Location | Current |
|---|---|---|
| ZANGETSU_LIVE_PATH | env + miniapp default | `/tmp/zangetsu_live.json` |
| CURRENT_TASK_PATH | env + miniapp default | `/tmp/j13-current-task.md` |
| CURRENT_TASK_MAX_BYTES | miniapp constant | various |
| ISSUES_DIR | miniapp hardcoded | `/home/j13/issues` |
| CALCIFER_BLOCK_FILE | Calcifer daemon + miniapp readers + r2_n4_watchdog | `/tmp/calcifer_deploy_block.json` |
| SHORTCUT_DICT_KEY | miniapp constant | redis key `shorthand:dict:v1` |
| TASK_QUEUE_ZSET | miniapp constant | redis key |

---

## §3 — Duplication clusters

**Cluster A: Thresholds (D-03 drift)** — 9 locations, same semantic, 4 values in active use.

**Cluster B: Path constants** — `/tmp/zangetsu_live.json` referenced in zangetsu_snapshot.sh (writer), miniapp server.py (reader), r2_n4_watchdog.py (reader). 3 locations, 0 registry.

**Cluster C: Telegram config** — `TELEGRAM_BOT_TOKEN` in .env (bot) + hardcoded fallback in notifier.py + env override in launchd plist. 3 sources, 2 different tokens possible.

**Cluster D: Lease TTL** — `LEASE_MINUTES` in arena23_orchestrator.py + `lease_until` computed inline + `reap_expired_leases` default param. 3 places.

**Cluster E: Cron schedules** — `zangetsu_ctl.sh` spawns non-cron workers; `crontab -l` lists 10 entries not in repo. Schedule truth lives only on live crontab.

---

## §4 — Hidden defaults (risk scan)

Parameters with env fallback to a literal, where literal is rarely overridden and rarely discovered:

- `ALPHA_ENTRY_THR` unset → 0.80 (post-R2) — different from what older docs may expect
- `ALPHA_EXIT_THR` unset → 0.50
- `ALPHA_FORWARD_HORIZON` unset → 60
- `ALPHA_N_GEN` unset → 20
- `ALPHA_POP_SIZE` unset → 100
- `ALPHA_TOP_K` unset → 10
- `ALPHA_MIN_HOLD` unset → 60
- `ALPHA_COOLDOWN` unset → 60
- `PSET_MODE` unset → full (not lean)
- `TRAIN_SPLIT_RATIO` unset → (hardcoded 0.7, not actually env)
- `STRATEGY_ID` unset → default j01 (exact behavior depends on code path)
- `A1_WORKER_COUNT` unset → 1
- `ZANGETSU_LIVE_PATH` unset → `/tmp/zangetsu_live.json`
- `CURRENT_TASK_PATH` unset → `/tmp/j13-current-task.md`
- `DMAIL_WARN_TURNS` unset → 80
- `DMAIL_COMPACT_TURNS` unset → 150
- `STRATEGY_ID` unset → (per code path default, usually `j01`) — **silent behavioral branch** (added v2 per Gemini §D.3)
- `A1_LANE` unset → default lane (see zangetsu_ctl.sh start logic) — **silent behavioral branch** (added v2)
- `A1_WORKER_COUNT` unset → 1 (worker scaling)
- `A1_WORKER_ID` unset → 0

**Risk**: an operator running a worker with no env vars gets a fully-functioning but silently-configured process. They wouldn't know what values are in play. **STRATEGY_ID and A1_LANE in particular change which fitness function and which DB lane the worker writes to — silently.**

---

## §5 — Recommended Phase 2 control-plane design deliverables

(These are INPUTS to Phase 2; not actions now.)

1. **Parameter registry** — every parameter gets a single canonical key + type + default + valid range + consumer list.
2. **Ordered resolution** — registry > env > module constant > hardcoded literal (warn on each level down).
3. **Introspection endpoint** — `GET /api/control/params` shows all parameters + current source + lineage.
4. **Change audit** — every parameter change → audit row with actor / before / after / reason.
5. **Cron-in-repo** — crontab committed alongside code, with an install script.

---

## §6 — Confidence

- **VERIFIED**: literal values above were extracted from the repo in Phase 0 survey + repo reads today.
- **PROBABLE**: some parameters may have additional override chains I haven't traced (charter §17 allows project-level CLAUDE.md to extend rules; similar patterns may exist in zangetsu).
- **INCONCLUSIVE**: how many of the "INERT" yaml parameters would be easy to wire vs require deep refactor.
