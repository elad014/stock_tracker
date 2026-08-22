from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="New user message")
    document_id: Optional[str] = Field(
        None,
        min_length=1,
        description="Optional PDF path if the user is viewing a document",
    )
    reset_session: bool = Field(
        False,
        description="Clear stored conversation history before this message",
    )


class ChatResponse(BaseModel):
    content: str
    model: str
