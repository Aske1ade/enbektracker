from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.enums import (
    TaskDeadlineState,
    TaskHistoryAction,
    TaskUrgencyState,
)


class TaskBase(SQLModel):
    title: str
    description: str
    project_id: int
    assignee_id: int | None = None
    assignee_ids: list[int] | None = None
    controller_id: int | None = None
    due_date: datetime


class TaskCreate(TaskBase):
    pass


class TaskUpdate(SQLModel):
    title: str | None = None
    description: str | None = None
    assignee_id: int | None = None
    assignee_ids: list[int] | None = None
    controller_id: int | None = None
    due_date: datetime | None = None
    workflow_status_id: int | None = None


class TaskCloseRequest(SQLModel):
    comment: str | None = None
    attachment_ids: list[int] = Field(default_factory=list)


class TaskPublic(TaskBase):
    id: int
    creator_id: int
    workflow_status_id: int
    workflow_status_name: str | None = None
    status_name: str | None = None
    project_name: str | None = None
    assignee_name: str | None = None
    assignee_ids: list[int] = Field(default_factory=list)
    assignee_names: list[str] = Field(default_factory=list)
    department_name: str | None = None
    controller_name: str | None = None
    computed_deadline_state: TaskDeadlineState
    deadline_state: TaskDeadlineState | None = None
    computed_urgency_state: TaskUrgencyState
    is_overdue: bool
    closed_overdue: bool = False
    last_activity_at: datetime | None = None
    last_activity_by: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class TasksPublic(SQLModel):
    data: list[TaskPublic]
    count: int
    total: int | None = None
    page: int | None = None
    page_size: int | None = None


class TaskCommentCreate(SQLModel):
    task_id: int
    comment: str


class TaskCommentUpdate(SQLModel):
    comment: str


class TaskCommentPublic(SQLModel):
    id: int
    task_id: int
    author_id: int
    author_name: str | None = None
    author_email: str | None = None
    comment: str
    created_at: datetime
    updated_at: datetime


class TaskCommentsPublic(SQLModel):
    data: list[TaskCommentPublic]
    count: int


class TaskAttachmentPublic(SQLModel):
    id: int
    task_id: int
    uploaded_by_id: int
    file_name: str
    object_key: str
    content_type: str | None
    size_bytes: int
    created_at: datetime


class TaskAttachmentsPublic(SQLModel):
    data: list[TaskAttachmentPublic]
    count: int


class TaskHistoryPublic(SQLModel):
    id: int
    task_id: int
    actor_id: int
    actor_name: str | None = None
    action: TaskHistoryAction
    field_name: str | None
    old_value: str | None
    new_value: str | None
    created_at: datetime


class TaskHistoryListPublic(SQLModel):
    data: list[TaskHistoryPublic]
    count: int
