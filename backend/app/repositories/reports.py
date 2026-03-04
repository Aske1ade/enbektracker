from datetime import date

from sqlmodel import Session, func, or_, select

from app.models import Department, OrgGroup, Project, ProjectStatus, Task, TaskAssignee, User


def query_tasks_report(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
    workflow_status_id: int | None = None,
    overdue_only: bool = False,
    project_ids: set[int] | None = None,
    viewer_user_ids: set[int] | None = None,
):
    statement = (
        select(
            Task.id,
            Task.title,
            Project.name,
            func.coalesce(User.full_name, User.email),
            func.coalesce(OrgGroup.name, Department.name, "Без департамента"),
            ProjectStatus.name,
            Task.due_date,
            Task.is_overdue,
            Task.closed_at,
        )
        .join(Project, Task.project_id == Project.id)
        .join(ProjectStatus, Task.workflow_status_id == ProjectStatus.id)
        .join(User, Task.assignee_id == User.id, isouter=True)
        .join(OrgGroup, User.primary_group_id == OrgGroup.id, isouter=True)
        .join(Department, User.department_id == Department.id, isouter=True)
        .order_by(Task.due_date.desc())
    )

    if date_from is not None:
        statement = statement.where(func.date(Task.due_date) >= date_from)
    if date_to is not None:
        statement = statement.where(func.date(Task.due_date) <= date_to)
    if project_id is not None:
        statement = statement.where(Task.project_id == project_id)
    if department_id is not None:
        statement = statement.where(
            or_(
                User.department_id == department_id,
                User.primary_group_id == department_id,
            )
        )
    if assignee_id is not None:
        linked_assignee_exists = (
            select(TaskAssignee.id)
            .where(
                TaskAssignee.task_id == Task.id,
                TaskAssignee.user_id == assignee_id,
            )
            .exists()
        )
        statement = statement.where(
            or_(
                Task.assignee_id == assignee_id,
                linked_assignee_exists,
            )
        )
    if workflow_status_id is not None:
        statement = statement.where(Task.workflow_status_id == workflow_status_id)
    if project_ids is not None:
        if not project_ids:
            return []
        statement = statement.where(Task.project_id.in_(sorted(project_ids)))
    if viewer_user_ids is not None:
        if not viewer_user_ids:
            return []
        participant_scope = sorted(viewer_user_ids)
        linked_assignee_exists = (
            select(TaskAssignee.id)
            .where(
                TaskAssignee.task_id == Task.id,
                TaskAssignee.user_id.in_(participant_scope),
            )
            .exists()
        )
        statement = statement.where(
            or_(
                Task.creator_id.in_(participant_scope),
                Task.assignee_id.in_(participant_scope),
                Task.controller_id.in_(participant_scope),
                linked_assignee_exists,
            )
        )
    if overdue_only:
        statement = statement.where(
            (Task.is_overdue.is_(True))
            | ((Task.closed_at.is_not(None)) & (Task.closed_at > Task.due_date))
        )

    return session.exec(statement).all()
