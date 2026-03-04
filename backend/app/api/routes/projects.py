from datetime import date, datetime, timezone
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from minio.error import S3Error
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.permissions import ROLE_TITLES
from app.integrations.minio_client import get_minio_client
from app.models import (
    GroupMembership,
    OrgGroup,
    Organization,
    Project,
    ProjectAccessSubjectType,
    ProjectMember,
    ProjectMemberRole,
    ProjectSubjectRole,
    Role,
    Task,
    User,
)
from app.repositories import blocks as block_repo
from app.repositories import projects as project_repo
from app.schemas.block import (
    ProjectDepartmentPublic,
    ProjectDepartmentsPublic,
    ProjectDepartmentsUpdate,
)
from app.schemas.project import (
    ProjectAccessGroupPublic,
    ProjectAccessGroupsPublic,
    ProjectAccessGroupsReplace,
    ProjectAccessUserPublic,
    ProjectAccessUsersPublic,
    ProjectAccessUsersReplace,
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberPublic,
    ProjectMembersPublic,
    ProjectMemberUpdate,
    ProjectPublic,
    ProjectsPublic,
    ProjectUpdate,
)
from app.services import project_service, rbac_service
from app.services.calendar_service import build_calendar_view
from app.schemas.calendar import CalendarScope, CalendarViewMode
from app.services.task_service import refresh_deadline_flags_for_open_tasks

router = APIRouter(prefix="/projects", tags=["projects"])

PROJECT_ACCESS_ROLE_KEYS = {"reader", "contributor", "project_admin"}
PROJECT_MEMBER_TO_ACCESS_ROLE: dict[ProjectMemberRole, str] = {
    ProjectMemberRole.READER: "reader",
    ProjectMemberRole.EXECUTOR: "reader",
    ProjectMemberRole.CONTROLLER: "project_admin",
    ProjectMemberRole.MANAGER: "project_admin",
}
GROUP_ROLE_PRIORITY: dict[str, int] = {
    "owner": 30,
    "manager": 20,
    "member": 10,
}
MAX_PAGE_SIZE = 500
PROJECT_ICON_MAX_BYTES = 2 * 1024 * 1024
PROJECT_ICON_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "svg", "gif"}
PROJECT_ICON_CONTENT_TYPE_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "gif": "image/gif",
}


def _project_icon_object_key(project_id: int, ext: str) -> str:
    return f"project-icons/projects/{project_id}/current.{ext}"


def _extract_icon_ext(icon_path: str | None, *, project_id: int) -> str | None:
    raw = (icon_path or "").strip()
    if not raw:
        return None
    marker = f"/projects/{project_id}/icon."
    marker_index = raw.rfind(marker)
    if marker_index == -1:
        return None
    ext_part = raw[marker_index + len(marker) :]
    ext = ext_part.split("?")[0].strip().lower()
    if ext in PROJECT_ICON_EXTENSIONS:
        return ext
    return None


def _resolve_upload_icon_extension(file: UploadFile) -> str:
    ext = ""
    if file.filename and "." in file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower().strip()
    if ext in PROJECT_ICON_EXTENSIONS:
        return ext
    content_type = (file.content_type or "").lower().strip()
    for known_ext, known_content_type in PROJECT_ICON_CONTENT_TYPE_BY_EXT.items():
        if content_type == known_content_type:
            return known_ext
    raise HTTPException(
        status_code=400,
        detail="Поддерживаются только изображения PNG/JPG/WEBP/SVG/GIF",
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _display_owner_name(
    owner_id: int | None,
    owner_full_name: str | None,
    owner_email: str | None,
) -> str | None:
    if owner_id is None:
        return None
    if owner_full_name:
        return owner_full_name
    if owner_email:
        return owner_email
    return f"User #{owner_id}"


def resolve_pagination(
    *,
    skip: int,
    limit: int,
    page: int | None,
    page_size: int | None,
) -> tuple[int, int, int, int]:
    requested_page_size = page_size or limit
    resolved_page_size = max(1, min(requested_page_size, MAX_PAGE_SIZE))
    if page is not None:
        resolved_skip = (page - 1) * resolved_page_size
        resolved_page = page
    else:
        resolved_skip = skip
        resolved_page = (resolved_skip // resolved_page_size) + 1
    return resolved_skip, resolved_page_size, resolved_page, resolved_page_size


def to_project_public(
    project: Project,
    *,
    members_count: int | None = None,
    member_user_ids: list[int] | None = None,
    tasks_count: int | None = None,
) -> ProjectPublic:
    department_names = [
        link.department.name
        for link in project.project_departments
        if link.department is not None and link.department.name
    ]
    if not department_names and project.department is not None and project.department.name:
        department_names = [project.department.name]
    block_link = project.block_links[0] if project.block_links else None
    data = ProjectPublic.model_validate(project)
    return data.model_copy(
        update={
            "owner_name": _display_owner_name(
                project.created_by_id,
                project.creator.full_name if project.creator is not None else None,
                project.creator.email if project.creator is not None else None,
            ),
            "organization_name": (
                project.organization.name if project.organization is not None else None
            ),
            "department_name": project.department.name if project.department is not None else None,
            "department_names": department_names,
            "block_id": block_link.block_id if block_link is not None else None,
            "block_name": (
                block_link.block.name
                if block_link is not None and block_link.block is not None
                else None
            ),
            "members_count": members_count,
            "member_user_ids": member_user_ids
            if member_user_ids is not None
            else list(data.member_user_ids),
            "tasks_count": tasks_count,
        }
    )


def to_project_member_public(member: ProjectMember) -> ProjectMemberPublic:
    user_name = None
    user_email = None
    if member.user is not None:
        user_name = member.user.full_name or member.user.email
        user_email = member.user.email
    base = ProjectMemberPublic.model_validate(member)
    return base.model_copy(
        update={
            "user_name": user_name,
            "user_email": user_email,
        },
    )


def _project_public_with_counts(session: SessionDep, *, project: Project) -> ProjectPublic:
    if project.id is None:
        return to_project_public(project, members_count=0, tasks_count=0)
    members_count = project_repo.get_project_members_count_map(
        session,
        project_ids=[project.id],
    ).get(project.id, 0)
    member_user_ids = project_repo.get_project_member_user_ids_map(
        session,
        project_ids=[project.id],
    ).get(project.id, [])
    tasks_count = project_repo.get_project_tasks_count_map(
        session,
        project_ids=[project.id],
    ).get(project.id, 0)
    return to_project_public(
        project,
        members_count=members_count,
        member_user_ids=member_user_ids,
        tasks_count=tasks_count,
    )


def _resolve_project_role(session: SessionDep, role_key: str) -> Role:
    if role_key not in PROJECT_ACCESS_ROLE_KEYS:
        raise HTTPException(status_code=422, detail="Unsupported project role")
    role = session.exec(select(Role).where(Role.name == role_key)).first()
    if role is None:
        raise HTTPException(status_code=404, detail="Project role not found")
    if role.id is None:
        raise HTTPException(status_code=500, detail="Invalid role record")
    return role


def _upsert_project_subject_role(
    session: SessionDep,
    *,
    project_id: int,
    role_id: int,
    subject_type: ProjectAccessSubjectType,
    subject_user_id: int | None = None,
    subject_group_id: int | None = None,
    is_active: bool = True,
) -> ProjectSubjectRole:
    existing = session.exec(
        select(ProjectSubjectRole).where(
            ProjectSubjectRole.project_id == project_id,
            ProjectSubjectRole.role_id == role_id,
            ProjectSubjectRole.subject_type == subject_type,
            ProjectSubjectRole.subject_user_id == subject_user_id,
            ProjectSubjectRole.subject_group_id == subject_group_id,
        )
    ).first()
    if existing is None:
        existing = ProjectSubjectRole(
            project_id=project_id,
            role_id=role_id,
            subject_type=subject_type,
            subject_user_id=subject_user_id,
            subject_group_id=subject_group_id,
            is_active=is_active,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    else:
        existing.is_active = is_active
        existing.updated_at = utcnow()
    session.add(existing)
    return existing


def _sync_project_member_assignment_to_subject_role(
    session: SessionDep,
    *,
    project_id: int,
    member: ProjectMember,
) -> None:
    role_key = PROJECT_MEMBER_TO_ACCESS_ROLE.get(member.role)
    if role_key is None:
        return
    role = _resolve_project_role(session, role_key)
    _upsert_project_subject_role(
        session,
        project_id=project_id,
        role_id=role.id,
        subject_type=ProjectAccessSubjectType.USER,
        subject_user_id=member.user_id,
        subject_group_id=None,
        is_active=member.is_active,
    )


def _collect_project_access_users(
    session: SessionDep,
    *,
    project_id: int,
) -> ProjectAccessUsersPublic:
    assignments = session.exec(
        select(ProjectSubjectRole)
        .where(
            ProjectSubjectRole.project_id == project_id,
            ProjectSubjectRole.subject_type == ProjectAccessSubjectType.USER,
        )
        .order_by(ProjectSubjectRole.id.asc())
    ).all()
    rows: list[ProjectAccessUserPublic] = []
    for assignment in assignments:
        user = session.get(User, assignment.subject_user_id) if assignment.subject_user_id else None
        role = session.get(Role, assignment.role_id)
        if user is None or role is None:
            continue
        if not assignment.is_active:
            continue
        rows.append(
            ProjectAccessUserPublic(
                user_id=user.id,
                user_name=user.full_name or user.email,
                user_email=user.email,
                role_key=role.name,
                role_title=ROLE_TITLES.get(role.name, role.name),
                is_active=assignment.is_active,
            )
        )
    return ProjectAccessUsersPublic(data=rows, count=len(rows))


def _collect_project_access_groups(
    session: SessionDep,
    *,
    project_id: int,
) -> ProjectAccessGroupsPublic:
    assignments = session.exec(
        select(ProjectSubjectRole)
        .where(
            ProjectSubjectRole.project_id == project_id,
            ProjectSubjectRole.subject_type == ProjectAccessSubjectType.GROUP,
        )
        .order_by(ProjectSubjectRole.id.asc())
    ).all()
    rows: list[ProjectAccessGroupPublic] = []
    has_explicit_group_assignments = bool(assignments)
    for assignment in assignments:
        group = session.get(OrgGroup, assignment.subject_group_id) if assignment.subject_group_id else None
        role = session.get(Role, assignment.role_id)
        if group is None or role is None:
            continue
        if not assignment.is_active:
            continue
        rows.append(
            ProjectAccessGroupPublic(
                group_id=group.id,
                group_name=group.name,
                organization_id=group.organization_id,
                role_key=role.name,
                role_title=ROLE_TITLES.get(role.name, role.name),
                is_active=assignment.is_active,
            )
        )

    # Backward-compatible UX: also expose implicit groups derived from active project participants
    # so the "Доступ групп" tab reflects the real project contour even for legacy/demo data.
    existing_group_ids = {row.group_id for row in rows}
    project_member_user_ids = {
        int(user_id)
        for user_id in session.exec(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.is_active.is_(True),
            )
        ).all()
    }
    if (not has_explicit_group_assignments) and project_member_user_ids:
        primary_group_ids = {
            int(group_id)
            for group_id in session.exec(
                select(User.primary_group_id).where(
                    User.id.in_(sorted(project_member_user_ids)),
                    User.primary_group_id.is_not(None),
                    User.is_active.is_(True),
                )
            ).all()
            if group_id is not None
        }
        users_without_primary = project_member_user_ids - {
            int(user_id)
            for user_id in session.exec(
                select(User.id).where(
                    User.id.in_(sorted(project_member_user_ids)),
                    User.primary_group_id.is_not(None),
                    User.is_active.is_(True),
                )
            ).all()
        }
        fallback_group_ids: set[int] = set()
        if users_without_primary:
            fallback_group_ids = {
                int(group_id)
                for group_id in session.exec(
                    select(GroupMembership.group_id)
                    .join(User, User.id == GroupMembership.user_id)
                    .where(
                        GroupMembership.user_id.in_(sorted(users_without_primary)),
                        GroupMembership.is_active.is_(True),
                        User.is_active.is_(True),
                    )
                ).all()
            }
        for group_id in sorted(primary_group_ids | fallback_group_ids):
            if group_id in existing_group_ids:
                continue
            group = session.get(OrgGroup, group_id)
            if group is None:
                continue
            org = session.get(Organization, group.organization_id) if group.organization_id else None
            if org is not None and org.is_global:
                # Skip global utility groups from implicit rendering.
                continue
            rows.append(
                ProjectAccessGroupPublic(
                    group_id=group.id,
                    group_name=group.name,
                    organization_id=group.organization_id,
                    role_key="contributor",
                    role_title=ROLE_TITLES.get("contributor", "Контрибьютор"),
                    is_active=True,
                )
            )
            existing_group_ids.add(group.id)
    return ProjectAccessGroupsPublic(data=rows, count=len(rows))


def _normalize_group_role_name(role_name: str | None) -> str:
    return (role_name or "").strip().lower() or "member"


def _project_member_role_from_group_role(role_name: str | None) -> ProjectMemberRole:
    normalized = _normalize_group_role_name(role_name)
    if normalized == "owner":
        return ProjectMemberRole.READER
    if normalized in {"manager", "lead", "controller", "admin"}:
        return ProjectMemberRole.CONTROLLER
    return ProjectMemberRole.EXECUTOR


def _collect_group_user_roles(
    session: SessionDep,
    *,
    group_id: int,
) -> dict[int, str]:
    role_by_user: dict[int, str] = {}
    priority_by_user: dict[int, int] = {}
    membership_rows = session.exec(
        select(GroupMembership.user_id, GroupMembership.role_name)
        .join(User, User.id == GroupMembership.user_id)
        .where(
            GroupMembership.group_id == group_id,
            GroupMembership.is_active.is_(True),
            User.is_active.is_(True),
        )
    ).all()
    for user_id, role_name in membership_rows:
        if user_id is None:
            continue
        normalized_role = _normalize_group_role_name(role_name)
        priority = GROUP_ROLE_PRIORITY.get(normalized_role, 0)
        previous_priority = priority_by_user.get(int(user_id), -1)
        if priority >= previous_priority:
            role_by_user[int(user_id)] = normalized_role
            priority_by_user[int(user_id)] = priority

    primary_user_ids = {
        int(user_id)
        for user_id in session.exec(
            select(User.id).where(
                User.primary_group_id == group_id,
                User.is_active.is_(True),
            )
        ).all()
    }
    for user_id in primary_user_ids:
        if user_id not in role_by_user:
            role_by_user[user_id] = "member"
    return role_by_user


def _sync_group_assignment_members(
    session: SessionDep,
    *,
    project_id: int,
    group_id: int,
    is_active: bool,
) -> None:
    if not is_active:
        return

    role_by_user = _collect_group_user_roles(session, group_id=group_id)
    for user_id, group_role_name in role_by_user.items():
        desired_role = _project_member_role_from_group_role(group_role_name)
        member = project_repo.get_project_member(
            session,
            project_id=project_id,
            user_id=user_id,
        )
        if member is None:
            member = ProjectMember(
                project_id=project_id,
                user_id=user_id,
                role=desired_role,
                is_active=True,
            )
            session.add(member)
            _sync_project_member_assignment_to_subject_role(
                session,
                project_id=project_id,
                member=member,
            )
            continue

        member.is_active = True
        if desired_role == ProjectMemberRole.READER:
            # Directors (owner) must stay reader in project members.
            member.role = ProjectMemberRole.READER
        elif member.role != ProjectMemberRole.MANAGER:
            # Preserve manually elevated "manager", update others from group policy.
            member.role = desired_role
        member.updated_at = utcnow()
        session.add(member)
        _sync_project_member_assignment_to_subject_role(
            session,
            project_id=project_id,
            member=member,
        )


def _ensure_actor_keeps_project_admin_access(
    session: SessionDep,
    *,
    project_id: int,
    actor: User,
) -> None:
    if rbac_service.is_system_admin(actor):
        return
    session.flush()
    if not rbac_service.can_view_project(session, project_id=project_id, user=actor):
        raise HTTPException(
            status_code=422,
            detail="Нельзя удалить собственный доступ к проекту",
        )
    if not rbac_service.has_permission(
        session,
        user=actor,
        permission_key="update_project",
        project_id=project_id,
    ):
        raise HTTPException(
            status_code=422,
            detail="Нельзя удалить собственные права администрирования проекта",
        )


@router.get("/", response_model=ProjectsPublic)
def read_projects(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    department_id: int | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> ProjectsPublic:
    resolved_skip, resolved_limit, resolved_page, resolved_page_size = resolve_pagination(
        skip=skip,
        limit=limit,
        page=page,
        page_size=page_size,
    )
    can_view_all = rbac_service.is_system_admin(current_user)
    accessible_project_ids = rbac_service.get_accessible_project_ids(session, user=current_user)

    projects, total = project_repo.list_projects(
        session,
        skip=resolved_skip,
        limit=resolved_limit,
        department_id=department_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        viewer_user_id=current_user.id,
        can_view_all=can_view_all,
        accessible_project_ids=accessible_project_ids if not can_view_all else None,
    )
    project_ids = [project.id for project in projects if project.id is not None]
    members_count_map = project_repo.get_project_members_count_map(
        session,
        project_ids=project_ids,
    )
    member_user_ids_map = project_repo.get_project_member_user_ids_map(
        session,
        project_ids=project_ids,
    )
    tasks_count_map = project_repo.get_project_tasks_count_map(
        session,
        project_ids=project_ids,
    )
    items = [
        to_project_public(
            project,
            members_count=members_count_map.get(project.id, 0),
            member_user_ids=member_user_ids_map.get(project.id, []),
            tasks_count=tasks_count_map.get(project.id, 0),
        )
        for project in projects
        if project.id is not None
    ]

    return ProjectsPublic(
        data=items,
        count=len(items),
        total=total,
        page=resolved_page,
        page_size=resolved_page_size,
    )


@router.post("/", response_model=ProjectPublic)
def create_project(
    session: SessionDep,
    current_user: CurrentUser,
    payload: ProjectCreate,
) -> ProjectPublic:
    rbac_service.require_controller(current_user)
    organization_id = payload.organization_id
    if organization_id is not None:
        if session.get(Organization, organization_id) is None:
            raise HTTPException(status_code=404, detail="Organization not found")
    elif payload.department_id is not None:
        organization_id = session.exec(
            select(OrgGroup.organization_id).where(
                OrgGroup.legacy_department_id == payload.department_id
            )
        ).first()
    if organization_id is None:
        organization_id = session.exec(
            select(Organization.id).where(Organization.is_global.is_(True))
        ).first()

    project = project_service.create_project_with_defaults(
        session,
        creator=current_user,
        name=payload.name,
        icon=payload.icon,
        description=payload.description,
        organization_id=organization_id,
        department_id=payload.department_id,
        require_close_comment=payload.require_close_comment,
        require_close_attachment=payload.require_close_attachment,
        deadline_yellow_days=payload.deadline_yellow_days,
        deadline_normal_days=payload.deadline_normal_days,
    )
    if payload.department_id is not None:
        project_repo.replace_project_departments(
            session,
            project_id=project.id,
            department_ids=[payload.department_id],
        )
    if payload.block_id is not None:
        block_repo.add_block_project(session, block_id=payload.block_id, project_id=project.id)
        project = project_repo.get_project(session, project.id) or project

    return to_project_public(project, members_count=0, tasks_count=0)


@router.get("/{project_id}", response_model=ProjectPublic)
def read_project(
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectPublic:
    project = project_repo.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rbac_service.require_project_access(session, project_id=project_id, user=current_user)
    viewer_user_ids = (
        None
        if rbac_service.is_system_admin(current_user)
        else rbac_service.get_same_group_user_ids(session, user=current_user)
    )
    members_count = project_repo.get_project_members_count_map(session, project_ids=[project_id]).get(
        project_id, 0
    )
    member_user_ids = project_repo.get_project_member_user_ids_map(
        session,
        project_ids=[project_id],
    ).get(project_id, [])
    tasks_count = project_repo.get_project_tasks_count_map(session, project_ids=[project_id]).get(
        project_id, 0
    )
    return to_project_public(
        project,
        members_count=members_count,
        member_user_ids=member_user_ids,
        tasks_count=tasks_count,
    )


@router.post("/{project_id}/icon", response_model=ProjectPublic)
async def upload_project_icon(
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile = File(...),
) -> ProjectPublic:
    project = project_repo.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    rbac_service.require_project_controller_or_manager(
        session,
        project_id=project_id,
        user=current_user,
    )

    icon_bytes = await file.read()
    if not icon_bytes:
        raise HTTPException(status_code=400, detail="Файл иконки пустой")
    if len(icon_bytes) > PROJECT_ICON_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Размер иконки не должен превышать 2 МБ")

    ext = _resolve_upload_icon_extension(file)
    content_type = PROJECT_ICON_CONTENT_TYPE_BY_EXT.get(ext, file.content_type or "application/octet-stream")
    object_key = _project_icon_object_key(project_id, ext)
    old_ext = _extract_icon_ext(project.icon, project_id=project_id)

    client = get_minio_client()
    try:
        client.put_object(
            settings.MINIO_BUCKET,
            object_key,
            BytesIO(icon_bytes),
            len(icon_bytes),
            content_type=content_type,
        )
        if old_ext and old_ext != ext:
            old_key = _project_icon_object_key(project_id, old_ext)
            try:
                client.remove_object(settings.MINIO_BUCKET, old_key)
            except S3Error:
                pass
    except S3Error as exc:
        raise HTTPException(status_code=502, detail="Не удалось сохранить иконку проекта") from exc

    project.icon = f"{settings.API_V1_STR}/projects/{project_id}/icon.{ext}"
    project.updated_at = utcnow()
    updated = project_repo.update_project(session, project)
    return _project_public_with_counts(session, project=updated)


@router.get("/{project_id}/icon.{ext}")
def read_project_icon(
    project_id: int,
    ext: str,
    session: SessionDep,
) -> Response:
    project = project_repo.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    normalized_ext = ext.lower().strip()
    current_ext = _extract_icon_ext(project.icon, project_id=project_id)
    if current_ext is None or normalized_ext != current_ext:
        raise HTTPException(status_code=404, detail="Иконка проекта не найдена")

    object_key = _project_icon_object_key(project_id, current_ext)
    object_stream = None
    try:
        object_stream = get_minio_client().get_object(settings.MINIO_BUCKET, object_key)
        content = object_stream.read()
    except S3Error as exc:
        raise HTTPException(status_code=404, detail="Иконка проекта не найдена") from exc
    finally:
        if object_stream is not None:
            object_stream.close()
            object_stream.release_conn()

    return Response(
        content=content,
        media_type=PROJECT_ICON_CONTENT_TYPE_BY_EXT.get(current_ext, "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/{project_id}/wall")
def read_project_wall(
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    day: date | None = Query(default=None, alias="date"),
    mode: CalendarViewMode = Query(default=CalendarViewMode.MONTH),
) -> dict:
    project = project_repo.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rbac_service.require_project_access(session, project_id=project_id, user=current_user)
    refresh_deadline_flags_for_open_tasks(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    viewer_user_ids = (
        None if can_view_all else rbac_service.get_same_group_user_ids(session, user=current_user)
    )
    members_count = project_repo.get_project_members_count_map(session, project_ids=[project_id]).get(
        project_id, 0
    )
    tasks_count = project_repo.get_project_tasks_count_map(session, project_ids=[project_id]).get(
        project_id, 0
    )
    project_public = to_project_public(
        project,
        members_count=members_count,
        tasks_count=tasks_count,
    )
    calendar = build_calendar_view(
        session,
        anchor=day or date.today(),
        mode=mode,
        scope=CalendarScope.PROJECT,
        project_id=project_id,
        department_id=None,
        project_ids={project_id},
        viewer_user_id=current_user.id,
        viewer_user_ids=viewer_user_ids,
    )
    participant_statement = (
        select(Task.assignee_id, User.full_name, User.email, func.count(Task.id))
        .join(User, User.id == Task.assignee_id, isouter=True)
        .where(Task.project_id == project_id)
        .group_by(Task.assignee_id, User.full_name, User.email)
        .order_by(func.count(Task.id).desc())
    )
    if viewer_user_ids is not None:
        if not viewer_user_ids:
            participant_rows = []
        else:
            participant_rows = session.exec(
                participant_statement.where(Task.assignee_id.in_(sorted(viewer_user_ids)))
            ).all()
    else:
        participant_rows = session.exec(participant_statement).all()
    participants = [
        {
            "user_id": row[0],
            "user_name": row[1] or row[2] or (f"User #{row[0]}" if row[0] is not None else "Не назначен"),
            "tasks_count": int(row[3]),
        }
        for row in participant_rows
    ]
    group_rows = session.exec(
        select(OrgGroup.id, OrgGroup.name, OrgGroup.organization_id, Role.name)
        .join(
            ProjectSubjectRole,
            ProjectSubjectRole.subject_group_id == OrgGroup.id,
        )
        .join(Role, Role.id == ProjectSubjectRole.role_id)
        .where(
            ProjectSubjectRole.project_id == project_id,
            ProjectSubjectRole.subject_type == ProjectAccessSubjectType.GROUP,
            ProjectSubjectRole.is_active.is_(True),
        )
        .order_by(OrgGroup.name.asc(), Role.name.asc())
    ).all()
    groups = [
        {
            "group_id": row[0],
            "group_name": row[1],
            "organization_id": row[2],
            "role_key": row[3],
            "role_title": ROLE_TITLES.get(row[3], row[3]),
        }
        for row in group_rows
    ]
    return {
        "project": project_public.model_dump(),
        "calendar": calendar.model_dump(),
        "participants": participants,
        "groups": groups,
    }


@router.patch("/{project_id}", response_model=ProjectPublic)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectPublic:
    project = project_repo.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rbac_service.require_project_controller_or_manager(
        session,
        project_id=project_id,
        user=current_user,
    )
    update_payload = payload.model_dump(exclude_unset=True)
    if "organization_id" in update_payload and update_payload["organization_id"] is not None:
        organization = session.get(Organization, int(update_payload["organization_id"]))
        if organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
    elif "department_id" in update_payload and update_payload["department_id"] is not None:
        inferred_org_id = session.exec(
            select(OrgGroup.organization_id).where(
                OrgGroup.legacy_department_id == int(update_payload["department_id"])
            )
        ).first()
        if inferred_org_id is not None:
            update_payload["organization_id"] = int(inferred_org_id)

    project.sqlmodel_update(update_payload)
    project.updated_at = utcnow()
    updated = project_repo.update_project(session, project)
    if payload.department_id is not None:
        project_repo.replace_project_departments(
            session,
            project_id=project_id,
            department_ids=[payload.department_id],
        )
    if payload.block_id is not None:
        block_repo.add_block_project(
            session,
            block_id=payload.block_id,
            project_id=project_id,
        )
    updated = project_repo.get_project(session, project_id) or updated

    members_count = project_repo.get_project_members_count_map(session, project_ids=[project_id]).get(
        project_id, 0
    )
    tasks_count = project_repo.get_project_tasks_count_map(session, project_ids=[project_id]).get(
        project_id, 0
    )
    return to_project_public(
        updated,
        members_count=members_count,
        tasks_count=tasks_count,
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    project = project_repo.get_project(session, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rbac_service.require_project_manager(session, project_id=project_id, user=current_user)
    project_repo.delete_project(session, project)

    return {"message": "Project deleted successfully"}


@router.get("/{project_id}/members", response_model=ProjectMembersPublic)
def read_project_members(
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> ProjectMembersPublic:
    rbac_service.require_project_access(session, project_id=project_id, user=current_user)
    members, count = project_repo.list_project_members(
        session,
        project_id,
        skip=skip,
        limit=limit,
    )
    return ProjectMembersPublic(
        data=[to_project_member_public(member) for member in members],
        count=count,
    )


@router.post("/{project_id}/members", response_model=ProjectMemberPublic)
def create_project_member(
    project_id: int,
    payload: ProjectMemberCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectMemberPublic:
    rbac_service.require_project_controller_or_manager(
        session,
        project_id=project_id,
        user=current_user,
    )

    existing = project_repo.get_project_member(
        session,
        project_id=project_id,
        user_id=payload.user_id,
    )
    if existing:
        raise HTTPException(status_code=409, detail="User already in project")

    member = ProjectMember(
        project_id=project_id,
        user_id=payload.user_id,
        role=payload.role,
        is_active=payload.is_active,
    )

    created = project_repo.create_project_member(session, member)
    _sync_project_member_assignment_to_subject_role(
        session,
        project_id=project_id,
        member=created,
    )
    session.commit()
    session.refresh(created)
    return to_project_member_public(created)


@router.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberPublic)
def update_project_member(
    project_id: int,
    user_id: int,
    payload: ProjectMemberUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectMemberPublic:
    rbac_service.require_project_controller_or_manager(
        session,
        project_id=project_id,
        user=current_user,
    )

    member = project_repo.get_project_member(
        session,
        project_id=project_id,
        user_id=user_id,
    )
    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")

    member.sqlmodel_update(payload.model_dump(exclude_unset=True))
    member.updated_at = utcnow()
    updated = project_repo.update_project_member(session, member)
    _sync_project_member_assignment_to_subject_role(
        session,
        project_id=project_id,
        member=updated,
    )
    session.commit()
    session.refresh(updated)
    return to_project_member_public(updated)


@router.delete("/{project_id}/members/{user_id}")
def delete_project_member(
    project_id: int,
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    rbac_service.require_project_manager(session, project_id=project_id, user=current_user)

    member = project_repo.get_project_member(
        session,
        project_id=project_id,
        user_id=user_id,
    )
    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")

    project_repo.delete_project_member(session, member)
    subject_roles = session.exec(
        select(ProjectSubjectRole).where(
            ProjectSubjectRole.project_id == project_id,
            ProjectSubjectRole.subject_type == ProjectAccessSubjectType.USER,
            ProjectSubjectRole.subject_user_id == user_id,
        )
    ).all()
    for subject_role in subject_roles:
        subject_role.is_active = False
        subject_role.updated_at = utcnow()
        session.add(subject_role)
    session.commit()
    return {"message": "Project member deleted successfully"}


@router.get("/{project_id}/departments", response_model=ProjectDepartmentsPublic)
def read_project_departments(
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectDepartmentsPublic:
    rbac_service.require_project_access(session, project_id=project_id, user=current_user)
    rows = project_repo.list_project_departments(session, project_id=project_id)
    data = [
        ProjectDepartmentPublic(
            department_id=row.department_id,
            department_name=row.department.name if row.department is not None else None,
        )
        for row in rows
    ]
    return ProjectDepartmentsPublic(data=data, count=len(data))


@router.put("/{project_id}/departments", response_model=ProjectDepartmentsPublic)
def replace_project_departments(
    project_id: int,
    payload: ProjectDepartmentsUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectDepartmentsPublic:
    rbac_service.require_project_controller_or_manager(
        session,
        project_id=project_id,
        user=current_user,
    )
    rows = project_repo.replace_project_departments(
        session,
        project_id=project_id,
        department_ids=sorted(set(payload.department_ids)),
    )
    data = [
        ProjectDepartmentPublic(
            department_id=row.department_id,
            department_name=row.department.name if row.department is not None else None,
        )
        for row in rows
    ]
    return ProjectDepartmentsPublic(data=data, count=len(data))


@router.get("/{project_id}/access/users", response_model=ProjectAccessUsersPublic)
def read_project_access_users(
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectAccessUsersPublic:
    rbac_service.require_project_access(session, project_id=project_id, user=current_user)
    return _collect_project_access_users(session, project_id=project_id)


@router.put("/{project_id}/access/users", response_model=ProjectAccessUsersPublic)
def replace_project_access_users(
    project_id: int,
    payload: ProjectAccessUsersReplace,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectAccessUsersPublic:
    rbac_service.require_project_manager(session, project_id=project_id, user=current_user)
    project = project_repo.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    existing = session.exec(
        select(ProjectSubjectRole).where(
            ProjectSubjectRole.project_id == project_id,
            ProjectSubjectRole.subject_type == ProjectAccessSubjectType.USER,
        )
    ).all()
    for assignment in existing:
        assignment.is_active = False
        assignment.updated_at = utcnow()
        session.add(assignment)

    for item in payload.assignments:
        user = session.get(User, item.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User not found: {item.user_id}")
        role = _resolve_project_role(session, item.role_key)
        _upsert_project_subject_role(
            session,
            project_id=project_id,
            role_id=role.id,
            subject_type=ProjectAccessSubjectType.USER,
            subject_user_id=item.user_id,
            subject_group_id=None,
            is_active=item.is_active,
        )
    _ensure_actor_keeps_project_admin_access(
        session,
        project_id=project_id,
        actor=current_user,
    )
    session.commit()
    return _collect_project_access_users(session, project_id=project_id)


@router.get("/{project_id}/access/groups", response_model=ProjectAccessGroupsPublic)
def read_project_access_groups(
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectAccessGroupsPublic:
    rbac_service.require_project_access(session, project_id=project_id, user=current_user)
    return _collect_project_access_groups(session, project_id=project_id)


@router.put("/{project_id}/access/groups", response_model=ProjectAccessGroupsPublic)
def replace_project_access_groups(
    project_id: int,
    payload: ProjectAccessGroupsReplace,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectAccessGroupsPublic:
    rbac_service.require_project_manager(session, project_id=project_id, user=current_user)
    project = project_repo.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    existing = session.exec(
        select(ProjectSubjectRole).where(
            ProjectSubjectRole.project_id == project_id,
            ProjectSubjectRole.subject_type == ProjectAccessSubjectType.GROUP,
        )
    ).all()
    for assignment in existing:
        assignment.is_active = False
        assignment.updated_at = utcnow()
        session.add(assignment)

    for item in payload.assignments:
        group = session.get(OrgGroup, item.group_id)
        if group is None:
            raise HTTPException(status_code=404, detail=f"Group not found: {item.group_id}")
        role = _resolve_project_role(session, item.role_key)
        _upsert_project_subject_role(
            session,
            project_id=project_id,
            role_id=role.id,
            subject_type=ProjectAccessSubjectType.GROUP,
            subject_user_id=None,
            subject_group_id=item.group_id,
            is_active=item.is_active,
        )
        _sync_group_assignment_members(
            session,
            project_id=project_id,
            group_id=item.group_id,
            is_active=item.is_active,
        )
    _ensure_actor_keeps_project_admin_access(
        session,
        project_id=project_id,
        actor=current_user,
    )
    session.commit()
    return _collect_project_access_groups(session, project_id=project_id)
