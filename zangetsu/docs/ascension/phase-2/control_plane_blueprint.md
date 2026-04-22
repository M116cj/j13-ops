# Zangetsu — Control Plane Blueprint (Phase 2, D-01 BLOCKER primary deliverable)

**Program:** Ascension v1 Phase 2
**Date:** 2026-04-23
**Author:** Claude Lead
**Priority:** BLOCKER — D-01 of `architecture_drift_map.md` requires a Control Plane before any migration proceeds.
**Status:** DESIGN (planning-only). Implementation is Phase 7.
**Zero-intrusion:** pure documentation.

---

## §1 — Purpose

Zangetsu today has no central governance surface for its 13 config storage classes, 30 uncontrolled IO paths, 48 mutation surfaces, and 20 drift entries. The Control Plane (L1 in the intended layered architecture) is the **single authoritative boundary** through which every parameter, mode, schedule, kill switch, rollout state, and operator-command flows.

This blueprint specifies **what the Control Plane must be**, not **how to implement it**. Implementation is staged in Phase 7.

---

## §2 — Hard requirements (non-negotiable)

1. **Single source of truth** for every runtime parameter. If a parameter is read in production code, its canonical location is the Control Plane parameter registry.
2. **Ordered resolution**: registry > env > module constant > hardcoded literal. Each level-down emits a warning.
3. **All writes go through a gate**. Distributed lock + decision-rights matrix enforced at write time.
4. **Every write is audited**. Actor + before + after + reason + timestamp + source.
5. **Read surface is introspectable**. `GET /api/control/params` returns all parameters, current value, source, lineage. Available to operator + miniapp + agents.
6. **Cron schedules are versioned**. `crontab` content is in-repo; install script applies + diffs.
7. **Deploy block integration**. Calcifer RED is the primary kill switch; CP consults block before any mutation.
8. **Decision-rights matrix embedded**. Which roles can change which parameter classes; violations blocked at write time.
9. **Fail-closed**. If the CP is unreachable, all writes are refused; reads serve last-known values from a local cache.
10. **Integrity attestation**. CP state + param registry have SHA manifests; out-of-band edits detected.

---

## §3 — Shape (architectural style)

### §3.1 Deployment model
- Single process, co-located with an existing trusted host (Alaya).
- No distributed DB for CP state — uses Postgres (already authoritative for Zangetsu DB) + Redis (already present) in a specific schema.
- Exposed via:
  - HTTP API on an internal port (e.g. `:8773` behind Caddy internal-only)
  - CLI client `zctl` (new, replaces scattered ctl scripts)
  - gRPC / event stream for worker subscribers (Phase 7 option)

### §3.2 Layer coupling
- CP reads from and writes to Postgres using a dedicated schema `control_plane.*` (no collision with existing zangetsu schema).
- CP notifies subscribers via `pg_notify` or Redis pub/sub (reuse what's already live).
- CP itself is observed by L8 (metrics + audit pipeline).

### §3.3 Compatibility with existing surfaces
- `zangetsu_ctl.sh` behavior preserved as shim → calls CP under the hood.
- `@macmini13bot` slash-commands become CP API calls.
- v0.5.5 miniapp endpoints re-routed through CP for mutation ops; reads can bypass CP for now.

---

## §4 — Functional scope (what CP governs)

Per Ascension spec §5 and `scattered_config_map.md` §5, CP governs:

### §4.1 System controls
- engine mode (safe / shadow / canary / production)
- worker counts per strategy (A1_WORKERS, A1_LANE, A1_WORKER_COUNT)
- resource budgets (CPU quota, RAM, IO weight per worker — new per Gemini §D.1)
- concurrency scaling (max total workers)
- schedules (cron entries — versioned)
- kill switches (per-subsystem shutdown)
- rollout states (per-feature tier: off / shadow / canary / full)

### §4.2 Search controls
- mutation rate, search depth, exploration/exploitation
- factor pools, pset selection (full / lean / custom)
- horizon sweep (D1 target)
- regime partitioning
- promotion policy, tournament policy

### §4.3 Validation controls
- replay windows, OOS policies (TRAIN_SPLIT_RATIO)
- gate thresholds (the 6-distinct-active-value cluster collapsed into ONE registry)
- cost models per tier
- deployment conditions (PROMOTE_WILSON_LB, PROMOTE_MIN_TRADES)
- validation versions (v0.7.1 / v0.7.2.3 etc.)
- shadow policies

### §4.4 Input controls
- data sources (Binance endpoints, symbol universe)
- time windows, feature families
- blacklists, whitelists
- routing policies (family_tag → pset / cost model)

### §4.5 Output controls
- output schemas
- ranking tables
- champion reports
- evidence bundles
- dashboard feeds, alert routing
- export targets

---

## §5 — Decision-rights matrix (who can change what)

Per Ascension spec §12 + `production_safety_contract.md`:

| Parameter class | j13 direct | Claude Lead (autonomous) | Gemini | Codex | Calcifer | Human-via-miniapp |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| System mode (safe/prod/shadow) | YES | PROPOSE | CHALLENGE | n/a | n/a | YES (owner-fresh) |
| Worker counts | YES | YES (within bounds) | CHALLENGE | n/a | n/a | YES (owner-fresh) |
| Kill switches | YES | YES (for own scope) | CHALLENGE | n/a | EMERGENCY | YES (owner-fresh) |
| Search params (mutation, pset, horizon) | YES | YES (with ADR) | CHALLENGE | n/a | n/a | YES (with ADR) |
| Gate thresholds | YES | PROPOSE (requires ADR + before/after) | CHALLENGE | n/a | n/a | NO direct (require ADR path) |
| Cost models | YES | NO (market truth) | CHALLENGE | n/a | n/a | NO |
| Data sources | YES | PROPOSE | CHALLENGE | n/a | n/a | YES (read-only changes) |
| Output routing | YES | YES (within contract) | CHALLENGE | n/a | n/a | YES |
| Deploy block state | CALCIFER-OWNED | n/a | n/a | n/a | YES | `/unblock` command only |
| Cron schedule | YES | PROPOSE | CHALLENGE | n/a | n/a | NO |
| Validation version bumps (feat/vN) | BUMP-SCRIPT | n/a | WITNESS (§17.2) | n/a | BLOCK (RED) | NO |

"PROPOSE" = agent generates a plan + ADR; human or higher authority approves.
"CHALLENGE" = Gemini has veto before apply.
"WITNESS" = independent agent signs AKASHA record.
"EMERGENCY" = Calcifer can toggle on block conditions without human.

---

## §6 — State model

### §6.1 Operating modes (global)
- `SAFE` — everything read-only; no writes allowed; used during incident investigation
- `SHADOW` — writes go to shadow tables only; canary consumers read shadow
- `CANARY` — limited production writes (e.g. single symbol, or 10% sample); observed for N hours
- `PRODUCTION` — normal full operation
- `FROZEN` — production reads continue; writes blocked pending ADR

### §6.2 Per-subsystem rollout tier
- `OFF` — subsystem disabled
- `SHADOW_ONLY` — running but not writing live
- `CANARY_X%` — partial live (explicit scope)
- `FULL` — full live

### §6.3 Parameter lifecycle
- `PROPOSED` — written in registry but not yet committed
- `ACTIVE` — currently in effect
- `DEPRECATED` — still readable but emits warnings; consumers warned
- `REMOVED` — error on read

---

## §7 — Schemas (shape only; concrete YAML in Phase 7)

### §7.1 Parameter entry
```
parameter:
  id: <canonical_key>
  type: {int, float, str, bool, enum, list, map}
  default: <value>
  valid_range: <spec>
  consumers: [<service names>]
  owners: [<roles>]
  rollout_tier: OFF|SHADOW|CANARY_X|FULL
  version: <semver or migration-id>
  change_history: [<audit rows>]
  last_changed_by: <actor>
  last_changed_at: <ts>
  lineage: [<trace-from canonical → env → constant → literal>]
```

### §7.2 Audit row
```
audit:
  id: <uuid>
  ts: <iso>
  actor: <user_id or agent_name>
  action: {read, write, propose, approve, reject, emergency}
  target: parameter | mode | schedule | rollout | kill_switch
  key: <canonical_key or id>
  before: <value>
  after: <value>
  reason: <text>
  adr_link: <path or url>
```

### §7.3 Rollout state
```
rollout:
  subsystem: <name>
  tier: OFF|SHADOW|CANARY_X|FULL
  scope: <symbols/workers/lanes>
  entered_at: <ts>
  entered_by: <actor>
  condition: <auto-promotion criteria or "manual">
```

---

## §8 — API sketch

Read:
- `GET /api/control/params` → full registry
- `GET /api/control/params/{key}` → single param + lineage + history
- `GET /api/control/mode` → current operating mode
- `GET /api/control/rollout/{subsystem}` → rollout state
- `GET /api/control/audit?since=<ts>` → audit stream

Write (all gated):
- `POST /api/control/params/{key}/propose` — proposes a change; returns proposal_id
- `POST /api/control/params/{key}/approve/{proposal_id}` — approves (requires role)
- `POST /api/control/mode` — change operating mode
- `POST /api/control/kill/{subsystem}` — emergency kill switch
- `POST /api/control/rollout/{subsystem}/advance` — rollout tier promotion

All writes:
- Require initData-equivalent auth or service-token
- Produce audit row before state change
- Propagate via pg_notify or Redis stream to subscribers

---

## §9 — Integration with existing governance

- **Charter §17 rules** remain binding; CP enforces what's now HUMAN discipline:
  - §17.3 Calcifer RED: CP reads block file; refuses `feat(/vN)` proposals (BL-F-005).
  - §17.5 Version bumps: CP only accepts bump proposals signed by `bin/bump_version.py` (BL-F-006).
  - §17.6 Stale-service: CP runs pre-done-stale-check on every subsystem restart.
  - §17.7 Decision record CI: CP write operations require `adr_link`.
- **Mutation blocklist v2**: every BL-F-### rule is codified as a CP pre-write check.
- **Detection cron suite** (Phase 6): reconcilers consult CP audit stream + state registry.

---

## §10 — Relationship to BLOCKER CS-05 (docker exec)

The docker-exec surface bypasses all code-level gates. CP alone cannot solve this — BUT CP raises the cost of bypass by:
- Publishing an expected DB-schema hash
- Running a reconciler cron that compares live DB hash vs expected + flags divergence
- Emitting an alert when any out-of-band DDL/DML is detected (pg_stat_statements audit)

Hard solution for CS-05 is operational (restrict docker group membership + require MFA for `docker exec`), out of Phase 2 scope. Phase 2 delivers detection; Phase 7 / ops-hardening delivers prevention.

---

## §11 — Migration staging (preview; full plan in `migration_plan_to_modular_engine.md`)

Suggested sequence:
1. **CP skeleton**: Postgres schema + API service with read-only endpoints; seed from current registry.
2. **Parameter migration**: convert scattered thresholds (Cluster A) to CP registry with shim-fallback for consumers.
3. **Write gates**: enable propose/approve flow for one parameter class (thresholds) first.
4. **Worker subscription**: workers refresh param from CP on every N minutes.
5. **Cron in-repo**: commit cron content + install script.
6. **Decision rights enforced**: bot + miniapp + agents pushed through CP write path.
7. **Rollout tier**: enable `FULL` only after N days of `SHADOW` + `CANARY`.

---

## §12 — Non-goals

- NOT solving CS-05 blocker outright (ops-hardening scope).
- NOT implementing the CP here — Phase 7.
- NOT specifying concrete Postgres schema / API framework choice — that's Phase 7 implementation.
- NOT a dashboard — dashboards are L7 consumers of CP reads.
- NOT a secrets manager — secrets stay in .env / vault; CP only references names.

---

## §13 — Confidence

- **VERIFIED**: requirements 1-10 are derived from Phase 1 drift evidence; each hard requirement maps to a specific drift entry.
- **PROBABLE**: decision-rights matrix rows (may shift after Phase 2 team-process review).
- **INCONCLUSIVE**: whether Postgres + Redis suffice vs dedicated state store (Phase 7 decides).

---

## §14 — Ascension §6 layer compliance

Per Ascension spec §6 "For each layer, define purpose / responsibilities / inputs / outputs / configs / states / metrics / failure modes / test boundaries / replacement boundaries":

- purpose: §1
- responsibilities: §4 (five control classes) + §5 (decision rights)
- inputs: §8 write API + param proposals from agents
- outputs: §8 read API + pg_notify stream + audit log
- configs: §7.1 parameter-entry schema (CP is self-bootstrapping)
- states: §6 operating modes + rollout tiers + parameter lifecycle
- metrics: command latency, conflict rate, approval queue depth, audit coverage
- failure modes: §2 hard-requirement 9 (fail-closed)
- test boundary: mocked subsystems; verify correct dispatch + ordering + auditing
- replacement boundary: pluggable auth, pluggable storage (Postgres + Redis initial; move to dedicated if scale)
