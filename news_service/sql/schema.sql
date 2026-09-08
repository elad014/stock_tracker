-- news_service schema for stock_tracker.
-- Owner: news_service (read/write) as news_db_user.
--
-- news_db_user also holds USAGE on stock_schema and SELECT on
-- stock_schema.stock_quotes, which is the only table it may read outside this
-- schema. Queries that touch it must qualify it explicitly, because
-- stock_schema is deliberately kept off the news_db_user search_path.
--
-- Apply order (stock_articles references stock_schema.stock_quotes):
--   1. ui_service/sql/schema.sql
--   2. stock_service/sql/schema.sql
--   3. news_service/sql/schema.sql   (this file)
--
-- Roles, grants and the migration off the shared public schema live in
-- sql/migrations/001_schema_role_isolation.sql.

CREATE SCHEMA IF NOT EXISTS news_schema;
SET search_path TO news_schema;

-- ---------------------------------------------------------------------------
-- News articles fetched from the news provider
-- Owner: news_service (read/write). stock_service does not touch these tables.
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
-- stock_id crosses into stock_schema, which stock_service owns. The cascade
-- still fires: PostgreSQL runs referential-integrity triggers as the owner of
-- the constrained table, not as the caller.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_articles (
    stock_id UUID NOT NULL REFERENCES stock_schema.stock_quotes (stock_id) ON DELETE CASCADE,
    article_id UUID NOT NULL REFERENCES news_articles (article_id) ON DELETE CASCADE,
    PRIMARY KEY (stock_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_articles_article_id ON stock_articles (article_id);
