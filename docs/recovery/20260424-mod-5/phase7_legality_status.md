# Phase 7 Legality Status

**Order**: `/home/j13/claude-inbox/0-7` Phase 5 deliverable
**Produced**: 2026-04-24T01:10Z
**Purpose**: Single authoritative document answering "Is Phase 7 migration legal to start now?"

---

## 1. Bottom-line answer

**NO. Phase 7 migration is NOT legal to start.**

Gate-A is CLEARED (Gate-A clearance is prerequisite 1.1 of 8), but prerequisites 1.4, 1.5, 1.6, 1.8 remain NOT MET.

## 2. Phase 7 entry requirements (per `phase7_entry_pack.md §1`)

| § | Requirement | Status | Evidence / gap |
|---|---|---|---|
| 1.1 | Gate-A CLEARED (all 6 CQG conditions VERIFIED) | ✅ **MET** | `gate_a_post_mod5_memo.md §2` — all 6 VERIFIED |
| 1.2 | MOD-5 queue closed | ✅ **MET** | `remaining_findings_resolution_table.md §3` zero ambiguous |
| 1.3 | Latest Gemini round clean ACCEPT | ✅ **MET** | `mod5_adversarial_verdict.md §1` round-5 ACCEPT, zero amendments |
| 1.4 | `enforce_admins=true` active | ❌ **NOT MET** | Currently `enforce_admins=false` under Path B compensation (MOD-5 Phase 1); Phase 7 entry transition requires activation |
| 1.5 | Server-side Gate-A + Gate-B workflows committed | ❌ **NOT MET** | `.github/workflows/phase-7-gate.yml` + `module-migration-gate.yml` spec'd in MOD-3 + MOD-4 but not yet committed as actual workflow YAML files |
| 1.6 | cp_api skeleton operational | ❌ **NOT MET** | CP service not implemented; `control_plane.*` Postgres schema not created |
| 1.7 | Controlled-diff framework operational | ⚠️ **PARTIAL MET** | Framework defined + manual protocol (`controlled_diff_framework.md`); snapshot cron Phase 7 dependency |
| 1.8 | ≥1 rollback rehearsal recorded | ❌ **NOT MET** | No module shadow-rehearsed yet |

**Total: 3/8 fully MET + 1/8 partially MET + 4/8 NOT MET.**

## 3. What Phase 7 migration would look like (for context)

Phase 7 is the implementation of the 9 mandatory modules into the modular target architecture:
- Commits create `zangetsu/src/modules/<module_id>/` directories
- Each module ships with complete 15-field contract YAML at `zangetsu/module_contracts/`
- Gate-B server-side workflow validates per-module on merge
- Modules migrate live-runtime consumption of cp_worker_bridge
- R2 hotfix preserved; Calcifer RED preserved; arena remains frozen initially

## 4. What remains between now and legal Phase 7 start

Per `gate_a_post_mod5_blocker_matrix.md §6` dependency ordering:

### 4.1 Condition 1.4 — activate enforce_admins=true
Prerequisite: j13 GPG key registered + verified on GitHub (user action).
Then: `gh api -X PUT /repos/M116cj/j13-ops/branches/main/protection --field enforce_admins=true`.

### 4.2 Condition 1.5 — commit Gate-A + Gate-B workflow YAMLs
Files already specified:
- `.github/workflows/phase-7-gate.yml` per `amended_modularization_execution_gate_v3.md §5.1`
- `.github/workflows/module-migration-gate.yml` per `github_actions_gate_b_enforcement_spec.md §2`
Plus helper scripts (`validate_module_contract.py`, `verify_rollout_sla.py`, etc.) per Phase 7 implementation scope.

### 4.3 Condition 1.6 — cp_api skeleton
Minimal cp_api service:
- FastAPI at localhost:8773
- `control_plane.parameters` schema + seed from current settings.py
- `control_plane.modules` registry (empty initially)
- cp_audit append-only log table
- Workers consume via cp_worker_bridge library

### 4.4 Condition 1.8 — rollback rehearsal
First rehearsal candidate: cp_worker_bridge (M9) — smallest dependency footprint.
- Author M9 implementation + contract YAML
- Deploy in SHADOW tier via CP rollout
- Execute rollback via `rollback_surface.rollback_path`
- Record empirical p95 in `rollback_surface.rollback_rehearsal_p95`
- Commit rehearsal log in `docs/rehearsal/cp_worker_bridge_rollback_<date>.md`

## 5. Permissible operations during MOD-5 → Phase-7-entry window

Per all prior orders:

| Action | Permitted? |
|---|---|
| MOD-6+ Team Orders from j13 | YES (if issued) |
| Authoring module contract YAMLs (non-commit) | YES (spec work) |
| Authoring workflow YAML (non-commit) | YES |
| Authoring cp_api skeleton code (non-commit) | YES |
| Commit to `main` for spec / doc work | YES (under admin-bypass compensation G21/G22) |
| Commit `phase-7-gate.yml` workflow file | YES |
| Activate `enforce_admins=true` | YES (when j13 ready) |
| Any actual module migration into `zangetsu/src/modules/` | **NO** — waits for all 8 prerequisites |
| Cp_api service start | NO (waits for workflow + admin enforcement) |
| Arena restart | NO |
| Track 3 discovery restart | NO |
| Threshold or gate change in live production | NO |

## 6. Condition 5 continuous enforcement

Even though Gate-A is CLEARED, Condition 5 Controlled-Diff continues to apply. During MOD-5 → Phase-7-entry window:
- Every commit to main requires controlled-diff doc (pre + post snapshot + explained-diff classification)
- Any unexplained runtime/config drift → Condition 5 DISPROVEN → Gate-A regresses to BLOCKED

This is the tripwire keeping the system stable while Phase 7 prep progresses.

## 7. How Phase 7 becomes legal

Exact transition (deterministic, condition-based):

```
current state: 3/8 fully MET + 1/8 partial

At some point j13 issues MOD-6 Team Order OR continues directly.

As each remaining prerequisite is MET:
  §1.4 activate enforce_admins=true → 4/8 MET
  §1.5 commit workflow YAMLs     → 5/8 MET
  §1.6 cp_api operational        → 6/8 MET
  §1.7 snapshot cron active      → 7/8 MET (1.7 upgrades from PARTIAL to FULL)
  §1.8 first rollback rehearsal  → 8/8 MET

At 8/8 MET: Phase 7 kickoff commit may land.
Phase 7 kickoff commit must include Gate-A-CLEARED ADR + all 8 verifications.
```

No date trigger, no time window. Purely condition-based, per 0-6 framework.

## 8. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 1. No silent production mutation | ✅ — all prerequisite activations will be explicit |
| 6. No Phase 7 migration work | ✅ — this doc IS the answer: not legal |
| 9. No time-based unlock | ✅ — all transitions are condition-based |

## 9. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — 8 prerequisites enumerated; status per-prerequisite |
| Silent failure | PASS — §1 bottom-line NO is explicit |
| External dep | PASS — Gate-A CLEARED from Gemini round-5 evidence |
| Concurrency | PASS — single answer |
| Scope creep | PASS — answer only |

## 10. Label per 0-7 rule 10

- §1 bottom-line: **VERIFIED** (derived from §2)
- §2 requirement matrix: **VERIFIED** (each row cites evidence)
- §4 remaining work: **PROBABLE** (design-time; conditions to be met by future MOD-N)
- §5 permissible operations: **VERIFIED** (aligned with all prior orders)
- §7 transition: **VERIFIED** (deterministic, condition-based)
