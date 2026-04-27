# 06 — Controlled Diff Report

**TEAM ORDER**: 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX
**Phase**: 6 — Governance / Controlled-Diff Verification
**Subagent**: governance-verifier
**Repo**: `/Users/a13/dev/j13-ops` @ `main` `0370b3e` (uncommitted patch applied)
**Date**: 2026-04-27

## 1. Diff Inventory

`git status --short`:
```
 M zangetsu/services/arena_pipeline.py
?? docs/recovery/20260424-mod-7/0-9x-arena-batch-metrics-accounting-fix/
?? zangetsu/tests/test_arena_batch_metrics_accounting.py
```

`git diff --stat`:
```
zangetsu/services/arena_pipeline.py | 81 ++++++++++++++++++++++++++++++++------
1 file changed, 68 insertions(+), 13 deletions(-)
```

| Path | Status | Classification |
|------|--------|---------------|
| `zangetsu/services/arena_pipeline.py` | modified | EXPLAINED_TELEMETRY_EMITTER_ONLY |
| `zangetsu/tests/test_arena_batch_metrics_accounting.py` | new (200 LOC) | EXPLAINED_TEST_ONLY |
| `docs/recovery/20260424-mod-7/0-9x-arena-batch-metrics-accounting-fix/` | new (00–05 + this 06) | EXPLAINED_DOCS_ONLY |

No other source / config / script files changed. `git diff --stat zangetsu/ scripts/` reports only `arena_pipeline.py`.

## 2. arena_pipeline.py change summary

- **Helper added**: `_compute_a1_reject_deltas()` — pure function — confirmed in diff.
- **State added**: `_A1_REJECT_STATS_KEYS: tuple[str, ...]`, `_A1_PREV_REJECT_STATS_SNAPSHOT: dict[str, int]` — confirmed in diff.
- **Emitter modified**: `_emit_a1_batch_metrics_from_stats_safe()` — refactored to consume per-round deltas via `_compute_a1_reject_deltas()` and update snapshot.
- **Validator increment lines unchanged**: Only diff-changed `^[+-]` line containing `stats["reject_` is a comment-text fix (line 262: `# Map stats["reject_*"]` → `# stats["reject_*"]`). All 9 increment sites still present at current lines 1030, 1043, 1075, 1094, 1103, 1106, 1109, 1113, 1121 (shifted from spec'd 975…1066 by insertions above; spec lines noted to be approximate). No `stats["reject_..."] += 1` line appears as +/- in diff.

## 3. Forbidden-file check

`git diff --stat zangetsu/services/arena_gates.py zangetsu/services/arena_rejection_taxonomy.py zangetsu/config/settings.py`: **empty output** — none modified.
`zangetsu/services/admission_validator.py`: **does not exist in repo** — N/A.

## 4. A2_MIN_TRADES current value

| File | Line | Value |
|------|------|-------|
| `zangetsu/services/arena_gates.py` | 48 | `A2_MIN_TRADES: int = 25` |
| `zangetsu/config/settings.py` | 29 | `ARENA2_MIN_TRADES: int = 25` (Patch H1 alignment) |

Unchanged — PASS.

## 5. alpha_zoo no-db-write status

`zangetsu/scripts/alpha_zoo_injection.py`:
- L86: defense-in-depth ladder doc.
- L139–157: `--no-db-write` hard-block + default-deny + `--confirm-write` precondition gate.
- L237: `--no-db-write` default `True`.
- L241: `--confirm-write` default `False`.

Defaults intact — PASS.

## 6. Apply path matches (classification)

`grep -RnE "APPLY|apply_budget|runtime-switchable" zangetsu` → 8 matches:

| Match | Classification |
|-------|----------------|
| `zangetsu/tools/sparse_canary_readiness_check.py:115 "apply_budget"` | pre-existing readiness-check string literal (not new apply path) |
| `zangetsu/tests/test_generation_profile_identity_and_scoring.py:409 "apply_budget"` | pre-existing test fixture (test scope) |
| `zangetsu/tests/test_sparse_canary_observer.py:694–695 mode == "APPLY"` | **forbidden-list assertion** (test asserts no APPLY paths) |
| `zangetsu/docs/decisions/20260422-r2-hotfix.md:19 APPLY WITH CONDITIONS` | pre-existing doc prose |
| 2 `__pycache__/*.pyc` binary | compiled cache, no source change |

No new apply path / runtime-switchable budget — PASS.

## 7. Per-Dimension Classification Table

| Dimension | Verdict | Evidence |
|-----------|--------|----------|
| arena_pipeline.py = EXPLAINED_TELEMETRY_EMITTER_ONLY | PASS | helper+state+emitter only, validator increments unchanged |
| New test file = EXPLAINED_TEST_ONLY | PASS | `zangetsu/tests/test_arena_batch_metrics_accounting.py` (200 LOC) |
| Docs evidence = EXPLAINED_DOCS_ONLY | PASS | 00–06 under `docs/recovery/20260424-mod-7/0-9x-…/` |
| arena_gates.py / arena_rejection_taxonomy.py / config/settings.py changed? | PASS (none changed) | empty `git diff --stat` |
| A2_MIN_TRADES unchanged at 25 | PASS | arena_gates.py:48 = 25 |
| alpha_zoo_injection.py defaults intact | PASS | L237 `--no-db-write` default True; L241 `--confirm-write` default False |
| No apply path / runtime-switchable budget added | PASS | all matches pre-existing test forbidden-list / doc prose |
| No validator threshold / pass-fail change | PASS | no diff in arena_gates.py / settings.py |
| No Arena pass/fail / champion promotion / deployable_count change | PASS | no diff in pipeline pass-decision logic |
| No execution / capital / risk / DB guard change | PASS | no diff in scripts/, no diff in alpha_zoo_injection.py |
| Validator stats[reject_*] += 1 increment sites preserved | PASS | 9 sites present at current lines 1030/1043/1075/1094/1103/1106/1109/1113/1121, none in diff as +/- |

## 8. Final Verdict

**CONTROLLED_DIFF_PASS**
