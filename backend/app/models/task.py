
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import (
    TaskDeadlineState,
    TaskUrgencyState,
    sa_str_enum,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Task(SQLModel, table=True):
    __tablename__ = "task"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    description: str

    project_id: int = Field(foreign_key="project.id", nullable=False, index=True)
    assignee_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    creator_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    controller_id: int | None = Field(default=None, foreign_key="user.id", index=True)

    due_date: datetime = Field(nullable=False, index=True)

    workflow_status_id: int = Field(
        foreign_key="project_status.id",
        nullable=False,
        index=True,
    )

    computed_deadline_state: TaskDeadlineState = Field(
        default=TaskDeadlineState.GREEN,
        sa_column=Column(
            sa_str_enum(TaskDeadlineState, "taskdeadlinestate"),
            nullable=False,
        ),
    )
    computed_urgency_state: TaskUrgencyState = Field(
        default=TaskUrgencyState.RESERVE,
        sa_column=Column(
            sa_str_enum(TaskUrgencyState, "taskurgencystate"),
            nullable=False,
        ),
    )
    is_overdue: bool = Field(default=False)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
    closed_at: datetime | None = Field(default=None)

    project: "Project" = Relationship(back_populates="tasks")
    assignee: Optional["User"] = Relationship(
        back_populates="assigned_tasks",
        sa_relationship_kwargs={"foreign_keys": "Task.assignee_id"},
    )
    creator: "User" = Relationship(
        back_populates="created_tasks",
        sa_relationship_kwargs={"foreign_keys": "Task.creator_id"},
    )
    controller: Optional["User"] = Relationship(
        back_populates="controlled_tasks",
        sa_relationship_kwargs={"foreign_keys": "Task.controller_id"},
    )

    workflow_status: "ProjectStatus" = Relationship(back_populates="tasks")
    comments: list["TaskComment"] = Relationship(back_populates="task")
    attachments: list["TaskAttachment"] = Relationship(back_populates="task")
    history: list["TaskHistory"] = Relationship(back_populates="task")
    task_assignees: list["TaskAssignee"] = Relationship(back_populates="task")
