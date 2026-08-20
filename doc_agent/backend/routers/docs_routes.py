from fastapi import APIRouter, Depends, Query

from deps import verify_internal_api_key
from models.docs import (
    AskRequest,
    AskResponse,
    DeleteVectorsResponse,
    IngestRequest,
    IngestResponse,
)
import services.doc_service as doc_service

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        429: {"description": "LLM rate limit exceeded"},
        500: {"description": "INTERNAL_API_KEY or model configuration missing"},
        502: {"description": "Upstream storage, embedding, or LLM request failed"},
    },
)


@router.post(
    "/api/v1/docs/upload",
    tags=["Documents"],
    summary="Ingest a stored PDF into the vector index",
    description=(
        "Downloads `{user_id}/{document_id}` from object storage, extracts "
        "markdown (tables kept intact), chunks the full document with section "
        "metadata, embeds each chunk, and replaces stored vectors."
    ),
    response_model=IngestResponse,
    responses={
        400: {"description": "Invalid user_id, document path, or PDF"},
        404: {"description": "Document missing in storage or no extractable text"},
    },
)
async def upload_document(req: IngestRequest) -> IngestResponse:
    return await doc_service.ingest_document(req.user_id, req.document_id)


@router.post(
    "/api/v1/docs/ask",
    tags=["Documents"],
    summary="Answer a question from one tenant document",
    description=(
        "Embeds `query`, retrieves the top matching chunks for `(user_id, document_id)`, "
        "and asks the LLM to answer using only those excerpts."
    ),
    response_model=AskResponse,
    responses={
        400: {"description": "Empty or invalid query, user_id, or document_id"},
    },
)
async def ask_document(req: AskRequest) -> AskResponse:
    return await doc_service.ask_document(req.query, req.user_id, req.document_id)


@router.delete(
    "/api/v1/docs/vectors",
    tags=["Documents"],
    summary="Delete stored vectors for a document",
    description="Removes every chunk for `(user_id, document_id)` after the PDF is deleted.",
    response_model=DeleteVectorsResponse,
    responses={
        400: {"description": "Invalid user_id or document path"},
    },
)
async def delete_document_vectors(
    user_id: str = Query(..., min_length=1, description="Owning user id"),
    document_id: str = Query(
        ...,
        min_length=1,
        description="Path relative to the user's own folder",
    ),
) -> DeleteVectorsResponse:
    return await doc_service.delete_document_vectors(user_id, document_id)
