
from datetime import datetime, timezone

from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import NotificationType, sa_str_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Notification(SQLModel, table=True):
    __tablename__ = "notification"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    type: NotificationType = Field(
        default=NotificationType.SYSTEM,
        sa_column=Column(sa_str_enum(NotificationType, "notificationtype"), nullable=False),
    )
    title: str
    message: str
    payload_json: str | None = None
    is_read: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    read_at: datetime | None = None

    user: "User" = Relationship(back_populates="notifications")

