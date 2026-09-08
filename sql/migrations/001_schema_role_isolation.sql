-- ===========================================================================
-- 001_schema_role_isolation
--
-- Moves the stock_tracker tables out of the shared `public` schema into one
-- owned schema per service, and creates one least-privilege login role per
-- service so a service can only reach its own tables.
--
--   ui_schema     ui_db_user      user_auth_data
--   stock_schema  stock_db_user   stock_quotes, stock_history,
--                                 stock_history_archive, watchlist
--   news_schema   news_db_user    news_articles, stock_articles
--   doc_schema    doc_db_user     document_vectors, document_ingest_quota
--
-- Single documented exception: news_db_user gets USAGE on stock_schema and
-- SELECT on stock_schema.stock_quotes only, so it can JOIN to filter by symbol.
--
-- Run as neondb_owner in the Neon SQL Editor.
-- Take a Neon branch/snapshot first: this is not trivially reversible.
-- Replace every REPLACE_ME_* placeholder with a distinct strong password
-- before running, and store those passwords in the per-service .env files.
-- ===========================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Roles
--    Deliberately not created with IN ROLE neon_superuser: these are plain
--    login roles with no privileges beyond what is granted below.
-- ---------------------------------------------------------------------------
CREATE ROLE ui_db_user    LOGIN PASSWORD 'REPLACE_ME_UI';
CREATE ROLE stock_db_user LOGIN PASSWORD 'REPLACE_ME_STOCK';
CREATE ROLE news_db_user  LOGIN PASSWORD 'REPLACE_ME_NEWS';
CREATE ROLE doc_db_user   LOGIN PASSWORD 'REPLACE_ME_DOC';

-- neondb_owner must be a member of each role to reassign object ownership to
-- it. This also keeps an admin path open afterwards via SET ROLE <role>.
GRANT ui_db_user, stock_db_user, news_db_user, doc_db_user TO neondb_owner;

-- ---------------------------------------------------------------------------
-- 2. Schemas
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS ui_schema    AUTHORIZATION ui_db_user;
CREATE SCHEMA IF NOT EXISTS stock_schema AUTHORIZATION stock_db_user;
CREATE SCHEMA IF NOT EXISTS news_schema  AUTHORIZATION news_db_user;
CREATE SCHEMA IF NOT EXISTS doc_schema   AUTHORIZATION doc_db_user;

-- ---------------------------------------------------------------------------
-- 3. Move the tables
--    Indexes, primary keys and foreign keys follow their table automatically.
--    The two ON DELETE CASCADE constraints (watchlist -> user_auth_data and
--    stock_articles -> stock_quotes) survive the move and simply become
--    cross-schema. Nothing needs to be dropped and re-created.
-- ---------------------------------------------------------------------------
ALTER TABLE public.user_auth_data          SET SCHEMA ui_schema;

ALTER TABLE public.stock_quotes            SET SCHEMA stock_schema;
ALTER TABLE public.stock_history           SET SCHEMA stock_schema;
ALTER TABLE public.stock_history_archive   SET SCHEMA stock_schema;
ALTER TABLE public.watchlist               SET SCHEMA stock_schema;

ALTER TABLE public.news_articles           SET SCHEMA news_schema;
ALTER TABLE public.stock_articles          SET SCHEMA news_schema;

ALTER TABLE public.document_vectors        SET SCHEMA doc_schema;
ALTER TABLE public.document_ingest_quota   SET SCHEMA doc_schema;

-- ---------------------------------------------------------------------------
-- 4. Transfer table ownership
--    Ownership, not just GRANT ALL: doc_service runs CREATE/ALTER/DROP TABLE
--    from its startup hook, and owning its tables keeps every service able to
--    migrate its own schema without an elevated role.
-- ---------------------------------------------------------------------------
ALTER TABLE ui_schema.user_auth_data           OWNER TO ui_db_user;

ALTER TABLE stock_schema.stock_quotes          OWNER TO stock_db_user;
ALTER TABLE stock_schema.stock_history         OWNER TO stock_db_user;
ALTER TABLE stock_schema.stock_history_archive OWNER TO stock_db_user;
ALTER TABLE stock_schema.watchlist             OWNER TO stock_db_user;

ALTER TABLE news_schema.news_articles          OWNER TO news_db_user;
ALTER TABLE news_schema.stock_articles         OWNER TO news_db_user;

ALTER TABLE doc_schema.document_vectors        OWNER TO doc_db_user;
ALTER TABLE doc_schema.document_ingest_quota   OWNER TO doc_db_user;

-- ---------------------------------------------------------------------------
-- 5. Least privilege
-- ---------------------------------------------------------------------------

-- Nobody reaches these schemas by default.
REVOKE ALL ON SCHEMA ui_schema, stock_schema, news_schema, doc_schema FROM PUBLIC;

-- Each role gets its own schema, and nothing else.
GRANT ALL ON SCHEMA ui_schema    TO ui_db_user;
GRANT ALL ON SCHEMA stock_schema TO stock_db_user;
GRANT ALL ON SCHEMA news_schema  TO news_db_user;
GRANT ALL ON SCHEMA doc_schema   TO doc_db_user;

GRANT ALL ON ALL TABLES    IN SCHEMA ui_schema    TO ui_db_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA ui_schema    TO ui_db_user;

GRANT ALL ON ALL TABLES    IN SCHEMA stock_schema TO stock_db_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA stock_schema TO stock_db_user;

GRANT ALL ON ALL TABLES    IN SCHEMA news_schema  TO news_db_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA news_schema  TO news_db_user;

GRANT ALL ON ALL TABLES    IN SCHEMA doc_schema   TO doc_db_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA doc_schema   TO doc_db_user;

-- Anything neondb_owner creates in these schemas later stays usable by the
-- owning service without a follow-up GRANT.
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA ui_schema
    GRANT ALL ON TABLES TO ui_db_user;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA ui_schema
    GRANT ALL ON SEQUENCES TO ui_db_user;

ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA stock_schema
    GRANT ALL ON TABLES TO stock_db_user;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA stock_schema
    GRANT ALL ON SEQUENCES TO stock_db_user;

ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA news_schema
    GRANT ALL ON TABLES TO news_db_user;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA news_schema
    GRANT ALL ON SEQUENCES TO news_db_user;

ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA doc_schema
    GRANT ALL ON TABLES TO doc_db_user;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA doc_schema
    GRANT ALL ON SEQUENCES TO doc_db_user;

-- No service may create objects in public. doc_service still needs USAGE
-- there so the pgvector type, the <=> operator and vector_cosine_ops resolve.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO doc_db_user;

-- ---------------------------------------------------------------------------
-- 6. The news_service exception
--    news_service JOINs stock_quotes to filter articles by symbol. It gets
--    read access to that one table and nothing else in stock_schema:
--    stock_history, stock_history_archive and watchlist stay invisible.
-- ---------------------------------------------------------------------------
GRANT USAGE  ON SCHEMA stock_schema       TO news_db_user;
GRANT SELECT ON stock_schema.stock_quotes TO news_db_user;

-- ---------------------------------------------------------------------------
-- 7. Default search_path per role
--    Belt and suspenders alongside the server_settings search_path the
--    application passes to asyncpg.
--
--    news_db_user deliberately does NOT get stock_schema on its search_path.
--    The one cross-schema query is explicitly qualified, so an accidental
--    unqualified reference to another stock table fails loudly.
--
--    doc_db_user needs public for the pgvector type and operators.
-- ---------------------------------------------------------------------------
ALTER ROLE ui_db_user    IN DATABASE neondb SET search_path = ui_schema;
ALTER ROLE stock_db_user IN DATABASE neondb SET search_path = stock_schema;
ALTER ROLE news_db_user  IN DATABASE neondb SET search_path = news_schema;
ALTER ROLE doc_db_user   IN DATABASE neondb SET search_path = doc_schema, public;

COMMIT;
