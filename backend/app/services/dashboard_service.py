from datetime import date, timedelta

from sqlmodel import Session

from app.repositories import dashboards as dashboard_repo
from app.schemas.dashboard import (
    DashboardDepartmentMetric,
    DashboardDistributions,
    DashboardExecutorMetric,
    DashboardProjectMetric,
    DashboardStatusMetric,
    DashboardSummary,
    DashboardTrendPoint,
    DashboardTrendsPublic,
)

STATUS_CODE_ALIASES: dict[str, str] = {
    "new": "new",
    "todo": "new",
    "не начато": "new",
    "in_progress": "in_progress",
    "in progress": "in_progress",
    "review": "in_progress",
    "testing": "in_progress",
    "в работе": "in_progress",
    "на проверке": "in_progress",
    "на тестировании": "in_progress",
    "blocked": "blocked",
    "rejected": "blocked",
    "заблокировано": "blocked",
    "done": "done",
    "closed": "done",
    "готово": "done",
    "закрыто": "done",
}

STATUS_LABELS: dict[str, str] = {
    "new": "Не начато",
    "in_progress": "В работе",
    "blocked": "Заблокировано",
    "done": "Готово",
}

STATUS_SORT_ORDER: dict[str, int] = {
    "new": 0,
    "in_progress": 1,
    "blocked": 2,
    "done": 3,
}


def _normalize_status_key(raw_key: str | None, raw_name: str | None) -> str:
    key = (raw_key or "").strip().lower()
    if key in STATUS_CODE_ALIASES:
        return STATUS_CODE_ALIASES[key]
    name_key = (raw_name or "").strip().lower()
    if name_key in STATUS_CODE_ALIASES:
        return STATUS_CODE_ALIASES[name_key]
    return key or name_key or "unknown"


def _status_sort_key(status: DashboardStatusMetric) -> tuple[int, str]:
    if status.status_code in STATUS_SORT_ORDER:
        return (STATUS_SORT_ORDER[status.status_code], status.status_name)
    return (100, status.status_name)


def build_dashboard_summary(
    session: Session,
    *,
    top_limit: int = 5,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> DashboardSummary:
    resolved_top_limit = 10 if top_limit == 10 else 5
    total_tasks = dashboard_repo.get_total_tasks(
        session,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    deadline = dashboard_repo.get_deadline_metrics(
        session,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )

    top_executors = [
        DashboardExecutorMetric(user_id=row[0], user_name=row[1], count=row[2])
        for row in dashboard_repo.get_top_executors(
            session,
            limit=resolved_top_limit,
            overdue_only=False,
            project_ids=project_ids,
            viewer_user_ids=viewer_user_ids,
        )
        if row[2] > 0
    ]
    top_overdue_executors = [
        DashboardExecutorMetric(user_id=row[0], user_name=row[1], count=row[2])
        for row in dashboard_repo.get_top_executors(
            session,
            limit=resolved_top_limit,
            overdue_only=True,
            project_ids=project_ids,
            viewer_user_ids=viewer_user_ids,
        )
        if row[2] > 0
    ]

    return DashboardSummary(
        total_tasks=total_tasks,
        deadline_in_time_count=deadline["in_time_open"],
        deadline_overdue_count=deadline["overdue_open"],
        closed_in_time_count=deadline["closed_in_time"],
        closed_overdue_count=deadline["closed_overdue"],
        top_executors=top_executors,
        top_overdue_executors=top_overdue_executors,
    )


def build_dashboard_distributions(
    session: Session,
    *,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> DashboardDistributions:
    status_buckets: dict[str, DashboardStatusMetric] = {}
    for status_id, raw_key, raw_name, count in dashboard_repo.get_status_distribution(
        session,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    ):
        if count <= 0:
            continue
        normalized_key = _normalize_status_key(raw_key, raw_name)
        status_code = normalized_key if normalized_key in STATUS_LABELS else None
        status_name = STATUS_LABELS.get(
            normalized_key,
            raw_name or raw_key or "Без статуса",
        )
        bucket_key = status_code or f"name:{status_name.lower()}"
        existing = status_buckets.get(bucket_key)
        if existing is None:
            status_buckets[bucket_key] = DashboardStatusMetric(
                status_id=status_id,
                status_name=status_name,
                status_code=status_code,
                count=count,
            )
            continue
        existing.count += count
        existing.status_id = min(existing.status_id, status_id)

    statuses = sorted(
        status_buckets.values(),
        key=lambda item: (-item.count, _status_sort_key(item)),
    )
    departments = [
        DashboardDepartmentMetric(department_id=row[0], department_name=row[1], count=row[2])
        for row in dashboard_repo.get_department_distribution(
            session,
            project_ids=project_ids,
            viewer_user_ids=viewer_user_ids,
        )
        if row[2] > 0
    ]
    projects = [
        DashboardProjectMetric(project_id=row[0], project_name=row[1], count=row[2])
        for row in dashboard_repo.get_project_distribution(
            session,
            project_ids=project_ids,
            viewer_user_ids=viewer_user_ids,
        )
        if row[2] > 0
    ]
    return DashboardDistributions(
        statuses=statuses,
        departments=departments,
        projects=projects,
    )


def _normalize_period(period: str) -> str:
    if period not in {"day", "week", "month"}:
        return "week"
    return period


def _align_period_start(value: date, period: str) -> date:
    if period == "week":
        return value - timedelta(days=value.weekday())
    if period == "month":
        return value.replace(day=1)
    return value


def _next_bucket(value: date, period: str) -> date:
    if period == "day":
        return value + timedelta(days=1)
    if period == "week":
        return value + timedelta(days=7)
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1, day=1)
    return value.replace(month=value.month + 1, day=1)


def build_dashboard_trends(
    session: Session,
    *,
    period: str,
    date_from: date,
    date_to: date,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> DashboardTrendsPublic:
    normalized_period = _normalize_period(period)
    rows = dashboard_repo.get_due_trends(
        session,
        period=normalized_period,
        date_from=date_from,
        date_to=date_to,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    rows_map = {
        row[0]: {
            "total_tasks": row[1] or 0,
            "in_time_tasks": row[2] or 0,
            "overdue_tasks": row[3] or 0,
            "closed_tasks": row[4] or 0,
            "closed_in_time_tasks": row[5] or 0,
        }
        for row in rows
    }

    bucket = _align_period_start(date_from, normalized_period)
    end_bucket = _align_period_start(date_to, normalized_period)
    points: list[DashboardTrendPoint] = []
    while bucket <= end_bucket:
        data = rows_map.get(bucket, {})
        points.append(
            DashboardTrendPoint(
                bucket_start=bucket,
                total_tasks=data.get("total_tasks", 0),
                in_time_tasks=data.get("in_time_tasks", 0),
                overdue_tasks=data.get("overdue_tasks", 0),
                closed_tasks=data.get("closed_tasks", 0),
                closed_in_time_tasks=data.get("closed_in_time_tasks", 0),
            )
        )
        bucket = _next_bucket(bucket, normalized_period)

    return DashboardTrendsPublic(
        period=normalized_period,
        date_from=date_from,
        date_to=date_to,
        data=points,
    )
