from typing import Optional

from pydantic import BaseModel, Field

from constant import DOC_MAX_QUERY_CHARS


class IngestRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    document_id: str = Field(
        ...,
        min_length=1,
        description="Path relative to the user's own folder",
        examples=["reports/10k.pdf"],
    )


class IngestResponse(BaseModel):
    user_id: str
    document_id: str
    chunk_count: int = Field(..., ge=0)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=DOC_MAX_QUERY_CHARS)
    user_id: str = Field(..., min_length=1)
    document_id: Optional[str] = Field(
        None,
        min_length=1,
        description="Path relative to the user's folder. Omit to search all of their documents.",
    )


class AskResponse(BaseModel):
    answer: str
    excerpts: list[str] = Field(default_factory=list)


class DeleteVectorsResponse(BaseModel):
    user_id: str
    document_id: str
    deleted_chunks: int = Field(..., ge=0)


class PurgeUserResponse(BaseModel):
    user_id: str
    deleted_chunks: int = Field(..., ge=0)
    quota_deleted: bool
