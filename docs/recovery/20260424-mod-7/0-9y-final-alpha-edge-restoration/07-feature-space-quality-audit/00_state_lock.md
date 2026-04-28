# 07 Feature Space Quality Audit — State Lock

- **Audit date**: 2026-04-28
- **Repo**: `/Users/a13/dev/j13-ops`
- **Branch**: `main`
- **HEAD**: `348eeb7 docs(zangetsu/0-9y-d): strategic redesign decision (#60) (2026-04-28 12:33:05 +0800)`
- **Auditor role**: SUBAGENT for TEAM ORDER `0-9Y-FS1-FEATURE-SPACE-QUALITY-AUDIT` (master `0-9Y-FINAL`)
- **Mission**: read-only audit of formula / search-space diversity to decide whether the upcoming horizon-redesign test will be informative on the current population.

## Code paths inspected (read-only)

- `zangetsu/engine/components/alpha_engine.py` — DEAP primitive set, MAX_DEPTH, INDICATOR_NAMES, PERIODS
- `zangetsu/engine/components/alpha_primitives.py` — operator definitions
- `zangetsu/engine/components/indicator.py` — full indicator catalog (`INDICATOR_CATEGORIES`)
- `zangetsu/engine/components/pset_lean_config.py` — lean-mode terminal subset
- `zangetsu/services/arena_pipeline.py` — single-symbol-artifact gate (combined Sharpe at A2)

The spec requested `alpha_grammar.py`, `gp_operators.py`, `feature_*.py`. **None of those filenames exist** in the repo. Grammar / operators are inlined in `alpha_engine._build_primitive_set`; no `feature_*.py` modules. Audit substituted the actual files listed above.

## Data sources

- **Postgres** (Alaya `deploy-postgres-1`):
  - `champion_pipeline_staging` — 184 rows, 89 distinct `alpha_hash`
  - `champion_pipeline` — 89 rows, 89 distinct
  - `champion_pipeline_fresh` — 89 rows, 89 distinct
- **Engine batch snapshot**: `/tmp/c_batches_snapshot.jsonl` — 106 batches (`aggregate_metrics` events)

## Sample / population characteristics

- 100% of staging rows: `evolution_operator='random'`, `generation=0`, `status='ARENA1_COMPLETE'`, `deployable_tier=NULL`
- 100% of staging rows: `passport.arena1.source='manual_cold_start.v1'` — i.e. **all 89 unique formulas are hand-seeded**, not GP-evolved
- 0 rows have arena2/arena3/arena4 outcomes recorded — the population has not yet faced any single-symbol-artifact gate
- Engine batches: 14 symbols × 2 lanes × 3 regimes × 2 generation profiles, 10 alphas/batch, 1060 GP candidates evaluated, 0 promoted into staging

## What this lock guarantees

- All counts below derive from the live DB at the timestamp shown
- Code references (operator set, indicator set, MAX_DEPTH=6) reflect HEAD `348eeb7`
- No file under `zangetsu/` was modified by this audit
- Output written exclusively to `docs/recovery/20260424-mod-7/.../07-feature-space-quality-audit/`
