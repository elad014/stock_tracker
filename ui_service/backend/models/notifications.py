from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    message: str
    is_read: bool
    created_at: datetime
