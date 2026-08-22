from typing import Any

from fastapi import APIRouter, Depends, status

import services.chat_service as chat_service
from deps import get_current_user
from models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a message to the chat agent",
)
async def create_chat(
    req: ChatRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> ChatResponse:
    return await chat_service.send_chat(user, req)
