from datetime import date

from sqlalchemy import case
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, or_, select

from app.models import Task, TaskAssignee, User


def _apply_visibility_scope(statement, *, viewer_user_ids: set[int] | None):
    if viewer_user_ids is None:
        return statement
    if not viewer_user_ids:
        return statement.where(False)
    participant_scope = sorted(viewer_user_ids)
    linked_assignee_exists = (
        select(TaskAssignee.id)
        .where(
            TaskAssignee.task_id == Task.id,
            TaskAssignee.user_id.in_(participant_scope),
        )
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


def get_calendar_summary(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    project_id: int | None = None,
    department_id: int | None = None,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
):
    overdue_condition = (Task.is_overdue.is_(True)) | (
        (Task.closed_at.is_not(None)) & (Task.closed_at > Task.due_date)
    )
    in_time_condition = ~overdue_condition
    statement = (
        select(
            func.date(Task.due_date).label("day"),
            func.count(Task.id).label("total_count"),
            func.sum(case((overdue_condition, 1), else_=0)).label("overdue_count"),
            func.sum(case((in_time_condition, 1), else_=0)).label("in_time_count"),
            func.sum(case((Task.closed_at.is_not(None), 1), else_=0)).label("closed_count"),
            func.bool_or(Task.is_overdue).label("has_overdue"),
            func.bool_or(Task.computed_deadline_state == "yellow").label("has_yellow"),
        )
        .where(func.date(Task.due_date) >= date_from, func.date(Task.due_date) <= date_to)
        .group_by(func.date(Task.due_date))
        .order_by(func.date(Task.due_date))
    )

    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    elif project_ids is not None:
        if not project_ids:
            return []
        statement = statement.where(Task.project_id.in_(sorted(project_ids)))
    if department_id is not None:
        statement = statement.where(
            select(User.id)
            .where(
                User.id == Task.assignee_id,
                or_(
                    User.department_id == department_id,
                    User.primary_group_id == department_id,
                ),
            )
            .exists()
        )
    statement = _apply_visibility_scope(statement, viewer_user_ids=viewer_user_ids)

    return session.exec(statement).all()


def get_calendar_day_tasks(
    session: Session,
    *,
    day: date,
    project_id: int | None = None,
    department_id: int | None = None,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
) -> list[Task]:
    statement = (
        select(Task)
        .options(
            selectinload(Task.project),
            selectinload(Task.assignee).selectinload(User.department),
            selectinload(Task.assignee).selectinload(User.primary_group),
            selectinload(Task.controller),
            selectinload(Task.workflow_status),
        )
        .where(func.date(Task.due_date) == day)
        .order_by(Task.due_date.asc(), Task.id.asc())
    )
    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    elif project_ids is not None:
        if not project_ids:
            return []
        statement = statement.where(Task.project_id.in_(sorted(project_ids)))
    if department_id is not None:
        statement = statement.where(
            select(User.id)
            .where(
                User.id == Task.assignee_id,
                or_(
                    User.department_id == department_id,
                    User.primary_group_id == department_id,
                ),
            )
            .exists()
        )
    statement = _apply_visibility_scope(statement, viewer_user_ids=viewer_user_ids)
    return session.exec(statement).all()


def get_calendar_tasks_in_range(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    project_id: int | None = None,
    department_id: int | None = None,
    project_ids: set[int] | None = None,
    participant_user_id: int | None = None,
    viewer_user_ids: set[int] | None = None,
) -> list[Task]:
    statement = (
        select(Task)
        .options(
            selectinload(Task.project),
            selectinload(Task.assignee).selectinload(User.department),
            selectinload(Task.assignee).selectinload(User.primary_group),
            selectinload(Task.controller),
            selectinload(Task.workflow_status),
        )
        .where(func.date(Task.due_date) >= date_from, func.date(Task.due_date) <= date_to)
        .order_by(Task.due_date.asc(), Task.id.asc())
    )
    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    elif project_ids is not None:
        if not project_ids:
            return []
        statement = statement.where(Task.project_id.in_(sorted(project_ids)))
    if department_id is not None:
        statement = statement.where(
            select(User.id)
            .where(
                User.id == Task.assignee_id,
                or_(
                    User.department_id == department_id,
                    User.primary_group_id == department_id,
                ),
            )
            .exists()
        )
    if participant_user_id is not None:
        participant_assignee_exists = (
            select(TaskAssignee.id)
            .where(
                TaskAssignee.task_id == Task.id,
                TaskAssignee.user_id == participant_user_id,
            )
            .exists()
        )
        statement = statement.where(
            or_(
                Task.creator_id == participant_user_id,
                Task.assignee_id == participant_user_id,
                Task.controller_id == participant_user_id,
                participant_assignee_exists,
            )
        )
    statement = _apply_visibility_scope(statement, viewer_user_ids=viewer_user_ids)
    return session.exec(statement).all()
