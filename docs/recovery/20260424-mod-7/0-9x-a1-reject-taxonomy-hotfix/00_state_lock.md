# 00 — State Lock

Order: TEAM ORDER 0-9X-A1-REJECT-TAXONOMY-HOTFIX
Phase: 0
Captured (UTC): 2026-04-27T14:35Z
Captured-by: Claude Lead

## Repo state

| Field | Mac | Alaya |
|---|---|---|
| HEAD | `9f4bf8a44a05dd3dd68f371b8806e8d1195a3021` | `9f4bf8a44a05dd3dd68f371b8806e8d1195a3021` |
| Branch | `main` | `main` |
| origin/main | `9f4bf8a44a05dd3dd68f371b8806e8d1195a3021` | (parity) |
| Source dirty files | 1 (engine.jsonl.1, runtime artifact) | 1 (same) |

Repo is **clean of source modifications** at state-lock time. The single dirty file on Alaya is `zangetsu/logs/engine.jsonl.1` which is a live runtime log being rotated by the engine.

HEAD subject: `docs(zangetsu): diagnose A1 reject distribution shift (#48)` — final report from the previous diagnosis order.

## Worker process state (Alaya)

`workers_alive=6` ✓ (4× `arena_pipeline.py` + 1× `arena23_orchestrator.py` + 1× `arena45_orchestrator.py`).

## Lockfile state (`/tmp/zangetsu/`)

`lockfiles=6` ✓ — all six target lockfiles present.

## DB sanity (v0.7.1)

Connection via `docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu`:

| Object | Count |
|---|---|
| `champion_pipeline` | 89 |
| `champion_pipeline_staging` | 184 |
| `champion_pipeline_fresh` | 89 |

DB schema PASS. Same v0.7.1 contract as previous orders.

## Known root cause (carried forward from previous order)

`UNKNOWN_REJECT_TAXONOMY_MAPPING_BUG` — PR #43 added `reject_train_neg_pnl` and `reject_combined_sharpe_low` to the A1 emitter walk at `arena_pipeline.py:206-209` but did not add corresponding `RAW_TO_REASON` entries. `classify()` falls through and returns `UNKNOWN_REJECT` for both, producing the ~50 % UNKNOWN_REJECT bucket in `arena_batch_metrics.reject_reason_distribution`.

## Phase 0 classification

| Dimension | Status |
|---|---|
| HEAD status | `9f4bf8a` matches origin/main |
| Branch status | on `main`, parity with origin |
| Repo clean / dirty | **clean** of source modifications (1 runtime log artifact) |
| Mac / Alaya sync | **in sync** (same SHA on both) |
| Runtime process status | **6 / 6 alive** |
| Lockfile status | **6 / 6 present** |
| DB v0.7.1 sanity | **PASS** (3 critical objects visible with expected counts) |
| Known root cause | UNKNOWN_REJECT taxonomy mapping bug (this order's target) |

## STOP-condition evaluation

| STOP condition | Triggered? |
|---|---|
| repo dirty with unexplained source changes | NO |
| HEAD not equal to origin/main unexpectedly | NO |
| A1 runtime dead without known reason | NO |
| DATABASE_URL unavailable | NO — DB reached via `docker exec`; psql confirmed live |
| v0.7.1 DB objects missing | NO |

**No STOP. Proceed to Phase 1.**

## Q1 / Q2 / Q3 for this hotfix

- **Q1 Adversarial (5-dim)**:
  - Input boundary: 2 raw keys are well-defined Python string literals; classify() never raises.
  - Silent failure: existing `classify()` fallback returns `UNKNOWN_REJECT` for unknown keys, preserved by tests.
  - External dependency: pure in-memory dict, no DB / network / file-system change.
  - Concurrency: `RAW_TO_REASON` is module-level read-only constant; multi-worker safe.
  - Scope creep: only `arena_rejection_taxonomy.py` + `test_arena_rejection_taxonomy.py` modified; no `arena_pipeline.py` / validator change.
- **Q2 Structural**: existing 22 mappings unchanged; existing 30 taxonomy tests pass; UNKNOWN_REJECT fallback covered by new test.
- **Q3 Efficiency**: 2-line dict insertion + 5 small tests + 6 evidence docs. Per-task target ≤ 7 evidence files.
