from datetime import datetime

from sqlmodel import SQLModel

from app.models.enums import NotificationType


class NotificationPublic(SQLModel):
    id: int
    user_id: int
    type: NotificationType
    title: str
    message: str
    payload_json: str | None
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    count: int
