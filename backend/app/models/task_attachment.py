
from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskAttachment(SQLModel, table=True):
    __tablename__ = "task_attachment"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", nullable=False, index=True)
    uploaded_by_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    file_name: str
    object_key: str = Field(unique=True, index=True)
    content_type: str | None = None
    size_bytes: int = 0
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    task: "Task" = Relationship(back_populates="attachments")
    uploader: "User" = Relationship(back_populates="task_attachments")


