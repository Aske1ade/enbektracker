from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, delete, func, or_, select

from app.models import (
    DesktopEventType,
    GroupMembership,
    NotificationType,
    Project,
    ProjectMember,
    ProjectMemberRole,
    ProjectStatus,
    Task,
    TaskAttachment,
    TaskComment,
    TaskDeadlineState,
    TaskHistoryAction,
    TaskAssignee,
    TaskUrgencyState,
    User,
)
from app.repositories import task_attachments as attachment_repo
from app.repositories import task_comments as comment_repo
from app.repositories import tasks as task_repo
from app.services import (
    audit_service,
    desktop_event_service,
    notification_service,
    rbac_service,
    system_settings_service,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_deadline_flags(
    due_date: datetime,
    *,
    normal_days: int,
    yellow_days: int | None = None,
) -> tuple[TaskDeadlineState, TaskUrgencyState, bool]:
    # `yellow_days` is kept for backward compatibility with legacy tests/callers.
    _ = yellow_days
    now = utcnow()
    delta_days = (due_date.date() - now.date()).days

    if delta_days < 0:
        return TaskDeadlineState.RED, TaskUrgencyState.OVERDUE, True

    if delta_days < normal_days:
        return TaskDeadlineState.YELLOW, TaskUrgencyState.CRITICAL, False

    return TaskDeadlineState.GREEN, TaskUrgencyState.RESERVE, False


def refresh_task_computed_fields(task: Task, project: Project) -> None:
    if task.closed_at:
        closed_overdue = task.closed_at > task.due_date
        if closed_overdue:
            task.computed_deadline_state = TaskDeadlineState.RED
            task.computed_urgency_state = TaskUrgencyState.OVERDUE
            task.is_overdue = True
        else:
            task.computed_deadline_state = TaskDeadlineState.GREEN
            task.computed_urgency_state = TaskUrgencyState.RESERVE
            task.is_overdue = False
        return

    deadline_state, urgency_state, is_overdue = compute_deadline_flags(
        task.due_date,
        normal_days=project.deadline_normal_days,
    )
    task.computed_deadline_state = deadline_state
    task.computed_urgency_state = urgency_state
    task.is_overdue = is_overdue


WORKFLOW_STATUS_IN_PROGRESS = "in_progress"
WORKFLOW_STATUS_REVIEW = "review"
WORKFLOW_STATUS_DONE = "done"
WORKFLOW_STATUS_PRESET = [
    ("В работе", WORKFLOW_STATUS_IN_PROGRESS, "#DD6B20", 0, True, False),
    ("На проверке", WORKFLOW_STATUS_REVIEW, "#2B6CB0", 1, False, False),
    ("Готово", WORKFLOW_STATUS_DONE, "#2F855A", 2, False, True),
]

GROUP_CONTROLLER_ROLE_NAMES = {"controller", "manager", "lead", "owner", "admin"}
LEGACY_CONTROLLER_SYSTEM_ROLES = {
    "system_admin",
    "controller",
    "manager",
    "admin",
}


def _find_status_by_code(session: Session, *, project_id: int, code: str) -> ProjectStatus | None:
    return session.exec(
        select(ProjectStatus)
        .where(ProjectStatus.project_id == project_id, ProjectStatus.code == code)
        .order_by(ProjectStatus.order.asc(), ProjectStatus.id.asc())
    ).first()


def _ensure_three_status_workflow(session: Session, *, project_id: int) -> None:
    existing_rows = session.exec(
        select(ProjectStatus).where(ProjectStatus.project_id == project_id).order_by(ProjectStatus.order.asc())
    ).all()
    existing_by_code = {str(status_obj.code or "").lower(): status_obj for status_obj in existing_rows}
    for name, code, color, order, is_default, is_final in WORKFLOW_STATUS_PRESET:
        status_obj = existing_by_code.get(code)
        if status_obj is None:
            status_obj = ProjectStatus(
                project_id=project_id,
                name=name,
                code=code,
                color=color,
                order=order,
                is_default=is_default,
                is_final=is_final,
            )
        else:
            status_obj.name = name
            status_obj.color = color
            status_obj.order = order
            status_obj.is_default = is_default
            status_obj.is_final = is_final
        session.add(status_obj)
    session.commit()


def _get_status_by_code(session: Session, *, project_id: int, code: str) -> ProjectStatus:
    status_obj = _find_status_by_code(session, project_id=project_id, code=code)
    if status_obj is None:
        _ensure_three_status_workflow(session, project_id=project_id)
        status_obj = _find_status_by_code(session, project_id=project_id, code=code)
    if status_obj is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project has no workflow status '{code}' configured",
        )
    return status_obj


def _get_in_progress_status(session: Session, project_id: int) -> ProjectStatus:
    return _get_status_by_code(session, project_id=project_id, code=WORKFLOW_STATUS_IN_PROGRESS)


def _get_review_status(session: Session, project_id: int) -> ProjectStatus:
    return _get_status_by_code(session, project_id=project_id, code=WORKFLOW_STATUS_REVIEW)


def _get_final_status(session: Session, project_id: int) -> ProjectStatus:
    status_obj = _find_status_by_code(session, project_id=project_id, code=WORKFLOW_STATUS_DONE)
    if status_obj is None:
        _ensure_three_status_workflow(session, project_id=project_id)
        status_obj = _find_status_by_code(session, project_id=project_id, code=WORKFLOW_STATUS_DONE)
    if status_obj is not None:
        return status_obj

    status_obj = session.exec(
        select(ProjectStatus)
        .where(ProjectStatus.project_id == project_id, ProjectStatus.is_final)
        .order_by(ProjectStatus.order)
    ).first()
    if not status_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no final status configured",
        )
    return status_obj


def _unique_users(
    users: list[User | None],
    *,
    exclude_user_id: int | None = None,
) -> list[User]:
    result: list[User] = []
    seen_ids: set[int] = set()
    for user in users:
        if user is None or user.id is None:
            continue
        if exclude_user_id is not None and user.id == exclude_user_id:
            continue
        if user.id in seen_ids:
            continue
        seen_ids.add(user.id)
        result.append(user)
    return result


def _task_participants(session: Session, task: Task) -> list[User]:
    creator = session.get(User, task.creator_id)
    assignee = session.get(User, task.assignee_id) if task.assignee_id else None
    controller = session.get(User, task.controller_id) if task.controller_id else None
    extra_assignees = session.exec(
        select(User)
        .join(TaskAssignee, TaskAssignee.user_id == User.id)
        .where(TaskAssignee.task_id == task.id)
    ).all()
    return _unique_users([creator, assignee, controller, *extra_assignees])


def _project_review_watchers(session: Session, *, task: Task) -> list[User]:
    watchers = session.exec(
        select(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(
            ProjectMember.project_id == task.project_id,
            ProjectMember.is_active.is_(True),
            ProjectMember.role.in_(
                [ProjectMemberRole.CONTROLLER, ProjectMemberRole.MANAGER]
            ),
            User.is_active.is_(True),
        )
        .order_by(User.id.asc())
    ).all()
    task_controller = session.get(User, task.controller_id) if task.controller_id else None
    return _unique_users([*watchers, task_controller])


def _select_review_recipient(
    session: Session,
    *,
    actor: User,
    review_watchers: list[User],
) -> User | None:
    candidates = [
        user
        for user in review_watchers
        if user.id is not None and user.is_active and user.id != actor.id
    ]
    if not candidates:
        return None

    actor_group_ids = rbac_service.get_user_group_ids(session, user=actor)
    if actor_group_ids:
        for candidate in sorted(candidates, key=lambda row: int(row.id or 0)):
            candidate_group_ids = rbac_service.get_user_group_ids(session, user=candidate)
            shared_group_ids = actor_group_ids & candidate_group_ids
            if shared_group_ids and _is_user_group_controller(
                session,
                user=candidate,
                group_ids=shared_group_ids,
            ):
                return candidate

    return sorted(candidates, key=lambda row: int(row.id or 0))[0]


def _normalize_assignee_ids(
    *,
    primary_assignee_id: int | None,
    assignee_ids: list[int] | None,
) -> list[int]:
    ordered_ids: list[int] = []
    if primary_assignee_id is not None:
        ordered_ids.append(int(primary_assignee_id))
    if assignee_ids:
        ordered_ids.extend(int(user_id) for user_id in assignee_ids if user_id is not None)

    normalized: list[int] = []
    seen: set[int] = set()
    for user_id in ordered_ids:
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        normalized.append(user_id)
    return normalized


def _require_non_empty_assignee_ids(assignee_ids: list[int]) -> None:
    if assignee_ids:
        return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="У задачи должен быть хотя бы один исполнитель",
    )


def _task_assignee_ids(session: Session, *, task: Task) -> list[int]:
    rows = session.exec(
        select(TaskAssignee.user_id)
        .where(TaskAssignee.task_id == task.id)
        .order_by(TaskAssignee.id.asc())
    ).all()
    ids = [int(user_id) for user_id in rows]
    if not ids and task.assignee_id is not None:
        ids = [int(task.assignee_id)]
    return ids


def _sync_task_assignees(
    session: Session,
    *,
    task_id: int,
    assignee_ids: list[int],
) -> None:
    session.exec(delete(TaskAssignee).where(TaskAssignee.task_id == task_id))
    for user_id in assignee_ids:
        session.add(TaskAssignee(task_id=task_id, user_id=user_id))
    session.commit()


def _validate_assignee_scope(
    session: Session,
    *,
    actor: User,
    assignee_ids: list[int],
    project_id: int,
    allow_project_scope: bool = False,
) -> None:
    if not assignee_ids:
        return

    for user_id in assignee_ids:
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Assignee user not found or inactive: {user_id}",
            )

    if rbac_service.is_system_admin(actor):
        return

    if allow_project_scope:
        allowed_project_member_ids = {
            int(user_id)
            for user_id in session.exec(
                select(ProjectMember.user_id).where(
                    ProjectMember.project_id == project_id,
                    ProjectMember.is_active.is_(True),
                )
            ).all()
            if user_id is not None
        }
        forbidden_ids = sorted(set(assignee_ids) - allowed_project_member_ids)
        if forbidden_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно назначать только активных участников проекта",
            )
        return

    allowed_ids = rbac_service.get_same_group_user_ids(session, user=actor)
    if actor.id is not None:
        allowed_ids.add(int(actor.id))
    forbidden_ids = sorted(set(assignee_ids) - allowed_ids)
    if forbidden_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Можно назначать только себя или коллег из своей группы",
        )


def _is_user_group_controller(
    session: Session,
    *,
    user: User,
    group_ids: set[int] | None = None,
) -> bool:
    if user.is_superuser:
        return True
    if str(user.system_role) in LEGACY_CONTROLLER_SYSTEM_ROLES:
        return True
    if group_ids is not None and not group_ids:
        return False

    statement = select(GroupMembership.id).where(
        GroupMembership.user_id == user.id,
        GroupMembership.is_active.is_(True),
        func.lower(GroupMembership.role_name).in_(sorted(GROUP_CONTROLLER_ROLE_NAMES)),
    )
    if group_ids is not None:
        statement = statement.where(GroupMembership.group_id.in_(sorted(group_ids)))
    return session.exec(statement.limit(1)).first() is not None


def _resolve_auto_controller_id(
    session: Session,
    *,
    actor: User,
) -> int:
    group_ids = rbac_service.get_user_group_ids(session, user=actor)
    if not group_ids:
        return int(actor.id)

    candidate_rows = session.exec(
        select(User)
        .where(
            User.is_active.is_(True),
            or_(
                (
                    select(GroupMembership.id)
                    .where(
                        GroupMembership.user_id == User.id,
                        GroupMembership.group_id.in_(sorted(group_ids)),
                        GroupMembership.is_active.is_(True),
                    )
                    .exists()
                ),
                User.primary_group_id.in_(sorted(group_ids)),
            ),
        )
        .order_by(User.id.asc())
    ).all()
    for candidate in candidate_rows:
        if candidate.id is None:
            continue
        if _is_user_group_controller(
            session,
            user=candidate,
            group_ids=group_ids,
        ):
            return int(candidate.id)
    return int(actor.id)


def _active_project_member_ids(session: Session, *, project_id: int) -> set[int]:
    return {
        int(user_id)
        for user_id in session.exec(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.is_active.is_(True),
            )
        ).all()
        if user_id is not None
    }


def can_complete_task(
    session: Session,
    *,
    task: Task,
    actor: User,
) -> bool:
    if rbac_service.is_system_admin(actor):
        return True
    if actor.id == task.controller_id:
        return True

    if task.controller_id is None:
        return False
    controller_user = session.get(User, task.controller_id)
    if controller_user is None:
        return False
    controller_group_ids = rbac_service.get_user_group_ids(session, user=controller_user)
    if not controller_group_ids:
        return False
    actor_group_ids = rbac_service.get_user_group_ids(session, user=actor)
    shared_group_ids = controller_group_ids & actor_group_ids
    return bool(
        shared_group_ids
        and _is_user_group_controller(
            session,
            user=actor,
            group_ids=shared_group_ids,
        )
    )


def _emit_assignment_event(session: Session, *, task: Task, assignee: User) -> None:
    desktop_event_service.enqueue_task_event(
        session,
        user_id=assignee.id,
        event_type=DesktopEventType.ASSIGN,
        task=task,
        title="Назначена задача",
        message=f"Вам назначена задача '{task.title}'",
        payload={"task_id": task.id, "project_id": task.project_id},
        dedupe_key=f"task:{task.id}:assign:{assignee.id}",
    )


def _emit_due_window_events(
    session: Session,
    *,
    task: Task,
    assignee_id: int,
    previous_due_soon: bool,
    previous_overdue: bool,
) -> None:
    assignee = session.get(User, assignee_id)
    if not assignee:
        return

    due_soon = not task.is_overdue and desktop_event_service.is_due_soon(task.due_date)
    if due_soon and not previous_due_soon:
        desktop_event_service.enqueue_task_event(
            session,
            user_id=assignee.id,
            event_type=DesktopEventType.DUE_SOON,
            task=task,
            title="Срок задачи скоро наступит",
            message=f"Задача '{task.title}' скоро просрочится",
            payload={"task_id": task.id, "due_date": task.due_date.isoformat()},
            dedupe_key=f"task:{task.id}:due_soon:{task.due_date.date().isoformat()}",
        )

    if task.is_overdue and not previous_overdue:
        desktop_event_service.enqueue_task_event(
            session,
            user_id=assignee.id,
            event_type=DesktopEventType.OVERDUE,
            task=task,
            title="Задача просрочена",
            message=f"Задача '{task.title}' просрочена",
            payload={"task_id": task.id, "due_date": task.due_date.isoformat()},
            dedupe_key=f"task:{task.id}:overdue:{task.due_date.date().isoformat()}",
        )


def _emit_status_changed_events(
    session: Session,
    *,
    task: Task,
    actor: User,
    old_status_id: int,
    new_status_id: int,
    new_status_name: str | None,
) -> None:
    status_label = new_status_name or str(new_status_id)
    participants = _task_participants(session, task)
    recipients = _unique_users(participants, exclude_user_id=actor.id)
    for user in recipients:
        desktop_event_service.enqueue_task_event(
            session,
            user_id=user.id,
            event_type=DesktopEventType.STATUS_CHANGED,
            task=task,
            title="Статус задачи изменен",
            message=f"Статус задачи '{task.title}' изменен на {status_label}",
            payload={
                "task_id": task.id,
                "old_status_id": old_status_id,
                "new_status_id": new_status_id,
            },
            dedupe_key=f"task:{task.id}:status:{old_status_id}:{new_status_id}:{user.id}",
        )


def _emit_review_requested_events(
    session: Session,
    *,
    task: Task,
    actor: User,
    old_status_id: int,
    new_status_id: int,
) -> None:
    review_watchers = _project_review_watchers(session, task=task)
    recipient = _select_review_recipient(
        session,
        actor=actor,
        review_watchers=review_watchers,
    )
    if recipient is None:
        return
    notification_service.notify_user(
        session,
        user_id=recipient.id,
        notification_type=NotificationType.TASK_STATUS_CHANGED,
        title="Задача отправлена на проверку",
        message=f"Задача '{task.title}' отправлена на проверку",
        payload={
            "task_id": task.id,
            "project_id": task.project_id,
            "old_status_id": old_status_id,
            "new_status_id": new_status_id,
        },
        user_email=recipient.email,
    )
    desktop_event_service.enqueue_task_event(
        session,
        user_id=recipient.id,
        event_type=DesktopEventType.STATUS_CHANGED,
        task=task,
        title="Задача отправлена на проверку",
        message=f"Задача '{task.title}' отправлена на проверку",
        payload={
            "task_id": task.id,
            "project_id": task.project_id,
            "old_status_id": old_status_id,
            "new_status_id": new_status_id,
        },
        dedupe_key=(
            f"task:{task.id}:review_requested:{old_status_id}:{new_status_id}:{recipient.id}"
        ),
    )


def _emit_close_events(session: Session, *, task: Task, actor: User) -> None:
    participants = _task_participants(session, task)
    recipients = _unique_users(participants, exclude_user_id=actor.id)
    for user in recipients:
        desktop_event_service.enqueue_task_event(
            session,
            user_id=user.id,
            event_type=DesktopEventType.CLOSE_REQUESTED,
            task=task,
            title="Запрошено закрытие задачи",
            message=f"Запрошено закрытие задачи '{task.title}' пользователем {actor.email}",
            payload={"task_id": task.id, "actor_id": actor.id},
            dedupe_key=f"task:{task.id}:close_requested:{user.id}",
        )
        desktop_event_service.enqueue_task_event(
            session,
            user_id=user.id,
            event_type=DesktopEventType.CLOSE_APPROVED,
            task=task,
            title="Задача закрыта",
            message=f"Задача '{task.title}' была закрыта пользователем {actor.email}",
            payload={"task_id": task.id, "actor_id": actor.id},
            dedupe_key=f"task:{task.id}:close_approved:{user.id}",
        )


def create_task(
    session: Session,
    *,
    project: Project,
    creator: User,
    title: str,
    description: str,
    assignee_id: int | None,
    assignee_ids: list[int] | None = None,
    controller_id: int | None,
    due_date: datetime,
) -> Task:
    allow_backdated_creation = system_settings_service.get_bool(
        session,
        key=system_settings_service.TASK_ALLOW_BACKDATED_CREATION_KEY,
        default=False,
    )
    if not allow_backdated_creation and due_date < utcnow():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Создание задач задним числом запрещено администратором",
        )

    if rbac_service.is_regular_user(creator):
        effective_assignee_ids = [int(creator.id)]
        resolved_controller_id = _resolve_auto_controller_id(
            session,
            actor=creator,
        )
    else:
        can_manage_project_assignments = rbac_service.has_project_admin_scope(
            session,
            user=creator,
            project_ids={project.id},
        )
        effective_assignee_ids = _normalize_assignee_ids(
            primary_assignee_id=assignee_id,
            assignee_ids=assignee_ids,
        )
        _require_non_empty_assignee_ids(effective_assignee_ids)
        _validate_assignee_scope(
            session,
            actor=creator,
            assignee_ids=effective_assignee_ids,
            project_id=project.id,
            allow_project_scope=can_manage_project_assignments,
        )
        resolved_controller_id = (
            int(controller_id)
            if controller_id is not None
            else _resolve_auto_controller_id(
                session,
                actor=creator,
            )
        )
        if controller_id is not None:
            project_member_ids = _active_project_member_ids(session, project_id=project.id)
            if resolved_controller_id not in project_member_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Контроллер для задачи должен быть активным участником проекта",
                )

    primary_assignee_id = effective_assignee_ids[0] if effective_assignee_ids else int(creator.id)
    default_status = _get_in_progress_status(session, project.id)

    task = Task(
        title=title,
        description=description,
        project_id=project.id,
        creator_id=creator.id,
        assignee_id=primary_assignee_id,
        controller_id=resolved_controller_id,
        due_date=due_date,
        workflow_status_id=default_status.id,
    )
    refresh_task_computed_fields(task, project)
    created = task_repo.create_task(session, task)
    _sync_task_assignees(
        session,
        task_id=created.id,
        assignee_ids=effective_assignee_ids,
    )

    audit_service.add_task_history(
        session,
        task_id=created.id,
        actor_id=creator.id,
        action=TaskHistoryAction.CREATED,
        new_value=f"Task {created.title} created",
    )

    for assigned_user_id in effective_assignee_ids:
        assignee = session.get(User, assigned_user_id)
        if assignee:
            notification_service.notify_user(
                session,
                user_id=assignee.id,
                notification_type=NotificationType.TASK_ASSIGNED,
                title="Назначена задача",
                message=f"Вам назначена задача: {created.title}",
                payload={"task_id": created.id, "project_id": created.project_id},
                user_email=assignee.email,
            )
            _emit_assignment_event(session, task=created, assignee=assignee)
            _emit_due_window_events(
                session,
                task=created,
                assignee_id=assignee.id,
                previous_due_soon=False,
                previous_overdue=False,
            )

    refreshed = task_repo.get_task(session, created.id)
    return refreshed or created


def update_task(
    session: Session,
    *,
    task: Task,
    actor: User,
    project: Project,
    title: str | None = None,
    description: str | None = None,
    assignee_id: int | None = None,
    assignee_ids: list[int] | None = None,
    controller_id: int | None = None,
    due_date: datetime | None = None,
    workflow_status_id: int | None = None,
) -> Task:
    old_assignee_id = task.assignee_id
    old_assignee_ids = _task_assignee_ids(session, task=task)
    old_due_date = task.due_date
    old_status_id = task.workflow_status_id
    old_is_overdue = task.is_overdue
    old_due_soon = (not old_is_overdue) and desktop_event_service.is_due_soon(task.due_date)

    effective_assignee_ids: list[int] | None = None
    if assignee_ids is not None:
        effective_assignee_ids = _normalize_assignee_ids(
            primary_assignee_id=assignee_id,
            assignee_ids=assignee_ids,
        )
    elif assignee_id is not None:
        effective_assignee_ids = _normalize_assignee_ids(
            primary_assignee_id=assignee_id,
            assignee_ids=None,
        )

    can_manage_task_controls = can_complete_task(
        session,
        task=task,
        actor=actor,
    ) or rbac_service.has_project_admin_scope(
        session,
        user=actor,
        project_ids={task.project_id},
    )
    if effective_assignee_ids is not None:
        _require_non_empty_assignee_ids(effective_assignee_ids)
        _validate_assignee_scope(
            session,
            actor=actor,
            assignee_ids=effective_assignee_ids,
            project_id=task.project_id,
            allow_project_scope=can_manage_task_controls,
        )
    if due_date is not None and due_date != task.due_date and not can_manage_task_controls:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Срок задачи может менять только контроллер или системный администратор",
        )
    if (
        (effective_assignee_ids is not None and set(effective_assignee_ids) != set(old_assignee_ids))
        or (controller_id is not None and controller_id != task.controller_id)
    ) and not can_manage_task_controls:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Назначения исполнителей и контроллера меняет только контроллер",
        )
    if controller_id is not None:
        controller = session.get(User, controller_id)
        if controller is None or not controller.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Контроллер не найден или отключен",
            )
        if can_manage_task_controls:
            project_member_ids = _active_project_member_ids(session, project_id=task.project_id)
            if controller_id not in project_member_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Контроллер для задачи должен быть активным участником проекта",
                )

    target_status: ProjectStatus | None = None
    if workflow_status_id is not None:
        target_status = session.get(ProjectStatus, workflow_status_id)
        if target_status is None or target_status.project_id != task.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status does not belong to task project",
            )
        target_code = (target_status.code or "").strip().lower()
        if target_code == WORKFLOW_STATUS_REVIEW:
            comment_count = session.exec(
                select(TaskComment.id).where(TaskComment.task_id == task.id).limit(1)
            ).first()
            attachment_count = session.exec(
                select(TaskAttachment.id).where(TaskAttachment.task_id == task.id).limit(1)
            ).first()
            if comment_count is None and attachment_count is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Для перевода на проверку нужен комментарий или вложение",
                )
        if target_code == WORKFLOW_STATUS_DONE and not can_manage_task_controls:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только контроллер группы или superadmin могут завершить задачу",
            )

    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if effective_assignee_ids is not None:
        task.assignee_id = effective_assignee_ids[0] if effective_assignee_ids else None
    if controller_id is not None:
        task.controller_id = controller_id
    if due_date is not None:
        task.due_date = due_date
    if workflow_status_id is not None:
        task.workflow_status_id = workflow_status_id

    task.updated_at = utcnow()

    refresh_task_computed_fields(task, project)

    updated = task_repo.update_task(session, task)
    if effective_assignee_ids is not None:
        _sync_task_assignees(
            session,
            task_id=updated.id,
            assignee_ids=effective_assignee_ids,
        )
    updated_assignee_ids = (
        effective_assignee_ids
        if effective_assignee_ids is not None
        else _task_assignee_ids(session, task=updated)
    )

    audit_service.add_task_history(
        session,
        task_id=updated.id,
        actor_id=actor.id,
        action=TaskHistoryAction.UPDATED,
        new_value="Task updated",
    )

    if old_due_date != updated.due_date:
        audit_service.add_task_history(
            session,
            task_id=updated.id,
            actor_id=actor.id,
            action=TaskHistoryAction.DUE_DATE_CHANGED,
            field_name="due_date",
            old_value=str(old_due_date),
            new_value=str(updated.due_date),
        )

        for assignee_user_id in updated_assignee_ids:
            assignee = session.get(User, assignee_user_id)
            if assignee:
                notification_service.notify_user(
                    session,
                    user_id=assignee.id,
                    notification_type=NotificationType.TASK_DUE_DATE_CHANGED,
                    title="Изменен срок задачи",
                    message=f"Изменен срок задачи: {updated.title}",
                    payload={"task_id": updated.id},
                    user_email=assignee.email,
                )

    if old_status_id != updated.workflow_status_id:
        status_obj = target_status or session.get(ProjectStatus, updated.workflow_status_id)
        audit_service.add_task_history(
            session,
            task_id=updated.id,
            actor_id=actor.id,
            action=TaskHistoryAction.STATUS_CHANGED,
            field_name="workflow_status_id",
            old_value=str(old_status_id),
            new_value=str(updated.workflow_status_id),
        )
        if status_obj and status_obj.is_final:
            updated.closed_at = utcnow()
            updated = task_repo.update_task(session, updated)
        elif updated.closed_at is not None:
            # Reopened from final state.
            updated.closed_at = None
            updated = task_repo.update_task(session, updated)
        _emit_status_changed_events(
            session,
            task=updated,
            actor=actor,
            old_status_id=old_status_id,
            new_status_id=updated.workflow_status_id,
            new_status_name=status_obj.name if status_obj else None,
        )
        if status_obj and (status_obj.code or "").strip().lower() == WORKFLOW_STATUS_REVIEW:
            _emit_review_requested_events(
                session,
                task=updated,
                actor=actor,
                old_status_id=old_status_id,
                new_status_id=updated.workflow_status_id,
            )

    if old_assignee_id != updated.assignee_id and updated.assignee_id:
        audit_service.add_task_history(
            session,
            task_id=updated.id,
            actor_id=actor.id,
            action=TaskHistoryAction.ASSIGNEE_CHANGED,
            field_name="assignee_id",
            old_value=str(old_assignee_id),
            new_value=str(updated.assignee_id),
        )
    old_assignee_id_set = set(old_assignee_ids)
    new_assignee_id_set = set(updated_assignee_ids)
    for assignee_user_id in sorted(new_assignee_id_set):
        assignee = session.get(User, assignee_user_id)
        if assignee is None:
            continue

        if assignee_user_id not in old_assignee_id_set:
            notification_service.notify_user(
                session,
                user_id=assignee.id,
                notification_type=NotificationType.TASK_ASSIGNED,
                title="Назначена задача",
                message=f"Вам назначена задача: {updated.title}",
                payload={"task_id": updated.id},
                user_email=assignee.email,
            )
            _emit_assignment_event(session, task=updated, assignee=assignee)

        previous_due_soon = old_due_soon if assignee_user_id in old_assignee_id_set else False
        previous_overdue = old_is_overdue if assignee_user_id in old_assignee_id_set else False
        _emit_due_window_events(
            session,
            task=updated,
            assignee_id=assignee_user_id,
            previous_due_soon=previous_due_soon,
            previous_overdue=previous_overdue,
        )

    refreshed = task_repo.get_task(session, updated.id)
    return refreshed or updated


def submit_task_for_review(
    session: Session,
    *,
    task: Task,
    actor: User,
    project: Project,
) -> Task:
    review_status = _get_review_status(session, task.project_id)
    return update_task(
        session,
        task=task,
        actor=actor,
        project=project,
        workflow_status_id=review_status.id,
    )


def complete_task(
    session: Session,
    *,
    task: Task,
    actor: User,
    project: Project,
) -> Task:
    final_status = _get_final_status(session, task.project_id)
    updated = update_task(
        session,
        task=task,
        actor=actor,
        project=project,
        workflow_status_id=final_status.id,
    )
    audit_service.add_task_history(
        session,
        task_id=updated.id,
        actor_id=actor.id,
        action=TaskHistoryAction.CLOSED,
        new_value="Task closed",
    )
    _emit_close_events(session, task=updated, actor=actor)
    return updated


def close_task(
    session: Session,
    *,
    task: Task,
    actor: User,
    project: Project,
    close_comment: str | None,
    attachment_ids: list[int],
) -> Task:
    if project.require_close_comment and not close_comment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Close comment is required for this project",
        )

    if project.require_close_attachment:
        if not attachment_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Attachment is required for this project",
            )

        for attachment_id in attachment_ids:
            attachment = attachment_repo.get_task_attachment(session, attachment_id)
            if not attachment or attachment.task_id != task.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Attachment {attachment_id} does not belong to task",
                )

    final_status = _get_final_status(session, task.project_id)

    task.workflow_status_id = final_status.id
    task.closed_at = utcnow()
    task.updated_at = utcnow()
    refresh_task_computed_fields(task, project)

    updated = task_repo.update_task(session, task)

    audit_service.add_task_history(
        session,
        task_id=updated.id,
        actor_id=actor.id,
        action=TaskHistoryAction.CLOSED,
        new_value="Task closed",
    )

    if close_comment:
        comment_obj = TaskComment(task_id=updated.id, author_id=actor.id, comment=close_comment)
        comment_repo.create_task_comment(session, comment_obj)
        audit_service.add_task_history(
            session,
            task_id=updated.id,
            actor_id=actor.id,
            action=TaskHistoryAction.COMMENT_ADDED,
            new_value=close_comment,
        )

    recipients: list[User] = []
    creator = session.get(User, updated.creator_id)
    assignee = session.get(User, updated.assignee_id) if updated.assignee_id else None
    controller = session.get(User, updated.controller_id) if updated.controller_id else None

    for user in [creator, assignee, controller]:
        if user and user.id != actor.id:
            recipients.append(user)

    for user in recipients:
        notification_service.notify_user(
            session,
            user_id=user.id,
            notification_type=NotificationType.TASK_STATUS_CHANGED,
            title="Задача закрыта",
            message=f"Задача '{updated.title}' закрыта пользователем {actor.email}",
            payload={"task_id": updated.id},
            user_email=user.email,
        )

    _emit_close_events(session, task=updated, actor=actor)

    return updated


def add_task_comment(
    session: Session,
    *,
    task: Task,
    actor: User,
    comment: str,
) -> TaskComment:
    comment_obj = TaskComment(task_id=task.id, author_id=actor.id, comment=comment)
    created = comment_repo.create_task_comment(session, comment_obj)

    audit_service.add_task_history(
        session,
        task_id=task.id,
        actor_id=actor.id,
        action=TaskHistoryAction.COMMENT_ADDED,
        new_value=comment,
    )

    for participant in _unique_users(_task_participants(session, task), exclude_user_id=actor.id):
        notification_service.notify_user(
            session,
            user_id=participant.id,
            notification_type=NotificationType.TASK_COMMENTED,
            title="Новый комментарий к задаче",
            message=f"Новый комментарий в задаче: {task.title}",
            payload={"task_id": task.id},
            user_email=participant.email,
        )

    return created


def refresh_deadline_flags_for_open_tasks(session: Session) -> int:
    rows = session.exec(
        select(Task, Project).join(Project, Project.id == Task.project_id).where(Task.closed_at.is_(None))
    ).all()
    updated_count = 0

    for task, project in rows:
        before = (
            task.computed_deadline_state,
            task.computed_urgency_state,
            task.is_overdue,
        )
        refresh_task_computed_fields(task, project)
        after = (
            task.computed_deadline_state,
            task.computed_urgency_state,
            task.is_overdue,
        )
        if before != after:
            task.updated_at = utcnow()
            session.add(task)
            updated_count += 1

    if updated_count:
        session.commit()

    return updated_count
