
from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskComment(SQLModel, table=True):
    __tablename__ = "task_comment"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", nullable=False, index=True)
    author_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    comment: str
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    task: "Task" = Relationship(back_populates="comments")
    author: "User" = Relationship(back_populates="task_comments")


