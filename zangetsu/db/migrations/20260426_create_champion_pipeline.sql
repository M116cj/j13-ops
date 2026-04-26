-- =====================================================================
-- Migration: 20260426_create_champion_pipeline.sql
-- Order:    0-9V-A13-CHAMPION-PIPELINE-SCHEMA
-- Purpose:  Restore a backwards-compatible 'champion_pipeline' relation
--           that v0.7.1_governance.sql renamed away on 2026-04-20.
--           Implemented as a non-destructive VIEW over champion_pipeline_fresh
--           per arena23_orchestrator.py:336 design intent.
-- Idempotency: uses CREATE OR REPLACE VIEW (safe to run repeatedly).
-- Safety: no removal of tables, no row removal, no destructive schema change.
-- =====================================================================

CREATE OR REPLACE VIEW public.champion_pipeline AS
SELECT * FROM public.champion_pipeline_fresh;

COMMENT ON VIEW public.champion_pipeline IS
    'Backwards-compatibility VIEW for downstream readers (e.g. arena13_feedback) '
    'that reference the legacy table name. The authoritative source is '
    'champion_pipeline_fresh; this VIEW is a transparent SELECT * alias. '
    'Created by 0-9V-A13-CHAMPION-PIPELINE-SCHEMA on 2026-04-26.';
