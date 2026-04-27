# 07 — Controlled Diff Report

**Order**: 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS Phase 7
**Subagent**: governance-verifier
**Repo**: `/Users/a13/dev/j13-ops` `main` @ `b1615c67` (`docs(zangetsu): finalize cold boot recovery evidence (#47)`)
**Mode**: READ-ONLY

## 1. Diff summary

| File / Path | Status | Classification |
|---|---|---|
| `docs/recovery/20260424-mod-7/0-9x-a1-reject-distribution-shift-diagnosis/00_state_lock.md` | untracked (new) | EXPLAINED_DOCS_ONLY |
| `…/01_live_distribution_snapshot.md` | untracked (new) | EXPLAINED_DOCS_ONLY |
| `…/02_reject_taxonomy_map.md` | untracked (new) | EXPLAINED_DOCS_ONLY |
| `…/03_code_path_trace.md` | untracked (new) | EXPLAINED_DOCS_ONLY |
| `…/04_unknown_reject_root_cause.md` | untracked (new) | EXPLAINED_DOCS_ONLY |
| `…/05_counter_inconsistency_root_cause.md` | untracked (new) | EXPLAINED_DOCS_ONLY |
| `…/06_regression_window_analysis.md` | untracked (new) | EXPLAINED_DOCS_ONLY |
| `zangetsu/`, `scripts/` | unchanged | N/A (no diff vs HEAD) |
| `/tmp/0_9x_a1_shift_*_check.txt` | NOT_COMMITTED | scratch only |

`git diff --stat HEAD` → empty. `git diff --cached --stat` → empty. Only untracked artefacts are the 7 evidence markdowns under the order's evidence dir.

## 2. A2_MIN_TRADES value

- `zangetsu/services/arena_gates.py:48` → `A2_MIN_TRADES: int = 25`
- `zangetsu/services/arena_gates.py:54` → `if n < A2_MIN_TRADES:`
- `zangetsu/config/settings.py:29` → `ARENA2_MIN_TRADES: int = 25` (Patch H1 alignment)

Matches expected baseline (25). No change introduced by this order.

## 3. alpha_zoo no-db-write default

`zangetsu/scripts/alpha_zoo_injection.py`:
- `:139–143` `--no-db-write` hard-block default-on
- `:147–153` default-deny unless `--confirm-write`
- `:237` `parser.add_argument("--no-db-write", action="store_true", default=True)`
- `:241` `parser.add_argument("--confirm-write", action="store_true", default=False)`

Default = no-db-write True, confirm-write False. Unchanged.

## 4. Apply path scan

`grep -RnE "APPLY|apply_budget|runtime-switchable" zangetsu` → 8 matches, all pre-existing, all benign:

| Match | Classification |
|---|---|
| `zangetsu/tools/sparse_canary_readiness_check.py:115` `"apply_budget"` (forbidden-list literal) | test-file forbidden-list literal |
| `zangetsu/tests/test_generation_profile_identity_and_scoring.py:409` `"apply_budget"` (forbidden-list literal) | test-file forbidden-list literal |
| `zangetsu/tests/test_sparse_canary_observer.py:694–695` (assert `mode == "APPLY"` NOT in src) | test enforces absence of apply path |
| `zangetsu/docs/decisions/20260422-r2-hotfix.md:19` "APPLY WITH CONDITIONS" | doc prose, not code |
| 2× `__pycache__` binary hits | compiled artefacts of the above test files |

No real APPLY / apply_budget / runtime-switchable budget code path added by this order.

## 5. Per-dimension classification

| Dimension | Result |
|---|---|
| docs evidence = EXPLAINED_DOCS_ONLY | PASS |
| /tmp parser scripts NOT_COMMITTED | PASS |
| read-only diagnostic script EXPLAINED_DIAGNOSTIC_ONLY | N/A (none committed) |
| A2_MIN_TRADES unchanged at 25 | PASS |
| alpha_zoo_injection no-db-write default | PASS |
| no apply path / runtime-switchable budget added | PASS |
| no Arena pass/fail semantics change | PASS |
| no champion promotion / deployable_count semantics change | PASS |
| no execution / capital / risk change | PASS |
| no DB guard weakening | PASS |

## 6. Verdict

**CONTROLLED_DIFF_PASS** — read-only diagnosis, only 7 evidence docs added (untracked), zero source / test / config / runtime mutation. All forbidden-token scans confirm no behaviour-shifting change introduced by this order.
