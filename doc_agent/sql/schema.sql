-- Doc-agent vector store for stock_tracker.
-- Keep this file in sync with doc_agent/backend/db_logics/schema_init.py.
-- schema_init.py is the executed source of truth (run on service startup).

CREATE EXTENSION IF NOT EXISTS vector;

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
