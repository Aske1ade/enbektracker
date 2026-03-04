from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskAssignee(SQLModel, table=True):
    __tablename__ = "task_assignee"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_task_assignee_task_user"),
    )

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    task: "Task" = Relationship(back_populates="task_assignees")
    user: "User" = Relationship(back_populates="task_assignee_links")

