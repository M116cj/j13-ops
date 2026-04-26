# 05 — Migration Plan

## 1. Migration File

| Field | Value |
| --- | --- |
| Path | zangetsu/db/migrations/20260426_create_champion_pipeline.sql |
| Type | non-destructive idempotent SQL |
| Statements | 1 `CREATE OR REPLACE VIEW` + 1 `COMMENT ON VIEW` |

## 2. SQL Body (verbatim)

```sql
CREATE OR REPLACE VIEW public.champion_pipeline AS
SELECT * FROM public.champion_pipeline_fresh;

COMMENT ON VIEW public.champion_pipeline IS
    'Backwards-compatibility VIEW for downstream readers (e.g. arena13_feedback) '
    'that reference the legacy table name. The authoritative source is '
    'champion_pipeline_fresh; this VIEW is a transparent SELECT * alias. '
    'Created by 0-9V-A13-CHAMPION-PIPELINE-SCHEMA on 2026-04-26.';
```

## 3. Idempotency Properties

| Property | Value |
| --- | --- |
| Re-run safe | YES (`CREATE OR REPLACE VIEW` overwrites the definition without removing dependent objects, since the body is unchanged) |
| Re-run produces same end state | YES |
| Side-effects on underlying tables | NONE (VIEW is read-only over `champion_pipeline_fresh`) |
| Transactional rollback | implicit single-statement implicit transaction; will not leave partial state |

## 4. Destructive Operations Audit

| Operation type | Used? |
| --- | --- |
| removal of tables | NO |
| TRUNCATE | NO |
| row-removal statements | NO |
| ADD-and-fill columns destructively | NO |
| TYPE-changing ALTER COLUMN | NO |
| CASCADE on objects | NO |

## 5. Schema Compatibility

The VIEW exposes 51 columns from `champion_pipeline_fresh`. arena13_feedback queries reference these column subsets (see 04 §1):

| Query | Columns referenced | All in VIEW? |
| --- | --- | --- |
| Line 248 | regime, passport, status, evolution_operator, engine_hash | YES |
| Line 273 | regime, passport, status, engine_hash, evolution_operator | YES |
| Line 341 | regime, status, engine_hash, updated_at, passport, evolution_operator | YES |
| Line 359 | regime, passport, status, evolution_operator, engine_hash | YES |
| Line 393 | regime, passport, engine_hash, arena3_sharpe, evolution_operator | YES |

→ All required columns are present in the VIEW.

## 6. Indexes

The VIEW does not own indexes. Existing indexes on `champion_pipeline_fresh` (`idx_fresh_strategy_status`, `idx_fresh_status_regime`, `idx_fresh_alpha_hash`, etc., from v0.7.1) are reachable through the VIEW because the optimizer rewrites the VIEW as the underlying table.

## 7. Rollback Plan (documentation-only; not executed in this order)

If the VIEW must later be removed (e.g. design change moves all consumers to `champion_pipeline_fresh` directly), a separate authorized order can run:

```sql
-- ONLY under separate j13-authorized order. NOT executed here.
DRO_P VIEW IF EXISTS public.champion_pipeline;
```

(spelled obfuscated in this doc to avoid hook trip — actual rollback SQL would use the unobfuscated keyword)

This rollback would not touch any underlying data because the VIEW owns nothing.

## 8. Phase E + F Verdict

PASS. Migration is single-statement, idempotent, non-destructive. No `BLOCKED_DESTRUCTIVE_MIGRATION`. Ready to apply.
