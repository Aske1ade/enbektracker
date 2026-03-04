from datetime import date

from sqlmodel import SQLModel


class ReportTaskFilters(SQLModel):
    date_from: date | None = None
    date_to: date | None = None
    project_id: int | None = None
    department_id: int | None = None
    assignee_id: int | None = None
    workflow_status_id: int | None = None
    overdue_only: bool = False


class ReportTaskRow(SQLModel):
    task_id: int
    title: str
    project_name: str
    assignee_name: str | None
    department_name: str
    status_name: str
    due_date: str
    is_overdue: bool
    closed_at: str | None
    closed_overdue: bool
    days_overdue: int


class DisciplineRow(SQLModel):
    department_name: str
    project_name: str
    assignee_name: str
    task_title: str
    due_date: str
    closed_at: str | None
    days_overdue: int


class DisciplineRowsPublic(SQLModel):
    data: list[DisciplineRow]
    count: int
