"""Idempotent pgvector schema for document_vectors.

Must stay in sync with doc_agent/sql/schema.sql. This module is the executed
source of truth and runs from the FastAPI lifespan on startup.
"""

import logging

from database_client import db

logger = logging.getLogger(__name__)

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    """
    CREATE TABLE IF NOT EXISTS document_vectors (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id VARCHAR NOT NULL,
        document_id VARCHAR NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding vector(1536),
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_doc_vectors_user_doc
        ON document_vectors (user_id, document_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_doc_vectors_embedding
        ON document_vectors USING hnsw (embedding vector_cosine_ops)
    """,
)


async def ensure_vector_schema() -> None:
    """Create the vector extension, table, and indexes if they are missing."""
    try:
        for statement in _SCHEMA_STATEMENTS:
            await db.execute(statement)
    except Exception:
        logger.exception("Failed to initialize document_vectors schema")
        raise
    logger.info("document_vectors schema is ready")
