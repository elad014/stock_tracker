-- ===========================================================================
-- Verification for 001_schema_role_isolation.
--
-- Run as neondb_owner after the migration and before pointing the services at
-- the new credentials. Every block states what a correct result looks like.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Every table landed in the right schema with the right owner.
--    public should hold none of the nine application tables.
-- ---------------------------------------------------------------------------
SELECT schemaname, tablename, tableowner
FROM pg_tables
WHERE schemaname IN ('public', 'ui_schema', 'stock_schema', 'news_schema', 'doc_schema')
ORDER BY schemaname, tablename;

-- ---------------------------------------------------------------------------
-- 2. The two cross-schema foreign keys survived, still with ON DELETE CASCADE
--    (confdeltype 'c').
--
--    expected rows:
--      stock_schema.watchlist      -> ui_schema.user_auth_data     c
--      news_schema.stock_articles  -> stock_schema.stock_quotes    c
-- ---------------------------------------------------------------------------
SELECT c.conname,
       cn.nspname || '.' || cl.relname AS child,
       pn.nspname || '.' || pl.relname AS parent,
       c.confdeltype
FROM pg_constraint c
JOIN pg_class     cl ON cl.oid = c.conrelid
JOIN pg_namespace cn ON cn.oid = cl.relnamespace
JOIN pg_class     pl ON pl.oid = c.confrelid
JOIN pg_namespace pn ON pn.oid = pl.relnamespace
WHERE c.contype = 'f'
  AND cn.nspname <> pn.nspname
ORDER BY child;

-- ---------------------------------------------------------------------------
-- 3. Schema-level privileges are what we think they are.
--    news_db_user should appear on stock_schema with USAGE only.
-- ---------------------------------------------------------------------------
SELECT n.nspname AS schema_name,
       r.rolname AS role_name,
       has_schema_privilege(r.rolname, n.nspname, 'USAGE')  AS has_usage,
       has_schema_privilege(r.rolname, n.nspname, 'CREATE') AS has_create
FROM pg_namespace n
CROSS JOIN pg_roles r
WHERE n.nspname IN ('ui_schema', 'stock_schema', 'news_schema', 'doc_schema')
  AND r.rolname IN ('ui_db_user', 'stock_db_user', 'news_db_user', 'doc_db_user')
ORDER BY n.nspname, r.rolname;

-- ---------------------------------------------------------------------------
-- 4. Isolation actually holds. Each statement is annotated with the result it
--    must produce; run them one at a time so a failure is unambiguous.
-- ---------------------------------------------------------------------------
SET ROLE news_db_user;
SELECT count(*) FROM stock_schema.stock_quotes;          -- must succeed
SELECT count(*) FROM stock_schema.stock_history;         -- must fail: permission denied
SELECT count(*) FROM stock_schema.watchlist;             -- must fail: permission denied
SELECT count(*) FROM ui_schema.user_auth_data;           -- must fail: permission denied
RESET ROLE;

SET ROLE stock_db_user;
SELECT count(*) FROM stock_schema.stock_quotes;          -- must succeed
SELECT count(*) FROM news_schema.news_articles;          -- must fail: permission denied
SELECT count(*) FROM ui_schema.user_auth_data;           -- must fail: permission denied
RESET ROLE;

SET ROLE doc_db_user;
SELECT count(*) FROM doc_schema.document_vectors;        -- must succeed
SELECT count(*) FROM stock_schema.stock_quotes;          -- must fail: permission denied
RESET ROLE;

SET ROLE ui_db_user;
SELECT count(*) FROM ui_schema.user_auth_data;           -- must succeed
SELECT count(*) FROM stock_schema.watchlist;             -- must fail: permission denied
RESET ROLE;

-- ---------------------------------------------------------------------------
-- 5. Unqualified names resolve through the per-role search_path, so the
--    existing application queries keep working untouched.
-- ---------------------------------------------------------------------------
SET ROLE stock_db_user;
SHOW search_path;                                        -- expect: stock_schema
SELECT count(*) FROM stock_quotes;                       -- must succeed unqualified
RESET ROLE;

SET ROLE doc_db_user;
SHOW search_path;                                        -- expect: doc_schema, public
SELECT 'document_vectors'::regclass;                     -- expect: doc_schema.document_vectors
SELECT count(*) FROM document_vectors;                   -- must succeed unqualified
RESET ROLE;

-- ---------------------------------------------------------------------------
-- 6. Cross-schema CASCADE deletes still fire even though parent and child are
--    owned by different roles. PostgreSQL runs referential-integrity triggers
--    as the owner of the constrained table and skips the caller's permission
--    checks, but confirm it rather than trusting it.
--
--    Rolled back at the end, so no real data is touched.
-- ---------------------------------------------------------------------------
BEGIN;

INSERT INTO ui_schema.user_auth_data (id, user_name, password, email, phone_number)
VALUES ('00000000-0000-0000-0000-0000000000ff', 'fk_probe', 'x',
        'fk_probe@example.invalid', '+000000000000');

INSERT INTO stock_schema.stock_quotes (stock_id, symbol, name)
VALUES ('00000000-0000-0000-0000-0000000000fe', '__FKPROBE__', 'fk probe');

-- Written by stock_db_user, referencing a row owned by ui_db_user.
SET ROLE stock_db_user;
INSERT INTO stock_schema.watchlist (user_id, stock_id)
VALUES ('00000000-0000-0000-0000-0000000000ff',
        '00000000-0000-0000-0000-0000000000fe');
RESET ROLE;

-- ui_db_user deletes its own row; the cascade must remove the watchlist row
-- living in stock_schema.
SET ROLE ui_db_user;
DELETE FROM ui_schema.user_auth_data
WHERE id = '00000000-0000-0000-0000-0000000000ff';
RESET ROLE;

SELECT count(*) AS orphaned_watchlist_rows
FROM stock_schema.watchlist
WHERE user_id = '00000000-0000-0000-0000-0000000000ff';   -- expect: 0

ROLLBACK;
