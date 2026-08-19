from fastapi import APIRouter, Depends, Path

from deps import verify_internal_api_key
from models.llm import (
    ChatRequest,
    ChatResponse,
    SessionClearResponse,
)
import services.llm_service as llm_service

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        500: {"description": "INTERNAL_API_KEY or LLM_MODEL not configured on server"},
        502: {"description": "LLM vendor request failed"},
    },
)


@router.post(
    "/chat",
    tags=["Chat"],
    summary="Stateful chat completion (per-user history, last 20 messages)",
    response_model=ChatResponse,
)
async def create_chat(request: ChatRequest) -> ChatResponse:
    return await llm_service.chat(request)


@router.delete(
    "/chat/{user_id}",
    tags=["Chat"],
    summary="Clear stored conversation history for a user",
    response_model=SessionClearResponse,
)
async def clear_user_chat(
    user_id: str = Path(..., description="User UUID whose session should be cleared"),
) -> SessionClearResponse:
    await llm_service.clear_session(user_id)
    return SessionClearResponse(
        user_id=user_id,
        message="Conversation history cleared",
    )
