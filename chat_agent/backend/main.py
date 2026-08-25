import logging

from dotenv import load_dotenv
from fastapi import FastAPI

from internal_docs import disabled_docs_kwargs, mount_protected_docs
from routers.chat_routes import router as chat_router
from utils import mount_health

load_dotenv()
logging.basicConfig(level=logging.INFO)

API_DESCRIPTION = """
Internal Chat Agent orchestrator for stock_tracker.

Gathers information only through internal HTTP clients (doc-agent, news-agent,
stock-manager). It does not access a database. LiteLLM tool calling routes
user questions to those agents and synthesizes a conversational reply.

## Auth
Chat endpoints require header:

`X-Internal-Api-Key: <INTERNAL_API_KEY>`

`/docs`, `/redoc`, and `/openapi.json` require the same key (header, HTTP Basic
password, or `?api_key=`). They are not public.

## Endpoints
- `POST /api/v1/chat` — stateful UI chat with tools (last 20 messages per `user_id`)
- `DELETE /api/v1/chat/{user_id}` — clear chat history

## Configuration
- `LLM_MODEL` — default LiteLLM model id
- `LLM_MAX_TOKENS` — default max output tokens
- `LLM_SYSTEM_PROMPT` — extra system prompt appended to the orchestrator prompt
- `LLM_SESSION_MAX_MESSAGES` — chat history cap (default: 20)
- Provider keys: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
"""

app = FastAPI(
    title="Chat Agent API",
    description=API_DESCRIPTION,
    version="1.0.0",
    **disabled_docs_kwargs(),
    openapi_tags=[
        {
            "name": "Chat",
            "description": "Orchestrated chat with per-user in-memory history.",
        },
        {
            "name": "Health",
            "description": "Service liveness checks (no API key required).",
        },
    ],
)
app.include_router(chat_router)
mount_protected_docs(app)
mount_health(app)
