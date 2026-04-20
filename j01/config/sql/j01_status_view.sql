-- ============================================================
-- j01_status — §17.1 single-truth VIEW for J01 strategy
-- ============================================================
-- Canonical source of "is J01 producing DEPLOYABLE alphas?".
-- Every hook / skill / bot / version-bump check must read through
-- this VIEW. Inline count queries against champion_pipeline filtered
-- by strategy_id='j01' are rejected at CI level.
--
-- Keep this file in sync with the live DB definition. When the VIEW
-- changes, emit a new migration under `zangetsu/migrations/postgres/`
-- (engine owns schema); never ALTER VIEW in place.
-- ============================================================

CREATE OR REPLACE VIEW j01_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE')
     AS deployable_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'historical')
     AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'fresh')
     AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'live_proven')
     AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j01' AND card_status = 'ACTIVE')
     AS active_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j01' AND status = 'CANDIDATE')
     AS candidate_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j01' AND created_at > now() - INTERVAL '1 hour')
     AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric
     FROM champion_pipeline
     WHERE strategy_id = 'j01'
       AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at_age_h,
    (SELECT max(created_at)
     FROM champion_pipeline
     WHERE strategy_id = 'j01'
       AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at,
    now() AS ts;
