from fastapi import APIRouter, Depends, Path

from deps import verify_internal_api_key
from models.chat import ChatRequest, ChatResponse, SessionClearResponse
import services.chat_service as chat_service

router = APIRouter(
    dependencies=[Depends(verify_internal_api_key)],
    responses={
        401: {"description": "Missing or invalid X-Internal-Api-Key"},
        429: {"description": "Chat rate limit exceeded"},
        500: {"description": "INTERNAL_API_KEY or LLM_MODEL not configured on server"},
        502: {"description": "LLM vendor or downstream agent request failed"},
    },
)


@router.post(
    "/api/v1/chat",
    tags=["Chat"],
    summary="Orchestrated chat with stock, news, and document tools",
    response_model=ChatResponse,
)
async def create_chat(request: ChatRequest) -> ChatResponse:
    return await chat_service.chat(request)


@router.post(
    "/chat",
    tags=["Chat"],
    summary="Alias for POST /api/v1/chat",
    response_model=ChatResponse,
    include_in_schema=False,
)
async def create_chat_alias(request: ChatRequest) -> ChatResponse:
    return await chat_service.chat(request)


@router.delete(
    "/api/v1/chat/{user_id}",
    tags=["Chat"],
    summary="Clear stored conversation history for a user",
    response_model=SessionClearResponse,
)
async def clear_user_chat(
    user_id: str = Path(..., description="User UUID whose session should be cleared"),
) -> SessionClearResponse:
    await chat_service.clear_session(user_id)
    return SessionClearResponse(
        user_id=user_id,
        message="Conversation history cleared",
    )


@router.delete(
    "/chat/{user_id}",
    tags=["Chat"],
    summary="Alias for DELETE /api/v1/chat/{user_id}",
    response_model=SessionClearResponse,
    include_in_schema=False,
)
async def clear_user_chat_alias(
    user_id: str = Path(..., description="User UUID whose session should be cleared"),
) -> SessionClearResponse:
    await chat_service.clear_session(user_id)
    return SessionClearResponse(
        user_id=user_id,
        message="Conversation history cleared",
    )
