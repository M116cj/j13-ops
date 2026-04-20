-- ============================================================
-- zangetsu_status — §17.1 Single Truth VIEW
-- ============================================================
-- Canonical source of "is Zangetsu producing DEPLOYABLE alphas?"
-- Every hook / skill / bot / version-bump check MUST read through
-- this VIEW. Inline count queries against champion_pipeline are
-- rejected at CI level.
--
-- Keep this file in sync with the live DB definition. When you edit
-- the VIEW, emit a new migration in migrations/postgres/ that drops
-- and recreates the VIEW; never ALTER VIEW in place.
-- ============================================================

CREATE OR REPLACE VIEW zangetsu_status AS
SELECT
    (SELECT count(*)
     FROM champion_pipeline
     WHERE status = 'DEPLOYABLE') AS deployable_count,

    (SELECT count(*)
     FROM champion_pipeline
     WHERE status = 'DEPLOYABLE'
       AND engine_hash ~ 'zv5_v10') AS deployable_v10_count,

    (SELECT count(*)
     FROM champion_pipeline
     WHERE card_status = 'ACTIVE') AS active_count,

    (SELECT count(*)
     FROM champion_pipeline
     WHERE status = 'CANDIDATE') AS candidate_count,

    (SELECT count(*)
     FROM champion_pipeline
     WHERE created_at > now() - INTERVAL '1 hour') AS champions_last_1h,

    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric
     FROM champion_pipeline
     WHERE status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE'])) AS last_live_at_age_h,

    (SELECT max(created_at)
     FROM champion_pipeline
     WHERE status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE'])) AS last_live_at,

    now() AS ts;
