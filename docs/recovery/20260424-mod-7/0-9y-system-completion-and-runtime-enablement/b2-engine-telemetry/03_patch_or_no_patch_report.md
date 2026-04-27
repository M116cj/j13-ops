# 03 — Patch / No-Patch Report (Subprogram B2)

## Decision: NO source patch in this PR

This subprogram concludes with the verdict `COMPLETE_ENGINE_JSONL_CANONICAL_DB_TELEMETRY_OBSOLETE`. The decision is implemented via documentation only — the codebase is not modified.

## What this PR does NOT do

| Action | Status |
|---|---|
| modify `arena_pipeline.py` flush gating | NOT DONE |
| add increment sites for the 10 dead counters | NOT DONE |
| retire `engine_telemetry` table or constraint | NOT DONE |
| retire `fresh_pool_process_health` view | NOT DONE |
| migrate JSONL → DB writer | NOT DONE |
| change validation, thresholds, A2_MIN_TRADES, alpha generation, Arena gates | NOT DONE |

All of the above are explicitly **forbidden** or **out of scope** for B2.

## What this PR DOES

| Action | Status |
|---|---|
| Document the flush-gating root cause | DONE (02_root_cause.md) |
| Document the counter-wiring gap | DONE (02_root_cause.md) |
| Document JSONL as canonical observability | DONE (02_root_cause.md) |
| Catalogue path-forward sub-orders for future work | DONE |
| Confirm 0-9Y program is not blocked by this gap | DONE (next: Subprogram B3, then C using JSONL stream) |

## Rationale for no-patch

1. **JSONL is a strict superset.** B1 (PR #55) extended `arena_batch_metrics` with 15 numeric + 21 availability flags. Together with the existing entered/passed/rejected/skipped/distribution semantics, JSONL covers everything that engine_telemetry was originally designed to expose, and more.

2. **Master order accepts this verdict.** The order's verdict options explicitly include `COMPLETE_ENGINE_JSONL_CANONICAL_DB_TELEMETRY_OBSOLETE`. The classification is honest given the analysis.

3. **Risk minimization.** Subprograms B3 (Calcifer NULL-safety) and C (economic edge decomposition using B1) are higher-priority for unblocking the deployable flow. Spending B2's risk budget on a flush-gating patch that produces 12 rows of zeros every 5 min is poor return.

4. **No runtime behavior change.** This PR is docs-only. Forbidden ops audit will be 0.

## What downstream orders should know

- `engine_telemetry` table and `fresh_pool_process_health` view exist but contain no rows.
- Do not assume process-health metrics are queryable from DB; query `zangetsu/logs/engine.jsonl` instead.
- The JSONL stream's `arena_batch_metrics` event is the canonical per-batch observability surface.
- The B2A / B2B / B2-RETIRE follow-up sub-orders (catalogued in 02_root_cause.md) are optional improvements; none are blocking.
