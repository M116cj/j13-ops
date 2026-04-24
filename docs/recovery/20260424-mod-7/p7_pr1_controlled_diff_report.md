# P7-PR1 Controlled-Diff Report

Per TEAM ORDER 0-9E §12 + MOD-6 `controlled_diff_framework.md`.

## 1. Snapshots

| Role | File | Captured at | sha256_manifest |
|---|---|---|---|
| Pre  | `docs/governance/snapshots/2026-04-24T043907Z-pre-j13_alaya.json`  | 2026-04-24T04:39:07Z | `69e62d06b9beb2518742993212b53265686c7afeab1fd0485d60b47fe0104139` |
| Post | `docs/governance/snapshots/2026-04-24T044538Z-post-j13_alaya.json` | 2026-04-24T04:45:38Z | `00d5b39255352fb49c451e4ca3f2529697bb08c089abc83798c91f404fc54109` |

`Manifest match: False` — expected. A trivial manifest match would indicate nothing was added; we added 6 authorized files between pre and post, so the manifest must differ. What matters is the *per-field classification* of the differences, below.

## 2. Classification — **EXPLAINED**

```
Zero diff:       40 fields
Explained diff:   4 fields
Forbidden diff:   0 fields
```

**Verdict: EXPLAINED** — all changes trace to allowed catalog entries per 0-9E §12 "Allowed explained diffs" + MOD-5 `state_diff_acceptance_rules.md`.

## 3. Zero-diff surfaces (critical invariants — 40 fields)

All Arena runtime / governance surfaces unchanged between pre and post snapshots:

- **Arena runtime files** (critical invariants per 0-9E §9):
  - `config.arena_pipeline_sha` — unchanged
  - `config.arena23_orchestrator_sha` — unchanged
  - `config.arena45_orchestrator_sha` — unchanged
  - `config.zangetsu_settings_sha` — unchanged
  - `config.calcifer_supervisor_sha` — unchanged
  - `config.zangetsu_outcome_sha` — unchanged
- **Branch protection** (7 fields): `enforce_admins=true`, `req_sig=true`, `linear=true`, `force_push=false`, `deletions=false` — all unchanged.
- **Systemd units** (6 units × 3 fields each = 18 fields): all unchanged.
- **Repo HEAD**: `966cd59326b970055d1c398f2a9d45215bbfbc49` in both snapshots.
- **Gate-A classification**: `CLEARED` both.
- **AKASHA health**: unchanged.
- **Arena processes count**: 0 → 0 (arena is still frozen post-MOD-3).

## 4. Explained-diff surfaces (4 fields)

| Field | Pre | Post | Classification rationale |
|---|---|---|---|
| `config.calcifer_deploy_block_file_sha` | `b66a136d...` | `82c7fe27...` | Calcifer runtime state file tick — § 4 a of `state_diff_acceptance_rules.md` (runtime state is expected to tick; `deploy_block` SHA reflects a fresh status heartbeat write, not a governance change). |
| `config.calcifer_state_file_sha` | `b66a136d...` | `82c7fe27...` | Same — calcifer maintains paired state files; both tick together on a heartbeat. |
| `runtime.calcifer_deploy_block_ts_iso` | `2026-04-24T04:38:31` | `2026-04-24T04:43:32` | Runtime timestamp advance (monotonic, 5-min heartbeat). Expected. |
| `repo.git_status_porcelain_lines` | 1 | 8 | Working tree gained 7 entries: 6 new authorized P7-PR1 files + 1 pre-snapshot artifact written to `docs/governance/snapshots/`. All new entries are in authorized paths per 0-9E §8 / §10. |

## 5. Forbidden-diff check — **0 forbidden diffs**

Explicitly verified: none of the following forbidden-diff triggers fired.

- Production service mutation → not triggered (no systemd unit transitioned).
- Threshold mutation → not triggered (arena_pipeline SHA + settings SHA unchanged).
- Runtime config mutation → not triggered (zangetsu_settings_sha unchanged).
- Branch protection mutation → not triggered (all 5 protection fields unchanged).
- Alpha formula mutation → not triggered (arena_pipeline + arena23_orchestrator + arena45_orchestrator SHAs unchanged).
- Arena decision logic mutation outside telemetry → not triggered (all Arena SHAs unchanged; no Arena code touched).
- Execution engine mutation → not triggered (no files under an execution path were modified).

## 6. File-level delta (for completeness)

Files added in the working tree between pre and post snapshot:

| Path | Purpose | Authorized by |
|---|---|---|
| `zangetsu/services/arena_rejection_taxonomy.py` | Taxonomy: 18 reasons × 14 categories × 4 severities + classifier | 0-9E §8.1–§8.2 |
| `zangetsu/services/arena_telemetry.py` | RejectionTrace + TelemetryCollector + JSON serialization | 0-9E §8.3–§8.8 |
| `zangetsu/services/candidate_trace.py` | CandidateLifecycle + derive_deployable_count | 0-9E §8.4–§8.6 |
| `zangetsu/tests/test_arena_rejection_taxonomy.py` | 18 taxonomy tests | 0-9E §8.9 |
| `zangetsu/tests/test_arena_telemetry.py` | 19 telemetry + trace tests | 0-9E §8.10 |
| `zangetsu/tests/test_p7_pr1_behavior_invariance.py` | 9 behavior-invariance tests (threshold pinning + import isolation) | 0-9E §8.11 |
| `docs/recovery/20260424-mod-7/p7_pr1_*.md` (6 files) | Docs (this file among them) | 0-9E §10 |
| `docs/governance/snapshots/2026-04-24T043907Z-pre-j13_alaya.json` | Pre-snapshot artifact | `scripts/governance/capture_snapshot.sh` |
| `docs/governance/snapshots/2026-04-24T044538Z-post-j13_alaya.json` | Post-snapshot artifact | `scripts/governance/capture_snapshot.sh` |

Files modified: **none**.
Files deleted: **none**.

## 7. Verdict

```
Controlled-diff = EXPLAINED
Forbidden-diff  = 0
Verdict         = PASS (no STOP condition triggered)
```

Proceed to commit, push, and PR per 0-9E §16.
