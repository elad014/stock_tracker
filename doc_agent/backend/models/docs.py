from pydantic import BaseModel, Field

from constant import DOC_MAX_QUERY_CHARS


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


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
    document_id: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    answer: str


class DeleteVectorsResponse(BaseModel):
    user_id: str
    document_id: str
    deleted_chunks: int = Field(..., ge=0)


class PurgeUserResponse(BaseModel):
    user_id: str
    deleted_chunks: int = Field(..., ge=0)
    quota_deleted: bool
