from datetime import datetime, timezone

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.models.enums import DesktopEventType, sa_str_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DesktopEvent(SQLModel, table=True):
    __tablename__ = "desktop_event"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    task_id: int | None = Field(default=None, foreign_key="task.id", index=True)
    project_id: int | None = Field(default=None, foreign_key="project.id", index=True)
    event_type: DesktopEventType = Field(
        default=DesktopEventType.SYSTEM,
        sa_column=Column(
            sa_str_enum(DesktopEventType, "desktopeventtype"),
            nullable=False,
        ),
    )
    title: str
    message: str
    deeplink: str | None = None
    payload_json: str | None = None
    dedupe_key: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False, index=True)
