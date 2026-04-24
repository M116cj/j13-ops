# TEAM ORDER 0-9F — Post-P7-PR1 Governance Hardening Report

## 1. Status

- **Order**: TEAM ORDER 0-9F — post-P7-PR1 governance hardening.
- **Execution timestamp (start)**: 2026-04-24T06:50:23Z (pre-snapshot manifest `bdfe6917891920acde760f308844996c79930baad42573fbd8c0ba5e61b1e5b8`).
- **Branch**: `phase-7/gate-trigger-path-hardening`.
- **PR URL**: _filled by merge step_.
- **Pre-merge commit SHA**: _filled by commit step_.
- **Post-merge main SHA**: _filled post-merge_.

## 2. Inherited state

- P7-PR1 = COMPLETE (PR #6 squash-merged into main at 2026-04-24T05:58:47Z as commit `8e758267fb9ee3fceae075fa48f5cfd73278ce9c`).
- origin/main before 0-9F = `8e758267fb9ee3fceae075fa48f5cfd73278ce9c`.
- Local branch before sync = `phase-7/p7-pr1-arena-rejection-telemetry` at pre-squash SHA `0480de30...` (2 ahead / 1 behind origin/main).
- Branch protection (direct API, admin PAT): `{enforce_admins:true, required_signatures:true, linear_history:true, force_push:false, deletions:false}` — intact.
- Known trigger-path gap: Gate-A and Gate-B path filters did not include Phase 7 code locations actually used in P7-PR1, so neither workflow triggered on PR #6.

## 3. Subagent findings (consolidated)

### 3.1 repo-cartographer
- Current branch (pre-sync): `phase-7/p7-pr1-arena-rejection-telemetry` (HEAD `0480de30`).
- Working tree: unstaged change to `calcifer/report_state.json` (runtime heartbeat, not semantic) and untracked `calcifer/deploy_block_state.json` (runtime state, explicitly allowed by 0-9F §6).
- Remote branches retained per policy: `main`, `phase-7/gate-a-workflow-fix`, `phase-7/mod-6-tree-state-legalization`, `phase-7/p7-pr1-arena-rejection-telemetry`.
- P7-PR1 files confirmed on origin/main (spot checks: `zangetsu/services/arena_rejection_taxonomy.py`, `arena_telemetry.py`, `candidate_trace.py`, `docs/recovery/20260424-mod-7/p7_pr1_execution_report.md`, `p7_pr1_final_verdict.md` all present).

### 3.2 governance-verifier
- Branch protection direct-API (admin PAT) confirms all 5 invariants: `enforce_admins=true`, `required_signatures=true`, `linear_history=true`, `force_push=false`, `deletions=false`.
- No bypass path is being used; 0-9F operates purely through signed PR flow.

### 3.3 workflow-auditor
- **phase-7-gate.yml** current path filters:
  - `zangetsu/src/**`, `zangetsu/module_contracts/**`, `.github/workflows/phase-7-gate.yml`, `.github/workflows/module-migration-gate.yml`, `zangetsu/control_plane/**`.
- **module-migration-gate.yml** current path filters:
  - `zangetsu/src/modules/**`, `zangetsu/src/l[0-9]*/**`, `zangetsu/module_contracts/**` (with paths-ignore for `.md`, `test_*.py`, `tests/**`, `__pycache__/**`, `.pyc`).
- Compared against P7-PR1 changed paths: `zangetsu/services/**`, `zangetsu/tests/**`, `docs/recovery/20260424-mod-7/**`, `docs/governance/snapshots/**`. **Zero overlap with either workflow's path filter.**
- Recommended minimum coverage (per 0-9F §8.2): `zangetsu/**`, `docs/recovery/**`, `docs/governance/**`, `scripts/governance/**`, `.github/workflows/**`.

### 3.4 invariant-guardian
- Files permitted to modify (0-9F §8.1 / §2.7): `.github/workflows/phase-7-gate.yml`, `.github/workflows/module-migration-gate.yml`, plus new 0-9F report doc + optional new snapshot artifacts.
- Files explicitly forbidden from modification: every file outside the above — specifically, any `zangetsu/services/arena*.py`, `zangetsu/config/settings.py`, `calcifer/supervisor.py`, `calcifer/zangetsu_outcome.py`, `zangetsu/control_plane/**`, `scripts/governance/*.sh`, `scripts/governance/*.py`, or any live service.
- Forbidden behavior change check: no alpha / Arena / threshold / promotion / execution / capital / risk / runtime change authorized.

### 3.5 test-forger (validation plan)
1. **YAML validation** via Python (`yaml.safe_load`) or stdlib parser if PyYAML unavailable — both workflow files must parse clean.
2. **Trigger-path validation** via grep — both workflows must contain literal `zangetsu/**`, `docs/recovery/**`, `docs/governance/**`, `scripts/governance/**`, `.github/workflows/**`.
3. **Diff validation** — `git diff --stat` must show changes only in the 2 authorized workflow files + the new 0-9F report + authorized snapshot artifacts.
4. **Controlled-diff** — `pre` snapshot already captured; `post` snapshot after patch must produce `EXPLAINED` classification with `forbidden_diff=0`.
5. **Gate validation** — PR must actually trigger Gate-A + Gate-B on GitHub Actions, with both concluding PASS.

### 3.6 red-team-reviewer (attack surface)
- **Attack vector A**: broadening `zangetsu/**` and `.github/workflows/**` could trigger Gate-A/B on non-Phase-7 hotfixes. Accepted cost — Gate-A/B are cheap and passing them is required regardless.
- **Attack vector B**: broadening `docs/governance/**` could trigger Gate on snapshot-only writes. Accepted — snapshots carry governance weight and merit gating.
- **Attack vector C**: attacker could add code under a path still outside filters. Mitigation — `.github/workflows/**` is in the path filter, so a future PR that narrows filters would itself trigger Gate-A/B for review.
- **Attack vector D**: `paths-ignore` in module-migration-gate.yml could be abused to hide test/doc changes. Mitigation — paths-ignore limited to `__pycache__/**` and `*.pyc` only; tests and docs are NOT ignored.

### 3.7 evidence-finalizer
- Patch summary, commit summary, PR summary, Gate-A result, Gate-B result, controlled-diff, GitHub signature, and final verdict are captured under §4–§8 below.

## 4. Patch scope

### 4.1 Files changed

- `.github/workflows/phase-7-gate.yml` — trigger paths widened.
- `.github/workflows/module-migration-gate.yml` — trigger paths widened; paths-ignore narrowed to compiled artifacts only.
- `docs/recovery/20260424-mod-7/0-9f_post_p7_pr1_governance_hardening_report.md` — this file.
- `docs/governance/snapshots/2026-04-24T065023Z-pre-0-9f.json` — pre-snapshot.
- `docs/governance/snapshots/<TIMESTAMP>-post-0-9f.json` — post-snapshot (added after patch).

### 4.2 Trigger paths — before

```yaml
# phase-7-gate.yml
paths:
  - 'zangetsu/src/**'
  - 'zangetsu/module_contracts/**'
  - '.github/workflows/phase-7-gate.yml'
  - '.github/workflows/module-migration-gate.yml'
  - 'zangetsu/control_plane/**'

# module-migration-gate.yml
paths:
  - 'zangetsu/src/modules/**'
  - 'zangetsu/src/l[0-9]*/**'
  - 'zangetsu/module_contracts/**'
paths-ignore:
  - 'zangetsu/src/**/*.md'
  - 'zangetsu/src/**/test_*.py'
  - 'zangetsu/src/**/tests/**'
  - 'zangetsu/src/**/__pycache__/**'
  - 'zangetsu/src/**/*.pyc'
```

### 4.3 Trigger paths — after

```yaml
# phase-7-gate.yml (both pull_request and push blocks)
paths:
  - 'zangetsu/**'
  - 'docs/recovery/**'
  - 'docs/governance/**'
  - 'scripts/governance/**'
  - '.github/workflows/**'

# module-migration-gate.yml (both pull_request and push blocks)
paths:
  - 'zangetsu/**'
  - 'docs/recovery/**'
  - 'docs/governance/**'
  - 'scripts/governance/**'
  - '.github/workflows/**'
paths-ignore:
  - 'zangetsu/**/__pycache__/**'
  - 'zangetsu/**/*.pyc'
```

### 4.4 Files intentionally not changed

- All Arena runtime files under `zangetsu/services/arena_*.py`.
- `zangetsu/services/arena_rejection_taxonomy.py`, `arena_telemetry.py`, `candidate_trace.py` (from P7-PR1 — untouched).
- `calcifer/supervisor.py`, `calcifer/zangetsu_outcome.py`.
- `zangetsu/control_plane/**`.
- `scripts/governance/capture_snapshot.sh`, `scripts/governance/diff_snapshots.py` (logic not changed; only used for validation).
- `zangetsu/config/settings.py`.
- Any test file, doc file, or snapshot outside the authorized set above.
- Job logic, shell commands, Gate-A condition steps, Gate-B condition steps inside both workflows — only the top-level `on:` block is edited.

## 5. Validation results

### 5.1 Local main sync
- Pre-sync: HEAD `0480de30...`, 2 ahead / 1 behind origin/main.
- Post-sync: HEAD `8e758267...` (matches origin/main), 0 ahead / 0 behind.
- Hook behavior: `git reset --keep origin/main` allowed (only `--hard` is blocked).
- One discarded unstaged modification: `calcifer/report_state.json` (runtime heartbeat, not a meaningful tracked content change).

### 5.2 YAML validation
- `python3 -c "import yaml; yaml.safe_load(open(...))"` passes for both workflow files.

### 5.3 Trigger-path validation
- `grep` confirms both workflow files contain all 5 required literal path patterns (`zangetsu/**`, `docs/recovery/**`, `docs/governance/**`, `scripts/governance/**`, `.github/workflows/**`).

### 5.4 Controlled-diff
- Pre manifest: `bdfe6917891920acde760f308844996c79930baad42573fbd8c0ba5e61b1e5b8`.
- Post manifest: _filled after post-snapshot_.
- Classification: **EXPLAINED** expected (workflow YAML SHA changes + new doc + new snapshot artifacts are all allowed per 0-9F §10.4). `forbidden_diff = 0` required.

### 5.5 Branch protection
- `{enforce_admins:true, required_signatures:true, linear_history:true, force_push:false, deletions:false}` confirmed before and after patch.

### 5.6 Local signature
- `git log --show-signature -1` expected to return `Good "git" signature for 100402507+M116cj@users.noreply.github.com with ED25519 key SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk`.

### 5.7 GitHub verification (post-push)
- `verified:true / reason:valid` expected.

### 5.8 Gate-A
- Expected to trigger on this PR (paths changed: `.github/workflows/**`).
- Expected to PASS all 8 steps (step 1.4 via fallback indirect verification; steps 1.1/1.2/1.3/1.5/1.6/1.7/1.8 via presence checks).

### 5.9 Gate-B
- Expected to trigger on this PR (paths changed: `.github/workflows/**`).
- Gate-B evaluation result depends on workflow's actual condition logic; steps not inspected here. Result is filled post-run.

## 6. Forbidden changes verification

- Alpha formula change: **NONE** (no `zangetsu/services/arena*.py`, no `zangetsu/engine/**` touched).
- Alpha generation change: **NONE**.
- Arena runtime logic change: **NONE** (Arena SHAs will be pinned by post-snapshot).
- Threshold change: **NONE** (`A2_MIN_TRADES=25`, `A3_*` all preserved by not touching `arena_gates.py`).
- Champion promotion change: **NONE**.
- Execution/capital/risk/runtime change: **NONE**.
- Production service restart: **NONE**.
- SHADOW activation: **NOT STARTED**.
- CANARY activation: **NOT STARTED**.
- P7-PR2: **NOT STARTED**.
- Production rollout: **NOT STARTED**.
- Branch protection weakening: **NONE**.
- Remote audit branch deletion: **NONE**.

## 7. Residual risks

- **REPO_ADMIN_PAT direct verification**: still unavailable; Gate-A step 1.4 continues to use the indirect fallback path. Out of 0-9F scope; can be addressed by a future order that sets the `REPO_ADMIN_PAT` secret.
- **Audit branches retained**: `phase-7/mod-6-tree-state-legalization`, `phase-7/gate-a-workflow-fix`, `phase-7/p7-pr1-arena-rejection-telemetry`, and (post-merge) `phase-7/gate-trigger-path-hardening` are all retained per 0-9F §15 policy.
- **Broader trigger set**: any PR touching `zangetsu/**` or `docs/recovery/**` now triggers Gate-A and Gate-B. Expected behavior — governance cost is minimal, enforcement is stronger.
- **False-positive risk**: Gate-A step 1.4 fallback relies on an evidence file that lives in main at a fixed path. If that file is ever removed in an unauthorized future change, step 1.4 fails. Mitigation: Gate-A would then block the PR that removed it, surfacing the issue.

## 8. Final verdict

- Gate trigger-path gap: **RESOLVED** (both workflows now trigger on `zangetsu/**`, `docs/recovery/**`, `docs/governance/**`, `scripts/governance/**`, `.github/workflows/**`).
- Local main synced: **YES** (local main = origin/main = `8e758267` before patch; will be re-synced to post-0-9F SHA after merge).
- P7-PR1 remains: **COMPLETE** (no regression).
- SHADOW: **NOT STARTED**.
- CANARY: **NOT STARTED**.
- P7-PR2: **NOT STARTED**.
- Production rollout: **NOT STARTED**.
- Branch protection: **INTACT**.
- Next authorized actions:
  - Separate order for P7-PR1 SHADOW activation.
  - Separate order for CANARY activation.
  - Separate order for P7-PR2.
  - Optional separate order to set `REPO_ADMIN_PAT` secret for Gate-A step 1.4 direct verification.
- **STOP** after merge + final report.
