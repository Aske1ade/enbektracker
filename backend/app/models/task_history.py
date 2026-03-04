
from datetime import datetime, timezone

from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import TaskHistoryAction, sa_str_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskHistory(SQLModel, table=True):
    __tablename__ = "task_history"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id", nullable=False, index=True)
    actor_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    action: TaskHistoryAction = Field(
        sa_column=Column(sa_str_enum(TaskHistoryAction, "taskhistoryaction"), nullable=False)
    )
    field_name: str | None = Field(default=None, index=True)
    old_value: str | None = None
    new_value: str | None = None
    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    task: "Task" = Relationship(back_populates="history")
    actor: "User" = Relationship(back_populates="task_history_entries")

