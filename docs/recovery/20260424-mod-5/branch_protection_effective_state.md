# Branch Protection Effective State — MOD-5 Phase 1

**Order**: `/home/j13/claude-inbox/0-7` Phase 1 deliverable
**Produced**: 2026-04-24T00:30Z
**Purpose**: Single document that distinguishes **intended state** vs **live state** vs **compensated state** for branch protection.

---

## 1. Live state (probed at 2026-04-24T00:23Z)

```bash
gh api /repos/M116cj/j13-ops/branches/main/protection --jq '.'
```

Response (structured):
```json
{
  "required_signatures":     {"enabled": true},
  "required_linear_history": {"enabled": true},
  "enforce_admins":          {"enabled": false},
  "allow_force_pushes":      {"enabled": false},
  "allow_deletions":         {"enabled": false},
  "block_creations":         {"enabled": false},
  "required_conversation_resolution": {"enabled": false},
  "lock_branch":             {"enabled": false},
  "allow_fork_syncing":      {"enabled": false}
}
```

## 2. Intended state (per Phase 7 entry pack)

At Phase 7 kickoff, target state (per `phase7_entry_pack.md §1.4`):

```json
{
  "required_signatures":     {"enabled": true},
  "required_linear_history": {"enabled": true},
  "enforce_admins":          {"enabled": true},   ← CHANGE vs live
  "allow_force_pushes":      {"enabled": false},
  "allow_deletions":         {"enabled": false},
  "required_status_checks":  {"contexts": ["Module Migration Gate (Gate-B) / gate_b_summary", "phase-7-gate / gate_a_checks"]},   ← NEW
  "required_pull_request_reviews": {"required_approving_review_count": 1}   ← NEW (PR-based workflow)
}
```

## 3. Current compensated state (authoritative for MOD-5)

Live state + compensating controls from `admin_bypass_resolution.md §3`:

| Protection | Live | MOD-5 compensation |
|---|---|---|
| required_signatures | enabled | admin-bypass permitted but tracked per G21/G22 |
| required_linear_history | enabled | unchanged |
| enforce_admins | **false** | **compensated via G21 ADR-within-24h + G22 AKASHA witness + G24 identity allowlist** |
| required_status_checks | not set | Phase 7 dependency (workflows not yet committed) |
| required_pull_request_reviews | not set | Phase 7 dependency (PR workflow not yet in effect) |

## 4. Why these 3 states are not conflated anywhere in governance docs

### 4.1 Historical risk

Prior docs sometimes wrote "required_signatures=true is live" without qualifying admin-bypass. R4b-F1 HIGH flagged this.

### 4.2 MOD-5 remediation

Every governance doc going forward distinguishes:
- **LIVE** (actual current API state)
- **INTENDED** (Phase 7 target)
- **COMPENSATED** (current + compensating control = acceptable for Condition 2)

The three states are never collapsed in memo language.

### 4.3 Worked example for any memo

✅ Correct memo language:
> "Branch protection live state has `required_signatures=enabled`, `enforce_admins=disabled`. Per MOD-5 compensating control (ADR-within-24h + AKASHA witness + identity allowlist), Condition 2 Governance Live Proof reaches VERIFIED. Phase 7 entry requires transitioning `enforce_admins=true` (see `phase7_entry_pack.md §1.4`)."

❌ Incorrect (conflated):
> "Branch protection fully enforces signature requirements."  ← hides admin-bypass

## 5. Live-state probe script (reproducible)

```bash
#!/bin/bash
# probe_branch_protection.sh
# Usage: ssh j13@100.123.49.102 bash probe_branch_protection.sh

echo "== Branch protection live state (UTC: $(date -u +%Y-%m-%dT%H:%M:%SZ)) =="
gh api /repos/M116cj/j13-ops/branches/main/protection \
  --jq '{req_sig: .required_signatures.enabled, linear: .required_linear_history.enabled, admin_enforce: .enforce_admins.enabled, force_push: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled, required_checks: .required_status_checks, required_reviews: .required_pull_request_reviews}' 2>&1
```

Run before any Gate-A memo — snapshot the live state.

## 6. Transition checklist for Phase 7 entry (per `phase7_entry_pack.md §1.4`)

Before first Phase 7 commit:
1. j13 registers GPG key on GitHub account (one-time)
2. `~/.claude/trust/j13.asc` created with key fingerprint pin
3. Agent workflows (Claude/Codex) switch to PR-based: open PR → j13 human-signs merge
4. `gh api -X PUT /repos/M116cj/j13-ops/branches/main/protection --field enforce_admins=true`
5. Commit Gate-A-CLEARED ADR via PR + human-signed merge

## 7. Rollback path (if compensation fails review)

If Gemini round-5 judges compensation COSMETIC (rejects Path B):

Option-1: activate Path A immediately
```bash
gh api -X PUT /repos/M116cj/j13-ops/branches/main/protection --field enforce_admins=true
```
Consequence: all subsequent pushes to main require GPG signature. j13 must register GPG key before any more commits can land.

Option-2: accept Condition 2 = PARTIAL for extended window
- Gate-A stays STILL_PARTIALLY_BLOCKED
- Block Phase 7 via Condition 2 gap
- Delay until j13 can register GPG key + switch to PR workflow

MOD-5 prefers Option-1 if compensation rejected.

## 8. Non-negotiable rules compliance

| Rule | Evidence |
|---|---|
| 1. No silent mutation | ✅ — §1 live state probed at specific UTC timestamp |
| 3. No live gate change unless disclosed | ✅ — distinguishes live vs intended vs compensated |
| 9. No time-based unlock | ✅ — transition criteria are condition-based |

## 9. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — 3-state framework (live/intended/compensated) |
| Silent failure | PASS — §4.3 worked example shows incorrect language explicitly |
| External dep | PASS — GitHub API repeatable |
| Concurrency | PASS — single source of truth |
| Scope creep | PASS — branch protection only |

## 10. Label per 0-7 rule 10

- §1 live state: **VERIFIED** (API response captured)
- §2 intended state: **VERIFIED** (Phase 7 pack cross-reference)
- §3 compensated state: **VERIFIED** (matches admin_bypass_resolution §3)
- §6 transition checklist: **VERIFIED** (Phase 7 pack aligned)
