-- doc_service vector store for stock_tracker.
-- Owner: doc_service (read/write) as doc_db_user. No other service may read it.
--
-- Keep this file in sync with doc_service/backend/db_logics/schema_init.py.
-- schema_init.py is the executed source of truth (run on service startup).
--
-- Roles, grants and the migration off the shared public schema live in
-- sql/migrations/001_schema_role_isolation.sql.

CREATE SCHEMA IF NOT EXISTS doc_schema;

-- public stays on the path because pgvector is installed there: the vector
-- type, the <=> operator and vector_cosine_ops all resolve through it.
-- doc_schema comes first, so the tables below are created in doc_schema.
SET search_path TO doc_schema, public;

-- Installed once by an admin role; doc_db_user only needs USAGE on public.
CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;

CREATE TABLE IF NOT EXISTS document_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    document_id VARCHAR NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doc_vectors_user_doc ON document_vectors (user_id, document_id);
CREATE INDEX IF NOT EXISTS idx_doc_vectors_embedding ON document_vectors USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS document_ingest_quota (
    user_id VARCHAR PRIMARY KEY,
    count_recent_ingests INTEGER NOT NULL,
    first_ingest TIMESTAMPTZ NOT NULL
);

DROP TABLE IF EXISTS document_ingest_events;
