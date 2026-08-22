import asyncio
import logging
import os
from typing import Any, Optional

from fastapi import HTTPException, status

from constant import (
    DOC_CHAT_MODEL,
    DOC_CHUNK_CHARS,
    DOC_CHUNK_OVERLAP,
    DOC_ALL_DOCS_TOP_K,
    DOC_CONTEXT_MAX_CHARS,
    DOC_MAX_INDEXED_FILES,
    DOC_MAX_INGESTS_PER_WEEK,
    DOC_MAX_QUERY_CHARS,
    DOC_NOT_FOUND_ANSWER,
    DOC_RAG_SYSTEM_PROMPT,
    DOC_TOP_K,
)
from database_client import db
from db_logics import ingest_events_db_logic as ingest_events_db
from db_logics import vectors_db_logic as vectors_db
from embedding_client import EmbeddingClient
from llm_guard import guarded_user_message
from llm_limits import ask_limiter, ingest_limiter
from llm_provider_client import LLMProviderClient
from models.docs import (
    AskResponse,
    DeleteVectorsResponse,
    IngestResponse,
    PurgeUserResponse,
)
from object_storage_client import ObjectStorageClient, ObjectStorageError, is_placeholder_key
from object_storage_client.util import normalize_key
from services.chunker import chunk_extracted_document
from services.pdf_extractor import PdfExtractError, extract_pdf_blocks

logger = logging.getLogger(__name__)

BUCKET: str = os.getenv("S3_BUCKET_USER_DOCUMENTS", "users_personal_documents")
storage = ObjectStorageClient(bucket=BUCKET)


def _embedding_client() -> EmbeddingClient:
    return EmbeddingClient()


def _llm_client() -> LLMProviderClient:
    return LLMProviderClient(model=DOC_CHAT_MODEL)


def _normalize_document_id(document_id: str) -> str:
    relative = document_id.strip().replace("\\", "/").lstrip("/")
    if not relative:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "document_id must not be empty")
    return relative


def _require_user_id(user_id: str) -> str:
    uid = user_id.strip()
    if not uid or "/" in uid or "\\" in uid or uid in {".", ".."}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid user_id")
    return uid


def document_storage_key(user_id: str, document_id: str) -> tuple[str, str]:
    """Build the tenant-scoped S3 key and the stored document_id."""
    uid = _require_user_id(user_id)

    relative = _normalize_document_id(document_id)
    try:
        key = normalize_key(f"{uid}/{relative}")
    except ObjectStorageError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid document path") from exc

    prefix = f"{uid}/"
    if not key.startswith(prefix) or key == uid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid document path")
    if is_placeholder_key(key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid document path")
    return key, key[len(prefix) :]


async def resolve_document_key(
    user_id: str,
    document_id: str,
    *,
    require_object: bool,
) -> tuple[str, str]:
    """Resolve a document path to the real S3 key, ignoring filename case."""
    key, stored_id = document_storage_key(user_id, document_id)
    uid = user_id.strip()
    prefix = f"{uid}/"
    try:
        if await storage.exists(key):
            return key, stored_id
        objects = await storage.list_objects(prefix)
    except ObjectStorageError as exc:
        logger.exception("Failed to stat document %s", key)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to reach document storage",
        ) from exc

    target = stored_id.casefold()
    matches: list[str] = []
    for obj in objects:
        if is_placeholder_key(obj.key):
            continue
        relative = obj.key[len(prefix) :] if obj.key.startswith(prefix) else obj.key
        if relative.casefold() == target:
            matches.append(relative)

    if len(matches) == 1:
        resolved = matches[0]
        return f"{prefix}{resolved}", resolved
    if len(matches) > 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Document path is ambiguous",
        )
    if require_object:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return key, stored_id


def _join_chunks(contents: list[str]) -> str:
    joined = "\n\n---\n\n".join(item.strip() for item in contents if item.strip())
    if len(joined) <= DOC_CONTEXT_MAX_CHARS:
        return joined
    return joined[:DOC_CONTEXT_MAX_CHARS]


def _join_chunk_matches(matches: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in matches:
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        document_id = str(row.get("document_id") or "").strip()
        if document_id:
            parts.append(f"Source document: {document_id}\n{content}")
        else:
            parts.append(content)
    return _join_chunks(parts)


async def _count_user_s3_files(user_id: str) -> int:
    """How many real files the user currently has in object storage."""
    try:
        objects = await storage.list_objects(f"{user_id}/")
    except ObjectStorageError as exc:
        logger.exception("Failed to list documents for %s", user_id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to reach document storage",
        ) from exc
    return len(objects)


async def _assert_ingest_quotas(user_id: str) -> None:
    """Reject ingest when S3 is over 10 files or the weekly quota row is at 20."""
    stored_files = await _count_user_s3_files(user_id)
    if stored_files > DOC_MAX_INDEXED_FILES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            (
                f"Document limit reached. You can index up to "
                f"{DOC_MAX_INDEXED_FILES} documents at a time."
            ),
        )

    try:
        weekly, first_ingest = await ingest_events_db.current_period_usage(
            user_id
        )
    except Exception as exc:
        logger.exception("Failed to read weekly ingest quota for %s", user_id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to check document ingest limits",
        ) from exc

    if weekly >= DOC_MAX_INGESTS_PER_WEEK:
        retry_after = ingest_events_db.retry_after_seconds(first_ingest)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            (
                f"Weekly ingest limit reached. You can ingest up to "
                f"{DOC_MAX_INGESTS_PER_WEEK} documents per week."
            ),
            headers={"Retry-After": str(retry_after)},
        )


async def ingest_document(user_id: str, document_id: str) -> IngestResponse:
    """Download a user's PDF, embed its chunks, and replace stored vectors."""
    key, stored_id = await resolve_document_key(
        user_id,
        document_id,
        require_object=True,
    )
    uid = user_id.strip()
    await _assert_ingest_quotas(uid)
    ingest_limiter.consume(uid)

    try:
        pdf_bytes = await storage.download_bytes(key)
    except ObjectStorageError as exc:
        logger.exception("Failed to download document %s", key)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to download document",
        ) from exc

    try:
        blocks = await asyncio.to_thread(extract_pdf_blocks, pdf_bytes)
    except PdfExtractError as exc:
        message = str(exc)
        if message == "PDF contains no extractable text":
            raise HTTPException(status.HTTP_404_NOT_FOUND, message) from exc
        raise HTTPException(status.HTTP_400_BAD_REQUEST, message) from exc

    document_name = stored_id.rsplit("/", 1)[-1]
    chunks = chunk_extracted_document(
        blocks,
        document_name,
        DOC_CHUNK_CHARS,
        DOC_CHUNK_OVERLAP,
    )
    if not chunks:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "PDF contains no extractable text",
        )

    try:
        embeddings = await _embedding_client().embed_texts(chunks)
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Embedding failed for %s", key)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    rows: list[tuple[int, str, list[float]]] = [
        (index, content, vector)
        for index, (content, vector) in enumerate(zip(chunks, embeddings))
    ]
    try:
        async with db.transaction() as conn:
            await vectors_db.delete_document_vectors(uid, stored_id, conn=conn)
            await vectors_db.insert_chunks(uid, stored_id, rows, conn=conn)
            await ingest_events_db.record_successful_ingest(uid, conn=conn)
    except Exception as exc:
        logger.exception("Failed to store vectors for %s", key)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to store document vectors",
        ) from exc

    return IngestResponse(
        user_id=uid,
        document_id=stored_id,
        chunk_count=len(rows),
    )


async def ask_document(
    query: str,
    user_id: str,
    document_id: Optional[str] = None,
) -> AskResponse:
    """Answer a question using chunks from one document, or all of the user's documents."""
    uid = user_id.strip()
    question = query.strip()[:DOC_MAX_QUERY_CHARS]
    if not uid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id must not be empty")
    if not question:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "query must not be empty")

    stored_id: Optional[str] = None
    requested_id = (document_id or "").strip()
    if requested_id:
        _key, stored_id = await resolve_document_key(
            uid,
            requested_id,
            require_object=False,
        )
    ask_limiter.consume(uid)
    search_limit = DOC_TOP_K if stored_id else DOC_ALL_DOCS_TOP_K
    scope = stored_id or "*"

    try:
        query_vector = await _embedding_client().embed_query(question)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Query embedding failed for %s / %s", uid, scope)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    try:
        matches = await vectors_db.search_similar(
            query_vector,
            uid,
            stored_id,
            limit=search_limit,
        )
    except Exception as exc:
        logger.exception("Vector search failed for %s / %s", uid, scope)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to search document vectors",
        ) from exc

    corpus = _join_chunk_matches(matches)
    if not corpus:
        return AskResponse(answer=DOC_NOT_FOUND_ANSWER)

    user_message = guarded_user_message(
        "Answer the query using only the document excerpts.",
        ("USER_QUERY", question),
        ("DOCUMENT_EXCERPTS", corpus),
    )
    try:
        llm = _llm_client()
        result = await llm.chat_completion(
            [
                {"role": "system", "content": DOC_RAG_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=llm._default_max_tokens(),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Doc RAG LLM failed for %s / %s", uid, scope)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    answer = result.content.strip()
    if not answer:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "LLM returned an empty answer")
    return AskResponse(answer=answer)


async def delete_document_vectors(user_id: str, document_id: str) -> DeleteVectorsResponse:
    """Drop stored vectors for a document after the PDF is removed."""
    uid = user_id.strip()
    _key, stored_id = await resolve_document_key(
        uid,
        document_id,
        require_object=False,
    )
    try:
        deleted = await vectors_db.delete_document_vectors(uid, stored_id)
    except Exception as exc:
        logger.exception("Failed to delete vectors for %s / %s", uid, stored_id)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to delete document vectors",
        ) from exc
    return DeleteVectorsResponse(
        user_id=uid,
        document_id=stored_id,
        deleted_chunks=deleted,
    )


async def purge_user(user_id: str) -> PurgeUserResponse:
    """Drop every vector chunk and the ingest quota row for one user."""
    uid = _require_user_id(user_id)
    try:
        async with db.transaction() as conn:
            deleted_chunks = await vectors_db.delete_user_vectors(uid, conn=conn)
            quota_deleted = await ingest_events_db.delete_user_quota(uid, conn=conn)
    except Exception as exc:
        logger.exception("Failed to purge document data for %s", uid)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Failed to delete user document index",
        ) from exc
    return PurgeUserResponse(
        user_id=uid,
        deleted_chunks=deleted_chunks,
        quota_deleted=quota_deleted,
    )
