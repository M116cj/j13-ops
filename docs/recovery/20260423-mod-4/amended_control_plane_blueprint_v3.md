# Amended Control Plane Blueprint v3 — MOD-4

**Order**: `/home/j13/claude-inbox/0-5` Phase 4 deliverable
**Produced**: 2026-04-23T10:32Z
**Supersedes**: `control_plane_blueprint_amendment.md` (MOD-3) via MOD-4 delta
**Scope**: Absorb MOD-4 Phase 2A signature-enforcement LIVE activation + M9 rate-limit clarification.

---

## 1. MOD-4 delta from MOD-3 blueprint amendment

| Section | MOD-3 | MOD-4 v3 |
|---|---|---|
| §5 decision-rights | Ownership column introduced | Unchanged (no MOD-4 row shift) |
| §5.4 branch protection | "applied when Phase 7 nears" | **LIVE** (ACTIVATED 2026-04-23T09:40Z; `enforce_admins=false`) |
| §7.1 parameter entry | schema with ownership_authority + subscribers | +2 keys: `cp_bridge.rest_fetch.single_flight_enabled`, `cp_bridge.rest_fetch.jitter_ms` |
| §8 API sketch | GET/POST endpoints + batch read | Unchanged |
| §10 CS-05 | detection-only, prevention out-of-scope | Unchanged |
| **NEW §11 Governance enforcement status** | — | Inline reference to `governance_enforcement_status_matrix.md` for 20 governance rules' live/pending/spec status |

## 2. Updated §5.4 (LIVE branch protection status)

Old (MOD-3):
> "branch protection `required_signatures=true` + `required_linear_history=true` are applied when Phase 7 nears, not in MOD-3."

New (MOD-4):
> "**§5.4 Branch protection — ACTIVE since 2026-04-23T09:40Z (MOD-4 Phase 2A).**
>
> Current configuration on `main` branch:
> - `required_signatures: enabled=true` (non-admin unsigned commits rejected at push)
> - `required_linear_history: enabled=true` (no merge commits on main)
> - `enforce_admins: false` (j13 repo-owner admin bypass preserved for bootstrap + emergency)
> - `allow_force_pushes: false` (GitHub default)
> - `allow_deletions: false` (GitHub default)
>
> **Disclosure**: `enforce_admins=false` is a deliberate trade-off — admin bypass enables this MOD-4 commit itself + future emergency operations. Non-admin paths (Gemini / Codex / PRs from non-j13 actors) DO get enforced. Long-term hardening: j13 should GPG-sign direct commits as habit; future ops hardening may flip `enforce_admins=true` once trust pins + emergency tooling exist."

Full spec in `required_signatures_enforcement_spec.md`.

## 3. Updated §7.1 parameter entry (2 new cp_bridge keys)

```yaml
parameter:
  id: <canonical_key>
  # ... all existing MOD-3 fields ...

# New keys added to CP registry (MOD-4):
- id: cp_bridge.rest_fetch.single_flight_enabled
  type: bool
  default: true
  owners: [gov_contract_engine]
  rollout_tier: FULL
- id: cp_bridge.rest_fetch.jitter_ms
  type: int
  default: 500
  valid_range: [0, 5000]
  owners: [gov_contract_engine]
  rollout_tier: FULL
```

## 4. NEW §11 — Governance enforcement status (pointer)

Full enforcement status table for all 20 governance rules (G1-G20) lives in `governance_enforcement_status_matrix.md` — MOD-4 Phase 2A deliverable. Summary:
- 7 LIVE (35%)
- 1 LIVE-by-coupling (5%)
- 6 PARTIAL (30%)
- 2 PENDING SPEC (10%)
- 4 SPEC-ONLY (20%)

Cross-reference from CP blueprint: each decision-rights row in §5 should reference the G-number when implemented. Phase 7 maps these 1:1 (e.g., G11 required_signatures = §5 branch-protection row; G3 Calcifer RED = §5 deploy-block row).

## 5. M9 rate-limit note (referencing `cp_worker_bridge_rate_limit_split.md`)

Add to §3.3 "Compatibility with existing surfaces":
> "cp_worker_bridge (M9) rate-limit split across three channels (cache_lookup / rest_fetch / subscribe_event) per MOD-4 Phase 2B. Rate-limits are CONTRACT-BOUND (declared in M9 module contract) not CP-TUNABLE — preventing accidental operator loosening. Observability of rate-limit drops available via obs_metrics `cp_worker_bridge_rate_limit_drop_total` counter."

Full spec: `cp_worker_bridge_rate_limit_split.md` + `amended_cp_worker_bridge_contract.md` + `control_surface_rate_limit_clarification.md`.

## 6. CS-05 status unchanged

MOD-4 makes no change to CS-05 status (detection-only; prevention out-of-scope). Noted for completeness.

## 7. Non-negotiable rules

| Rule | Compliance |
|---|---|
| 1. No silent production mutation | ✅ — §5.4 LIVE activation fully disclosed |
| 3. No live gate change | ✅ — runtime gate behavior unchanged; branch protection is governance, not production runtime |
| 8. No broad refactor | ✅ — targeted delta |
| 9. No black-box control surface | ✅ — §5.4 explicit about admin bypass |

## 8. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — §5.4 LIVE disclosure covers edge cases (admin bypass, non-admin enforcement) |
| Silent failure | PASS — §5.4 "Disclosure" block explicit about enforce_admins=false trade-off |
| External dep | PASS — GitHub API verified |
| Concurrency | PASS — protection is atomic branch-level |
| Scope creep | PASS — MOD-4 §2 delta scope |

## 9. Resolution status

Gemini R3a-F8 HIGH (signatures spec-only) — **RESOLVED** via §5.4 LIVE update.

## 10. Label per 0-5 rule 10

- §2 §5.4 update: **VERIFIED** (API response captured in `required_signatures_enforcement_spec.md §1`)
- §3 parameter additions: **VERIFIED** (keys align with M9 amended contract)
- §4 §11 governance matrix: **VERIFIED** (cross-referenced)
