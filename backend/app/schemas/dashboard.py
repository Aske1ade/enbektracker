from datetime import date

from sqlmodel import SQLModel


class DashboardStatusMetric(SQLModel):
    status_id: int
    status_name: str
    status_code: str | None = None
    count: int


class DashboardDepartmentMetric(SQLModel):
    department_id: int | None
    department_name: str
    count: int


class DashboardProjectMetric(SQLModel):
    project_id: int
    project_name: str
    count: int


class DashboardExecutorMetric(SQLModel):
    user_id: int
    user_name: str
    count: int


class DashboardSummary(SQLModel):
    total_tasks: int
    deadline_in_time_count: int
    deadline_overdue_count: int
    closed_in_time_count: int
    closed_overdue_count: int
    top_executors: list[DashboardExecutorMetric]
    top_overdue_executors: list[DashboardExecutorMetric]
    scope_mode: str = "personal"
    can_use_extended_scope: bool = False


class DashboardDistributions(SQLModel):
    statuses: list[DashboardStatusMetric]
    departments: list[DashboardDepartmentMetric]
    projects: list[DashboardProjectMetric]


class DashboardTrendPoint(SQLModel):
    bucket_start: date
    total_tasks: int
    in_time_tasks: int
    overdue_tasks: int
    closed_tasks: int
    closed_in_time_tasks: int


class DashboardTrendsPublic(SQLModel):
    period: str
    date_from: date
    date_to: date
    data: list[DashboardTrendPoint]
