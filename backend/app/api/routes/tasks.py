from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Project, Task, TaskAttachment, TaskComment, TaskDeadlineState, TaskHistory, User
from app.repositories import tasks as task_repo
from app.schemas.task import (
    TaskCloseRequest,
    TaskCreate,
    TaskHistoryListPublic,
    TaskHistoryPublic,
    TaskPublic,
    TasksPublic,
    TaskUpdate,
)
from app.services import rbac_service, task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _display_user_name(user_id: int | None, full_name: str | None, email: str | None) -> str | None:
    if user_id is None:
        return None
    if full_name:
        return full_name
    if email:
        return email
    return f"User #{user_id}"


def resolve_pagination(
    *,
    skip: int,
    limit: int,
    page: int | None,
    page_size: int | None,
) -> tuple[int, int, int, int]:
    resolved_page_size = page_size or limit
    if page is not None:
        resolved_skip = (page - 1) * resolved_page_size
        resolved_page = page
    else:
        resolved_skip = skip
        resolved_page = (resolved_skip // resolved_page_size) + 1
    return resolved_skip, resolved_page_size, resolved_page, resolved_page_size


def to_task_public(task: Task) -> TaskPublic:
    closed_overdue = bool(task.closed_at and task.closed_at > task.due_date)
    deadline_state = task.computed_deadline_state
    if task.closed_at:
        deadline_state = TaskDeadlineState.RED if closed_overdue else TaskDeadlineState.GREEN
    assignee_pairs: list[tuple[int, str]] = []
    if task.task_assignees:
        for link in task.task_assignees:
            if link.user_id is None:
                continue
            assignee_pairs.append(
                (
                    int(link.user_id),
                    _display_user_name(
                        link.user_id,
                        link.user.full_name if link.user is not None else None,
                        link.user.email if link.user is not None else None,
                    )
                    or f"User #{link.user_id}",
                )
            )
    elif task.assignee_id is not None:
        assignee_pairs.append(
            (
                int(task.assignee_id),
                _display_user_name(
                    task.assignee_id,
                    task.assignee.full_name if task.assignee is not None else None,
                    task.assignee.email if task.assignee is not None else None,
                )
                or f"User #{task.assignee_id}",
            )
        )
    # Keep stable order and uniqueness by id.
    seen_assignee_ids: set[int] = set()
    assignee_ids: list[int] = []
    assignee_names: list[str] = []
    for assignee_id, assignee_name in assignee_pairs:
        if assignee_id in seen_assignee_ids:
            continue
        seen_assignee_ids.add(assignee_id)
        assignee_ids.append(assignee_id)
        assignee_names.append(assignee_name)

    data = TaskPublic.model_validate(task)
    return data.model_copy(
        update={
            "status_name": task.workflow_status.name if task.workflow_status is not None else None,
            "workflow_status_name": (
                task.workflow_status.name if task.workflow_status is not None else None
            ),
            "project_name": task.project.name if task.project is not None else None,
            "assignee_name": _display_user_name(
                task.assignee_id,
                task.assignee.full_name if task.assignee is not None else None,
                task.assignee.email if task.assignee is not None else None,
            ),
            "assignee_ids": assignee_ids,
            "assignee_names": assignee_names,
            "department_name": (
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
            "controller_name": _display_user_name(
                task.controller_id,
                task.controller.full_name if task.controller is not None else None,
                task.controller.email if task.controller is not None else None,
            ),
            "deadline_state": deadline_state,
            "computed_deadline_state": deadline_state,
            "closed_overdue": closed_overdue,
        }
    )


@router.get("/", response_model=TasksPublic)
def read_tasks(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=500),
    search: str | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
    controller_id: int | None = None,
    workflow_status_id: int | None = None,
    deadline_state: TaskDeadlineState | None = None,
    include_completed: bool = Query(default=False),
    due_date_from: datetime | None = None,
    due_date_to: datetime | None = None,
    overdue_only: bool | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> TasksPublic:
    resolved_skip, resolved_limit, resolved_page, resolved_page_size = resolve_pagination(
        skip=skip,
        limit=limit,
        page=page,
        page_size=page_size,
    )
    can_view_all = rbac_service.is_system_admin(current_user)
    accessible_project_ids = rbac_service.get_accessible_project_ids(session, user=current_user)
    viewer_user_ids = (
        None
        if can_view_all
        else rbac_service.get_task_viewer_user_ids(
            session,
            user=current_user,
            project_ids=accessible_project_ids,
        )
    )

    tasks, total = task_repo.list_tasks(
        session,
        skip=resolved_skip,
        limit=resolved_limit,
        search=search,
        project_id=project_id,
        department_id=department_id,
        assignee_id=assignee_id,
        controller_id=controller_id,
        workflow_status_id=workflow_status_id,
        deadline_state=deadline_state,
        include_completed=include_completed,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        overdue_only=overdue_only,
        sort_by=sort_by,
        sort_order=sort_order,
        viewer_user_ids=viewer_user_ids,
        can_view_all=can_view_all,
        accessible_project_ids=accessible_project_ids if not can_view_all else None,
    )

    tasks_public = [to_task_public(t) for t in tasks]
    task_ids = [task.id for task in tasks if task.id is not None]
    last_activity_map = task_repo.get_last_activity_map(session, task_ids=task_ids)
    for item in tasks_public:
        activity = last_activity_map.get(item.id)
        if activity is None:
            item.last_activity_at = item.updated_at
            item.last_activity_by = item.assignee_name or item.controller_name
        else:
            item.last_activity_at = activity[0]
            item.last_activity_by = activity[2]
    return TasksPublic(
        data=tasks_public,
        count=len(tasks_public),
        total=total,
        page=resolved_page,
        page_size=resolved_page_size,
    )


@router.post("/", response_model=TaskPublic)
def create_task(
    session: SessionDep,
    current_user: CurrentUser,
    payload: TaskCreate,
) -> TaskPublic:
    project = session.get(Project, payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rbac_service.require_project_task_create(
        session,
        project_id=payload.project_id,
        user=current_user,
    )

    created = task_service.create_task(
        session,
        project=project,
        creator=current_user,
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        assignee_ids=payload.assignee_ids,
        controller_id=payload.controller_id,
        due_date=payload.due_date,
    )

    return to_task_public(created)


@router.get("/{task_id}", response_model=TaskPublic)
def read_task(task_id: int, session: SessionDep, current_user: CurrentUser) -> TaskPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    payload = to_task_public(task)
    activity = task_repo.get_last_activity_map(session, task_ids=[task_id]).get(task_id)
    if activity is None:
        payload.last_activity_at = payload.updated_at
        payload.last_activity_by = payload.assignee_name or payload.controller_name
    else:
        payload.last_activity_at = activity[0]
        payload.last_activity_by = activity[2]
    return payload


@router.patch("/{task_id}", response_model=TaskPublic)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> TaskPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    project = session.get(Project, task.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    participant_ids = rbac_service.get_task_participant_user_ids(session, task=task)
    is_participant = current_user.id in participant_ids
    can_control_task = task_service.can_complete_task(
        session,
        task=task,
        actor=current_user,
    )

    if not is_participant and not can_control_task:
        rbac_service.require_project_controller_or_manager(
            session,
            project_id=task.project_id,
            user=current_user,
        )

    updated = task_service.update_task(
        session,
        task=task,
        actor=current_user,
        project=project,
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        assignee_ids=(
            payload.assignee_ids if "assignee_ids" in payload.model_fields_set else None
        ),
        controller_id=payload.controller_id,
        due_date=payload.due_date,
        workflow_status_id=payload.workflow_status_id,
    )
    return to_task_public(updated)


@router.post("/{task_id}/submit-review", response_model=TaskPublic)
def submit_task_for_review(
    task_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> TaskPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = session.get(Project, task.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    assignee_ids = {
        int(link.user_id)
        for link in task.task_assignees
        if link.user_id is not None
    }
    if not assignee_ids and task.assignee_id is not None:
        assignee_ids.add(int(task.assignee_id))
    if current_user.id not in assignee_ids:
        raise HTTPException(
            status_code=403,
            detail="Отправить задачу на проверку может только исполнитель",
        )
    if task_service.can_complete_task(session, task=task, actor=current_user):
        raise HTTPException(
            status_code=403,
            detail="Контроллер отправляет задачу сразу через проверку/завершение",
        )
    has_comment = session.exec(
        select(func.count())
        .select_from(TaskComment)
        .where(TaskComment.task_id == task_id)
    ).one()
    has_attachment = session.exec(
        select(func.count())
        .select_from(TaskAttachment)
        .where(TaskAttachment.task_id == task_id)
    ).one()
    if int(has_comment) <= 0 and int(has_attachment) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Для отправки на проверку нужен комментарий или вложение",
        )
    updated = task_service.submit_task_for_review(
        session,
        task=task,
        actor=current_user,
        project=project,
    )
    return to_task_public(updated)


@router.post("/{task_id}/complete", response_model=TaskPublic)
def complete_task(
    task_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> TaskPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    project = session.get(Project, task.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not task_service.can_complete_task(session, task=task, actor=current_user):
        raise HTTPException(
            status_code=403,
            detail="Только контроллер группы или superadmin могут завершить задачу",
        )
    updated = task_service.complete_task(
        session,
        task=task,
        actor=current_user,
        project=project,
    )
    return to_task_public(updated)


@router.post("/{task_id}/close", response_model=TaskPublic)
def close_task(
    task_id: int,
    payload: TaskCloseRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> TaskPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    project = session.get(Project, task.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if (
        not rbac_service.is_system_admin(current_user)
        and task.assignee_id != current_user.id
        and task.controller_id != current_user.id
    ):
        rbac_service.require_project_controller_or_manager(
            session,
            project_id=task.project_id,
            user=current_user,
        )

    closed = task_service.close_task(
        session,
        task=task,
        actor=current_user,
        project=project,
        close_comment=payload.comment,
        attachment_ids=payload.attachment_ids,
    )
    return to_task_public(closed)


@router.get("/{task_id}/history", response_model=TaskHistoryListPublic)
def read_task_history(
    task_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> TaskHistoryListPublic:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not rbac_service.can_view_task(session, task=task, user=current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    count = session.exec(
        select(func.count()).select_from(TaskHistory).where(TaskHistory.task_id == task_id)
    ).one()
    history = session.exec(
        select(TaskHistory)
        .where(TaskHistory.task_id == task_id)
        .order_by(TaskHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    actor_ids = sorted({int(item.actor_id) for item in history if item.actor_id is not None})
    actor_rows = (
        session.exec(select(User.id, User.full_name, User.email).where(User.id.in_(actor_ids))).all()
        if actor_ids
        else []
    )
    actor_name_by_id = {
        row[0]: (row[1] or row[2] or f"User #{row[0]}")
        for row in actor_rows
    }

    return TaskHistoryListPublic(
        data=[
            TaskHistoryPublic.model_validate(h).model_copy(
                update={"actor_name": actor_name_by_id.get(h.actor_id)}
            )
            for h in history
        ],
        count=count,
    )


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    task = task_repo.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    rbac_service.require_project_controller_or_manager(
        session,
        project_id=task.project_id,
        user=current_user,
    )

    task_repo.delete_task(session, task)
    return {"message": "Task deleted successfully"}
