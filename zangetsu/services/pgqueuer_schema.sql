-- PGQueuer schema for Zangetsu V9 A23/A45 orchestrators
-- Generated via: python -m pgqueuer install (pgqueuer 0.26.3)
-- Tables and types required for PGQueuer job queuing

CREATE TABLE IF NOT EXISTS pgqueuer (
    id BIGSERIAL PRIMARY KEY,
    priority INT NOT NULL DEFAULT 0,
    created TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    execute_after TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'picked', 'successful', 'exception', 'canceled', 'deleted')),
    entrypoint TEXT NOT NULL,
    payload BYTEA,
    queue_manager_id UUID,
    headers JSONB
);

CREATE INDEX IF NOT EXISTS pgqueuer_priority_id_idx ON pgqueuer (priority DESC, id ASC)
    WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS pgqueuer_updated_idx ON pgqueuer (updated);
CREATE INDEX IF NOT EXISTS pgqueuer_entrypoint_idx ON pgqueuer (entrypoint);
CREATE INDEX IF NOT EXISTS pgqueuer_execute_after_idx ON pgqueuer (execute_after)
    WHERE status = 'queued';

-- Statistics log table
CREATE TABLE IF NOT EXISTS pgqueuer_statistics (
    id BIGSERIAL PRIMARY KEY,
    created TIMESTAMPTZ NOT NULL DEFAULT date_trunc('second', NOW()),
    count BIGINT NOT NULL,
    priority INT NOT NULL,
    time_in_queue INTERVAL NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('exception', 'successful', 'canceled')),
    entrypoint TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS pgqueuer_statistics_entrypoint_idx ON pgqueuer_statistics (entrypoint);
CREATE INDEX IF NOT EXISTS pgqueuer_statistics_status_idx ON pgqueuer_statistics (status);

-- NOTIFY channel trigger for LISTEN-based job pickup
CREATE OR REPLACE FUNCTION fn_pgqueuer_changed() RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('ch_pgqueuer', json_build_object(
        'channel', 'ch_pgqueuer',
        'operation', TG_OP,
        'sent_at', NOW(),
        'table', TG_TABLE_NAME,
        'type', 'table_changed_event'
    )::text);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_pgqueuer_changed ON pgqueuer;
CREATE TRIGGER tg_pgqueuer_changed
    AFTER INSERT OR UPDATE OR DELETE ON pgqueuer
    FOR EACH STATEMENT EXECUTE FUNCTION fn_pgqueuer_changed();
