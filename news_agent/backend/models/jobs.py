from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])


class JobTriggerResponse(BaseModel):
    job: str
    message: str
