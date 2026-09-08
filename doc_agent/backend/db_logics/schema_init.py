"""Idempotent pgvector schema for document_vectors.

Must stay in sync with doc_agent/sql/schema.sql. This module is the executed
source of truth and runs from the FastAPI lifespan on startup.
"""

import logging

from constant import EMBEDDING_DIMENSIONS
from clients.database_client import db

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


async def _quota_columns() -> set[str]:
    rows = await db.fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'document_ingest_quota'
        """
    )
    return {str(row["column_name"]) for row in rows}


async def _ensure_ingest_quota_table() -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS document_ingest_quota (
            user_id VARCHAR PRIMARY KEY,
            count_recent_ingests INTEGER NOT NULL,
            first_ingest TIMESTAMPTZ NOT NULL
        )
        """
    )
    columns = await _quota_columns()
    if "period_started_at" in columns and "first_ingest" not in columns:
        await db.execute(
            "ALTER TABLE document_ingest_quota RENAME COLUMN period_started_at TO first_ingest"
        )
    if "ingest_count" in columns and "count_recent_ingests" not in columns:
        await db.execute(
            "ALTER TABLE document_ingest_quota RENAME COLUMN ingest_count TO count_recent_ingests"
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
        await db.execute("DROP TABLE IF EXISTS document_ingest_events")
        await _ensure_ingest_quota_table()
    except Exception:
        logger.exception("Failed to initialize document_vectors schema")
        raise
    logger.info("document_vectors schema is ready")
