# Modularization Execution Gate — Zangetsu MOD-1

**Order**: `/home/j13/claude-inbox/0-2` Phase 6 deliverable (second output)
**Produced**: 2026-04-23T02:50Z
**Author**: Claude (Lead)
**Status**: **HARD GATE** — modularization implementation is BLOCKED until the conditions below hold. This gate is referenced by `control_plane_blueprint.md §11` migration staging and `r2_patch_validation_plan.md §2` restart triggers.

---

## §1 — Purpose

MOD-1 delivers eight architectural documents. It does NOT authorize:
- writing any new code
- migrating any existing code into a module
- spinning up a control-plane service
- replacing any current worker with a module-style implementation
- modifying production DB schemas for CP storage

This gate defines the exact **three pre-conditions** that must be satisfied before Phase 7 (implementation) starts, and the exact **three further pre-conditions** before any module migration touches `main`, and the exact **three further pre-conditions** before any runtime control-plane takeover is allowed.

If a team member proposes starting Phase 7 without these conditions, the gate REJECTS and the proposal returns to MOD-1 rework.

---

## §2 — Gate-A — Before MOD-1 → Phase 7 transition

**All three MUST be satisfied concurrently.**

### A.1 — MOD-1 deliverables ACCEPTED by Gemini round-2

| Deliverable | Status at gate check | Accept criterion |
|---|---|---|
| `intended_architecture.md` | must be present + ACCEPTED | Gemini signs off the 10-layer target (or documents deviation rationale) |
| `actual_architecture.md` | must be present + VERIFIED | live-query evidence cited for every claim of "currently exists" |
| `architecture_drift_map.md` | must be present + ACCEPTED | every drift has severity + root cause + remediation phase |
| `module_boundary_map.md` | must be present + ACCEPTED | 7 mandatory modules each have full 14-field contract |
| `modular_target_architecture.md` | must be present + ACCEPTED | module topology is coherent single design, not a list of ideas |
| `control_plane_blueprint.md` | must be present + ACCEPTED | governs all 5 surface classes (System/Search/Validation/Input/Output) |
| `module_contract_template.md` | must be present | 14-field template locked |
| `modularization_execution_gate.md` (this file) | must be present | gate conditions locked |

Acceptance = Gemini adversarial review written + all CRITICAL findings resolved + sign-off recorded in ADR.

### A.2 — Recovery baseline survives 7-day quiescence

No `feat(zangetsu/vN)` commits for ≥7 consecutive days.
No Calcifer RED transitions.
No `champion_pipeline_*` row-count mutations outside gov-approved cron.
No arena restart events.

Rationale: if the frozen system can't even stay stable for a week, the modularization project is premature.

### A.3 — Scope freeze on recovery-path

The R2 hotfix (bd91face) remains authoritative recovery.
No additional Track-R patches proposed or merged.
`r2_recovery_review §8` gaps remain OPEN, tracked in drift map, but not scheduled for pre-Phase-7 fix.

Rationale: Phase 7 will naturally address those gaps via module migration; addressing them ad-hoc before Phase 7 adds drift and contaminates modularization.

---

## §3 — Gate-B — Before any module migration touches `main`

**All three MUST be satisfied for EACH module migration PR.**

### B.1 — Module has complete contract registered

- YAML contract at `zangetsu/module_contracts/<module_id>.yaml` ACCEPTED per §module_contract_template §4 checklist
- Module entry INSERTED into `control_plane.modules` via CI/CD sync workflow (not ad-hoc)
- Module has passed Gemini adversarial on contract terms
- ADR `docs/decisions/YYYYMMDD-module-<id>.md` committed

### B.2 — Shadow + CANARY rehearsal completed

- Module deployed in SHADOW tier (writes to shadow tables, reads ignored by production consumers)
- SHADOW observation window ≥72 hours
- CANARY tier exercised with ≤10% scope (e.g. single symbol / single lane)
- CANARY observation window ≥72 hours
- No FAILURE_* metric exceeded alert threshold during either window
- Rollback path rehearsed successfully (actual `rollback_surface.rollback_path` invoked in test)

### B.3 — Rollback + forward-compat contract signed

- Rollback runbook in `docs/rollback/<module_id>.md` with exact commands + expected log lines
- Forward-compat: new module can coexist with predecessor for ≥1 release cycle (no hard cutover)
- Consumer modules have been notified via CP registry bump + have `contract_version_max` honoring new version
- Rollback time estimate (p95) ≤ 10 minutes

---

## §4 — Gate-C — Before any runtime control-plane takeover is allowed

**All three MUST be satisfied before removing legacy config/scatter sites.**

### C.1 — CP API + storage is FULL rollout for `≥30 days`

`cp_api`, `cp_storage`, `cp_audit` modules in `FULL` rollout tier.
30 consecutive days with:
- ≥99.9% read-API availability
- Zero audit-log gaps (no write unaudited)
- All parameter-class writes have gone through CP (verified by reconciler)

### C.2 — Decision-rights matrix enforced END-TO-END

Every parameter-class write path (§5 of `control_plane_blueprint.md`) has been tested:
- j13 direct writes: pass
- Claude Lead autonomous writes: pass with ADR requirement honored
- Gemini CHALLENGE: enforceable pre-commit hook verified
- Calcifer emergency kill switches: tested by triggering artificial RED
- `@macmini13bot` owner-fresh writes: tested via miniapp

No parameter is writable outside CP. Any bypass attempt triggers reconciler alert.

### C.3 — Scatter-site removal plan executed to ≤20% residual

Of the 13 config storage classes listed in `scattered_config_map.md`, at least 80% have been:
- migrated to `cp_storage` as canonical source
- removed from predecessor location (not just shimmed — actually deleted from file)
- consumers refactored to read via CP

Remaining ≤20% must have explicit "legacy-forever" ADR documenting why not migrable (e.g. OS-level env for secrets).

---

## §5 — Gate enforcement

Each gate is a **code-enforced pre-commit / pre-merge hook**:

### §5.1 Gate-A enforcement
- Location: `~/.claude/hooks/pre-phase-7-gate.sh` (new, written in Phase 7-kickoff commit)
- Trigger: any PR labeled `phase-7-start` or commit touching `zangetsu/src/<new modular paths>`
- Action: verify the 8 MOD-1 deliverables exist + ACCEPTED tag in their ADRs; verify §A.2 quiescence SQL query; verify §A.3 absence of Track-R patches

### §5.2 Gate-B enforcement
- Location: GitHub Actions workflow `module-migration-gate.yml`
- Trigger: any PR with label `module-migration/<module_id>`
- Action: verify §B.1 CP registry entry exists; verify §B.2 rollout tier logs in `control_plane.rollout_audit`; verify §B.3 rollback doc exists

### §5.3 Gate-C enforcement
- Location: `control_plane.cp_api` API-level check before accepting scatter-site removal PRs
- Trigger: any PR removing files listed in `scattered_config_map.md` canonical paths
- Action: verify §C.1 uptime metrics; verify §C.2 recent audit entries from each role; verify §C.3 % metric

If a gate check cannot run (e.g. CP not yet live), the check is treated as FAIL until the infrastructure supporting the check exists.

---

## §6 — Override procedure

Only j13 can override a gate, via written override in `docs/decisions/YYYYMMDD-gate-override.md` that includes:

1. Which gate (A / B / C) and which sub-condition is being overridden
2. Why override is necessary (concrete incident or deadline)
3. Compensating safeguards during the override window
4. Expiry of the override (max 7 days, then auto-reinstates)
5. Retro commitment post-override

No agent (Claude / Gemini / Codex / Markl / Calcifer) can override. Claude may PROPOSE override, j13 decides.

---

## §7 — Current status at MOD-1 completion (2026-04-23)

| Condition | Status |
|---|---|
| A.1 MOD-1 deliverables ACCEPTED | PENDING (awaiting Gemini round-2 on MOD-1 outputs) |
| A.2 7-day quiescence | COUNTDOWN in progress (starts at freeze 2026-04-23T00:35Z → minimum earliest Phase-7 start: 2026-04-30T00:35Z) |
| A.3 Recovery-path scope freeze | HOLDING (R2 frozen, no new Track-R patches since 0-1 executed) |
| B.1-B.3 | N/A (no module migration attempted yet) |
| C.1-C.3 | N/A (CP not yet implemented) |

**Conclusion**: Gate-A earliest viable clearing date = **2026-04-30** (A.2 min) + contingent on A.1 Gemini re-review.

No Phase 7 code commits may land in `main` before that date.

---

## §8 — Stop conditions (mirror `0-2 §STOP CONDITIONS`)

If any of the following happens during modularization:
- mutation of production without ADR
- threshold change without ADR + Gemini
- arena services restart without validation plan §3 protocol
- attempted mixing with Track 3 discovery
- attempted mixing with broad recovery patching
- proposal of a black-box control surface (violates rule 8)
- module migration PR without rollback boundary (violates B.3)
- console ownership proposed without state + config contracts (violates B.1)

→ immediately HALT Phase 7; escalate to j13 via Telegram; require retro + gate-reinstatement ADR before resume.

---

## §9 — Relationship to Constitution §17

This gate implements §17.7 (Decision record CI gate) for modularization specifically. Additional §17 ties:
- §17.2 (witness): Phase 7 module migrations require AKASHA witness per §17.2 — independent service confirms `deployable_count` did not regress.
- §17.3 (Calcifer outcome watch): migrations MUST NOT proceed while Calcifer RED unless explicit override.
- §17.4 (auto-regression): a migration PR that causes `deployable_count` to drop for >12h is auto-reverted (same mechanism as feature bumps).
- §17.5 (bot-only version bump): migrations that ship code increment version per `bin/bump_version.py`, not manual `feat()` commits.
- §17.6 (stale-service): any service restart during migration hits pre-done-stale-check hook.

---

## §10 — Q1 adversarial

| Dim | Assertion | Verdict |
|---|---|---|
| Input boundary | 3 gates × 3 conditions = 9 conditions total, each with concrete check; covers MOD-1 Phase 6 execution gate requirements (a/b/c from spec) | PASS |
| Silent failure | §5 enforcement specifies WHERE the check runs; no gate is "honor system" | PASS |
| External dep | Gates depend on CP/GitHub Actions/reconciler being present; §5 treats absence as FAIL | PASS |
| Concurrency | Gate-B applies PER module migration (parallel modules allowed); Gate-C applies globally (serializes the CP takeover) | PASS |
| Scope creep | Gate does not prescribe implementation details; only conditions | PASS |
