-- ============================================================
-- Migration v0.7.1 — Governance upgrade: physical split + staging +
--                    provenance + telemetry + two evidence VIEWs
-- Applied: 2026-04-20
-- ============================================================
-- Rules enforced (j13 directive 2026-04-20):
--   1. Epoch A rows are read-only and never promoted / ranked / deployed
--   2. No alpha enters champion_pipeline_fresh without passing the three
--      gates inside admission_validator()
--   3. Provenance 11 fields (engine_version, git_commit, config_hash,
--      grammar_hash, fitness_version, patches_applied, run_id,
--      worker_id, seed, epoch, created_ts) are NOT NULL on both staging
--      and fresh tables — malformed INSERT is rejected at DB layer
--   4. Recovery un-proven => fitness locked (enforced at code layer
--      by pre-commit hook; SQL records fitness_version per row)
--   5. Downstream readers only query *_fresh or explicitly-named archive
-- ============================================================

BEGIN;

-- ---------------------------------------------------------------
-- 0. DROP dependent VIEWs so RENAME can succeed
-- ---------------------------------------------------------------
DROP VIEW IF EXISTS zangetsu_status;
DROP VIEW IF EXISTS zangetsu_engine_status;
DROP VIEW IF EXISTS j01_status;
DROP VIEW IF EXISTS j02_status;

-- ---------------------------------------------------------------
-- 1. Rename legacy table to archive
-- ---------------------------------------------------------------
ALTER TABLE champion_pipeline RENAME TO champion_legacy_archive;

-- ---------------------------------------------------------------
-- 2. Create champion_pipeline_fresh (Epoch B only, 11 provenance
--    fields NOT NULL, same functional columns as archive)
-- ---------------------------------------------------------------
CREATE TABLE champion_pipeline_fresh (
    id                    bigserial PRIMARY KEY,
    regime                text NOT NULL,
    indicator_hash        text NOT NULL,
    status                text NOT NULL DEFAULT 'ARENA1_READY',
    lease_until           timestamptz,
    worker_id_str         text,                      -- A23/A45 lease holder (string)
    retry_count           integer DEFAULT 0,
    n_indicators          integer NOT NULL,
    arena1_score          double precision,
    arena1_win_rate       double precision,
    arena1_pnl            double precision,
    arena1_n_trades       integer,
    arena2_win_rate       double precision,
    arena2_n_trades       integer,
    arena3_sharpe         double precision,
    arena3_expectancy     double precision,
    arena3_pnl            double precision,
    arena4_hell_wr        double precision,
    arena4_variability    double precision,
    quant_class           text,
    elo_rating            double precision DEFAULT 1200,
    elo_consecutive_first integer DEFAULT 0,
    card_status           text DEFAULT 'INACTIVE',
    passport              jsonb NOT NULL DEFAULT '{}'::jsonb,
    parent_hash           text,
    generation            integer DEFAULT 0,
    evolution_operator    text DEFAULT 'random',
    engine_hash           text NOT NULL,
    arena1_completed_at   timestamptz,
    arena2_completed_at   timestamptz,
    arena3_completed_at   timestamptz,
    arena4_completed_at   timestamptz,
    arena5_last_tested    timestamptz,
    created_at            timestamptz DEFAULT NOW(),
    updated_at            timestamptz DEFAULT NOW(),
    family_id             varchar(16),
    family_tag            varchar(64),
    alpha_hash            text,
    deployable_tier       text,
    strategy_id           text NOT NULL,

    -- ── Provenance (11 fields, ALL NOT NULL — this is the hard gate) ──
    engine_version        text    NOT NULL,
    git_commit            text    NOT NULL,
    config_hash           text    NOT NULL,
    grammar_hash          text    NOT NULL,
    fitness_version       text    NOT NULL,
    patches_applied       text[]  NOT NULL,
    run_id                text    NOT NULL,
    worker_id             integer NOT NULL,
    seed                  bigint  NOT NULL,
    epoch                 text    NOT NULL,
    created_ts            timestamptz NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_strategy_id_fresh
        CHECK (strategy_id IN ('j01', 'j02')),
    CONSTRAINT valid_deployable_tier_fresh
        CHECK (deployable_tier IS NULL
            OR deployable_tier IN ('historical', 'fresh', 'live_proven')),
    CONSTRAINT valid_epoch_fresh
        CHECK (epoch = 'B_full_space'),
    CONSTRAINT valid_status_fresh
        CHECK (status IN ('ARENA1_READY', 'ARENA1_PROCESSING', 'ARENA1_COMPLETE',
            'ARENA1_REJECTED', 'ARENA2_READY', 'ARENA2_PROCESSING',
            'ARENA2_COMPLETE', 'ARENA2_REJECTED', 'ARENA3_READY',
            'ARENA3_PROCESSING', 'ARENA3_COMPLETE', 'ARENA3_REJECTED',
            'ARENA4_READY', 'ARENA4_PROCESSING', 'ARENA4_ELIMINATED',
            'CANDIDATE', 'DEPLOYABLE', 'ELO_ACTIVE', 'ELO_RETIRED',
            'EVOLVING', 'EVOLVED', 'DEAD_LETTER'))
);

CREATE INDEX idx_fresh_alpha_hash   ON champion_pipeline_fresh (alpha_hash)
    WHERE alpha_hash IS NOT NULL;
CREATE INDEX idx_fresh_strategy_status
    ON champion_pipeline_fresh (strategy_id, status);
CREATE INDEX idx_fresh_strategy_tier
    ON champion_pipeline_fresh (strategy_id, deployable_tier)
    WHERE status = 'DEPLOYABLE';
CREATE INDEX idx_fresh_status_regime
    ON champion_pipeline_fresh (status, regime);
CREATE INDEX idx_fresh_lease
    ON champion_pipeline_fresh (lease_until)
    WHERE lease_until IS NOT NULL;
CREATE INDEX idx_fresh_elo
    ON champion_pipeline_fresh (regime, elo_rating DESC)
    WHERE status = 'DEPLOYABLE';
CREATE INDEX idx_fresh_run_id
    ON champion_pipeline_fresh (run_id);
CREATE UNIQUE INDEX uniq_fresh_alpha_hash
    ON champion_pipeline_fresh (alpha_hash)
    WHERE alpha_hash IS NOT NULL;

-- ---------------------------------------------------------------
-- 3. Create champion_pipeline_staging (same schema as fresh +
--    admission state)
-- ---------------------------------------------------------------
CREATE TABLE champion_pipeline_staging (
    LIKE champion_pipeline_fresh INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    admission_state   text NOT NULL DEFAULT 'pending',
    rejection_reason  text,
    validated_at      timestamptz,

    CONSTRAINT valid_admission_state CHECK (
        admission_state IN ('pending', 'admitted', 'rejected', 'pending_validator_error')
    )
);

CREATE INDEX idx_staging_admission
    ON champion_pipeline_staging (admission_state);
CREATE INDEX idx_staging_validated_at
    ON champion_pipeline_staging (validated_at)
    WHERE validated_at IS NOT NULL;

-- ---------------------------------------------------------------
-- 4. Rejection forensics table (rejected rows moved here for audit)
-- ---------------------------------------------------------------
CREATE TABLE champion_pipeline_rejected (
    LIKE champion_pipeline_staging INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    archived_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rejected_archived_at
    ON champion_pipeline_rejected (archived_at);
CREATE INDEX idx_rejected_reason
    ON champion_pipeline_rejected (rejection_reason);

-- ---------------------------------------------------------------
-- 5. Engine telemetry (process evidence metrics time-series)
-- ---------------------------------------------------------------
CREATE TABLE engine_telemetry (
    id          bigserial PRIMARY KEY,
    run_id      text        NOT NULL,
    worker_id   integer     NOT NULL,
    strategy_id text        NOT NULL,
    ts          timestamptz NOT NULL DEFAULT NOW(),
    metric_name text        NOT NULL,
    value       double precision NOT NULL,

    CONSTRAINT valid_telemetry_metric CHECK (
        metric_name IN (
            'compile_success_count',
            'compile_exception_count',
            'evaluate_success_count',
            'evaluate_exception_count',
            'indicator_terminal_call_count',
            'indicator_terminal_exception_count',
            'cache_hit_count',
            'cache_miss_count',
            'nan_inf_count',
            'zero_variance_count',
            'admitted_count',
            'rejected_count',
            'round_duration_ms',
            'population_size'
        )
    )
);

CREATE INDEX idx_telemetry_ts ON engine_telemetry (ts);
CREATE INDEX idx_telemetry_metric_ts ON engine_telemetry (metric_name, ts);
CREATE INDEX idx_telemetry_strategy_ts ON engine_telemetry (strategy_id, ts);

-- ---------------------------------------------------------------
-- 6. Archive read-only triggers
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION archive_readonly_trigger()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'champion_legacy_archive is READ-ONLY (Epoch A). '
        'Modification blocked by governance rule #1.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER archive_readonly_insert
    BEFORE INSERT ON champion_legacy_archive
    FOR EACH ROW EXECUTE FUNCTION archive_readonly_trigger();

CREATE TRIGGER archive_readonly_update
    BEFORE UPDATE ON champion_legacy_archive
    FOR EACH ROW EXECUTE FUNCTION archive_readonly_trigger();

CREATE TRIGGER archive_readonly_delete
    BEFORE DELETE ON champion_legacy_archive
    FOR EACH ROW EXECUTE FUNCTION archive_readonly_trigger();

-- ---------------------------------------------------------------
-- 7. Fresh-table insert guard (only admission_validator() may INSERT)
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION fresh_insert_guard()
RETURNS TRIGGER AS $$
BEGIN
    IF current_setting('zangetsu.admission_active', true)
       IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION
            'champion_pipeline_fresh direct INSERT forbidden. '
            'Only admission_validator() may promote rows. '
            'Governance rule #2.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER fresh_insert_gated
    BEFORE INSERT ON champion_pipeline_fresh
    FOR EACH ROW EXECUTE FUNCTION fresh_insert_guard();

-- ---------------------------------------------------------------
-- 8. Admission validator — the ONLY path from staging to fresh
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION admission_validator(_staging_id BIGINT)
RETURNS TEXT AS $$
DECLARE
    row_data RECORD;
    fail_reason TEXT;
BEGIN
    SELECT * INTO row_data
        FROM champion_pipeline_staging
        WHERE id = _staging_id
          AND admission_state = 'pending'
        FOR UPDATE;

    IF NOT FOUND THEN
        RETURN 'not_found_or_already_processed';
    END IF;

    -- Gate 1 (structural): alpha_hash must be 16-char hex if present
    IF row_data.alpha_hash IS NOT NULL
       AND row_data.alpha_hash !~ '^[0-9a-f]{16}$' THEN
        fail_reason := 'gate1_invalid_alpha_hash_format';
        UPDATE champion_pipeline_staging
           SET admission_state = 'rejected',
               rejection_reason = fail_reason,
               validated_at = NOW()
         WHERE id = _staging_id;
        INSERT INTO champion_pipeline_rejected
            SELECT * FROM champion_pipeline_staging WHERE id = _staging_id;
        RETURN 'rejected:' || fail_reason;
    END IF;

    -- Gate 2 (provenance): epoch must be B; provenance NOT NULL already
    -- enforced by column CHECKs on INSERT. Re-validate here as
    -- defense-in-depth.
    IF row_data.epoch IS DISTINCT FROM 'B_full_space' THEN
        fail_reason := 'gate2_epoch_not_B';
        UPDATE champion_pipeline_staging
           SET admission_state = 'rejected',
               rejection_reason = fail_reason,
               validated_at = NOW()
         WHERE id = _staging_id;
        INSERT INTO champion_pipeline_rejected
            SELECT * FROM champion_pipeline_staging WHERE id = _staging_id;
        RETURN 'rejected:' || fail_reason;
    END IF;

    -- Gate 3 (post-write admission): arena1_score must be finite
    IF row_data.arena1_score IS NOT NULL
       AND (row_data.arena1_score = 'NaN'::double precision
            OR row_data.arena1_score = 'Infinity'::double precision
            OR row_data.arena1_score = '-Infinity'::double precision) THEN
        fail_reason := 'gate3_score_not_finite';
        UPDATE champion_pipeline_staging
           SET admission_state = 'rejected',
               rejection_reason = fail_reason,
               validated_at = NOW()
         WHERE id = _staging_id;
        INSERT INTO champion_pipeline_rejected
            SELECT * FROM champion_pipeline_staging WHERE id = _staging_id;
        RETURN 'rejected:' || fail_reason;
    END IF;

    -- All gates passed — promote to fresh.
    -- Set transaction-local session variable so fresh_insert_guard
    -- recognises this as a legitimate promotion.
    PERFORM set_config('zangetsu.admission_active', 'true', true);

    INSERT INTO champion_pipeline_fresh (
        regime, indicator_hash, status, lease_until, worker_id_str,
        retry_count, n_indicators, arena1_score, arena1_win_rate,
        arena1_pnl, arena1_n_trades, arena2_win_rate, arena2_n_trades,
        arena3_sharpe, arena3_expectancy, arena3_pnl, arena4_hell_wr,
        arena4_variability, quant_class, elo_rating, elo_consecutive_first,
        card_status, passport, parent_hash, generation, evolution_operator,
        engine_hash, arena1_completed_at, arena2_completed_at,
        arena3_completed_at, arena4_completed_at, arena5_last_tested,
        created_at, updated_at, family_id, family_tag, alpha_hash,
        deployable_tier, strategy_id,
        engine_version, git_commit, config_hash, grammar_hash,
        fitness_version, patches_applied, run_id, worker_id, seed,
        epoch, created_ts
    )
    SELECT
        regime, indicator_hash, status, lease_until, worker_id_str,
        retry_count, n_indicators, arena1_score, arena1_win_rate,
        arena1_pnl, arena1_n_trades, arena2_win_rate, arena2_n_trades,
        arena3_sharpe, arena3_expectancy, arena3_pnl, arena4_hell_wr,
        arena4_variability, quant_class, elo_rating, elo_consecutive_first,
        card_status, passport, parent_hash, generation, evolution_operator,
        engine_hash, arena1_completed_at, arena2_completed_at,
        arena3_completed_at, arena4_completed_at, arena5_last_tested,
        created_at, updated_at, family_id, family_tag, alpha_hash,
        deployable_tier, strategy_id,
        engine_version, git_commit, config_hash, grammar_hash,
        fitness_version, patches_applied, run_id, worker_id, seed,
        epoch, created_ts
    FROM champion_pipeline_staging WHERE id = _staging_id;

    -- Clear session variable immediately so subsequent direct INSERTs fail
    PERFORM set_config('zangetsu.admission_active', 'false', true);

    UPDATE champion_pipeline_staging
       SET admission_state = 'admitted', validated_at = NOW()
     WHERE id = _staging_id;

    RETURN 'admitted';

EXCEPTION WHEN OTHERS THEN
    -- Any unexpected error: mark row as pending_validator_error, keep
    -- it in staging for forensics, do NOT promote to fresh.
    UPDATE champion_pipeline_staging
       SET admission_state = 'pending_validator_error',
           rejection_reason = 'validator_exception: ' || SQLERRM,
           validated_at = NOW()
     WHERE id = _staging_id;
    RETURN 'error:' || SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------
-- 9. Per-strategy VIEWs — primary name points at fresh only
-- ---------------------------------------------------------------
CREATE VIEW j01_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE')
     AS deployable_count,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'historical')
     AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'fresh')
     AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'live_proven')
     AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01' AND card_status = 'ACTIVE')
     AS active_count,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01' AND status = 'CANDIDATE')
     AS candidate_count,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01' AND created_at > now() - INTERVAL '1 hour')
     AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric
     FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01'
       AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at_age_h,
    (SELECT max(created_at) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j01'
       AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at,
    now() AS ts;

CREATE VIEW j02_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE')
     AS deployable_count,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'historical')
     AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'fresh')
     AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02' AND status = 'DEPLOYABLE'
       AND deployable_tier = 'live_proven')
     AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02' AND card_status = 'ACTIVE')
     AS active_count,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02' AND status = 'CANDIDATE')
     AS candidate_count,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02' AND created_at > now() - INTERVAL '1 hour')
     AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric
     FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02'
       AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at_age_h,
    (SELECT max(created_at) FROM champion_pipeline_fresh
     WHERE strategy_id = 'j02'
       AND status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at,
    now() AS ts;

-- Archive-only VIEWs (reference for historical control group — never
-- used by ranking / promotion / deployment; data-science queries only).
CREATE VIEW j01_status_archive AS
SELECT
    (SELECT count(*) FROM champion_legacy_archive
     WHERE strategy_id = 'j01') AS total_count,
    (SELECT count(*) FROM champion_legacy_archive
     WHERE strategy_id = 'j01' AND status = 'LEGACY') AS legacy_count,
    (SELECT count(*) FROM champion_legacy_archive
     WHERE strategy_id = 'j01' AND status = 'ARENA2_REJECTED') AS a2_rejected_count,
    (SELECT count(*) FROM champion_legacy_archive
     WHERE strategy_id = 'j01' AND status = 'ARENA4_ELIMINATED') AS a4_elim_count,
    now() AS ts;

CREATE VIEW j02_status_archive AS
SELECT
    (SELECT count(*) FROM champion_legacy_archive
     WHERE strategy_id = 'j02') AS total_count,
    now() AS ts;

-- Engine rollup across all strategies (fresh only)
CREATE VIEW zangetsu_engine_status AS
SELECT
    strategy_id,
    (SELECT count(*) FROM champion_pipeline_fresh cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.status = 'DEPLOYABLE')
     AS deployable_count,
    (SELECT count(*) FROM champion_pipeline_fresh cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.status = 'CANDIDATE')
     AS candidate_count,
    (SELECT count(*) FROM champion_pipeline_fresh cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.card_status = 'ACTIVE')
     AS active_count,
    (SELECT count(*) FROM champion_pipeline_fresh cp2
     WHERE cp2.strategy_id = cp.strategy_id
       AND cp2.created_at > now() - INTERVAL '1 hour')
     AS champions_last_1h,
    now() AS ts
FROM (SELECT DISTINCT strategy_id FROM champion_pipeline_fresh) cp;

-- Backward-compat name (will be removed in v0.8.0 after all callers migrated).
CREATE VIEW zangetsu_status AS
SELECT
    (SELECT count(*) FROM champion_pipeline_fresh WHERE status = 'DEPLOYABLE')
     AS deployable_count,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE status = 'DEPLOYABLE' AND deployable_tier = 'historical')
     AS deployable_historical,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE status = 'DEPLOYABLE' AND deployable_tier = 'fresh')
     AS deployable_fresh,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE status = 'DEPLOYABLE' AND deployable_tier = 'live_proven')
     AS deployable_live_proven,
    (SELECT count(*) FROM champion_pipeline_fresh WHERE card_status = 'ACTIVE')
     AS active_count,
    (SELECT count(*) FROM champion_pipeline_fresh WHERE status = 'CANDIDATE')
     AS candidate_count,
    (SELECT count(*) FROM champion_pipeline_fresh
     WHERE created_at > now() - INTERVAL '1 hour')
     AS champions_last_1h,
    (SELECT EXTRACT(EPOCH FROM now() - max(created_at)) / 3600::numeric
     FROM champion_pipeline_fresh
     WHERE status = ANY (ARRAY['DEPLOYABLE', 'ACTIVE']))
     AS last_live_at_age_h,
    now() AS ts;

-- ---------------------------------------------------------------
-- 10. Fresh pool OUTCOME health VIEW (6 metrics, dual-evidence)
-- ---------------------------------------------------------------
CREATE VIEW fresh_pool_outcome_health AS
WITH per_strategy AS (
    SELECT
        strategy_id,
        count(*) AS total_fresh,
        count(*) FILTER (
            WHERE jsonb_array_length(
                COALESCE(passport->'arena1'->'used_indicators', '[]'::jsonb)
            ) > 0
        ) AS alphas_with_indicators,
        AVG((passport->'arena1'->>'depth')::numeric) AS avg_depth,
        AVG((passport->'arena1'->>'node_count')::numeric) AS avg_nodes,
        count(*) FILTER (WHERE status = 'DEPLOYABLE') AS deployable_count
    FROM champion_pipeline_fresh
    GROUP BY strategy_id
),
distinct_ind AS (
    SELECT
        cp.strategy_id,
        count(DISTINCT ind) AS distinct_indicators
    FROM champion_pipeline_fresh cp,
         jsonb_array_elements_text(
             COALESCE(cp.passport->'arena1'->'used_indicators', '[]'::jsonb)
         ) AS ind
    GROUP BY cp.strategy_id
)
SELECT
    p.strategy_id,
    p.total_fresh,
    p.alphas_with_indicators,
    CASE WHEN p.total_fresh > 0
         THEN ROUND(100.0 * p.alphas_with_indicators / p.total_fresh, 2)
         ELSE 0 END AS indicator_alpha_ratio_pct,
    COALESCE(d.distinct_indicators, 0) AS distinct_indicators,
    0::numeric AS usage_entropy, -- computed in miniapp layer (needs per-indicator counts)
    ROUND(COALESCE(p.avg_depth, 0), 2) AS avg_depth,
    ROUND(COALESCE(p.avg_nodes, 0), 2) AS avg_nodes,
    p.deployable_count
FROM per_strategy p
LEFT JOIN distinct_ind d ON p.strategy_id = d.strategy_id;

-- ---------------------------------------------------------------
-- 11. Fresh pool PROCESS health VIEW (8 metrics, dual-evidence)
-- ---------------------------------------------------------------
CREATE VIEW fresh_pool_process_health AS
WITH recent AS (
    SELECT strategy_id, metric_name, SUM(value) AS s
    FROM engine_telemetry
    WHERE ts > now() - INTERVAL '1 hour'
    GROUP BY strategy_id, metric_name
)
SELECT
    sid.strategy_id,
    COALESCE(MAX(value) FILTER (
        WHERE metric_name = 'compile_exception_count'
    ), 0) AS compile_exception_count,
    COALESCE(MAX(value) FILTER (
        WHERE metric_name = 'evaluate_exception_count'
    ), 0) AS evaluate_exception_count,
    COALESCE(MAX(value) FILTER (
        WHERE metric_name = 'indicator_terminal_exception_count'
    ), 0) AS indicator_terminal_exception_count,
    CASE
        WHEN (COALESCE(MAX(value) FILTER (WHERE metric_name = 'cache_hit_count'), 0)
            + COALESCE(MAX(value) FILTER (WHERE metric_name = 'cache_miss_count'), 0)) > 0
        THEN ROUND(
            MAX(value) FILTER (WHERE metric_name = 'cache_hit_count')::numeric
            / (MAX(value) FILTER (WHERE metric_name = 'cache_hit_count')
               + MAX(value) FILTER (WHERE metric_name = 'cache_miss_count'))::numeric,
            4)
        ELSE NULL
    END AS cache_hit_rate,
    COALESCE(MAX(value) FILTER (
        WHERE metric_name = 'nan_inf_count'
    ), 0) AS nan_inf_count,
    COALESCE(MAX(value) FILTER (
        WHERE metric_name = 'zero_variance_count'
    ), 0) AS zero_variance_count,
    CASE
        WHEN (COALESCE(MAX(value) FILTER (WHERE metric_name = 'admitted_count'), 0)
            + COALESCE(MAX(value) FILTER (WHERE metric_name = 'rejected_count'), 0)) > 0
        THEN ROUND(
            MAX(value) FILTER (WHERE metric_name = 'admitted_count')::numeric
            / (MAX(value) FILTER (WHERE metric_name = 'admitted_count')
               + MAX(value) FILTER (WHERE metric_name = 'rejected_count'))::numeric,
            4)
        ELSE NULL
    END AS admitted_rate,
    CASE
        WHEN (COALESCE(MAX(value) FILTER (WHERE metric_name = 'admitted_count'), 0)
            + COALESCE(MAX(value) FILTER (WHERE metric_name = 'rejected_count'), 0)) > 0
        THEN ROUND(
            MAX(value) FILTER (WHERE metric_name = 'rejected_count')::numeric
            / (MAX(value) FILTER (WHERE metric_name = 'admitted_count')
               + MAX(value) FILTER (WHERE metric_name = 'rejected_count'))::numeric,
            4)
        ELSE NULL
    END AS rejected_rate,
    now() AS ts
FROM (SELECT DISTINCT strategy_id FROM engine_telemetry
      WHERE ts > now() - INTERVAL '1 hour') sid
LEFT JOIN engine_telemetry et ON et.strategy_id = sid.strategy_id
    AND et.ts > now() - INTERVAL '1 hour'
GROUP BY sid.strategy_id;

COMMIT;
