from datetime import date

from sqlalchemy import Date, case
from sqlalchemy.orm import aliased
from sqlmodel import Session, func, or_, select

from app.models import Department, OrgGroup, Project, ProjectStatus, Task, TaskAssignee, User


def _apply_project_scope(statement, project_ids: set[int] | None):
    if project_ids is None:
        return statement
    if not project_ids:
        return statement.where(False)
    return statement.where(Task.project_id.in_(sorted(project_ids)))


def _apply_task_visibility_scope(statement, viewer_user_ids: set[int] | None):
    if viewer_user_ids is None:
        return statement
    if not viewer_user_ids:
        return statement.where(False)
    participant_scope = sorted(viewer_user_ids)
    linked_assignee = aliased(TaskAssignee)
    linked_assignee_exists = (
        select(linked_assignee.id)
        .where(
            linked_assignee.task_id == Task.id,
            linked_assignee.user_id.in_(participant_scope),
        )
        .correlate(Task)
        .exists()
    )
    return statement.where(
        or_(
            Task.creator_id.in_(participant_scope),
            Task.assignee_id.in_(participant_scope),
            Task.controller_id.in_(participant_scope),
            linked_assignee_exists,
        )
    )


def get_total_tasks(
    session: Session,
    *,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> int:
    statement = select(func.count()).select_from(Task).where(Task.closed_at.is_(None))
    statement = _apply_project_scope(statement, project_ids)
    statement = _apply_task_visibility_scope(statement, viewer_user_ids)
    return session.exec(statement).one()


def get_deadline_metrics(
    session: Session,
    *,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> dict[str, int]:
    overdue_open = (Task.closed_at.is_(None)) & (Task.is_overdue.is_(True))
    closed_overdue = (Task.closed_at.is_not(None)) & (Task.closed_at > Task.due_date)
    closed_in_time = (Task.closed_at.is_not(None)) & (Task.closed_at <= Task.due_date)
    in_time_open = (Task.closed_at.is_(None)) & (Task.is_overdue.is_(False))

    statement = select(
        func.sum(case((in_time_open, 1), else_=0)).label("in_time_open"),
        func.sum(case((overdue_open, 1), else_=0)).label("overdue_open"),
        func.sum(case((closed_in_time, 1), else_=0)).label("closed_in_time"),
        func.sum(case((closed_overdue, 1), else_=0)).label("closed_overdue"),
    ).select_from(Task)
    statement = _apply_project_scope(statement, project_ids)
    statement = _apply_task_visibility_scope(statement, viewer_user_ids)
    row = session.exec(statement).one()
    return {
        "in_time_open": row[0] or 0,
        "overdue_open": row[1] or 0,
        "closed_in_time": row[2] or 0,
        "closed_overdue": row[3] or 0,
    }


def get_top_executors(
    session: Session,
    *,
    limit: int = 5,
    overdue_only: bool = False,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> list[tuple[int, str, int]]:
    overdue_condition = (Task.is_overdue.is_(True)) | (
        (Task.closed_at.is_not(None)) & (Task.closed_at > Task.due_date)
    )
    task_count = func.count(func.distinct(Task.id))
    statement = (
        select(
            User.id,
            func.coalesce(User.full_name, User.email),
            task_count,
        )
        .join(TaskAssignee, TaskAssignee.user_id == User.id)
        .join(Task, Task.id == TaskAssignee.task_id)
        .group_by(User.id, User.full_name, User.email)
        .having(task_count > 0)
        .order_by(task_count.desc(), func.coalesce(User.full_name, User.email).asc())
        .limit(limit)
    )
    if overdue_only:
        statement = statement.where(overdue_condition)
    statement = _apply_project_scope(statement, project_ids)
    statement = _apply_task_visibility_scope(statement, viewer_user_ids)
    return session.exec(statement).all()


def get_status_distribution(
    session: Session,
    *,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> list[tuple[int, str | None, str | None, int]]:
    status_key = func.coalesce(
        func.nullif(ProjectStatus.code, ""),
        func.lower(ProjectStatus.name),
    ).label("status_key")
    statement = (
        select(
            func.min(ProjectStatus.id).label("status_id"),
            status_key,
            func.min(ProjectStatus.name).label("status_name"),
            func.count(Task.id).label("task_count"),
        )
        .join(Task, Task.workflow_status_id == ProjectStatus.id)
        .group_by(status_key)
        .having(func.count(Task.id) > 0)
        .order_by(func.count(Task.id).desc(), status_key.asc())
    )
    statement = _apply_project_scope(statement, project_ids)
    statement = _apply_task_visibility_scope(statement, viewer_user_ids)
    return session.exec(statement).all()


def get_department_distribution(
    session: Session,
    *,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> list[tuple[int | None, str, int]]:
    group_id_expr = func.coalesce(OrgGroup.id, Department.id)
    group_name_expr = func.coalesce(OrgGroup.name, Department.name, "Без департамента")
    statement = (
        select(
            group_id_expr,
            group_name_expr,
            func.count(Task.id),
        )
        .join(User, Task.assignee_id == User.id, isouter=True)
        .join(OrgGroup, User.primary_group_id == OrgGroup.id, isouter=True)
        .join(Department, User.department_id == Department.id, isouter=True)
        .group_by(group_id_expr, group_name_expr)
        .having(func.count(Task.id) > 0)
        .order_by(func.count(Task.id).desc(), group_name_expr.asc())
    )
    statement = _apply_project_scope(statement, project_ids)
    statement = _apply_task_visibility_scope(statement, viewer_user_ids)
    return session.exec(statement).all()


def get_project_distribution(
    session: Session,
    *,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> list[tuple[int, str, int]]:
    statement = (
        select(Project.id, Project.name, func.count(Task.id))
        .join(Task, Task.project_id == Project.id)
        .group_by(Project.id, Project.name)
        .having(func.count(Task.id) > 0)
        .order_by(func.count(Task.id).desc(), Project.name.asc())
    )
    if project_ids is not None:
        if not project_ids:
            return []
        statement = statement.where(Project.id.in_(sorted(project_ids)))
    statement = _apply_task_visibility_scope(statement, viewer_user_ids)
    return session.exec(statement).all()


def get_due_trends(
    session: Session,
    *,
    period: str,
    date_from: date,
    date_to: date,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> list[tuple[date, int, int, int, int, int]]:
    bucket = func.date_trunc(period, Task.due_date).cast(Date).label("bucket_start")
    overdue_condition = (Task.is_overdue.is_(True)) | (
        (Task.closed_at.is_not(None)) & (Task.closed_at > Task.due_date)
    )
    closed_condition = Task.closed_at.is_not(None)
    closed_in_time_condition = (Task.closed_at.is_not(None)) & (Task.closed_at <= Task.due_date)

    statement = (
        select(
            bucket,
            func.count(Task.id).label("total_tasks"),
            func.sum(case((~overdue_condition, 1), else_=0)).label("in_time_tasks"),
            func.sum(case((overdue_condition, 1), else_=0)).label("overdue_tasks"),
            func.sum(case((closed_condition, 1), else_=0)).label("closed_tasks"),
            func.sum(case((closed_in_time_condition, 1), else_=0)).label("closed_in_time_tasks"),
        )
        .where(
            func.date(Task.due_date) >= date_from,
            func.date(Task.due_date) <= date_to,
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    statement = _apply_project_scope(statement, project_ids)
    statement = _apply_task_visibility_scope(statement, viewer_user_ids)
    return session.exec(statement).all()
