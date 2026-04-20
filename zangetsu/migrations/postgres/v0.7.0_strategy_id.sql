-- ============================================================
-- Migration v0.7.0 — Zangetsu engine split + J01 / J02 strategies
-- Applied: 2026-04-20
-- ============================================================
-- Zangetsu becomes a neutral training engine; strategy-specific
-- fitness and threshold bundles live in separate projects (j01 =
-- harmonic K=2, j02 = ICIR K=5 + DSR). The champion_pipeline table
-- gains a strategy_id so the same DB can host multiple strategies
-- without collision. Each strategy gets its own §17.1 VIEW.
-- ============================================================

BEGIN;

ALTER TABLE champion_pipeline
    ADD COLUMN IF NOT EXISTS strategy_id text NOT NULL DEFAULT 'j01';

ALTER TABLE champion_pipeline
    DROP CONSTRAINT IF EXISTS valid_strategy_id;

ALTER TABLE champion_pipeline
    ADD CONSTRAINT valid_strategy_id
    CHECK (strategy_id = ANY (ARRAY['j01', 'j02', 'zangetsu_legacy']));

-- Backfill: legacy rows (V9 engine hash) get zangetsu_legacy,
-- V10 rows default to j01 (they were produced pre-split under what
-- is now the harmonic track conceptually).
UPDATE champion_pipeline
   SET strategy_id = 'zangetsu_legacy'
 WHERE engine_hash IS NOT NULL
   AND engine_hash NOT LIKE 'zv5_v10%'
   AND strategy_id = 'j01';

CREATE INDEX IF NOT EXISTS idx_pipeline_strategy_status
    ON champion_pipeline (strategy_id, status);

CREATE INDEX IF NOT EXISTS idx_pipeline_strategy_tier
    ON champion_pipeline (strategy_id, deployable_tier)
    WHERE status = 'DEPLOYABLE';

-- ============================================================
-- Engine-level rollup VIEW (aggregates across all strategies)
-- ============================================================
DROP VIEW IF EXISTS zangetsu_engine_status;

CREATE VIEW zangetsu_engine_status AS
SELECT
    strategy_id,
    (SELECT count(*) FROM champion_pipeline cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.status = 'DEPLOYABLE')
     AS deployable_count,
    (SELECT count(*) FROM champion_pipeline cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.status = 'DEPLOYABLE'
       AND cp2.deployable_tier = 'historical')
     AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.status = 'DEPLOYABLE'
       AND cp2.deployable_tier = 'fresh')
     AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.status = 'DEPLOYABLE'
       AND cp2.deployable_tier = 'live_proven')
     AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.card_status = 'ACTIVE')
     AS active_count,
    (SELECT count(*) FROM champion_pipeline cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.status = 'CANDIDATE')
     AS candidate_count,
    (SELECT count(*) FROM champion_pipeline cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.created_at > now() - INTERVAL '1 hour')
     AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(cp2.created_at)) / 3600::numeric
     FROM champion_pipeline cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at_age_h,
    now() AS ts
FROM (SELECT DISTINCT strategy_id FROM champion_pipeline) cp;

-- ============================================================
-- J01 (harmonic K=2) single-truth VIEW
-- ============================================================
DROP VIEW IF EXISTS j01_status;

CREATE VIEW j01_status AS
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

-- ============================================================
-- J02 (ICIR K=5) single-truth VIEW
-- ============================================================
DROP VIEW IF EXISTS j02_status;

CREATE VIEW j02_status AS
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

-- ============================================================
-- zangetsu_status (backward-compat: aggregates across strategies)
-- Kept so existing callers don't break until migration lands.
-- ============================================================
DROP VIEW IF EXISTS zangetsu_status;

CREATE VIEW zangetsu_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline
     WHERE status = 'DEPLOYABLE')
     AS deployable_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE status = 'DEPLOYABLE' AND deployable_tier = 'historical')
     AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline
     WHERE status = 'DEPLOYABLE' AND deployable_tier = 'fresh')
     AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline
     WHERE status = 'DEPLOYABLE' AND deployable_tier = 'live_proven')
     AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline
     WHERE status = 'DEPLOYABLE' AND engine_hash ~ 'zv5_v10')
     AS deployable_v10_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE card_status = 'ACTIVE')
     AS active_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE status = 'CANDIDATE')
     AS candidate_count,
    (SELECT count(*) FROM champion_pipeline
     WHERE created_at > now() - INTERVAL '1 hour')
     AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric
     FROM champion_pipeline
     WHERE status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at_age_h,
    (SELECT max(created_at)
     FROM champion_pipeline
     WHERE status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at,
    now() AS ts;

COMMIT;
