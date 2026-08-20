from fastapi import FastAPI

from internal_docs import disabled_docs_kwargs, mount_protected_docs
from models.llm import HealthResponse
from routers.llm_routes import router as llm_router

API_DESCRIPTION = """
Internal LLM gateway for stock_tracker chat.

News summaries are owned by news-agent via ``llm_provider_client``.
This service keeps stateful chat for the UI.

## Auth
Chat endpoints require header:

`X-Internal-Api-Key: <INTERNAL_API_KEY>`

`/docs`, `/redoc`, and `/openapi.json` require the same key (header, HTTP Basic
password, or `?api_key=`). They are not public.

## Endpoints
- `POST /chat` — stateful UI chat (last 20 messages per `user_id`)
- `DELETE /chat/{user_id}` — clear chat history

## Configuration
- `LLM_MODEL` — default LiteLLM model id
- `LLM_MAX_TOKENS` — default max output tokens
- `LLM_SYSTEM_PROMPT` — default system prompt
- `LLM_SESSION_MAX_MESSAGES` — chat history cap (default: 20)
- Provider keys: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
"""

app = FastAPI(
    title="LLM Service API",
    description=API_DESCRIPTION,
    version="1.0.0",
    **disabled_docs_kwargs(),
    openapi_tags=[
        {
            "name": "Chat",
            "description": "Stateful chat with per-user in-memory history.",
        },
        {
            "name": "Health",
            "description": "Service liveness checks (no API key required).",
        },
    ],
)
app.include_router(llm_router)
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
