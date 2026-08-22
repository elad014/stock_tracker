"""Idempotent pgvector schema for document_vectors.

Must stay in sync with doc_agent/sql/schema.sql. This module is the executed
source of truth and runs from the FastAPI lifespan on startup.
"""

import logging

from constant import EMBEDDING_DIMENSIONS
from database_client import db

logger = logging.getLogger(__name__)

_CREATE_TABLE = f"""
    CREATE TABLE IF NOT EXISTS document_vectors (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id VARCHAR NOT NULL,
        document_id VARCHAR NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding vector({EMBEDDING_DIMENSIONS}),
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
"""


async def _embedding_column_type() -> str | None:
    row = await db.fetch_one(
        """
        SELECT format_type(a.atttypid, a.atttypmod) AS coltype
        FROM pg_attribute a
        WHERE a.attrelid = 'document_vectors'::regclass
          AND a.attname = 'embedding'
          AND a.attnum > 0
          AND NOT a.attisdropped
        """
    )
    if row is None:
        return None
    return str(row.get("coltype") or "")


async def _ensure_embedding_width() -> None:
    expected = f"vector({EMBEDDING_DIMENSIONS})"
    coltype = await _embedding_column_type()
    if coltype is None or coltype == expected:
        return
    logger.warning(
        "Migrating document_vectors.embedding from %s to %s",
        coltype,
        expected,
    )
    await db.execute("DROP INDEX IF EXISTS idx_doc_vectors_embedding")
    await db.execute("TRUNCATE TABLE document_vectors")
    await db.execute(
        f"ALTER TABLE document_vectors ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSIONS})"
    )


async def ensure_vector_schema() -> None:
    """Create the vector extension, table, and indexes if they are missing."""
    try:
        await db.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await db.execute(_CREATE_TABLE)
        await _ensure_embedding_width()
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_doc_vectors_user_doc
                ON document_vectors (user_id, document_id)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_doc_vectors_embedding
                ON document_vectors USING hnsw (embedding vector_cosine_ops)
            """
        )
    except Exception:
        logger.exception("Failed to initialize document_vectors schema")
        raise
    logger.info("document_vectors schema is ready")
