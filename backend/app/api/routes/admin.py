from pathlib import Path
from uuid import uuid4

from datetime import datetime, timezone
from collections import defaultdict

from fastapi import APIRouter, File, HTTPException, UploadFile
from minio.error import S3Error
from sqlmodel import delete, select
from starlette import status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.security import verify_password
from app.integrations.minio_client import ensure_bucket_exists, get_minio_client
from app.models import (
    DesktopEventType,
    GroupMembership,
    OrgGroup,
    Organization,
    OrganizationMembership,
    Project,
    ProjectAccessSubjectType,
    ProjectMember,
    ProjectSubjectRole,
    Role,
    Task,
    TaskAssignee,
    TaskAttachment,
    TaskComment,
    TaskHistory,
    User,
)
from app.schemas.admin import (
    AdminAccessibleProject,
    AdminAccessGroupMembership,
    AdminAccessOrganizationMembership,
    AdminAccessProjectMembership,
    AdminAccessProjectRoleAssignment,
    AdminDesktopAgentPublic,
    AdminDesktopAgentUploadResult,
    AdminDesktopEventsTestRequest,
    AdminDesktopEventsTestResponse,
    AdminTaskPolicyPublic,
    AdminTaskPolicyUpdate,
    AdminTaskBulkDeleteRequest,
    AdminTaskBulkDeleteResponse,
    AdminTaskBulkSetControllerRequest,
    AdminTaskBulkSetControllerResponse,
    AdminUserAccessMapPublic,
)
from app.schemas.demo_data import DemoDataLockRequest, DemoDataSummary, DemoDataToggleRequest
from app.services import (
    demo_data_service,
    desktop_agent_service,
    desktop_event_service,
    rbac_service,
    system_settings_service,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

DESKTOP_AGENT_ALLOWED_EXTS = {"exe", "msi"}
DESKTOP_AGENT_MAX_SIZE_BYTES = 1024 * 1024 * 1024  # 1 GiB


def _project_member_role_label(role_value: str) -> str:
    labels = {
        "reader": "Читатель",
        "executor": "Исполнитель",
        "controller": "Контроллер",
        "manager": "Менеджер проекта",
    }
    return labels.get(role_value, role_value)


def _resolve_scoped_project_ids(
    session: SessionDep,
    *,
    project_id: int | None,
    group_id: int | None,
    organization_id: int | None,
) -> set[int]:
    scoped_project_ids: set[int] = set()
    if project_id is not None:
        scoped_project_ids.add(int(project_id))
    if group_id is not None:
        group_ids = rbac_service.get_group_descendant_ids(session, group_id=int(group_id))
        scoped_project_ids |= rbac_service.get_project_ids_for_group_ids(
            session,
            group_ids=group_ids,
        )
    if organization_id is not None:
        org_project_ids = {
            int(id_value)
            for id_value in session.exec(
                select(Project.id).where(Project.organization_id == int(organization_id))
            ).all()
            if id_value is not None
        }
        scoped_project_ids |= org_project_ids
    return scoped_project_ids


def _build_user_access_map(session: SessionDep, *, user: User) -> AdminUserAccessMapPublic:
    organization_memberships = session.exec(
        select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    ).all()
    group_memberships = session.exec(
        select(GroupMembership).where(GroupMembership.user_id == user.id)
    ).all()
    project_memberships = session.exec(
        select(ProjectMember).where(ProjectMember.user_id == user.id)
    ).all()

    user_group_ids = rbac_service.get_user_group_ids(session, user=user)
    managed_group_ids = rbac_service._get_direct_managed_group_ids(session, user=user)
    managed_organization_ids = rbac_service._get_managed_organization_ids(session, user=user)
    accessible_project_ids = rbac_service.get_accessible_project_ids(session, user=user)

    role_rows = session.exec(select(Role.id, Role.name, Role.description)).all()
    roles_by_id = {
        int(role_id): {
            "role_key": str(role_key),
            "role_title": str(role_title or role_key),
        }
        for role_id, role_key, role_title in role_rows
        if role_id is not None
    }

    organization_ids = {
        int(membership.organization_id)
        for membership in organization_memberships
        if membership.organization_id is not None
    }
    group_ids_from_memberships = {
        int(membership.group_id)
        for membership in group_memberships
        if membership.group_id is not None
    }
    project_ids_from_memberships = {
        int(membership.project_id)
        for membership in project_memberships
        if membership.project_id is not None
    }

    direct_role_assignments = session.exec(
        select(ProjectSubjectRole).where(
            ProjectSubjectRole.subject_type == ProjectAccessSubjectType.USER,
            ProjectSubjectRole.subject_user_id == user.id,
        )
    ).all()
    group_role_assignments: list[ProjectSubjectRole] = []
    if user_group_ids:
        group_role_assignments = session.exec(
            select(ProjectSubjectRole).where(
                ProjectSubjectRole.subject_type == ProjectAccessSubjectType.GROUP,
                ProjectSubjectRole.subject_group_id.in_(sorted(user_group_ids)),
            )
        ).all()
    role_assignments = [*direct_role_assignments, *group_role_assignments]

    role_assignment_project_ids = {
        int(assignment.project_id)
        for assignment in role_assignments
        if assignment.project_id is not None
    }
    role_assignment_group_ids = {
        int(assignment.subject_group_id)
        for assignment in role_assignments
        if assignment.subject_group_id is not None
    }

    all_group_ids = set(user_group_ids) | group_ids_from_memberships | role_assignment_group_ids
    if user.primary_group_id is not None:
        all_group_ids.add(int(user.primary_group_id))

    all_project_ids = (
        set(accessible_project_ids) | project_ids_from_memberships | role_assignment_project_ids
    )

    if managed_organization_ids:
        managed_group_ids_from_orgs = {
            int(group_id)
            for group_id in session.exec(
                select(OrgGroup.id).where(
                    OrgGroup.organization_id.in_(sorted(managed_organization_ids))
                )
            ).all()
            if group_id is not None
        }
    else:
        managed_group_ids_from_orgs = set()
    all_group_ids |= managed_group_ids_from_orgs

    group_map: dict[int, OrgGroup] = {}
    if all_group_ids:
        for group in session.exec(select(OrgGroup).where(OrgGroup.id.in_(sorted(all_group_ids)))).all():
            if group.id is not None:
                group_map[int(group.id)] = group
                if group.organization_id is not None:
                    organization_ids.add(int(group.organization_id))

    organization_map: dict[int, Organization] = {}
    if organization_ids:
        for organization in session.exec(
            select(Organization).where(Organization.id.in_(sorted(organization_ids)))
        ).all():
            if organization.id is not None:
                organization_map[int(organization.id)] = organization

    project_map: dict[int, Project] = {}
    if all_project_ids:
        for project in session.exec(select(Project).where(Project.id.in_(sorted(all_project_ids)))).all():
            if project.id is not None:
                project_map[int(project.id)] = project

    direct_user_assignment_project_ids = {
        int(assignment.project_id)
        for assignment in role_assignments
        if assignment.is_active
        and assignment.subject_type == ProjectAccessSubjectType.USER
        and assignment.project_id is not None
    }
    active_group_assignments: dict[int, set[str]] = defaultdict(set)
    for assignment in role_assignments:
        if (
            not assignment.is_active
            or assignment.subject_type != ProjectAccessSubjectType.GROUP
            or assignment.project_id is None
            or assignment.subject_group_id is None
        ):
            continue
        group_name = group_map.get(int(assignment.subject_group_id)).name if int(assignment.subject_group_id) in group_map else f"#{assignment.subject_group_id}"
        active_group_assignments[int(assignment.project_id)].add(group_name)

    active_project_member_roles: dict[int, set[str]] = defaultdict(set)
    for membership in project_memberships:
        if not membership.is_active or membership.project_id is None:
            continue
        active_project_member_roles[int(membership.project_id)].add(
            _project_member_role_label(str(membership.role.value))
        )

    managed_group_assignment_project_ids = (
        rbac_service._get_project_ids_for_groups(session, group_ids=managed_group_ids)
        if managed_group_ids
        else set()
    )
    managed_org_direct_project_ids = (
        {
            int(project_id)
            for project_id in session.exec(
                select(Project.id).where(Project.organization_id.in_(sorted(managed_organization_ids)))
            ).all()
            if project_id is not None
        }
        if managed_organization_ids
        else set()
    )
    managed_org_group_assignment_project_ids = (
        rbac_service._get_project_ids_for_groups(session, group_ids=managed_group_ids_from_orgs)
        if managed_group_ids_from_orgs
        else set()
    )
    managed_contour_project_ids = (
        managed_group_assignment_project_ids
        | managed_org_direct_project_ids
        | managed_org_group_assignment_project_ids
    )

    reasons_by_project: dict[int, set[str]] = defaultdict(set)
    for project_id in direct_user_assignment_project_ids:
        reasons_by_project[project_id].add(
            "Прямое назначение роли пользователю в настройках проекта"
        )
    for project_id, group_names in active_group_assignments.items():
        reasons_by_project[project_id].add(
            f"Доступ через группы проекта: {', '.join(sorted(group_names))}"
        )
    for project_id, role_names in active_project_member_roles.items():
        reasons_by_project[project_id].add(
            f"Участник проекта ({', '.join(sorted(role_names))})"
        )
    for project_id in managed_group_assignment_project_ids:
        reasons_by_project[project_id].add(
            "Руководитель группы: проект попал через назначение группы"
        )
    for project_id in managed_org_direct_project_ids:
        reasons_by_project[project_id].add(
            "Директор блока: проект принадлежит управляемой организации"
        )
    for project_id in managed_org_group_assignment_project_ids:
        reasons_by_project[project_id].add(
            "Директор блока: проект назначен на группы управляемой организации"
        )

    organizations_payload: list[AdminAccessOrganizationMembership] = []
    for membership in sorted(
        organization_memberships,
        key=lambda row: (
            organization_map.get(int(row.organization_id)).name
            if row.organization_id is not None and int(row.organization_id) in organization_map
            else "",
            int(row.organization_id or 0),
        ),
    ):
        org = organization_map.get(int(membership.organization_id))
        organizations_payload.append(
            AdminAccessOrganizationMembership(
                organization_id=int(membership.organization_id),
                organization_name=org.name if org is not None else None,
                role_name=membership.role_name or "member",
                is_active=bool(membership.is_active),
            )
        )

    groups_payload: list[AdminAccessGroupMembership] = []
    seen_group_ids: set[int] = set()
    for membership in sorted(
        group_memberships,
        key=lambda row: (
            group_map.get(int(row.group_id)).name
            if row.group_id is not None and int(row.group_id) in group_map
            else "",
            int(row.group_id or 0),
        ),
    ):
        group_id = int(membership.group_id)
        seen_group_ids.add(group_id)
        group = group_map.get(group_id)
        organization = (
            organization_map.get(int(group.organization_id))
            if group is not None and group.organization_id is not None
            else None
        )
        groups_payload.append(
            AdminAccessGroupMembership(
                group_id=group_id,
                group_name=group.name if group is not None else None,
                organization_id=int(group.organization_id)
                if group is not None and group.organization_id is not None
                else None,
                organization_name=organization.name if organization is not None else None,
                role_name=membership.role_name or "member",
                is_active=bool(membership.is_active),
                is_primary=user.primary_group_id == group_id,
                is_direct_membership=True,
            )
        )

    # Include implicit group links that are not present as direct memberships.
    for group_id in sorted(user_group_ids - seen_group_ids):
        group = group_map.get(group_id)
        if group is None:
            continue
        organization = (
            organization_map.get(int(group.organization_id))
            if group.organization_id is not None
            else None
        )
        groups_payload.append(
            AdminAccessGroupMembership(
                group_id=group_id,
                group_name=group.name,
                organization_id=int(group.organization_id)
                if group.organization_id is not None
                else None,
                organization_name=organization.name if organization is not None else None,
                role_name="member",
                is_active=True,
                is_primary=user.primary_group_id == group_id,
                is_direct_membership=False,
            )
        )

    project_memberships_payload: list[AdminAccessProjectMembership] = []
    for membership in sorted(project_memberships, key=lambda row: int(row.project_id or 0)):
        project_id = int(membership.project_id)
        project = project_map.get(project_id)
        organization = (
            organization_map.get(int(project.organization_id))
            if project is not None and project.organization_id is not None
            else None
        )
        project_memberships_payload.append(
            AdminAccessProjectMembership(
                project_id=project_id,
                project_name=project.name if project is not None else None,
                organization_id=int(project.organization_id)
                if project is not None and project.organization_id is not None
                else None,
                organization_name=organization.name if organization is not None else None,
                role=str(membership.role.value),
                is_active=bool(membership.is_active),
            )
        )

    project_role_assignments_payload: list[AdminAccessProjectRoleAssignment] = []
    for assignment in sorted(
        role_assignments,
        key=lambda row: (int(row.project_id or 0), str(row.subject_type.value), int(row.id or 0)),
    ):
        project_id = int(assignment.project_id)
        project = project_map.get(project_id)
        organization = (
            organization_map.get(int(project.organization_id))
            if project is not None and project.organization_id is not None
            else None
        )
        role_meta = roles_by_id.get(int(assignment.role_id), {})
        group = (
            group_map.get(int(assignment.subject_group_id))
            if assignment.subject_group_id is not None
            else None
        )
        project_role_assignments_payload.append(
            AdminAccessProjectRoleAssignment(
                project_id=project_id,
                project_name=project.name if project is not None else None,
                organization_id=int(project.organization_id)
                if project is not None and project.organization_id is not None
                else None,
                organization_name=organization.name if organization is not None else None,
                role_key=str(role_meta.get("role_key", f"role#{assignment.role_id}")),
                role_title=str(role_meta.get("role_title", f"Роль #{assignment.role_id}")),
                subject_type=str(assignment.subject_type.value),
                subject_user_id=assignment.subject_user_id,
                subject_group_id=assignment.subject_group_id,
                subject_group_name=group.name if group is not None else None,
                is_active=bool(assignment.is_active),
            )
        )

    accessible_projects_payload: list[AdminAccessibleProject] = []
    for project_id in sorted(
        accessible_project_ids,
        key=lambda pid: (
            project_map.get(pid).name.lower() if pid in project_map and project_map[pid].name else "",
            pid,
        ),
    ):
        project = project_map.get(project_id)
        if project is None:
            continue
        organization = (
            organization_map.get(int(project.organization_id))
            if project.organization_id is not None
            else None
        )
        reasons = sorted(reasons_by_project.get(project_id, set()))
        if not reasons:
            reasons = ["Вычисленный доступ по текущим правилам RBAC"]
        accessible_projects_payload.append(
            AdminAccessibleProject(
                project_id=project_id,
                project_name=project.name,
                organization_id=int(project.organization_id)
                if project.organization_id is not None
                else None,
                organization_name=organization.name if organization is not None else None,
                reasons=reasons,
            )
        )

    notes: list[str] = []
    if managed_contour_project_ids:
        notes.append(
            "Для пользователя включён управленческий контур: доступные проекты берутся из контура руководства группой/организацией."
        )
    if user.department_id is not None:
        notes.append(
            "У пользователя заполнен legacy department_id. Это может влиять на доступ через совместимость старых связей."
        )

    primary_group_name = None
    if user.primary_group_id is not None:
        primary_group = group_map.get(int(user.primary_group_id))
        primary_group_name = primary_group.name if primary_group is not None else None

    return AdminUserAccessMapPublic(
        user_id=int(user.id),
        email=user.email,
        full_name=user.full_name,
        system_role=str(user.system_role.value),
        is_superuser=bool(user.is_superuser),
        primary_group_id=user.primary_group_id,
        primary_group_name=primary_group_name,
        user_group_ids=sorted(user_group_ids),
        managed_group_ids=sorted(managed_group_ids),
        managed_organization_ids=sorted(managed_organization_ids),
        organizations=organizations_payload,
        groups=groups_payload,
        project_memberships=project_memberships_payload,
        project_role_assignments=project_role_assignments_payload,
        accessible_projects=accessible_projects_payload,
        notes=notes,
    )


def _resolve_desktop_agent_state(session: SessionDep) -> AdminDesktopAgentPublic:
    uploaded_meta = desktop_agent_service.get_uploaded_agent_meta(session)
    if uploaded_meta is not None:
        return AdminDesktopAgentPublic(
            configured=True,
            source="uploaded",
            file_name=uploaded_meta.get("file_name"),
            content_type=uploaded_meta.get("content_type"),
            size_bytes=int(uploaded_meta.get("size_bytes") or 0),
            uploaded_at=uploaded_meta.get("uploaded_at"),
        )

    if settings.DESKTOP_AGENT_BINARY_PATH:
        binary_path = Path(settings.DESKTOP_AGENT_BINARY_PATH)
        if binary_path.is_file():
            return AdminDesktopAgentPublic(
                configured=True,
                source="local_path",
                file_name=binary_path.name,
                content_type="application/octet-stream",
                size_bytes=binary_path.stat().st_size,
                uploaded_at=None,
            )

    if settings.DESKTOP_AGENT_DOWNLOAD_URL:
        return AdminDesktopAgentPublic(
            configured=True,
            source="redirect_url",
            file_name=None,
            content_type=None,
            size_bytes=None,
            uploaded_at=None,
        )

    return AdminDesktopAgentPublic(
        configured=False,
        source="none",
    )


@router.get("/demo-data", response_model=DemoDataSummary)
def get_demo_data_status(
    session: SessionDep,
    current_user: CurrentUser,
) -> DemoDataSummary:
    rbac_service.require_system_admin(current_user)
    return demo_data_service.get_demo_data_summary(session)


@router.put("/demo-data", response_model=DemoDataSummary)
def set_demo_data_status(
    payload: DemoDataToggleRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> DemoDataSummary:
    rbac_service.require_system_admin(current_user)
    if not payload.enabled:
        is_locked = system_settings_service.get_bool(
            session,
            key=system_settings_service.DEMO_DATA_LOCKED_KEY,
            default=False,
        )
        if is_locked:
            if not payload.admin_password:
                raise HTTPException(
                    status_code=403,
                    detail="Демо-данные защищены. Укажите пароль администратора для удаления.",
                )
            if not verify_password(payload.admin_password, current_user.hashed_password):
                raise HTTPException(
                    status_code=403,
                    detail="Неверный пароль администратора",
                )
    return demo_data_service.set_demo_data_enabled(
        session,
        actor=current_user,
        enabled=payload.enabled,
    )


@router.put("/demo-data/lock", response_model=DemoDataSummary)
def set_demo_data_lock(
    payload: DemoDataLockRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> DemoDataSummary:
    rbac_service.require_system_admin(current_user)
    system_settings_service.set_bool(
        session,
        key=system_settings_service.DEMO_DATA_LOCKED_KEY,
        value=payload.is_locked,
    )
    return demo_data_service.get_demo_data_summary(session)


@router.get("/users/{user_id}/access-map", response_model=AdminUserAccessMapPublic)
def get_user_access_map(
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminUserAccessMapPublic:
    rbac_service.require_system_admin(current_user)
    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return _build_user_access_map(session, user=target_user)


@router.post("/tasks/bulk-delete", response_model=AdminTaskBulkDeleteResponse)
def bulk_delete_tasks(
    payload: AdminTaskBulkDeleteRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminTaskBulkDeleteResponse:
    rbac_service.require_system_admin(current_user)
    project_ids = _resolve_scoped_project_ids(
        session,
        project_id=payload.project_id,
        group_id=payload.group_id,
        organization_id=payload.organization_id,
    )
    if not project_ids:
        raise HTTPException(
            status_code=422,
            detail="Укажите project_id, group_id или organization_id с задачами в контуре",
        )

    task_id_query = select(Task.id).where(Task.project_id.in_(sorted(project_ids)))
    if not payload.include_completed:
        task_id_query = task_id_query.where(Task.closed_at.is_(None))
    task_ids = [int(task_id) for task_id in session.exec(task_id_query).all() if task_id is not None]
    if not task_ids:
        return AdminTaskBulkDeleteResponse(matched_tasks=0, deleted_tasks=0)

    session.exec(delete(TaskHistory).where(TaskHistory.task_id.in_(task_ids)))
    session.exec(delete(TaskComment).where(TaskComment.task_id.in_(task_ids)))
    session.exec(delete(TaskAttachment).where(TaskAttachment.task_id.in_(task_ids)))
    session.exec(delete(TaskAssignee).where(TaskAssignee.task_id.in_(task_ids)))
    session.exec(delete(Task).where(Task.id.in_(task_ids)))
    session.commit()
    return AdminTaskBulkDeleteResponse(
        matched_tasks=len(task_ids),
        deleted_tasks=len(task_ids),
    )


@router.post(
    "/tasks/bulk-set-controller",
    response_model=AdminTaskBulkSetControllerResponse,
)
def bulk_set_controller(
    payload: AdminTaskBulkSetControllerRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminTaskBulkSetControllerResponse:
    rbac_service.require_system_admin(current_user)
    controller = session.get(User, payload.controller_id)
    if controller is None or not controller.is_active:
        raise HTTPException(status_code=404, detail="Контроллер не найден или неактивен")

    project_ids = _resolve_scoped_project_ids(
        session,
        project_id=payload.project_id,
        group_id=payload.group_id,
        organization_id=payload.organization_id,
    )
    if not project_ids:
        raise HTTPException(
            status_code=422,
            detail="Укажите project_id, group_id или organization_id с задачами в контуре",
        )

    tasks_query = select(Task).where(Task.project_id.in_(sorted(project_ids)))
    if not payload.include_completed:
        tasks_query = tasks_query.where(Task.closed_at.is_(None))
    tasks = session.exec(tasks_query).all()
    if not tasks:
        return AdminTaskBulkSetControllerResponse(matched_tasks=0, updated_tasks=0)

    now = datetime.now(timezone.utc)
    for task in tasks:
        task.controller_id = controller.id
        task.updated_at = now
        session.add(task)
    session.commit()
    return AdminTaskBulkSetControllerResponse(
        matched_tasks=len(tasks),
        updated_tasks=len(tasks),
    )


@router.post(
    "/users/{user_id}/desktop-events/test",
    response_model=AdminDesktopEventsTestResponse,
)
def send_test_desktop_events(
    user_id: int,
    payload: AdminDesktopEventsTestRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminDesktopEventsTestResponse:
    rbac_service.require_system_admin(current_user)
    target_user = session.get(User, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    base_payload = {
        "kind": "desktop_event_test",
        "mode": payload.mode,
        "generated_at": generated_at,
        "triggered_by_user_id": current_user.id,
        "target_user_id": target_user.id,
    }
    specs = [
        (
            DesktopEventType.ASSIGN,
            "Назначена задача (тест)",
            "Вам назначена задача 'Тестовое desktop-уведомление'",
        ),
        (
            DesktopEventType.DUE_SOON,
            "Срок задачи скоро наступит (тест)",
            "Задача 'Тестовое desktop-уведомление' скоро просрочится",
        ),
        (
            DesktopEventType.OVERDUE,
            "Задача просрочена (тест)",
            "Задача 'Тестовое desktop-уведомление' просрочена",
        ),
        (
            DesktopEventType.STATUS_CHANGED,
            "Статус задачи изменен (тест)",
            "Статус задачи 'Тестовое desktop-уведомление' изменен на Готово",
        ),
        (
            DesktopEventType.CLOSE_REQUESTED,
            "Запрошено закрытие задачи (тест)",
            "Запрошено закрытие задачи 'Тестовое desktop-уведомление'",
        ),
        (
            DesktopEventType.CLOSE_APPROVED,
            "Задача закрыта (тест)",
            "Задача 'Тестовое desktop-уведомление' была закрыта",
        ),
        (
            DesktopEventType.SYSTEM,
            "Системное событие (тест)",
            "Тестовое событие интеграции desktop-агента",
        ),
    ]
    if payload.mode == "single":
        specs = specs[:1]

    event_ids: list[int] = []
    for index, (event_type, title, message) in enumerate(specs, start=1):
        event = desktop_event_service.enqueue_event(
            session,
            user_id=target_user.id,
            event_type=event_type,
            title=title,
            message=message,
            deeplink="/tasks",
            payload={**base_payload, "sequence": index},
        )
        if event is not None:
            event_ids.append(event.id)

    return AdminDesktopEventsTestResponse(
        user_id=target_user.id,
        mode=payload.mode,
        created_count=len(event_ids),
        event_ids=event_ids,
    )


@router.get("/task-policy", response_model=AdminTaskPolicyPublic)
def get_task_policy(
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminTaskPolicyPublic:
    rbac_service.require_system_admin(current_user)
    allow_backdated_creation = system_settings_service.get_bool(
        session,
        key=system_settings_service.TASK_ALLOW_BACKDATED_CREATION_KEY,
        default=False,
    )
    overdue_desktop_reminders_enabled = system_settings_service.get_bool(
        session,
        key=system_settings_service.TASK_OVERDUE_DESKTOP_REMINDERS_ENABLED_KEY,
        default=True,
    )
    overdue_desktop_reminder_interval_minutes = system_settings_service.get_int(
        session,
        key=system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MINUTES_KEY,
        default=system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MIN,
    )
    overdue_desktop_reminder_interval_minutes = max(
        system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MIN,
        min(
            overdue_desktop_reminder_interval_minutes,
            system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MAX,
        ),
    )
    return AdminTaskPolicyPublic(
        allow_backdated_creation=allow_backdated_creation,
        overdue_desktop_reminders_enabled=overdue_desktop_reminders_enabled,
        overdue_desktop_reminder_interval_minutes=overdue_desktop_reminder_interval_minutes,
    )


@router.put("/task-policy", response_model=AdminTaskPolicyPublic)
def update_task_policy(
    payload: AdminTaskPolicyUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminTaskPolicyPublic:
    rbac_service.require_system_admin(current_user)
    if (
        payload.overdue_desktop_reminder_interval_minutes
        < system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MIN
        or payload.overdue_desktop_reminder_interval_minutes
        > system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MAX
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Интервал повторных desktop-напоминаний должен быть в диапазоне "
                f"{system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MIN}-"
                f"{system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MAX} минут"
            ),
        )
    allow_backdated_creation = system_settings_service.set_bool(
        session,
        key=system_settings_service.TASK_ALLOW_BACKDATED_CREATION_KEY,
        value=payload.allow_backdated_creation,
    )
    overdue_desktop_reminders_enabled = system_settings_service.set_bool(
        session,
        key=system_settings_service.TASK_OVERDUE_DESKTOP_REMINDERS_ENABLED_KEY,
        value=payload.overdue_desktop_reminders_enabled,
    )
    overdue_desktop_reminder_interval_minutes = system_settings_service.set_int(
        session,
        key=system_settings_service.TASK_OVERDUE_DESKTOP_REMINDER_INTERVAL_MINUTES_KEY,
        value=payload.overdue_desktop_reminder_interval_minutes,
    )
    return AdminTaskPolicyPublic(
        allow_backdated_creation=allow_backdated_creation,
        overdue_desktop_reminders_enabled=overdue_desktop_reminders_enabled,
        overdue_desktop_reminder_interval_minutes=overdue_desktop_reminder_interval_minutes,
    )


@router.get("/desktop-agent", response_model=AdminDesktopAgentPublic)
def get_desktop_agent_state(
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminDesktopAgentPublic:
    rbac_service.require_system_admin(current_user)
    return _resolve_desktop_agent_state(session)


@router.post(
    "/desktop-agent/upload",
    response_model=AdminDesktopAgentUploadResult,
)
def upload_desktop_agent_binary(
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> AdminDesktopAgentUploadResult:
    rbac_service.require_system_admin(current_user)
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=422, detail="Имя файла не указано")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in DESKTOP_AGENT_ALLOWED_EXTS:
        raise HTTPException(status_code=422, detail="Поддерживаются только .exe и .msi")

    file.file.seek(0, 2)
    file_size = int(file.file.tell())
    file.file.seek(0)
    if file_size <= 0:
        raise HTTPException(status_code=422, detail="Файл пустой")
    if file_size > DESKTOP_AGENT_MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Файл слишком большой (максимум 1 ГБ)",
        )

    previous_meta = desktop_agent_service.get_uploaded_agent_meta(session)
    object_key = f"desktop-agent/releases/{uuid4().hex}-{filename}"
    content_type = (file.content_type or "").strip() or "application/octet-stream"

    client = get_minio_client()
    ensure_bucket_exists(settings.MINIO_BUCKET)
    try:
        client.put_object(
            settings.MINIO_BUCKET,
            object_key,
            file.file,
            length=file_size,
            content_type=content_type,
        )
    except S3Error as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось загрузить файл в хранилище: {exc.code}",
        ) from exc

    if previous_meta is not None:
        previous_key = str(previous_meta.get("object_key") or "").strip()
        if previous_key:
            try:
                client.remove_object(settings.MINIO_BUCKET, previous_key)
            except S3Error:
                # Old binary cleanup should not fail upload flow.
                pass

    stored_meta = desktop_agent_service.set_uploaded_agent_meta(
        session,
        object_key=object_key,
        file_name=filename,
        content_type=content_type,
        size_bytes=file_size,
    )
    return AdminDesktopAgentUploadResult(
        configured=True,
        source="uploaded",
        file_name=stored_meta["file_name"],
        content_type=stored_meta["content_type"],
        size_bytes=stored_meta["size_bytes"],
        uploaded_at=stored_meta.get("uploaded_at"),
    )


@router.delete("/desktop-agent", response_model=AdminDesktopAgentPublic)
def clear_uploaded_desktop_agent_binary(
    session: SessionDep,
    current_user: CurrentUser,
) -> AdminDesktopAgentPublic:
    rbac_service.require_system_admin(current_user)
    uploaded_meta = desktop_agent_service.get_uploaded_agent_meta(session)
    if uploaded_meta is not None:
        object_key = str(uploaded_meta.get("object_key") or "").strip()
        if object_key:
            try:
                get_minio_client().remove_object(settings.MINIO_BUCKET, object_key)
            except S3Error:
                pass
    desktop_agent_service.clear_uploaded_agent_meta(session)
    return _resolve_desktop_agent_state(session)
