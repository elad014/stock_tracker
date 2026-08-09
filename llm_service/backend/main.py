from fastapi import FastAPI

from models.llm import HealthResponse
from routers.llm_routes import router as llm_router

API_DESCRIPTION = """
Internal LLM gateway for stock_tracker.

This is the **only** service allowed to talk to LLM vendors via LiteLLM
(`common/llm_provider_client`). Other services must call this gateway over HTTP.

## Auth
All chat/summarize endpoints require header:

`X-Internal-Api-Key: <INTERNAL_API_KEY>`

## Endpoints
- `POST /chat` — stateful UI chat (last 20 messages per `user_id`)
- `DELETE /chat/{user_id}` — clear chat history
- `POST /summarize` — stateless news/text summary

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
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"persistAuthorization": True},
    openapi_tags=[
        {
            "name": "Chat",
            "description": "Stateful chat with per-user in-memory history.",
        },
        {
            "name": "Summarize",
            "description": "Stateless text/news summarization for the news pipeline.",
        },
        {
            "name": "Health",
            "description": "Service liveness checks (no API key required).",
        },
    ],
)
app.include_router(llm_router)


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
