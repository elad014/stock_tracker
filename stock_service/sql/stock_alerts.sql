-- stock_alerts table for stock_tracker.
-- Owner: stock_service (read/write) as stock_db_user.
-- Lives in stock_schema alongside stock_quotes and watchlist.
--
-- user_id is VARCHAR (no cross-schema FK) — same rationale as document_vectors:
-- avoids a dependency on ui_schema and prevents failures during mid-delete.
-- stock_id FK to stock_quotes ON DELETE CASCADE so alerts are cleaned up
-- automatically when the quote (and its history) is archived.

SET search_path TO stock_schema;

CREATE TABLE IF NOT EXISTS stock_alerts (
    id UUID PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    stock_id UUID NOT NULL REFERENCES stock_quotes (stock_id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL CHECK (alert_type IN ('PERCENT', 'ABSOLUTE')),
    target_value NUMERIC NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('ABOVE', 'BELOW')),
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'TRIGGERED', 'CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_alerts_stock_id
    ON stock_alerts (stock_id);

-- Supports: list all PENDING alerts for a given user, cancel by user
CREATE INDEX IF NOT EXISTS idx_stock_alerts_user_status
    ON stock_alerts (user_id, status);
