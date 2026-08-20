import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI

from database_client import db
from db_logics.schema_init import ensure_vector_schema
from internal_docs import disabled_docs_kwargs, mount_protected_docs
from models.docs import HealthResponse
from routers.docs_routes import router as docs_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_DESCRIPTION = """
Internal Doc Agent for stock_tracker.

Owns `document_vectors` on the shared Neon database (pgvector). Downloads a
user's PDF from object storage, chunks and embeds it, and answers questions
with Retrieval-Augmented Generation. Every query is scoped to one
`(user_id, document_id)` pair.

## Auth
Document endpoints require header:

`X-Internal-Api-Key: <INTERNAL_API_KEY>`

`/docs`, `/redoc`, and `/openapi.json` require the same key (header, HTTP Basic
password, or `?api_key=`). They are not public.

## Endpoints
1. **Ingest** — `POST /api/v1/docs/upload`: download `{user_id}/{document_id}`
   from object storage, embed chunks, replace stored vectors
2. **Ask** — `POST /api/v1/docs/ask`: tenant-scoped RAG over one document
3. **Cleanup** — `DELETE /api/v1/docs/vectors`: drop vectors when a PDF is removed
"""


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await ensure_vector_schema()
    logger.info("Doc agent ready")
    try:
        yield
    finally:
        await db.close()


app = FastAPI(
    title="Doc Agent API",
    description=API_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    **disabled_docs_kwargs(),
    openapi_tags=[
        {
            "name": "Documents",
            "description": (
                "Ingest a stored PDF into pgvector and answer questions using "
                "only that user's document."
            ),
        },
        {
            "name": "Health",
            "description": "Service liveness checks (no API key required).",
        },
    ],
)
app.include_router(docs_router)
mount_protected_docs(app)


@app.api_route(
    "/",
    methods=["GET", "HEAD"],
    tags=["Health"],
    summary="Root health check",
    response_model=HealthResponse,
    include_in_schema=False,
)
@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    response_model=HealthResponse,
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
