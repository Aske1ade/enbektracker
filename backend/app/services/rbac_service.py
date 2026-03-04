from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlmodel import Session, func, select

from app.core.permissions import ALL_PERMISSION_KEYS
from app.models import (
    GroupMembership,
    OrgGroup,
    Organization,
    OrganizationMembership,
    Permission,
    Project,
    ProjectDepartment,
    ProjectAccessSubjectType,
    ProjectMember,
    ProjectMemberRole,
    ProjectSubjectRole,
    Task,
    TaskAssignee,
    Role,
    RolePermission,
    SystemRole,
    User,
)
from app.repositories import projects as project_repo


LEGACY_PROJECT_MEMBER_TO_ROLE_KEY: dict[ProjectMemberRole, str] = {
    ProjectMemberRole.READER: "reader",
    ProjectMemberRole.EXECUTOR: "reader",
    ProjectMemberRole.CONTROLLER: "project_admin",
    ProjectMemberRole.MANAGER: "project_admin",
}
MANAGED_GROUP_ROLE_NAMES = {
    "owner",
    "manager",
    "lead",
    "controller",
    "admin",
    "директор",
    "руководитель",
}
ORG_OWNER_ROLE_NAMES = {
    "owner",
    "директор",
}


def _normalized_role_name(role_name: str | None) -> str:
    return (role_name or "").strip().lower()


def _is_managed_group_role(role_name: str | None) -> bool:
    normalized = _normalized_role_name(role_name)
    if normalized in MANAGED_GROUP_ROLE_NAMES:
        return True
    # Accept descriptive variants like "руководитель департамента".
    return "руковод" in normalized or "директор" in normalized


def _is_org_owner_role(role_name: str | None) -> bool:
    normalized = _normalized_role_name(role_name)
    if normalized in ORG_OWNER_ROLE_NAMES:
        return True
    return "директор" in normalized


def canonical_system_role(user: User) -> SystemRole:
    if user.is_superuser:
        return SystemRole.SYSTEM_ADMIN
    if user.system_role in {
        SystemRole.SYSTEM_ADMIN,
        SystemRole.ADMIN,
        SystemRole.MANAGER,
    }:
        return SystemRole.SYSTEM_ADMIN
    return SystemRole.USER


def is_system_admin(user: User) -> bool:
    return canonical_system_role(user) == SystemRole.SYSTEM_ADMIN


def is_regular_user(user: User) -> bool:
    return canonical_system_role(user) == SystemRole.USER


def require_system_admin(user: User) -> None:
    if not is_system_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admin role required",
        )


def require_manager(user: User) -> None:
    require_system_admin(user)


def require_controller(user: User) -> None:
    require_system_admin(user)


def get_project_membership(
    session: Session,
    *,
    project_id: int,
    user_id: int,
) -> ProjectMember | None:
    return project_repo.get_project_member(session, project_id=project_id, user_id=user_id)


def _get_user_group_ids(session: Session, *, user: User) -> set[int]:
    membership_rows = session.exec(
        select(GroupMembership.group_id, GroupMembership.is_active).where(
            GroupMembership.user_id == user.id,
        )
    ).all()
    membership_state_by_group_id = {
        int(group_id): bool(is_active)
        for group_id, is_active in membership_rows
        if group_id is not None
    }
    group_ids = {
        group_id
        for group_id, is_active in membership_state_by_group_id.items()
        if is_active
    }
    if user.primary_group_id is not None:
        primary_group_id = int(user.primary_group_id)
        primary_membership_state = membership_state_by_group_id.get(primary_group_id)
        if primary_membership_state is None or primary_membership_state:
            group_ids.add(primary_group_id)
    if user.department_id is not None:
        legacy_group_id = session.exec(
            select(OrgGroup.id).where(OrgGroup.legacy_department_id == user.department_id)
        ).first()
        if legacy_group_id is not None:
            legacy_group_id_int = int(legacy_group_id)
            legacy_membership_state = membership_state_by_group_id.get(legacy_group_id_int)
            if legacy_membership_state is None or legacy_membership_state:
                group_ids.add(legacy_group_id_int)
    return group_ids


def get_user_group_ids(session: Session, *, user: User) -> set[int]:
    return _get_user_group_ids(session, user=user)


def get_same_group_user_ids(session: Session, *, user: User) -> set[int]:
    if user.id is None:
        return set()
    group_ids = _get_user_group_ids(session, user=user)
    if not group_ids:
        return {int(user.id)}
    result = _get_user_ids_for_groups(session, group_ids=group_ids)
    result.add(int(user.id))
    return result


def _get_direct_managed_group_ids(session: Session, *, user: User) -> set[int]:
    membership_rows = session.exec(
        select(GroupMembership.group_id, GroupMembership.role_name).where(
            GroupMembership.user_id == user.id,
            GroupMembership.is_active.is_(True),
        )
    ).all()
    managed_group_ids = {
        int(group_id)
        for group_id, role_name in membership_rows
        if group_id is not None and _is_managed_group_role(role_name)
    }
    # Fallback: if role exists on organization level and primary group is set, treat
    # the primary group as managed contour.
    effective_group_ids = _get_user_group_ids(session, user=user)
    if user.primary_group_id is not None and int(user.primary_group_id) in effective_group_ids:
        primary_group = session.get(OrgGroup, int(user.primary_group_id))
        if primary_group is not None and primary_group.organization_id is not None:
            org_membership_role = session.exec(
                select(OrganizationMembership.role_name).where(
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.organization_id == primary_group.organization_id,
                    OrganizationMembership.is_active.is_(True),
                )
            ).first()
            if _is_managed_group_role(org_membership_role):
                managed_group_ids.add(int(user.primary_group_id))
    return _expand_group_descendants(session, managed_group_ids)


def _expand_organization_descendants(
    session: Session,
    *,
    organization_ids: set[int],
) -> set[int]:
    if not organization_ids:
        return set()
    result = set(organization_ids)
    frontier = set(organization_ids)
    while frontier:
        child_ids = {
            int(org_id)
            for org_id in session.exec(
                select(Organization.id).where(
                    Organization.parent_organization_id.in_(sorted(frontier))
                )
            ).all()
        }
        new_ids = child_ids - result
        if not new_ids:
            break
        result |= new_ids
        frontier = new_ids
    return result


def _expand_group_descendants(session: Session, group_ids: set[int]) -> set[int]:
    if not group_ids:
        return set()
    result = set(group_ids)
    frontier = set(group_ids)
    while frontier:
        child_ids = {
            int(group_id)
            for group_id in session.exec(
                select(OrgGroup.id).where(OrgGroup.parent_group_id.in_(sorted(frontier)))
            ).all()
        }
        new_ids = child_ids - result
        if not new_ids:
            break
        result |= new_ids
        frontier = new_ids
    return result


def get_group_descendant_ids(session: Session, *, group_id: int) -> set[int]:
    return _expand_group_descendants(session, {group_id})


def _get_managed_organization_ids(session: Session, *, user: User) -> set[int]:
    active_group_org_ids = {
        int(organization_id)
        for organization_id in session.exec(
            select(OrgGroup.organization_id)
            .join(GroupMembership, GroupMembership.group_id == OrgGroup.id)
            .where(
                GroupMembership.user_id == user.id,
                GroupMembership.is_active.is_(True),
                OrgGroup.organization_id.is_not(None),
            )
        ).all()
        if organization_id is not None
    }
    org_membership_rows = session.exec(
        select(
            OrganizationMembership.organization_id,
            OrganizationMembership.role_name,
        ).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
        )
    ).all()
    direct_org_ids = {
        int(org_id)
        for org_id, role_name in org_membership_rows
        if org_id is not None and _is_org_owner_role(role_name)
    }
    # Guard against stale organization roles: organization scope is valid only
    # while the user has at least one active group membership in that organization.
    if active_group_org_ids:
        direct_org_ids &= active_group_org_ids
    else:
        direct_org_ids = set()
    # Fallback: block director can be configured as `owner` only on top-level group
    # without explicit organization_membership. Treat this as organization owner scope.
    top_group_owner_org_rows = session.exec(
        select(OrgGroup.organization_id, GroupMembership.role_name)
        .join(GroupMembership, GroupMembership.group_id == OrgGroup.id)
        .where(
            GroupMembership.user_id == user.id,
            GroupMembership.is_active.is_(True),
            OrgGroup.organization_id.is_not(None),
            OrgGroup.parent_group_id.is_(None),
        )
    ).all()
    top_group_owner_org_ids = {
        int(organization_id)
        for organization_id, role_name in top_group_owner_org_rows
        if organization_id is not None and _is_org_owner_role(role_name)
    }
    direct_org_ids |= top_group_owner_org_ids
    return _expand_organization_descendants(session, organization_ids=direct_org_ids)


def _get_user_ids_for_groups(session: Session, *, group_ids: set[int]) -> set[int]:
    if not group_ids:
        return set()
    membership_user_ids = {
        int(user_id)
        for user_id in session.exec(
            select(GroupMembership.user_id).where(
                GroupMembership.is_active.is_(True),
                GroupMembership.group_id.in_(sorted(group_ids)),
            )
        ).all()
    }
    primary_user_rows = session.exec(
        select(User.id, User.primary_group_id).where(User.primary_group_id.in_(sorted(group_ids)))
    ).all()
    primary_membership_rows = session.exec(
        select(GroupMembership.user_id, GroupMembership.group_id, GroupMembership.is_active).where(
            GroupMembership.group_id.in_(sorted(group_ids))
        )
    ).all()
    primary_membership_state = {
        (int(user_id), int(group_id)): bool(is_active)
        for user_id, group_id, is_active in primary_membership_rows
        if user_id is not None and group_id is not None
    }
    primary_user_ids: set[int] = set()
    for user_id, primary_group_id in primary_user_rows:
        if user_id is None or primary_group_id is None:
            continue
        state = primary_membership_state.get((int(user_id), int(primary_group_id)))
        if state is None or state:
            primary_user_ids.add(int(user_id))
    return membership_user_ids | primary_user_ids


def _get_project_ids_for_group_users(
    session: Session,
    *,
    group_ids: set[int],
) -> set[int]:
    if not group_ids:
        return set()
    group_user_ids = _get_user_ids_for_groups(session, group_ids=group_ids)
    if not group_user_ids:
        return set()
    return {
        int(project_id)
        for project_id in session.exec(
            select(ProjectMember.project_id).where(
                ProjectMember.user_id.in_(sorted(group_user_ids)),
                ProjectMember.is_active.is_(True),
            )
        ).all()
        if project_id is not None
    }


def _get_legacy_department_ids_for_groups(
    session: Session,
    *,
    group_ids: set[int],
) -> set[int]:
    if not group_ids:
        return set()
    return {
        int(department_id)
        for department_id in session.exec(
            select(OrgGroup.legacy_department_id).where(
                OrgGroup.id.in_(sorted(group_ids)),
                OrgGroup.legacy_department_id.is_not(None),
            )
        ).all()
        if department_id is not None
    }


def _get_project_ids_for_groups(
    session: Session,
    *,
    group_ids: set[int],
) -> set[int]:
    if not group_ids:
        return set()

    project_ids_from_assignments = {
        int(project_id)
        for project_id in session.exec(
            select(ProjectSubjectRole.project_id).where(
                ProjectSubjectRole.subject_type == ProjectAccessSubjectType.GROUP,
                ProjectSubjectRole.subject_group_id.in_(sorted(group_ids)),
                ProjectSubjectRole.is_active.is_(True),
            )
        ).all()
        if project_id is not None
    }

    legacy_department_ids = _get_legacy_department_ids_for_groups(
        session,
        group_ids=group_ids,
    )
    if not legacy_department_ids:
        return project_ids_from_assignments

    project_ids_from_legacy_departments = {
        int(project_id)
        for project_id in session.exec(
            select(Project.id).where(Project.department_id.in_(sorted(legacy_department_ids)))
        ).all()
    }
    project_ids_from_department_links = {
        int(project_id)
        for project_id in session.exec(
            select(ProjectDepartment.project_id).where(
                ProjectDepartment.department_id.in_(sorted(legacy_department_ids))
            )
        ).all()
    }

    return (
        project_ids_from_assignments
        | project_ids_from_legacy_departments
        | project_ids_from_department_links
    )


def get_project_ids_for_group_ids(
    session: Session,
    *,
    group_ids: set[int],
) -> set[int]:
    return _get_project_ids_for_groups(session, group_ids=group_ids)


def has_project_admin_scope(
    session: Session,
    *,
    user: User,
    project_ids: set[int] | None = None,
) -> bool:
    if is_system_admin(user):
        return True

    role_id = _get_role_id_by_name(session, "project_admin")
    if role_id is not None:
        group_ids = _get_user_group_ids(session, user=user)
        subject_condition = (
            (ProjectSubjectRole.subject_type == ProjectAccessSubjectType.USER)
            & (ProjectSubjectRole.subject_user_id == user.id)
        )
        if group_ids:
            subject_condition = or_(
                subject_condition,
                (
                    (ProjectSubjectRole.subject_type == ProjectAccessSubjectType.GROUP)
                    & (ProjectSubjectRole.subject_group_id.in_(sorted(group_ids)))
                ),
            )
        statement = select(ProjectSubjectRole.id).where(
            ProjectSubjectRole.is_active.is_(True),
            ProjectSubjectRole.role_id == role_id,
            subject_condition,
        )
        if project_ids is not None:
            if not project_ids:
                statement = statement.where(False)
            else:
                statement = statement.where(
                    ProjectSubjectRole.project_id.in_(sorted(project_ids))
                )
        if session.exec(statement.limit(1)).first() is not None:
            return True

    legacy_statement = select(ProjectMember.id).where(
        ProjectMember.user_id == user.id,
        ProjectMember.is_active.is_(True),
        ProjectMember.role.in_([ProjectMemberRole.CONTROLLER, ProjectMemberRole.MANAGER]),
    )
    if project_ids is not None:
        if not project_ids:
            legacy_statement = legacy_statement.where(False)
        else:
            legacy_statement = legacy_statement.where(
                ProjectMember.project_id.in_(sorted(project_ids))
            )
    if session.exec(legacy_statement.limit(1)).first() is not None:
        return True

    return False


def can_use_extended_dashboard_scope(
    session: Session,
    *,
    user: User,
    project_ids: set[int] | None = None,
) -> bool:
    if is_system_admin(user):
        return True
    if _get_direct_managed_group_ids(session, user=user):
        return True
    if project_ids:
        return True
    return has_project_admin_scope(session, user=user, project_ids=project_ids)


def get_dashboard_viewer_user_ids(
    session: Session,
    *,
    user: User,
    scope_mode: str = "managed",
    project_ids: set[int] | None = None,
) -> set[int] | None:
    if is_system_admin(user):
        return None

    if scope_mode == "managed":
        if has_project_admin_scope(session, user=user, project_ids=project_ids):
            return None
        managed_org_ids = _get_managed_organization_ids(session, user=user)
        if managed_org_ids:
            # Block/organization leaders can see the whole org contour.
            return None
        managed_group_ids = _get_direct_managed_group_ids(session, user=user)
        if managed_group_ids:
            # Group leaders are restricted to their group contour.
            scoped_user_ids = _get_user_ids_for_groups(session, group_ids=managed_group_ids)
            scoped_user_ids.add(int(user.id))
            return scoped_user_ids
        if project_ids:
            # Reader/contributor scope: see all tasks inside selected accessible projects.
            return None

    return {int(user.id)}


def get_task_viewer_user_ids(
    session: Session,
    *,
    user: User,
    project_ids: set[int] | None = None,
) -> set[int] | None:
    if is_system_admin(user):
        return None

    if has_project_admin_scope(session, user=user, project_ids=project_ids):
        return None

    managed_org_ids = _get_managed_organization_ids(session, user=user)
    if managed_org_ids:
        # Organization leaders can view the full project contour.
        return None
    managed_group_ids = _get_direct_managed_group_ids(session, user=user)
    if managed_group_ids:
        return None

    if project_ids:
        # Reader/contributor scope: can view all tasks of accessible projects.
        return None

    return {int(user.id)}


def get_task_participant_user_ids(session: Session, *, task: Task) -> set[int]:
    participant_ids = {
        int(user_id)
        for user_id in [task.creator_id, task.assignee_id, task.controller_id]
        if user_id is not None
    }
    extra_assignee_ids = {
        int(user_id)
        for user_id in session.exec(
            select(TaskAssignee.user_id).where(TaskAssignee.task_id == task.id)
        ).all()
    }
    return participant_ids | extra_assignee_ids


def can_view_task(session: Session, *, task: Task, user: User) -> bool:
    if is_system_admin(user):
        return True
    if not can_view_project(session, project_id=task.project_id, user=user):
        return False
    if has_permission(
        session,
        user=user,
        permission_key="issue_read",
        project_id=task.project_id,
    ):
        return True
    if has_project_admin_scope(session, user=user, project_ids={task.project_id}):
        return True
    if _get_managed_organization_ids(session, user=user):
        return True
    managed_group_ids = _get_direct_managed_group_ids(session, user=user)
    if managed_group_ids:
        participant_ids = get_task_participant_user_ids(session, task=task)
        managed_user_ids = _get_user_ids_for_groups(session, group_ids=managed_group_ids)
        if participant_ids & managed_user_ids:
            return True

    participant_ids = get_task_participant_user_ids(session, task=task)
    return user.id in participant_ids


def _get_role_id_by_name(session: Session, role_name: str) -> int | None:
    return session.exec(select(Role.id).where(Role.name == role_name)).first()


def _get_project_subject_role_ids_for_user(
    session: Session,
    *,
    user: User,
    project_id: int | None = None,
) -> set[int]:
    group_ids = _get_user_group_ids(session, user=user)

    subject_condition = (
        (ProjectSubjectRole.subject_type == ProjectAccessSubjectType.USER)
        & (ProjectSubjectRole.subject_user_id == user.id)
    )
    if group_ids:
        subject_condition = or_(
            subject_condition,
            (
                (ProjectSubjectRole.subject_type == ProjectAccessSubjectType.GROUP)
                & (ProjectSubjectRole.subject_group_id.in_(sorted(group_ids)))
            ),
        )

    statement = select(ProjectSubjectRole.role_id).where(
        ProjectSubjectRole.is_active.is_(True),
        subject_condition,
    )
    if project_id is not None:
        statement = statement.where(ProjectSubjectRole.project_id == project_id)

    return {int(role_id) for role_id in session.exec(statement).all()}


def _get_project_subject_project_ids_for_user(
    session: Session,
    *,
    user: User,
) -> set[int]:
    group_ids = _get_user_group_ids(session, user=user)
    subject_condition = (
        (ProjectSubjectRole.subject_type == ProjectAccessSubjectType.USER)
        & (ProjectSubjectRole.subject_user_id == user.id)
    )
    if group_ids:
        subject_condition = or_(
            subject_condition,
            (
                (ProjectSubjectRole.subject_type == ProjectAccessSubjectType.GROUP)
                & (ProjectSubjectRole.subject_group_id.in_(sorted(group_ids)))
            ),
        )

    return {
        int(project_id)
        for project_id in session.exec(
            select(ProjectSubjectRole.project_id).where(
                ProjectSubjectRole.is_active.is_(True),
                subject_condition,
            )
        ).all()
    }


def _get_legacy_project_ids(session: Session, *, user: User) -> set[int]:
    membership_project_ids = {
        int(project_id)
        for project_id in session.exec(
            select(ProjectMember.project_id).where(
                ProjectMember.user_id == user.id,
                ProjectMember.is_active.is_(True),
            )
        ).all()
    }
    return membership_project_ids


def _get_legacy_role_ids_for_project(
    session: Session,
    *,
    project_id: int,
    user: User,
) -> set[int]:
    role_ids: set[int] = set()
    membership = get_project_membership(session, project_id=project_id, user_id=user.id)
    if membership is not None and membership.is_active:
        role_key = LEGACY_PROJECT_MEMBER_TO_ROLE_KEY.get(membership.role)
        if role_key is not None:
            role_id = _get_role_id_by_name(session, role_key)
            if role_id is not None:
                role_ids.add(role_id)

    return role_ids


def get_permission_keys_for_user(
    session: Session,
    *,
    user: User,
    project_id: int | None = None,
) -> set[str]:
    if is_system_admin(user):
        return set(ALL_PERMISSION_KEYS)

    role_ids = _get_project_subject_role_ids_for_user(session, user=user, project_id=project_id)
    if project_id is not None:
        role_ids |= _get_legacy_role_ids_for_project(
            session,
            project_id=project_id,
            user=user,
        )

    if not role_ids:
        return {"update_self"} if project_id is None else set()

    rows = session.exec(
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id.in_(sorted(role_ids)))
    ).all()
    permissions = {str(key) for key in rows}
    if project_id is None:
        permissions.add("update_self")
    return permissions


def has_permission(
    session: Session,
    *,
    user: User,
    permission_key: str,
    project_id: int | None = None,
) -> bool:
    return permission_key in get_permission_keys_for_user(
        session,
        user=user,
        project_id=project_id,
    )


def require_permission(
    session: Session,
    *,
    user: User,
    permission_key: str,
    project_id: int | None = None,
    detail: str | None = None,
) -> None:
    if has_permission(
        session,
        user=user,
        permission_key=permission_key,
        project_id=project_id,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail or "Not enough permissions",
    )


def can_view_project(session: Session, *, project_id: int, user: User) -> bool:
    if is_system_admin(user):
        return True
    if project_id in get_accessible_project_ids(
        session,
        user=user,
        project_ids={project_id},
    ):
        return True
    return has_permission(
        session,
        user=user,
        permission_key="read_project_basic",
        project_id=project_id,
    ) or has_permission(
        session,
        user=user,
        permission_key="issue_read",
        project_id=project_id,
    )


def get_accessible_project_ids(
    session: Session,
    *,
    user: User,
    project_ids: set[int] | None = None,
) -> set[int]:
    if is_system_admin(user):
        all_ids = {int(project_id) for project_id in session.exec(select(Project.id)).all()}
        if project_ids is None:
            return all_ids
        return all_ids & set(project_ids)

    accessible_ids = _get_project_subject_project_ids_for_user(session, user=user)
    accessible_ids |= _get_legacy_project_ids(session, user=user)
    managed_contour_project_ids: set[int] = set()
    managed_group_ids = _get_direct_managed_group_ids(session, user=user)
    managed_org_ids = _get_managed_organization_ids(session, user=user)
    if managed_group_ids:
        managed_contour_project_ids |= _get_project_ids_for_groups(
            session,
            group_ids=managed_group_ids,
        )
    if managed_org_ids:
        managed_contour_project_ids |= {
            int(project_id)
            for project_id in session.exec(
                select(Project.id).where(Project.organization_id.in_(sorted(managed_org_ids)))
            ).all()
        }
        org_group_ids = {
            int(group_id)
            for group_id in session.exec(
                select(OrgGroup.id).where(OrgGroup.organization_id.in_(sorted(managed_org_ids)))
            ).all()
        }
        if org_group_ids:
            managed_contour_project_ids |= _get_project_ids_for_groups(
                session,
                group_ids=org_group_ids,
            )
    # For directors/managers keep a strict contour: only projects of managed
    # groups/organizations. This prevents leaking cross-block projects via
    # incidental global/legacy assignments.
    if managed_contour_project_ids:
        accessible_ids = managed_contour_project_ids
    if project_ids is not None:
        return accessible_ids & set(project_ids)
    return accessible_ids


def require_project_access(session: Session, *, project_id: int, user: User) -> None:
    if can_view_project(session, project_id=project_id, user=user):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No access to the project",
    )


def require_project_manager(session: Session, *, project_id: int, user: User) -> None:
    require_permission(
        session,
        user=user,
        permission_key="update_project",
        project_id=project_id,
        detail="Insufficient role in project",
    )


def require_project_controller_or_manager(
    session: Session,
    *,
    project_id: int,
    user: User,
) -> None:
    if has_permission(
        session,
        user=user,
        permission_key="task_update",
        project_id=project_id,
    ) or has_permission(
        session,
        user=user,
        permission_key="update_project",
        project_id=project_id,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient role in project",
    )


def require_project_executor_scope(
    session: Session,
    *,
    project_id: int,
    user: User,
) -> None:
    if has_permission(
        session,
        user=user,
        permission_key="issue_read",
        project_id=project_id,
    ) or has_permission(
        session,
        user=user,
        permission_key="task_update",
        project_id=project_id,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient role in project",
    )


def require_project_task_create(
    session: Session,
    *,
    project_id: int,
    user: User,
) -> None:
    if has_permission(
        session,
        user=user,
        permission_key="issue_create",
        project_id=project_id,
    ) or has_permission(
        session,
        user=user,
        permission_key="task_update",
        project_id=project_id,
    ) or has_permission(
        session,
        user=user,
        permission_key="update_project",
        project_id=project_id,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient role in project",
    )
