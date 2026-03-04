from datetime import datetime

from sqlmodel import SQLModel

from app.models.enums import DesktopEventType


class DesktopEventPublic(SQLModel):
    id: int
    user_id: int
    task_id: int | None = None
    project_id: int | None = None
    event_type: DesktopEventType
    title: str
    message: str
    deeplink: str | None = None
    payload_json: str | None = None
    created_at: datetime


class DesktopEventsPollPublic(SQLModel):
    data: list[DesktopEventPublic]
    next_cursor: int | None = None
    has_more: bool
    server_time: datetime
