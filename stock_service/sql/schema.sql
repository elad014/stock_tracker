-- stock_service schema for stock_tracker.
-- Owner: stock_service (read/write) as stock_db_user.
--
-- news_service holds SELECT on stock_quotes only, so it can JOIN to filter by
-- symbol. Nothing else in this schema is readable outside stock_service.
--
-- Apply order (watchlist references ui_schema.user_auth_data):
--   1. ui_service/sql/schema.sql
--   2. stock_service/sql/schema.sql   (this file)
--   3. news_service/sql/schema.sql
--
-- Roles, grants and the migration off the shared public schema live in
-- sql/migrations/001_schema_role_isolation.sql.

CREATE SCHEMA IF NOT EXISTS stock_schema;
SET search_path TO stock_schema;

-- ---------------------------------------------------------------------------
-- Current quotes for stocks that are actively watched
-- Owner: stock_service (read/write). news_service may JOIN this table
-- read-only as stock_schema.stock_quotes.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_quotes (
    stock_id UUID PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT,
    close NUMERIC,
    change NUMERIC,
    percent_change NUMERIC,
    previous_close NUMERIC,
    high NUMERIC,
    low NUMERIC,
    volume BIGINT,
    fifty_two_week_high NUMERIC,
    fifty_two_week_low NUMERIC,
    stock_summery TEXT,
    stock_news_published_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Active daily OHLCV history (rolling ~5 years for watched stocks)
-- One row per stock per trading day
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_history (
    stock_id UUID NOT NULL REFERENCES stock_quotes (stock_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume BIGINT,
    PRIMARY KEY (stock_id, date)
);

CREATE INDEX IF NOT EXISTS idx_stock_history_date ON stock_history (date);
CREATE INDEX IF NOT EXISTS idx_stock_history_symbol ON stock_history (symbol);

-- ---------------------------------------------------------------------------
-- Archived daily history for stocks no longer on any watchlist
-- Restored into stock_history when the symbol is watched again
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_history_archive (
    stock_id UUID NOT NULL,
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open NUMERIC NOT NULL,
    high NUMERIC NOT NULL,
    low NUMERIC NOT NULL,
    close NUMERIC NOT NULL,
    volume BIGINT,
    PRIMARY KEY (stock_id, date)
);

CREATE INDEX IF NOT EXISTS idx_stock_history_archive_stock_id ON stock_history_archive (stock_id);
CREATE INDEX IF NOT EXISTS idx_stock_history_archive_symbol ON stock_history_archive (symbol);

-- ---------------------------------------------------------------------------
-- User watchlists
-- user_id crosses into ui_schema, which ui_service owns. The cascade still
-- fires: PostgreSQL runs referential-integrity triggers as the owner of the
-- constrained table, not as the caller.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watchlist (
    user_id UUID NOT NULL REFERENCES ui_schema.user_auth_data (id) ON DELETE CASCADE,
    stock_id UUID NOT NULL REFERENCES stock_quotes (stock_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, stock_id)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_stock_id ON watchlist (stock_id);
