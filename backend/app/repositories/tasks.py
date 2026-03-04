from datetime import datetime

from sqlalchemy.orm import aliased, selectinload
from sqlmodel import Session, and_, delete, func, or_, select

from app.models import (
    Department,
    DesktopEvent,
    OrgGroup,
    ProjectStatus,
    Project,
    Task,
    TaskDeadlineState,
    TaskAssignee,
    TaskAttachment,
    TaskComment,
    TaskHistory,
    User,
)


def list_tasks(
    session: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
    controller_id: int | None = None,
    workflow_status_id: int | None = None,
    due_date_from: datetime | None = None,
    due_date_to: datetime | None = None,
    overdue_only: bool | None = None,
    deadline_state: TaskDeadlineState | None = None,
    include_completed: bool = False,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    viewer_user_ids: set[int] | None = None,
    can_view_all: bool = False,
    accessible_project_ids: set[int] | None = None,
) -> tuple[list[Task], int]:
    project_alias = aliased(Project)
    status_alias = aliased(ProjectStatus)
    assignee_alias = aliased(User)
    controller_alias = aliased(User)
    department_alias = aliased(Department)
    group_alias = aliased(OrgGroup)

    statement = select(Task).options(
        selectinload(Task.workflow_status),
        selectinload(Task.project),
        selectinload(Task.assignee).selectinload(User.department),
        selectinload(Task.assignee).selectinload(User.primary_group),
        selectinload(Task.controller),
        selectinload(Task.task_assignees).selectinload(TaskAssignee.user),
    )
    statement = statement.join(project_alias, project_alias.id == Task.project_id, isouter=True)
    statement = statement.join(status_alias, status_alias.id == Task.workflow_status_id, isouter=True)
    statement = statement.join(assignee_alias, assignee_alias.id == Task.assignee_id, isouter=True)
    statement = statement.join(controller_alias, controller_alias.id == Task.controller_id, isouter=True)
    statement = statement.join(
        department_alias, department_alias.id == assignee_alias.department_id, isouter=True
    )
    statement = statement.join(
        group_alias, group_alias.id == assignee_alias.primary_group_id, isouter=True
    )

    count_statement = select(func.count()).select_from(Task)

    filters = []

    if search:
        like = f"%{search.lower()}%"
        filters.append(
            or_(
                func.lower(Task.title).like(like),
                func.lower(Task.description).like(like),
            )
        )
    if project_id is not None:
        filters.append(Task.project_id == project_id)
    if department_id is not None:
        assignee_department_exists = (
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
        filters.append(assignee_department_exists)
    if assignee_id is not None:
        assignee_link_exists = (
            select(TaskAssignee.id)
            .where(
                TaskAssignee.task_id == Task.id,
                TaskAssignee.user_id == assignee_id,
            )
            .exists()
        )
        filters.append(or_(Task.assignee_id == assignee_id, assignee_link_exists))
    if controller_id is not None:
        filters.append(Task.controller_id == controller_id)
    if workflow_status_id is not None:
        filters.append(Task.workflow_status_id == workflow_status_id)
    if due_date_from is not None:
        filters.append(Task.due_date >= due_date_from)
    if due_date_to is not None:
        filters.append(Task.due_date <= due_date_to)
    if overdue_only is not None:
        filters.append(Task.is_overdue.is_(overdue_only))
    if deadline_state is not None:
        filters.append(Task.computed_deadline_state == deadline_state)
    if not include_completed:
        filters.append(Task.closed_at.is_(None))
    if not can_view_all:
        if accessible_project_ids is not None:
            if not accessible_project_ids:
                return [], 0
            filters.append(Task.project_id.in_(sorted(accessible_project_ids)))

        if viewer_user_ids is not None:
            if not viewer_user_ids:
                return [], 0
            participant_scope = sorted(viewer_user_ids)
            participant_conditions = [
                Task.assignee_id.in_(participant_scope),
                Task.creator_id.in_(participant_scope),
                Task.controller_id.in_(participant_scope),
                select(TaskAssignee.id)
                .where(
                    TaskAssignee.task_id == Task.id,
                    TaskAssignee.user_id.in_(participant_scope),
                )
                .exists(),
            ]
            filters.append(or_(*participant_conditions))

    if filters:
        condition = and_(*filters)
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)

    sortable_fields: dict[str, object] = {
        "id": Task.id,
        "title": func.lower(Task.title),
        "due_date": Task.due_date,
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "project_name": func.lower(func.coalesce(project_alias.name, "")),
        "assignee_name": func.lower(
            func.coalesce(assignee_alias.full_name, assignee_alias.email, "")
        ),
        "controller_name": func.lower(
            func.coalesce(controller_alias.full_name, controller_alias.email, "")
        ),
        "department_name": func.lower(
            func.coalesce(group_alias.name, department_alias.name, "")
        ),
        "status_name": func.lower(func.coalesce(status_alias.name, "")),
        "workflow_status_name": func.lower(func.coalesce(status_alias.name, "")),
        "deadline_state": Task.computed_deadline_state,
    }
    sort_column = sortable_fields.get(sort_by, Task.created_at)

    if sort_order == "asc":
        statement = statement.order_by(sort_column.asc(), Task.id.asc())
    else:
        statement = statement.order_by(sort_column.desc(), Task.id.desc())

    count = session.exec(count_statement).one()
    tasks = session.exec(statement.offset(skip).limit(limit)).all()

    return tasks, count


def get_task(session: Session, task_id: int) -> Task | None:
    return session.exec(
        select(Task)
        .options(
            selectinload(Task.workflow_status),
            selectinload(Task.project),
            selectinload(Task.assignee).selectinload(User.department),
            selectinload(Task.assignee).selectinload(User.primary_group),
            selectinload(Task.controller),
            selectinload(Task.task_assignees).selectinload(TaskAssignee.user),
        )
        .where(Task.id == task_id)
    ).first()


def create_task(session: Session, task: Task) -> Task:
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def update_task(session: Session, task: Task) -> Task:
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def delete_task(session: Session, task: Task) -> None:
    session.exec(delete(DesktopEvent).where(DesktopEvent.task_id == task.id))
    session.exec(delete(TaskHistory).where(TaskHistory.task_id == task.id))
    session.exec(delete(TaskComment).where(TaskComment.task_id == task.id))
    session.exec(delete(TaskAttachment).where(TaskAttachment.task_id == task.id))
    session.exec(delete(TaskAssignee).where(TaskAssignee.task_id == task.id))
    session.delete(task)
    session.commit()


def get_last_activity_map(
    session: Session,
    *,
    task_ids: list[int],
) -> dict[int, tuple[datetime | None, int | None, str | None]]:
    if not task_ids:
        return {}

    rows = session.exec(
        select(TaskHistory.task_id, TaskHistory.actor_id, TaskHistory.created_at)
        .where(TaskHistory.task_id.in_(task_ids))
        .order_by(TaskHistory.task_id.asc(), TaskHistory.created_at.desc(), TaskHistory.id.desc())
    ).all()
    latest_by_task: dict[int, tuple[datetime | None, int | None]] = {}
    actor_ids: set[int] = set()
    for task_id, actor_id, created_at in rows:
        if task_id in latest_by_task:
            continue
        latest_by_task[task_id] = (created_at, actor_id)
        if actor_id is not None:
            actor_ids.add(actor_id)

    actor_name_map: dict[int, str] = {}
    if actor_ids:
        user_rows = session.exec(
            select(User.id, User.full_name, User.email).where(User.id.in_(sorted(actor_ids)))
        ).all()
        actor_name_map = {
            row[0]: row[1] or row[2] or f"User #{row[0]}"
            for row in user_rows
        }

    return {
        task_id: (created_at, actor_id, actor_name_map.get(actor_id) if actor_id else None)
        for task_id, (created_at, actor_id) in latest_by_task.items()
    }
