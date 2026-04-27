-- ============================================================
-- Bootstrap: pre-v0.4 → v0.4-compatible schema
-- Applied: 2026-04-27 (TEAM ORDER 0-9X-DB-MIGRATION-MULTI-STAGE)
-- ============================================================
-- The current `champion_pipeline` table is at 14-col bootstrap state
-- (id, indicator_hash, regime, status, passport, retry_count,
--  processing_started_at, engine_hash, created_at, updated_at,
--  is_active_card, accepting_new_entries, elo, quant_class).
--
-- Migrations v0.4_v2_constraints and v0.6_deployable_tier and v0.7.0
-- and v0.7.1 reference columns that pre-date v0.4 but are missing
-- from the live DB. This bootstrap adds those columns (all nullable
-- with safe defaults) so the subsequent migrations can apply.
--
-- Properties:
--   - schema-additive (no DROP, no RENAME)
--   - idempotent (IF NOT EXISTS)
--   - row-preserving (0 rows but 0 also after)
--   - version-explicit (this file)
--   - fully documented
-- ============================================================

BEGIN;

ALTER TABLE champion_pipeline
    ADD COLUMN IF NOT EXISTS alpha_hash text,
    ADD COLUMN IF NOT EXISTS n_indicators integer DEFAULT 1,
    ADD COLUMN IF NOT EXISTS arena1_score double precision,
    ADD COLUMN IF NOT EXISTS arena1_win_rate double precision,
    ADD COLUMN IF NOT EXISTS arena1_pnl double precision,
    ADD COLUMN IF NOT EXISTS arena1_n_trades integer,
    ADD COLUMN IF NOT EXISTS arena2_win_rate double precision,
    ADD COLUMN IF NOT EXISTS arena2_n_trades integer,
    ADD COLUMN IF NOT EXISTS arena3_sharpe double precision,
    ADD COLUMN IF NOT EXISTS arena3_expectancy double precision,
    ADD COLUMN IF NOT EXISTS arena3_pnl double precision,
    ADD COLUMN IF NOT EXISTS arena4_hell_wr double precision,
    ADD COLUMN IF NOT EXISTS arena4_variability double precision,
    ADD COLUMN IF NOT EXISTS elo_rating double precision DEFAULT 1200,
    ADD COLUMN IF NOT EXISTS elo_consecutive_first integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS card_status text DEFAULT 'INACTIVE',
    ADD COLUMN IF NOT EXISTS parent_hash text,
    ADD COLUMN IF NOT EXISTS generation integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS evolution_operator text DEFAULT 'random',
    ADD COLUMN IF NOT EXISTS arena1_completed_at timestamptz,
    ADD COLUMN IF NOT EXISTS arena2_completed_at timestamptz,
    ADD COLUMN IF NOT EXISTS arena3_completed_at timestamptz,
    ADD COLUMN IF NOT EXISTS arena4_completed_at timestamptz,
    ADD COLUMN IF NOT EXISTS arena5_last_tested timestamptz,
    ADD COLUMN IF NOT EXISTS family_id varchar(16),
    ADD COLUMN IF NOT EXISTS family_tag varchar(64),
    ADD COLUMN IF NOT EXISTS lease_until timestamptz,
    ADD COLUMN IF NOT EXISTS worker_id_str text;

-- Backfill n_indicators NOT NULL constraint readiness (safe since we set DEFAULT)
ALTER TABLE champion_pipeline
    ALTER COLUMN n_indicators SET DEFAULT 1;

-- Status CHECK constraint expansion (v0.7.1 will overwrite this)
-- For now, leave the existing status freedom alone.

COMMIT;
