-- ui_service schema for stock_tracker.
-- Owner: ui_service (read/write) as ui_db_user.
--
-- No other service may read these tables. stock_service.watchlist holds a
-- cross-schema foreign key to user_auth_data, so apply this file first:
--   1. ui_service/sql/schema.sql   (this file)
--   2. stock_service/sql/schema.sql
--   3. news_service/sql/schema.sql
--
-- Roles, grants and the migration off the shared public schema live in
-- sql/migrations/001_schema_role_isolation.sql.

CREATE SCHEMA IF NOT EXISTS ui_schema;
SET search_path TO ui_schema;

-- ---------------------------------------------------------------------------
-- Users. Referenced by stock_schema.watchlist (ON DELETE CASCADE).
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
