# 04 — Controlled Diff Report (governance-verifier, Phase 5)

**TEAM ORDER**: 0-9X-A1-REJECT-TAXONOMY-HOTFIX
**Repo**: `/Users/a13/dev/j13-ops` on `main` @ `9f4bf8a`
**Mode**: READ-ONLY. No commit produced.

## 1. Diff Summary

| File | Status | Insertions / Deletions | Classification |
|---|---|---|---|
| `zangetsu/services/arena_rejection_taxonomy.py` | M (uncommitted) | +10 / -1 | EXPLAINED_TAXONOMY_ONLY |
| `zangetsu/tests/test_arena_rejection_taxonomy.py` | M (uncommitted) | +60 / -0 | EXPLAINED_TEST_ONLY |
| docs evidence (this file + bundle) | A | n/a | EXPLAINED_DOCS_ONLY |

`git diff --name-only` = exactly the two files above. `git diff --stat zangetsu/services/arena_pipeline.py zangetsu/services/arena_gates.py zangetsu/config/settings.py` returned **empty** — none of those files modified. No changes under `tests/`, `scripts/`, `bin/`, `Makefile`.

## 2. Exact Mappings Added (RAW_TO_REASON)

```python
"reject_train_neg_pnl":      RejectionReason.COST_NEGATIVE
"reject_combined_sharpe_low": RejectionReason.LOW_BACKTEST_SCORE
```

Plus 2 explanatory comment blocks (PR #43 family rationale) and 1 stale-line-number fix (`arena_pipeline.py:517` → `:707`). One existing line modified is comment text only — no semantic change to any prior mapping.

## 3. A2_MIN_TRADES Current Value

- `zangetsu/services/arena_gates.py:48` → `A2_MIN_TRADES: int = 25`
- `zangetsu/config/settings.py:29` → `ARENA2_MIN_TRADES: int = 25`
- Unchanged by this hotfix. **PASS**.

## 4. alpha_zoo_injection.py Default-Deny Status

- `zangetsu/scripts/alpha_zoo_injection.py:237` → `--no-db-write` `default=True`
- `zangetsu/scripts/alpha_zoo_injection.py:241` → `--confirm-write` `default=False`
- Defense-in-depth ladder intact (`alpha_zoo_injection.py:86`). Not modified. **PASS**.

## 5. Apply-Path Match Classification

| Match | File:line | Type |
|---|---|---|
| `apply_budget` | `zangetsu/tools/sparse_canary_readiness_check.py:115` | pre-existing forbidden-list literal (readiness check) — not new |
| `apply_budget` | `zangetsu/tests/test_generation_profile_identity_and_scoring.py:409` | pre-existing forbidden-list literal in test — not new |
| `'mode == "APPLY"'` (string literal) | `zangetsu/tests/test_sparse_canary_observer.py:694-695` | pre-existing **negative** assertion (`not in src`) — guards against apply path appearing — not new |
| `APPLY WITH CONDITIONS` | `zangetsu/docs/decisions/20260422-r2-hotfix.md:19` | pre-existing decision-record prose — not new |

No `runtime-switchable`, no real APPLY branch, no `apply_budget` constant added. **PASS**.

## 6. Per-Dimension Classification

| Dimension | Result |
|---|---|
| `arena_rejection_taxonomy.py` = mapping additions + comments only | **PASS** (EXPLAINED_TAXONOMY_ONLY) |
| Test file = 5 new tests appended; no existing test modified semantically | **PASS** (EXPLAINED_TEST_ONLY) |
| Docs evidence only | **PASS** (EXPLAINED_DOCS_ONLY) |
| `arena_pipeline.py` changed? | **N/A — not changed** (STOP not triggered) |
| `arena_gates.py` / `config/settings.py` changed? | **N/A — not changed** (STOP not triggered) |
| A2_MIN_TRADES unchanged at 25 | **PASS** |
| `alpha_zoo_injection.py` defaults intact (`--no-db-write` default=True, `--confirm-write` default=False) | **PASS** |
| No apply path / runtime-switchable budget added | **PASS** |
| No validator threshold / pass-fail change | **PASS** |
| No Arena pass/fail semantics / champion promotion / `deployable_count` change | **PASS** |
| No execution / capital / risk / DB guard change | **PASS** |

## 7. Verdict

**CONTROLLED_DIFF_PASS**
