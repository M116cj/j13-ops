# Zangetsu — Console Capability Spec (Phase 2)

**Program:** Ascension v1 Phase 2
**Date:** 2026-04-23
**Status:** DESIGN.

---

## §1 — Purpose

The "Console" is the human-facing operational surface for Zangetsu. Today that is scattered across `@macmini13bot`, v0.5.5 miniapp, `zangetsu_ctl.sh`, SSH. This spec defines the capabilities the unified console MUST expose on top of the Control Plane.

---

## §2 — Target surfaces (unified)

Three access modes:

1. **Miniapp (Telegram WebApp)** — primary daily operator UI
2. **`@macmini13bot` CLI commands** — quick remote ops (no WebApp needed)
3. **`zctl` terminal client** — direct Alaya access for power users

All three hit the same CP API. No functionality lives outside the API.

---

## §3 — Capability groups

### §3.1 System state (read)
- current operating mode
- deploy block status (Calcifer RED/GREEN)
- per-subsystem rollout tier
- worker health summary (bottoming out in §3.6)
- audit tail (last N)

### §3.2 Parameter inspection (read)
- show parameter
- show parameter history
- show parameter lineage (registry → env → constant → literal)
- diff param against a past timestamp

### §3.3 Parameter mutation (write, gated)
- propose parameter change (creates proposal_id)
- approve proposal (requires role + optional ADR)
- reject proposal
- bulk change via ADR (e.g. Cluster A threshold consolidation)

### §3.4 Mode transitions
- propose mode change (SAFE / SHADOW / CANARY / PRODUCTION / FROZEN)
- approve mode change
- emergency mode toggle (CALCIFER owns emergency; human owns deliberate)

### §3.5 Rollout control
- advance rollout tier for a subsystem
- roll back rollout tier
- view rollout history

### §3.6 Worker control
- list workers (PID / start / role / health)
- kill specific worker (with confirmation)
- restart worker (kicks off §17.6 stale-check)
- scale workers (count / lane / strategy)

### §3.7 Alpha / champion operations
- view fresh stats (ARENA state histogram)
- re-enqueue rejected alphas (owner-fresh; like R2-N3 UPDATE)
- reap stuck leases (with --dry-run)
- inspect specific champion (passport + all metrics + audit)

### §3.8 Data pipeline control
- view last-fetch timestamps
- trigger manual fetch
- view data health + integrity hashes (once D-13 / D-21 addressed)

### §3.9 Deploy + commit integration
- show current git HEAD + Calcifer status correlation
- view last N commits + version bump witness records
- trigger `bin/bump_version.py` (requires GREEN)

### §3.10 Audit + governance
- view audit stream (CP audit + gov audit)
- view block events (Calcifer state history)
- view recent ADRs
- view recent disagreements (Claude / Gemini / Codex log)

### §3.11 Research / discovery (when Phase 4+ lights up)
- view D1 / D2 / D3 / D4 verdicts
- manage shadow D1-D audit runs
- view horizon / pset / target registries
- launch / abort / inspect shadow experiments

### §3.12 Observability
- metric dashboards
- alert inbox
- silence alerts (with reason + TTL)
- reconciler health (each BL-F rule's detection cron state)

---

## §4 — Access model

| Capability group | Read | Write |
|---|---|---|
| §3.1 System state | auth (24h initData) | n/a |
| §3.2 Param inspect | 24h | n/a |
| §3.3 Param mutate | 24h | owner-fresh (1h) + ADR |
| §3.4 Mode | 24h | owner-fresh |
| §3.5 Rollout | 24h | owner-fresh |
| §3.6 Worker ctrl | 24h | owner-fresh |
| §3.7 Alpha ops (read) | 24h | — |
| §3.7 Alpha ops (mutate) | — | owner-fresh + ADR |
| §3.8 Data pipeline ctrl | 24h | owner-fresh |
| §3.9 Deploy/commit | 24h | bin/bump_version.py only |
| §3.10 Audit | 24h | n/a |
| §3.11 Research | 24h | owner-fresh |
| §3.12 Observability | 24h | owner-fresh (silencing) |

---

## §5 — Layout (miniapp)

Re-use v0.5.5 card pattern:
- Sticky header: mode + Calcifer dot + turns % + age
- Cards (tabs): Team / Zangetsu state / J01 / J02 / Issues / Upload / Output / AKASHA / **Control (NEW)** / **Audit (NEW)** / **Research (NEW)**
- Drawer for proposals (gated writes)

---

## §6 — Telegram bot slash-commands (unified via CP)

- `/status` — existing + mode + rollout
- `/cd` — existing; CP logs directory change as audit event
- `/param show <key>`
- `/param propose <key> <value>`
- `/mode <new>` — owner-fresh
- `/reap` — dry-run by default
- `/block` — show Calcifer state
- `/workers` — list
- `/bump` — trigger bump_version.py (only when GREEN)

---

## §7 — Non-goals

- NOT a trading dashboard / PnL tracker (that's L7 output consumer).
- NOT a chat UI for Claude — keep conversational input via @macmini13bot as separate primitive.
- NOT a code editor.
- NOT alert routing configuration UI (Phase 6 addresses).
