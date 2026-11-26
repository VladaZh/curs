import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_id: uuid.UUID | None
    kind: str
    channel: str
    status: str
    next_attempt_at: datetime
    sent_at: datetime | None


class AdminNotificationOut(NotificationOut):
    user_id: uuid.UUID
    attempts: int
    last_error: str | None
