-- Current Neon public schema for stock_tracker (stock domain + auth used by watchlist).
-- Reflects live DB as of the stock_manager cutover.
-- Does not include Neon Auth internal tables.

-- ---------------------------------------------------------------------------
-- Users (existing auth table; referenced by watchlist)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_auth_data (
    id UUID PRIMARY KEY,
    user_name TEXT,
    password TEXT,
    email TEXT NOT NULL UNIQUE,
    phone_number TEXT NOT NULL UNIQUE,
    admin TEXT,
    lock TEXT
);

-- ---------------------------------------------------------------------------
-- Current quotes for stocks that are actively watched
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
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watchlist (
    user_id UUID NOT NULL REFERENCES user_auth_data (id) ON DELETE CASCADE,
    stock_id UUID NOT NULL REFERENCES stock_quotes (stock_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, stock_id)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_stock_id ON watchlist (stock_id);
