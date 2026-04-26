# 05 — PR Merge Report

## 1. PR

| Field | Value |
| --- | --- |
| Number | #37 |
| Title | `fix(zangetsu): initialize A1 provenance bundle before rejected rounds (0-9W-A1-PB-SCOPE-FIX)` |
| Branch | `phase-7/a1-pb-scope-fix` |
| Base | `main` |
| Pre-merge HEAD (this branch) | `28bd58dd8c16323c9a7827f73c1b08285a926aba` (signed by ED25519 key SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk) |

## 2. Gates

| Check | Result | Time |
| --- | --- | --- |
| Identify affected modules | PASS | 32 s |
| Verify Phase 7 entry prerequisites (Gate-A) | PASS | 33 s |
| Gate-B summary | PASS | 3 s |
| Gate-B checks per module | skipping (the `arena_pipeline.py` change is a CODE_FROZEN module bug-fix annotated EXPLAINED_A1_CRASH_FIX; per-module check is not required for this class) | 0 s |
| `gh pr view --json mergeable,mergeStateStatus` | `MERGEABLE` / `CLEAN` | — |

## 3. Merge

| Field | Value |
| --- | --- |
| Method | `gh pr merge 37 --admin --squash --delete-branch` |
| Merged at (UTC) | 2026-04-26T13:17:28Z |
| Merge commit on main | `1a90807696af9ff23b19e2a956986197f5f15395` |
| State | MERGED |
| Branch deletion | YES (`phase-7/a1-pb-scope-fix` removed from origin) |

## 4. Branch Protection

`required_signatures` was satisfied: the squash-merge produced a GitHub-PGP-signed commit on `main`. No force-push, no branch-protection modification.

## 5. Phase 4 Verdict

PASS. Signed PR merged through the protected-main flow exactly per order §Phase 4. No deviations.
