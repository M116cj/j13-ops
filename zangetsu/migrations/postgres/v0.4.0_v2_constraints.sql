-- V2 fix: schema constraints to prevent bogus INSERT pollution
-- Agent-3 adversarial finding: champion_pipeline had only PKEY + status CHECKs
-- Adds: UNIQUE on (regime, indicator_hash) for V9 rows; numeric bounds; positive trade counts

-- UNIQUE only where alpha_hash IS NULL (V9 indicator-combo rows)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_regime_indicator_hash_v9
  ON champion_pipeline (regime, indicator_hash)
  WHERE alpha_hash IS NULL AND status != 'LEGACY';

-- UNIQUE on alpha_hash for V10 formula rows
CREATE UNIQUE INDEX IF NOT EXISTS uniq_alpha_hash_v10
  ON champion_pipeline (alpha_hash)
  WHERE alpha_hash IS NOT NULL;

-- Bound numeric metrics to sane ranges (soft alerts via CHECK)
ALTER TABLE champion_pipeline
  DROP CONSTRAINT IF EXISTS chk_sane_metrics;
ALTER TABLE champion_pipeline
  ADD CONSTRAINT chk_sane_metrics CHECK (
    (arena1_win_rate IS NULL OR (arena1_win_rate >= 0 AND arena1_win_rate <= 1)) AND
    (arena2_win_rate IS NULL OR (arena2_win_rate >= 0 AND arena2_win_rate <= 1)) AND
    (arena1_n_trades IS NULL OR arena1_n_trades >= 0) AND
    (arena2_n_trades IS NULL OR arena2_n_trades >= 0) AND
    (arena1_pnl IS NULL OR (arena1_pnl >= -10.0 AND arena1_pnl <= 100.0)) AND
    (elo_rating IS NULL OR (elo_rating >= -1000 AND elo_rating <= 5000)) AND
    (n_indicators >= 0 AND n_indicators <= 10)
  );
