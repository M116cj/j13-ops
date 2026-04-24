# TEAM ORDER 0-9I — Gate-B Pull Request Trigger Debugging Report

## 1. Status

| Field | Value |
|---|---|
| 0-9I status | **COMPLETE (pending Gate-B pull_request validation on this PR itself)** |
| Branch | `phase-7/gate-b-pr-trigger-debugging` |
| PR URL | _filled post-PR-open_ |
| origin/main (pre-patch) | `0b41550cad85695c53122a1f2f01e62b291c63c4` |
| Post-merge main SHA | _filled post-merge_ |
| Pre-snapshot manifest | `c9e4f3c9be9c219c64cf964ac1b922a5768a15ef6d59e3f82638c82616164a21` |
| Post-snapshot manifest | `799194e840fc0f17915c9d712e4a486e7a090bb178c42a5efe68f8dad812c869` |

## 2. Root cause

**Gate-B's on-block held both `paths` and `paths-ignore` filters on the same event** (`pull_request` and `push`). Across PRs #4–#9, every Gate-B run concluded with `"This run likely failed because of a workflow file issue"` at 0 s, and pull_request dispatch never fired. Gate-A, which had only `paths` on the same events, always triggered correctly.

### Evidence

1. **Workflow registration** (`gh api .../actions/workflows`):
   - Gate-A: `name = "Phase 7 Gate (Gate-A)"` — GitHub parsed the workflow's `name:` field.
   - Gate-B: `name = ".github/workflows/module-migration-gate.yml"` — GitHub fell back to the file path, which indicates no workflow run ever successfully initialised to populate the display name.

2. **Run history** (`gh run list --workflow module-migration-gate.yml --limit 50`):
   - 10/10 historical runs = `event=push`, `conclusion=failure`, `duration=0s`.
   - 0 pull_request runs across Phase 7 PRs #4, #5, #6, #7, #8, #9.

3. **Workflow run log** (`gh run view 24879747836`):
   - `"This run likely failed because of a workflow file issue"` at 0 s.
   - `gh run view --log` returns `"log not found"` — workflow failed at the pre-job validation step, never produced logs.

4. **Symmetric comparison**:
   - Gate-A `on.pull_request` keys: `['paths']` → works.
   - Gate-B `on.pull_request` keys (pre-fix): `['paths', 'paths-ignore']` → never triggered.

### Why the fix resolves it

Removing `paths-ignore` from both the `pull_request` and `push` event blocks makes Gate-B's on-block structurally identical to Gate-A's working structure:

```yaml
pull_request:
  paths:
    - 'zangetsu/**'
    - 'docs/recovery/**'
    - 'docs/governance/**'
    - 'scripts/governance/**'
    - '.github/workflows/**'
push:
  branches: [main]
  paths:
    - ... (same 5 patterns)
```

`paths-ignore` was originally present to exclude `__pycache__` and `*.pyc` from triggering Gate-B. Those files are filtered by the repo-level `.gitignore` and will not appear in Phase 7 PRs, so removing the `paths-ignore` block is a no-op in practice for PR content while restoring Gate-B's ability to dispatch on pull_request events.

### Hypothesis coverage

| # | Hypothesis | Evidence | Verdict |
|---|---|---|---|
| H1 | Gate-B workflow disabled | `state=active` in `gh api actions/workflows` | Rejected |
| H2 | Gate-B file path/name mismatch | path = `.github/workflows/module-migration-gate.yml` correct | Rejected |
| H3 | Gate-B YAML syntax invalid | PyYAML `safe_load` succeeds; `gh workflow view` shows full YAML | Rejected (parse OK, but GitHub's schema validation failing below parse level) |
| H4 | `pull_request` block absent | present in main-version workflow | Rejected |
| H5 | Path filters malformed | glob patterns well-formed | Rejected |
| H6 | Branch filters exclude PR target | `branches` only on push, not pull_request | Rejected |
| H7 | Trigger block nested under wrong key | `on.pull_request.paths` correct | Rejected |
| H8 | GitHub recognizes workflow but not pull_request | confirmed: no pull_request runs ever | **Confirmed as symptom** |
| H9 | Workflow not on default branch | on main since MOD-7B (`aff984a5`) | Rejected |
| H10 | YAML parse mismatch between local and GitHub | `gh workflow view --yaml` shows matching content | Rejected |
| H11 | Repository Actions setting suppresses workflow | Gate-A works on same repo | Rejected |
| H12 | Required status checks misconfigured | branch protection has no required_status_checks | Rejected |
| H13 | Workflow name collision | no other workflow named similarly | Rejected |
| H14 | push 0s failures mask pull_request absence | confirmed; both symptoms stem from same cause | **Confirmed as symptom** |
| H15 | **Config bug: paths + paths-ignore combined** | **Gate-A only has paths → works; Gate-B has both → fails** | **CONFIRMED AS ROOT CAUSE** |

## 3. Diagnostics

### 3.1 Workflow registration (before fix)

```
Gate-A workflow id 265574851
  name: "Phase 7 Gate (Gate-A)"
  path: .github/workflows/phase-7-gate.yml
  state: active
Gate-B workflow id 265574689
  name: ".github/workflows/module-migration-gate.yml"  ← file path fallback (no successful run ever)
  path: .github/workflows/module-migration-gate.yml
  state: active
```

### 3.2 Run history (before fix)

- Gate-A: mix of `pull_request success` + `push success` across PRs.
- Gate-B: 10/10 `push failure 0s`, zero `pull_request` runs.

### 3.3 Path-filter analysis

PR #9 (P7-PR1 V10 mapping patch) changed paths:
- `zangetsu/services/arena_rejection_taxonomy.py`
- `zangetsu/tests/test_arena_rejection_taxonomy.py`
- `docs/recovery/20260424-mod-7/*.md`
- `docs/governance/snapshots/*.json`

All 4 patterns match Gate-B's post-0-9F `paths` allowlist. None match the old `paths-ignore` (`__pycache__/**` or `*.pyc`). Logically Gate-B should have triggered. GitHub did not dispatch it — consistent with a GitHub-side validation failure on the combined paths + paths-ignore config.

### 3.4 YAML validation

- Pre-fix: `yaml.safe_load` succeeds on both files. PyYAML accepts paths + paths-ignore as a dict with both keys. GitHub's internal schema validator is stricter than PyYAML and rejects the combination or fails to evaluate it.
- Post-fix: both workflows parse identically:
  ```
  phase-7-gate.yml:           pull_request keys = ['paths']
  module-migration-gate.yml:  pull_request keys = ['paths']  ← now identical to Gate-A
  ```

### 3.5 Gate-A vs Gate-B structure diff

| Field | Gate-A | Gate-B (pre-fix) | Gate-B (post-fix) |
|---|---|---|---|
| `on.pull_request.paths` | ✅ | ✅ | ✅ |
| `on.pull_request.paths-ignore` | absent | **present (4 entries)** | absent |
| `on.push.branches` | `[main]` | `[main]` | `[main]` |
| `on.push.paths` | ✅ | ✅ | ✅ |
| `on.push.paths-ignore` | absent | **present (4 entries)** | absent |

## 4. Patch

### 4.1 Files changed

- `.github/workflows/module-migration-gate.yml` — 9 insertions, 11 deletions (net -2 lines). Updated `on:` block header comment + removed 2 × 3-line `paths-ignore` blocks.
- `docs/recovery/20260424-mod-7/0-9i_gate_b_pull_request_trigger_debugging_report.md` — this file.
- `docs/governance/snapshots/2026-04-24T085137Z-pre-0-9i.json`
- `docs/governance/snapshots/2026-04-24T085230Z-post-0-9i.json`

### 4.2 Trigger config diff (`on:` block)

**Before**:
```yaml
on:
  pull_request:
    paths:
      - 'zangetsu/**'
      - 'docs/recovery/**'
      - 'docs/governance/**'
      - 'scripts/governance/**'
      - '.github/workflows/**'
    paths-ignore:
      - 'zangetsu/**/__pycache__/**'
      - 'zangetsu/**/*.pyc'
  push:
    branches: [main]
    paths: [... same 5 patterns ...]
    paths-ignore: [... same 2 patterns ...]
```

**After**:
```yaml
on:
  pull_request:
    paths:
      - 'zangetsu/**'
      - 'docs/recovery/**'
      - 'docs/governance/**'
      - 'scripts/governance/**'
      - '.github/workflows/**'
  push:
    branches: [main]
    paths:
      - 'zangetsu/**'
      - 'docs/recovery/**'
      - 'docs/governance/**'
      - 'scripts/governance/**'
      - '.github/workflows/**'
```

### 4.3 Workflow logic changed?

**NO.** Gate-B's `jobs:` section (`identify_affected_modules`, `gate_b_per_module`, `gate_b_summary`), all steps, all conditions, all permissions, all concurrency settings — untouched. Only the top-level `on:` trigger filter changed.

## 5. Validation

### 5.1 YAML

Both workflows parse cleanly. Gate-A structure and Gate-B structure now match: `pull_request.keys = ['paths']`, `push.keys = ['branches', 'paths']`.

### 5.2 Controlled-diff

- Pre-snapshot: `docs/governance/snapshots/2026-04-24T085137Z-pre-0-9i.json` (manifest `c9e4f3c9...`).
- Post-snapshot: `docs/governance/snapshots/2026-04-24T085230Z-post-0-9i.json` (manifest `799194e8...`).
- Classification: **EXPLAINED**.
- Zero-diff: **43 fields** (all Arena runtime SHAs, branch protection, systemd units unchanged).
- Explained-diff: 1 field (`repo.git_status_porcelain_lines 1 → 3`, reflecting the staged workflow + report + pre-snapshot files).
- **Forbidden diff: 0**.

### 5.3 Gate-A (expected)

Must trigger on pull_request (this PR touches `.github/workflows/**`) and PASS all 8 steps. Filled post-PR-open.

### 5.4 Gate-B (definitive test)

**The merge decision for 0-9I depends on Gate-B actually triggering a pull_request run on this PR.** Required:
- Gate-B workflow run exists.
- `event = pull_request`.
- `head_branch = phase-7/gate-b-pr-trigger-debugging`.
- `head_sha = <0-9I commit SHA>`.
- `conclusion = success` (or documented noop-success — `identify_affected_modules` is expected to output `noop=true` because this PR doesn't touch `zangetsu/src/modules/**` or `zangetsu/module_contracts/**`; `gate_b_summary` then exits 0 with a notice).

If this fails, STOP and report unresolved Gate-B blocker.

### 5.5 Signature verification

Local and GitHub: `verified=true / reason=valid` expected (using Alaya ed25519 key `SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk`).

### 5.6 Branch protection

`{enforce_admins:true, req_sig:true, linear:true, force_push:false, deletions:false}` — unchanged throughout.

## 6. Forbidden changes verification

- Alpha formula: ✓ unchanged
- Alpha generation: ✓ unchanged
- Arena runtime: ✓ unchanged (all Arena SHAs preserved in controlled-diff)
- Thresholds: ✓ unchanged (A2_MIN_TRADES=25, A3_* pinned)
- Champion promotion: ✓ unchanged
- Execution / capital / risk / runtime: ✓ unchanged
- Service restart: ✓ none
- Branch protection: ✓ intact
- CANARY / P7-PR2 / production rollout: ✓ NOT STARTED

## 7. Final verdict

```
Root cause identified:       YES (paths + paths-ignore coexistence)
Minimal fix applied:         YES (remove paths-ignore; no job-logic change)
YAML validation:             PASS
Controlled-diff:             EXPLAINED, 0 forbidden
Gate-B pull_request restored: PENDING validation on this PR
                             If Gate-B triggers + passes on this PR:
                               merge; 0-9I COMPLETE.
                             If Gate-B still fails to trigger:
                               STOP per 0-9I §16.13; report unresolved blocker.
Next action recommendation:  separate order for P7-PR1 CANARY activation
                             (only after Gate-B pull_request trigger is
                              proven on this PR)
STOP
```
