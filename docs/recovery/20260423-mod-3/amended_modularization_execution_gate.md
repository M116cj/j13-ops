# Amended Modularization Execution Gate — MOD-3

**Order**: `/home/j13/claude-inbox/0-4` Phase 3 deliverable
**Produced**: 2026-04-23T08:00Z
**Supersedes**: `docs/recovery/20260423-mod-1/modularization_execution_gate.md` (full replacement with MOD-3 amendments)

---

## 1. Amendment summary

| Section | Change | Source finding |
|---|---|---|
| §2 A.1 | Requires "9 mandatory module contracts ACCEPTED" (was 7) | R2-F1 + R2-F3 |
| §2 A.2 | Unchanged (still 7-day; though R1a-F3 MEDIUM flagged for consideration) | R1a-F3 tracked |
| §2 A.3 | Unchanged (recovery-path freeze) | — |
| §3 B.1 | Contract validation uses 15-field template (was 14) | R1b-F1 |
| §3 B.1 | Responsibilities 1:1 to test fixtures required | R1b-F3 |
| §3 B.2 | Rollback rehearsal MUST record empirical p95 | R1a-F4 |
| §3 B.3 | Unchanged | — |
| **§5 Gate-B enforcement** | **Path-based (un-omittable) replaces label-based** | **R1a-F1 CRITICAL** |
| §5 | Server-side GitHub Actions workflow is authoritative; local hook non-authoritative | R1a-F2 HIGH |
| §6 Override | Require GPG-signed commit for `gate-override` ADRs | R1a-F5 MEDIUM |
| §7 | Updated current status (post-MOD-3) | — |

## 2. Purpose (unchanged)

MOD-1 delivered architectural documents. MOD-3 amended them. Neither authorizes:
- writing new code
- migrating existing code into a module
- spinning up a control-plane service
- replacing any current worker

This gate defines the three pre-conditions (A/B/C) before migration implementation may proceed.

## 3. Gate-A — Before MOD-1 → Phase 7 transition (AMENDED)

All three MUST be satisfied concurrently.

### A.1 — Amended MOD-1 corpus ACCEPTED by Gemini round-3

| Deliverable | Acceptance state target |
|---|---|
| `intended_architecture.md` | Gemini round-3 ACCEPT |
| `actual_architecture.md` | Gemini round-3 ACCEPT |
| `architecture_drift_map.md` | Gemini round-3 ACCEPT (incl. D-24 RESOLVED + D-26 RESOLVED + D-27/D-28/D-29 RESOLVED) |
| `amended_module_boundary_map.md` (MOD-3) | Gemini round-3 ACCEPT, 9 mandatory modules confirmed |
| `amended_modular_target_architecture.md` (MOD-3 delta) | Gemini round-3 ACCEPT |
| `amended_control_plane_blueprint.md` (MOD-3 delta) | Gemini round-3 ACCEPT |
| `amended_module_contract_template.md` (MOD-3) | Gemini round-3 ACCEPT, Field 15 mandatory |
| `amended_modularization_execution_gate.md` (this file) | Gemini round-3 ACCEPT |
| `module_registry_spec.md` | Gemini round-2 ACCEPT already held; no MOD-3 change |

A.1 transitions to CLEARED when Gemini round-3 returns ACCEPT (no mandatory amendments remaining) for the full amended corpus.

### A.2 — 7-day quiescence (unchanged)

Start: 2026-04-23T00:35:57Z (arena freeze)
Earliest clear: 2026-04-30T00:35:57Z

Loophole note (R1a-F3 MEDIUM tracked, NOT applied this round): current spec is "no `feat(zangetsu/vN)` commits". If tightened to "no non-documentation commits", the MOD-2 `ae738e37 fix(zangetsu/calcifer): …` commit would reset the clock. We DO NOT apply that tightening in MOD-3 to avoid resetting quiescence. Flagged for MOD-4+ consideration.

### A.3 — Recovery-path scope freeze (unchanged)

R2 hotfix bd91face unchanged; no additional Track-R patches; arena frozen; Calcifer RED preserved.

## 4. Gate-B — Before module migration touches `main` (AMENDED)

### B.1 — Module has complete contract registered (AMENDED)

- YAML contract at `zangetsu/module_contracts/<module_id>.yaml` passes `amended_module_contract_template.md §4` 15-field acceptance checklist
- **Responsibilities MUST map 1:1 to test_boundary golden fixtures** (R1b-F3)
- Module entry INSERTED into `control_plane.modules` via CI/CD sync workflow
- Module has passed Gemini adversarial
- ADR `docs/decisions/YYYYMMDD-module-<id>.md` committed with Gemini verdict recorded

### B.2 — Shadow + CANARY rehearsal (AMENDED)

- SHADOW tier ≥ 72h
- CANARY tier ≥ 72h at ≤ 10% scope
- No FAILURE_* metric exceeded alert threshold in either window
- **Rollback rehearsal actually executed, empirical p95 recorded in `rollback_surface.rollback_rehearsal_p95` field** (R1a-F4)

### B.3 — Rollback + forward-compat contract signed (unchanged)

## 5. Gate-B enforcement — AMENDED (path-based)

### 5.1 Gate-A enforcement (amended)

- Local: `~/.claude/hooks/pre-phase-7-gate.sh` (convenience; non-authoritative)
- **Server-side (authoritative)**: GitHub Actions workflow `.github/workflows/phase-7-gate.yml` on PR + push touching `zangetsu/src/**` or `zangetsu/module_contracts/**`

Local hook bypass via `--no-verify` has NO effect on server-side.

### 5.2 Gate-B enforcement (AMENDED — path-based)

- **Server-side authoritative**: GitHub Actions workflow `.github/workflows/module-migration-gate.yml`
- **Triggers** (any PR matching these paths — un-bypassable via label omission):
  - `zangetsu/src/modules/**`
  - `zangetsu/src/l[0-9]*/**`
  - `zangetsu/module_contracts/*.yaml`
  - `zangetsu/module_contracts/*.yml`
- Full spec in `github_actions_gate_b_enforcement_spec.md`
- Label `module-migration/<module_id>` remains but is ADDITIVE (documentation-only, NOT a trigger)

### 5.3 Gate-C enforcement (unchanged)

- Location: `control_plane.cp_api` API-level check before accepting scatter-site removal PRs
- Triggers on PRs removing files listed in `scattered_config_map.md` canonical paths

### 5.4 Branch protection (NEW in MOD-3)

`gh api repos/M116cj/j13-ops/branches/main/protection -X PUT \`
-  `-F required_status_checks[strict]=true \`
- `-F required_status_checks[contexts][]="Module Migration Gate (Gate-B) / gate_b_summary" \`
- `-F enforce_admins=true \` (j13 uses explicit override ADR, not admin-bypass)
- `-F required_linear_history=true \`
- `-F required_signatures=true`

This is applied when Phase 7 nears, not in MOD-3.

## 6. Override procedure (AMENDED — GPG signing required)

Only j13 can override a gate, via written ADR `docs/decisions/YYYYMMDD-gate-override.md`:

- **Commit containing the ADR MUST be GPG-signed** (R1a-F5)
- GitHub branch protection `required_signatures=true` (§5.4) verifies signature
- Signer key must match j13's public key pinned in `~/.claude/trust/j13.asc` (Phase 7 creates this pin file)
- ADR content: which gate (A/B/C) + sub-condition / why override / compensating safeguards / expiry (max 7 days) / retro commitment

Agent-originated ADRs cannot satisfy this requirement — agents do not hold j13's private key.

## 7. Current status (2026-04-23 MOD-3 completion time)

| Condition | State |
|---|---|
| A.1 | PARTIALLY CLEARED — awaits Gemini round-3 on amended corpus |
| A.2 | IN PROGRESS — earliest clear 2026-04-30T00:35:57Z |
| A.3 | CLEARED (R2 holding, no Track-R patches, arena frozen) |

## 8. Stop conditions (unchanged)

If any of the following happens during any phase, HALT + escalate to j13:
- mutation of production without ADR
- threshold change without ADR + Gemini
- arena service restart without validation plan §3 protocol
- mixing with Track 3 discovery
- mixing with broad recovery patching
- black-box control surface proposal
- module migration PR without rollback boundary
- console ownership proposed without state + config contracts

## 9. Relationship to Constitution §17

Unchanged from MOD-1. §17.2 witness + §17.3 Calcifer RED + §17.4 auto-regression + §17.5 bot-only-bump + §17.6 stale-check + §17.7 decision-record CI all remain binding.

## 10. Label per 0-4 rule 10

- §3 A.1 amended list: **VERIFIED** (1:1 with MOD-3 deliverables)
- §4 B.1/B.2 amendments: **VERIFIED** (maps to contract template + rollback changes)
- §5 Gate-B path-based: **VERIFIED** (spec matches `github_actions_gate_b_enforcement_spec.md`)
- §6 GPG override: **PROBABLE** (requires Phase 7 trust infra)
- §7 current status: **VERIFIED** (live observation)
