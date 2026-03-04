from datetime import date, timedelta

from sqlmodel import Session

from app.models import TaskDeadlineState
from app.repositories import calendar as calendar_repo
from app.schemas.calendar import (
    CalendarScope,
    CalendarDayDrilldown,
    CalendarDaySummary,
    CalendarDayTask,
    CalendarSummary,
    CalendarViewBucket,
    CalendarViewMode,
    CalendarViewPublic,
)


def build_calendar_summary(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    project_id: int | None = None,
    department_id: int | None = None,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> CalendarSummary:
    rows = calendar_repo.get_calendar_summary(
        session,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        department_id=department_id,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )

    data: list[CalendarDaySummary] = []
    for row in rows:
        day, total_count, overdue_count, in_time_count, closed_count, has_overdue, has_yellow = row
        if has_overdue:
            state = TaskDeadlineState.RED
        elif has_yellow:
            state = TaskDeadlineState.YELLOW
        else:
            state = TaskDeadlineState.GREEN
        day_state = "red" if overdue_count > in_time_count else "neutral"

        data.append(
            CalendarDaySummary(
                day=day,
                total_count=total_count,
                overdue_count=overdue_count,
                in_time_count=in_time_count,
                closed_count=closed_count,
                day_state=day_state,
                max_deadline_state=state,
            )
        )

    return CalendarSummary(data=data)


def _display_user_name(user_id: int | None, full_name: str | None, email: str | None) -> str | None:
    if user_id is None:
        return None
    if full_name:
        return full_name
    if email:
        return email
    return f"User #{user_id}"


def _to_calendar_day_task(task) -> CalendarDayTask:
    return CalendarDayTask(
        id=task.id,
        title=task.title,
        project_id=task.project_id,
        project_name=task.project.name if task.project is not None else None,
        assignee_id=task.assignee_id,
        assignee_name=_display_user_name(
            task.assignee_id,
            task.assignee.full_name if task.assignee is not None else None,
            task.assignee.email if task.assignee is not None else None,
        ),
        department_name=(
            (
                task.assignee.primary_group.name
                if task.assignee is not None and task.assignee.primary_group is not None
                else (
                    task.assignee.department.name
                    if task.assignee is not None and task.assignee.department is not None
                    else "-"
                )
            )
        ),
        controller_id=task.controller_id,
        controller_name=_display_user_name(
            task.controller_id,
            task.controller.full_name if task.controller is not None else None,
            task.controller.email if task.controller is not None else None,
        ),
        workflow_status_id=task.workflow_status_id,
        status_name=task.workflow_status.name if task.workflow_status is not None else None,
        due_date=task.due_date,
        computed_deadline_state=task.computed_deadline_state,
        is_overdue=task.is_overdue,
        closed_overdue=bool(task.closed_at and task.closed_at > task.due_date),
        closed_at=task.closed_at,
        updated_at=task.updated_at,
    )


def build_calendar_day(
    session: Session,
    *,
    day: date,
    project_id: int | None = None,
    department_id: int | None = None,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> CalendarDayDrilldown:
    tasks = calendar_repo.get_calendar_day_tasks(
        session,
        day=day,
        project_id=project_id,
        department_id=department_id,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    rows = [_to_calendar_day_task(task) for task in tasks if task.id is not None]
    return CalendarDayDrilldown(
        day=day,
        data=rows,
        count=len(rows),
    )


def _resolve_view_range(anchor: date, mode: CalendarViewMode) -> tuple[date, date]:
    if mode == CalendarViewMode.DAY:
        return anchor, anchor
    if mode == CalendarViewMode.WEEK:
        week_start = anchor - timedelta(days=anchor.weekday())
        return week_start, week_start + timedelta(days=6)
    if mode == CalendarViewMode.YEAR:
        year_start = anchor.replace(month=1, day=1)
        year_end = anchor.replace(month=12, day=31)
        return year_start, year_end
    month_start = anchor.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    return month_start, next_month - timedelta(days=1)


def build_calendar_view(
    session: Session,
    *,
    anchor: date,
    mode: CalendarViewMode,
    scope: CalendarScope,
    project_id: int | None = None,
    department_id: int | None = None,
    project_ids: set[int] | None = None,
    viewer_user_id: int | None = None,
    viewer_user_ids: set[int] | None = None,
) -> CalendarViewPublic:
    date_from, date_to = _resolve_view_range(anchor, mode)
    participant_user_id = viewer_user_id if scope == CalendarScope.MY else None
    tasks = calendar_repo.get_calendar_tasks_in_range(
        session,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        department_id=department_id,
        project_ids=project_ids,
        participant_user_id=participant_user_id,
        viewer_user_ids=viewer_user_ids,
    )

    tasks_by_day: dict[date, list[CalendarDayTask]] = {}
    for task in tasks:
        if task.id is None:
            continue
        day = task.due_date.date()
        tasks_by_day.setdefault(day, []).append(_to_calendar_day_task(task))

    buckets: list[CalendarViewBucket] = []
    cursor = date_from
    while cursor <= date_to:
        day_tasks = tasks_by_day.get(cursor, [])
        overdue_count = sum(1 for task in day_tasks if task.is_overdue or task.closed_overdue)
        closed_count = sum(1 for task in day_tasks if task.closed_at is not None)
        total_count = len(day_tasks)
        buckets.append(
            CalendarViewBucket(
                day=cursor,
                total_count=total_count,
                overdue_count=overdue_count,
                in_time_count=max(total_count - overdue_count, 0),
                closed_count=closed_count,
                tasks=day_tasks,
            )
        )
        cursor += timedelta(days=1)

    return CalendarViewPublic(
        mode=mode,
        scope=scope,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        data=buckets,
    )
