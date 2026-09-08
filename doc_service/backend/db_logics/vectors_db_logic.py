from typing import Any, Optional

import asyncpg

from clients.database_client import db

VECTORS_TABLE = "document_vectors"


def embedding_literal(values: list[float]) -> str:
    """Format a float list as a pgvector text literal: [0.1,0.2,...]."""
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


def _chunk_row(row: dict[str, Any]) -> dict[str, Any]:
    similarity = row.get("similarity")
    document_id = row.get("document_id")
    return {
        "document_id": str(document_id) if document_id is not None else "",
        "content": str(row["content"]),
        "similarity": float(similarity) if similarity is not None else None,
    }


async def insert_chunks(
    user_id: str,
    document_id: str,
    chunks: list[tuple[int, str, list[float]]],
    conn: Optional[asyncpg.Connection] = None,
) -> None:
    """Insert (chunk_index, content, embedding) rows for one tenant document."""
    if not chunks:
        return
    args: list[tuple[Any, ...]] = [
        (user_id, document_id, index, content, embedding_literal(vector))
        for index, content, vector in chunks
    ]
    await db.executemany(
        f"""
        INSERT INTO {VECTORS_TABLE} (
            user_id, document_id, chunk_index, content, embedding
        )
        VALUES ($1, $2, $3, $4, $5::vector)
        """,
        args,
        conn=conn,
    )


def _deleted_row_count(status: str) -> int:
    parts = status.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return int(parts[-1])
    return 0


async def delete_document_vectors(
    user_id: str,
    document_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> int:
    """Delete every chunk belonging to one (user_id, document_id)."""
    status = await db.execute(
        f"""
        DELETE FROM {VECTORS_TABLE}
        WHERE user_id = $1 AND document_id = $2
        """,
        user_id,
        document_id,
        conn=conn,
    )
    return _deleted_row_count(status)


async def delete_user_vectors(
    user_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> int:
    """Delete every chunk belonging to one user."""
    status = await db.execute(
        f"""
        DELETE FROM {VECTORS_TABLE}
        WHERE user_id = $1
        """,
        user_id,
        conn=conn,
    )
    return _deleted_row_count(status)


async def count_document_chunks(
    user_id: str,
    document_id: str,
    conn: Optional[asyncpg.Connection] = None,
) -> int:
    row = await db.fetch_one(
        f"""
        SELECT COUNT(*)::int AS chunk_count
        FROM {VECTORS_TABLE}
        WHERE user_id = $1 AND document_id = $2
        """,
        user_id,
        document_id,
        conn=conn,
    )
    if row is None:
        return 0
    return int(row["chunk_count"])


async def search_similar(
    query_embedding: list[float],
    user_id: str,
    document_id: Optional[str] = None,
    limit: int = 5,
    conn: Optional[asyncpg.Connection] = None,
) -> list[dict[str, Any]]:
    """Return the top-k cosine-similar chunks for one document, or all of a user's docs."""
    vector = embedding_literal(query_embedding)
    stored_id = (document_id or "").strip() or None
    if stored_id is None:
        rows = await db.fetch_all(
            f"""
            SELECT document_id, content, 1 - (embedding <=> $1::vector) AS similarity
            FROM {VECTORS_TABLE}
            WHERE user_id = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            vector,
            user_id,
            limit,
            conn=conn,
        )
        return [_chunk_row(row) for row in rows]
    rows = await db.fetch_all(
        f"""
        SELECT document_id, content, 1 - (embedding <=> $1::vector) AS similarity
        FROM {VECTORS_TABLE}
        WHERE user_id = $2 AND document_id = $3
        ORDER BY embedding <=> $1::vector
        LIMIT $4
        """,
        vector,
        user_id,
        stored_id,
        limit,
        conn=conn,
    )
    return [_chunk_row(row) for row in rows]
