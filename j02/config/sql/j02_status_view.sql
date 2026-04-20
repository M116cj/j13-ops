-- ============================================================
-- j02_status — §17.1 single-truth VIEW for J02 strategy
-- ============================================================
CREATE OR REPLACE VIEW j02_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE')
     AS deployable_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'historical')
     AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'fresh')
     AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'live_proven')
     AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j02' AND card_status = 'ACTIVE')
     AS active_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j02' AND status = 'CANDIDATE')
     AS candidate_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE strategy_id = 'j02' AND created_at > now() - INTERVAL '1 hour')
     AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric
     FROM champion_pipeline
     WHERE strategy_id = 'j02'
       AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at_age_h,
    (SELECT max(created_at)
     FROM champion_pipeline
     WHERE strategy_id = 'j02'
       AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at,
    now() AS ts;
