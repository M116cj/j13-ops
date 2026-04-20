-- ============================================================
-- Rollback script for migration v0.7.1 (governance upgrade)
-- ============================================================
-- Use only if the v0.7.1_governance.sql migration fails or is
-- rejected after smoke test. Restores the pre-v0.7.1 state:
--   champion_legacy_archive -> champion_pipeline
--   (drops all new tables, VIEWs, functions, triggers)
-- ============================================================

BEGIN;

-- Drop new VIEWs first
DROP VIEW IF EXISTS fresh_pool_process_health;
DROP VIEW IF EXISTS fresh_pool_outcome_health;
DROP VIEW IF EXISTS zangetsu_status;
DROP VIEW IF EXISTS zangetsu_engine_status;
DROP VIEW IF EXISTS j02_status_archive;
DROP VIEW IF EXISTS j01_status_archive;
DROP VIEW IF EXISTS j02_status;
DROP VIEW IF EXISTS j01_status;

-- Drop new tables
DROP TABLE IF EXISTS engine_telemetry;
DROP TABLE IF EXISTS champion_pipeline_rejected;
DROP TABLE IF EXISTS champion_pipeline_staging;
DROP TABLE IF EXISTS champion_pipeline_fresh;

-- Drop new triggers + functions
DROP TRIGGER IF EXISTS fresh_insert_gated ON champion_pipeline_fresh;
DROP TRIGGER IF EXISTS archive_readonly_insert ON champion_legacy_archive;
DROP TRIGGER IF EXISTS archive_readonly_update ON champion_legacy_archive;
DROP TRIGGER IF EXISTS archive_readonly_delete ON champion_legacy_archive;
DROP FUNCTION IF EXISTS admission_validator(BIGINT);
DROP FUNCTION IF EXISTS fresh_insert_guard();
DROP FUNCTION IF EXISTS archive_readonly_trigger();

-- Rename archive back to champion_pipeline
ALTER TABLE champion_legacy_archive RENAME TO champion_pipeline;

-- Recreate v0.7.0 VIEWs (from migrations/postgres/v0.6.0_deployable_tier.sql
-- and v0.7.0_strategy_id.sql combined)
CREATE VIEW zangetsu_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline WHERE status = 'DEPLOYABLE') AS deployable_count,
    (SELECT count(*) FROM champion_pipeline WHERE status = 'DEPLOYABLE' AND deployable_tier = 'historical') AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline WHERE status = 'DEPLOYABLE' AND deployable_tier = 'fresh') AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline WHERE status = 'DEPLOYABLE' AND deployable_tier = 'live_proven') AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline WHERE status = 'DEPLOYABLE' AND engine_hash ~ 'zv5_v10') AS deployable_v10_count,
    (SELECT count(*) FROM champion_pipeline WHERE card_status = 'ACTIVE') AS active_count,
    (SELECT count(*) FROM champion_pipeline WHERE status = 'CANDIDATE') AS candidate_count,
    (SELECT count(*) FROM champion_pipeline WHERE created_at > now() - INTERVAL '1 hour') AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric
     FROM champion_pipeline WHERE status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE'])) AS last_live_at_age_h,
    (SELECT max(created_at) FROM champion_pipeline WHERE status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE'])) AS last_live_at,
    now() AS ts;

CREATE VIEW j01_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE') AS deployable_count,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE' AND deployable_tier = 'historical') AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE' AND deployable_tier = 'fresh') AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE' AND deployable_tier = 'live_proven') AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j01' AND card_status = 'ACTIVE') AS active_count,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j01' AND status = 'CANDIDATE') AS candidate_count,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j01' AND created_at > now() - INTERVAL '1 hour') AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric FROM champion_pipeline WHERE strategy_id = 'j01' AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE'])) AS last_live_at_age_h,
    (SELECT max(created_at) FROM champion_pipeline WHERE strategy_id = 'j01' AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE'])) AS last_live_at,
    now() AS ts;

CREATE VIEW j02_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE') AS deployable_count,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE' AND deployable_tier = 'historical') AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE' AND deployable_tier = 'fresh') AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE' AND deployable_tier = 'live_proven') AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j02' AND card_status = 'ACTIVE') AS active_count,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j02' AND status = 'CANDIDATE') AS candidate_count,
    (SELECT count(*) FROM champion_pipeline WHERE strategy_id = 'j02' AND created_at > now() - INTERVAL '1 hour') AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric FROM champion_pipeline WHERE strategy_id = 'j02' AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE'])) AS last_live_at_age_h,
    (SELECT max(created_at) FROM champion_pipeline WHERE strategy_id = 'j02' AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE'])) AS last_live_at,
    now() AS ts;

COMMIT;
