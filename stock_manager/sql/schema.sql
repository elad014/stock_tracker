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
-- Owner: stock_manager (read/write). news_agent may JOIN this table read-only.
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
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watchlist (
    user_id UUID NOT NULL REFERENCES user_auth_data (id) ON DELETE CASCADE,
    stock_id UUID NOT NULL REFERENCES stock_quotes (stock_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, stock_id)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_stock_id ON watchlist (stock_id);

-- ---------------------------------------------------------------------------
-- News articles fetched from the news provider
-- Owner: news_agent (read/write). stock_manager does not touch these tables.
-- One row per article URL, shared by every stock that references it, so the
-- AI summary is generated once and reused by all users.
-- url_hash is a sha256 hex digest because raw URLs can exceed the btree limit.
-- ai_summary_status is one of: none, pending, ready, failed
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_articles (
    article_id UUID PRIMARY KEY,
    url_hash TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT,
    published_at TIMESTAMPTZ,
    provider TEXT NOT NULL DEFAULT 'finnhub',
    provider_summary TEXT,
    text TEXT,
    ai_summary TEXT,
    ai_summary_status TEXT NOT NULL DEFAULT 'none',
    ai_summary_model TEXT,
    ai_summary_error TEXT,
    ai_summary_started_at TIMESTAMPTZ,
    ai_summary_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_articles_published_at
    ON news_articles (published_at DESC);

ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS text TEXT;
ALTER TABLE news_articles DROP COLUMN IF EXISTS provider_article_id;

-- ---------------------------------------------------------------------------
-- Many-to-many link between stocks and articles
-- Owner: news_agent (read/write). stock_id references stock_quotes (owned by
-- stock_manager). news_agent reads stock_quotes only to join/filter by symbol.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_articles (
    stock_id UUID NOT NULL REFERENCES stock_quotes (stock_id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES news_articles (article_id) ON DELETE CASCADE,
    PRIMARY KEY (stock_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_articles_article_id ON stock_articles (article_id);
