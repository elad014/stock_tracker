from typing import Any

from fastapi import HTTPException, status

from chat_agent_client import chat_agent_client as chat_agent
from models.chat import ChatRequest, ChatResponse


async def send_chat(user: dict[str, Any], req: ChatRequest) -> ChatResponse:
    payload = await chat_agent.chat(
        user["id"],
        req.message,
        document_id=req.document_id,
        reset_session=req.reset_session,
    )
    if not isinstance(payload, dict):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Chat agent returned an invalid response",
        )
    content = str(payload.get("content") or "").strip()
    if not content:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Chat agent returned an empty answer",
        )
    return ChatResponse(
        content=content,
        model=str(payload.get("model") or ""),
    )
