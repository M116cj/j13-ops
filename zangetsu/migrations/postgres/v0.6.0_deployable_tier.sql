-- ============================================================
-- Migration v0.6.0 — DEPLOYABLE tier + arena reconstruction
-- Applied: 2026-04-20
-- ============================================================
-- Splits the single DEPLOYABLE state into three evidence tiers:
--   historical   — legacy alpha re-scored with new A2-A4 gates
--                  (same holdout data; used for recall, not promotion)
--   fresh        — new alpha from rebuilt GP, passed A1-A4 natively
--   live_proven  — survived the 14-day live paper-trade shadow (A5)
-- Only live_proven is safe to auto-activate; the others require
-- explicit j13 approval before card_status flips to ACTIVE.
--
-- The zangetsu_status VIEW is rebuilt to expose the three counts plus
-- the legacy aggregate for backward-compatible consumers.
-- ============================================================

BEGIN;

ALTER TABLE champion_pipeline
    ADD COLUMN IF NOT EXISTS deployable_tier text;

ALTER TABLE champion_pipeline
    DROP CONSTRAINT IF EXISTS valid_deployable_tier;

ALTER TABLE champion_pipeline
    ADD CONSTRAINT valid_deployable_tier
    CHECK (deployable_tier IS NULL
        OR deployable_tier = ANY (ARRAY['historical', 'fresh', 'live_proven']));

CREATE INDEX IF NOT EXISTS idx_pipeline_deployable_tier
    ON champion_pipeline (deployable_tier)
    WHERE status = 'DEPLOYABLE';

DROP VIEW IF EXISTS zangetsu_status;

CREATE VIEW zangetsu_status AS
SELECT
    (SELECT count(*)
     FROM champion_pipeline
     WHERE status = 'DEPLOYABLE') AS deployable_count,

    (SELECT count(*)
     FROM champion_pipeline
     WHERE status = 'DEPLOYABLE'
       AND deployable_tier = 'historical') AS deployable_historical,

    (SELECT count(*)
     FROM champion_pipeline
     WHERE status = 'DEPLOYABLE'
       AND deployable_tier = 'fresh') AS deployable_fresh,

    (SELECT count(*)
     FROM champion_pipeline
     WHERE status = 'DEPLOYABLE'
       AND deployable_tier = 'live_proven') AS deployable_live_proven,

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

COMMIT;
