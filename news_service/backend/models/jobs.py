from pydantic import BaseModel


class JobTriggerResponse(BaseModel):
    job: str
    message: str
