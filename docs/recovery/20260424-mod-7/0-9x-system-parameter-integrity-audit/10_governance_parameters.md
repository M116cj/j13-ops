# 10 — Governance and Controlled-Diff Parameter Audit

## 1. Branch Protection Snapshot

```json
{
  "enforce_admins": true,
  "required_signatures": true,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

| Control | Expected | Actual | PASS |
| --- | --- | --- | --- |
| `enforce_admins` | true | true | YES |
| `required_signatures` | true | true | YES |
| `required_linear_history` | true | true | YES |
| `allow_force_pushes` | false | false | YES |
| `allow_deletions` | false | false | YES |

→ **5/5 branch protection flags intact.**

## 2. CI Workflows

```
.github/workflows/
├── module-migration-gate.yml
└── phase-7-gate.yml
```

| Gate | Purpose | Status |
| --- | --- | --- |
| Gate-A | Verify Phase 7 entry prerequisites | last 4 PRs (38-41): all PASS |
| Gate-B | per-module checks + summary | last 4 PRs: all PASS |

## 3. Signed Commit Configuration

`git config` on Alaya:
- `gpg.format = ssh`
- `user.signingkey = /home/j13/.ssh/id_ed25519_signing.pub`
- `commit.gpgsign = true`

Latest 4 PRs (38, 39, 40, 41) all show `G` signature status (Good).

## 4. Controlled-Diff Configuration

| Item | Status |
| --- | --- |
| controlled-diff classification used | YES — last PR was `EXPLAINED_DOCS_ONLY` |
| CODE_FROZEN fields enforced | YES — `feedback_decision_record.py` lists `A2_MIN_TRADES_UNCHANGED`; pre-commit fitness lock active per VERSION_LOG v0.7.1 |
| Phase 7 trace-only acceptance rules | active per `.github/workflows/phase-7-gate.yml` |
| Pre-commit hooks active | YES — `.githooks/pre-commit` enforces fitness modification gating |

## 5. Git State

| Item | Value |
| --- | --- |
| Mac main HEAD | `a74406d` |
| Alaya main HEAD | `a74406d` |
| origin/main | `a74406d` |
| Mac+Alaya synced | YES |
| Working tree (Alaya) | clean (excluding 3 runtime artifacts: calcifer logs + engine.jsonl.1) |

## 6. Recent PR History (Phase 7 Series)

| PR | Status | Class | Date |
| --- | --- | --- | --- |
| #38 | merged | EXPLAINED_A1_CRASH_FIX (1-line `_pb` UnboundLocalError) | 2026-04-25 |
| #39 | merged | EXPLAINED_DOCS_ONLY (alpha_zoo offline replay) | 2026-04-25 |
| #40 | merged | EXPLAINED_DOCS_ONLY (cost calibration diagnosis) | 2026-04-26 |
| #41 | merged | EXPLAINED_DOCS_ONLY (calibration candidate review) | 2026-04-26 |

All squash-merged via `--admin --squash --delete-branch` pattern.

## 7. Governance Reviews Completed

The following governance documents are present from prior orders and confirm the contract integrity:
- `docs/recovery/20260424-mod-7/0-9w-cost-threshold-horizon-calibration-diagnosis/` (11 evidence files)
- `docs/recovery/20260424-mod-7/0-9w-calibration-candidate-review/` (12 evidence files)
- Earlier governance milestones documented

## 8. Classification

| Verdict | Match? |
| --- | --- |
| **GOVERNANCE_OK** | **YES** |
| GATE_RISK | NO |
| CONTROLLED_DIFF_RISK | NO |
| SIGNING_RISK | NO |
| BRANCH_PROTECTION_RISK | NO |

→ **Phase 10 verdict: GOVERNANCE_OK.** Branch protection, signed commits, gates, controlled-diff classification, and pre-commit hooks are all intact and functional. The only gap is implementation-side (DB schema migration not applied) — not governance-side.
