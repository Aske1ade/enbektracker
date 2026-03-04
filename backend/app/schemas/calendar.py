from datetime import date, datetime
from enum import Enum

from sqlmodel import SQLModel

from app.models.enums import TaskDeadlineState


class CalendarDaySummary(SQLModel):
    day: date
    total_count: int
    overdue_count: int
    in_time_count: int
    closed_count: int
    day_state: str
    max_deadline_state: TaskDeadlineState


class CalendarSummary(SQLModel):
    data: list[CalendarDaySummary]


class CalendarDayTask(SQLModel):
    id: int
    title: str
    project_id: int
    project_name: str | None = None
    assignee_id: int | None = None
    assignee_name: str | None = None
    department_name: str | None = None
    controller_id: int | None = None
    controller_name: str | None = None
    workflow_status_id: int
    status_name: str | None = None
    due_date: datetime
    computed_deadline_state: TaskDeadlineState
    is_overdue: bool
    closed_overdue: bool
    closed_at: datetime | None = None
    updated_at: datetime


class CalendarDayDrilldown(SQLModel):
    day: date
    data: list[CalendarDayTask]
    count: int


class CalendarViewMode(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class CalendarScope(str, Enum):
    PROJECT = "project"
    MY = "my"


class CalendarViewBucket(SQLModel):
    day: date
    total_count: int
    overdue_count: int
    in_time_count: int
    closed_count: int
    tasks: list[CalendarDayTask]


class CalendarViewPublic(SQLModel):
    mode: CalendarViewMode
    scope: CalendarScope
    date_from: date
    date_to: date
    project_id: int | None = None
    data: list[CalendarViewBucket]
