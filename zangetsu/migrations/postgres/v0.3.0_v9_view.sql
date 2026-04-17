-- V9 Sharpe Quant: filtered view over champion_pipeline.
CREATE OR REPLACE VIEW champion_pipeline_v9 AS
SELECT * FROM champion_pipeline
WHERE engine_hash IN ('zv5_v9', 'zv5_v71');
COMMENT ON VIEW champion_pipeline_v9 IS 'V9+V7.1. Migrate dashboard queries here. Drop v71 after V9 accumulates.';
