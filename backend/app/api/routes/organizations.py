from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlmodel import delete, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Department,
    GroupMembership,
    OrgGroup,
    Organization,
    OrganizationMembership,
    Project,
    ProjectSubjectRole,
    User,
)
from app.schemas.organization import (
    GroupCreate,
    GroupMemberAssign,
    GroupMemberUpdate,
    GroupMemberPublic,
    GroupMembersPublic,
    GroupPublic,
    GroupUpdate,
    GroupTreeNode,
    GroupTreePublic,
    GroupsPublic,
    OrganizationMemberAssign,
    OrganizationMemberPublic,
    OrganizationMembersPublic,
    OrganizationMemberUpdate,
    OrganizationCreate,
    OrganizationPublic,
    OrganizationTreeNode,
    OrganizationTreePublic,
    OrganizationsPublic,
    OrganizationUpdate,
)
from app.services import rbac_service

router = APIRouter(prefix="/organizations", tags=["organizations"])

MEMBERSHIP_ROLE_WEIGHTS: dict[str, int] = {
    "member": 0,
    "manager": 1,
    "owner": 2,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _organization_public(
    session: SessionDep,
    organization: Organization,
) -> OrganizationPublic:
    groups_count = session.exec(
        select(func.count()).select_from(OrgGroup).where(OrgGroup.organization_id == organization.id)
    ).one()
    projects_count = session.exec(
        select(func.count()).select_from(Project).where(Project.organization_id == organization.id)
    ).one()
    managers_count = session.exec(
        select(func.count())
        .select_from(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.is_active.is_(True),
            OrganizationMembership.role_name == "manager",
        )
    ).one()
    return OrganizationPublic(
        id=organization.id,
        name=organization.name,
        code=organization.code,
        description=organization.description,
        parent_organization_id=organization.parent_organization_id,
        groups_count=int(groups_count),
        projects_count=int(projects_count),
        managers_count=int(managers_count),
        created_at=organization.created_at,
        updated_at=organization.updated_at,
    )


def _ensure_org_exists(session: SessionDep, organization_id: int) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


def _ensure_group_exists(session: SessionDep, group_id: int) -> OrgGroup:
    group = session.get(OrgGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def _validate_organization_parent(
    session: SessionDep,
    *,
    organization_id: int | None,
    parent_organization_id: int | None,
) -> None:
    if parent_organization_id is None:
        return
    if organization_id is not None and parent_organization_id == organization_id:
        raise HTTPException(
            status_code=422,
            detail="Organization cannot be parent of itself",
        )
    parent = session.get(Organization, parent_organization_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent organization not found")


def _validate_group_parent(
    session: SessionDep,
    *,
    group_id: int | None,
    organization_id: int,
    parent_group_id: int | None,
) -> None:
    if parent_group_id is None:
        return
    if group_id is not None and parent_group_id == group_id:
        raise HTTPException(status_code=422, detail="Group cannot be parent of itself")
    parent_group = session.get(OrgGroup, parent_group_id)
    if parent_group is None:
        raise HTTPException(status_code=404, detail="Parent group not found")
    if parent_group.organization_id != organization_id:
        raise HTTPException(
            status_code=422,
            detail="Parent group must belong to the same organization",
        )


def _build_organization_tree_rows(organizations: list[Organization]) -> list[OrganizationTreeNode]:
    children_map: dict[int | None, list[Organization]] = {}
    for organization in organizations:
        children_map.setdefault(organization.parent_organization_id, []).append(organization)
    for rows in children_map.values():
        rows.sort(key=lambda row: (row.name.lower(), row.id or 0))

    def build_node(organization: Organization) -> OrganizationTreeNode:
        return OrganizationTreeNode(
            id=int(organization.id),
            name=organization.name,
            code=organization.code,
            parent_organization_id=organization.parent_organization_id,
            children=[build_node(child) for child in children_map.get(organization.id, [])],
        )

    return [build_node(row) for row in children_map.get(None, [])]


def _build_group_tree_rows(groups: list[OrgGroup]) -> list[GroupTreeNode]:
    children_map: dict[int | None, list[OrgGroup]] = {}
    for group in groups:
        children_map.setdefault(group.parent_group_id, []).append(group)
    for rows in children_map.values():
        rows.sort(key=lambda row: (row.name.lower(), row.id or 0))

    def build_node(group: OrgGroup) -> GroupTreeNode:
        return GroupTreeNode(
            id=int(group.id),
            organization_id=group.organization_id,
            name=group.name,
            code=group.code,
            parent_group_id=group.parent_group_id,
            children=[build_node(child) for child in children_map.get(group.id, [])],
        )

    return [build_node(row) for row in children_map.get(None, [])]


def _require_permission(
    session: SessionDep,
    *,
    current_user: CurrentUser,
    permission_key: str,
) -> None:
    rbac_service.require_permission(
        session,
        user=current_user,
        permission_key=permission_key,
    )


def _normalize_membership_role(role_name: str | None) -> str:
    normalized = (role_name or "member").strip().lower()
    if normalized not in MEMBERSHIP_ROLE_WEIGHTS:
        raise HTTPException(
            status_code=422,
            detail="role_name must be one of: member, manager, owner",
        )
    return normalized


def _max_membership_role(role_a: str, role_b: str) -> str:
    if MEMBERSHIP_ROLE_WEIGHTS.get(role_a, 0) >= MEMBERSHIP_ROLE_WEIGHTS.get(role_b, 0):
        return role_a
    return role_b


@router.get("/", response_model=OrganizationsPublic)
def list_organizations(
    session: SessionDep,
    current_user: CurrentUser,
) -> OrganizationsPublic:
    _require_permission(session, current_user=current_user, permission_key="read_organization")
    organizations = session.exec(select(Organization).order_by(Organization.id.asc())).all()
    rows = [_organization_public(session, organization) for organization in organizations]
    return OrganizationsPublic(data=rows, count=len(rows))


@router.get("/tree", response_model=OrganizationTreePublic)
def list_organizations_tree(
    session: SessionDep,
    current_user: CurrentUser,
) -> OrganizationTreePublic:
    _require_permission(session, current_user=current_user, permission_key="read_organization")
    organizations = session.exec(select(Organization).order_by(Organization.id.asc())).all()
    roots = _build_organization_tree_rows(organizations)
    return OrganizationTreePublic(data=roots, count=len(roots))


@router.post("/", response_model=OrganizationPublic)
def create_organization(
    session: SessionDep,
    current_user: CurrentUser,
    payload: OrganizationCreate,
) -> OrganizationPublic:
    _require_permission(session, current_user=current_user, permission_key="create_organization")
    _validate_organization_parent(
        session,
        organization_id=None,
        parent_organization_id=payload.parent_organization_id,
    )
    now = utcnow()
    organization = Organization(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        parent_organization_id=payload.parent_organization_id,
        created_at=now,
        updated_at=now,
    )
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return _organization_public(session, organization)


@router.get("/{organization_id}", response_model=OrganizationPublic)
def get_organization(
    organization_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrganizationPublic:
    _require_permission(session, current_user=current_user, permission_key="read_organization")
    organization = _ensure_org_exists(session, organization_id)
    return _organization_public(session, organization)


@router.get("/{organization_id}/members", response_model=OrganizationMembersPublic)
def list_organization_members(
    organization_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrganizationMembersPublic:
    _require_permission(session, current_user=current_user, permission_key="read_organization")
    _ensure_org_exists(session, organization_id)
    memberships = session.exec(
        select(OrganizationMembership)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.id.asc())
    ).all()
    rows: list[OrganizationMemberPublic] = []
    for membership in memberships:
        user = session.get(User, membership.user_id)
        if user is None:
            continue
        rows.append(
            OrganizationMemberPublic(
                user_id=user.id,
                user_name=user.full_name or user.email,
                user_email=user.email,
                role_name=membership.role_name or "member",
                is_active=bool(membership.is_active and user.is_active),
            )
        )
    return OrganizationMembersPublic(data=rows, count=len(rows))


@router.post("/{organization_id}/members", response_model=OrganizationMemberPublic)
def assign_organization_member(
    organization_id: int,
    payload: OrganizationMemberAssign,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrganizationMemberPublic:
    _require_permission(session, current_user=current_user, permission_key="update_organization")
    _ensure_org_exists(session, organization_id)
    user = session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    role_name = _normalize_membership_role(payload.role_name)
    membership = session.exec(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == payload.user_id,
        )
    ).first()
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=payload.user_id,
            role_name=role_name,
            is_active=True,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    else:
        membership.role_name = role_name
        membership.is_active = True
        membership.updated_at = utcnow()
    session.add(membership)
    session.commit()
    return OrganizationMemberPublic(
        user_id=user.id,
        user_name=user.full_name or user.email,
        user_email=user.email,
        role_name=membership.role_name or "member",
        is_active=bool(user.is_active and membership.is_active),
    )


@router.patch("/{organization_id}/members/{user_id}", response_model=OrganizationMemberPublic)
def update_organization_member(
    organization_id: int,
    user_id: int,
    payload: OrganizationMemberUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrganizationMemberPublic:
    _require_permission(session, current_user=current_user, permission_key="update_organization")
    _ensure_org_exists(session, organization_id)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    membership = session.exec(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization membership not found")

    if "role_name" in payload.model_fields_set and payload.role_name is not None:
        membership.role_name = _normalize_membership_role(payload.role_name)
    if "is_active" in payload.model_fields_set and payload.is_active is not None:
        membership.is_active = bool(payload.is_active)
    membership.updated_at = utcnow()
    session.add(membership)
    session.commit()
    return OrganizationMemberPublic(
        user_id=user.id,
        user_name=user.full_name or user.email,
        user_email=user.email,
        role_name=membership.role_name or "member",
        is_active=bool(user.is_active and membership.is_active),
    )


@router.delete("/{organization_id}/members/{user_id}")
def remove_organization_member(
    organization_id: int,
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    _require_permission(session, current_user=current_user, permission_key="update_organization")
    _ensure_org_exists(session, organization_id)
    membership = session.exec(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Organization membership not found")
    session.delete(membership)
    session.commit()
    return {"message": "User removed from organization"}


@router.patch("/{organization_id}", response_model=OrganizationPublic)
def update_organization(
    organization_id: int,
    payload: OrganizationUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrganizationPublic:
    _require_permission(session, current_user=current_user, permission_key="update_organization")
    organization = _ensure_org_exists(session, organization_id)
    if "parent_organization_id" in payload.model_fields_set:
        _validate_organization_parent(
            session,
            organization_id=organization_id,
            parent_organization_id=payload.parent_organization_id,
        )
    organization.sqlmodel_update(payload.model_dump(exclude_unset=True))
    organization.updated_at = utcnow()
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return _organization_public(session, organization)


@router.delete("/{organization_id}")
def delete_organization(
    organization_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    _require_permission(session, current_user=current_user, permission_key="delete_organization")
    organization = _ensure_org_exists(session, organization_id)
    if organization.is_global:
        raise HTTPException(status_code=400, detail="Global organization cannot be deleted")
    child_organizations = session.exec(
        select(func.count())
        .select_from(Organization)
        .where(Organization.parent_organization_id == organization_id)
    ).one()
    if int(child_organizations) > 0:
        raise HTTPException(
            status_code=400,
            detail="Organization has child organizations. Reparent or remove them first.",
        )
    linked_projects = session.exec(
        select(func.count()).select_from(Project).where(Project.organization_id == organization_id)
    ).one()
    if int(linked_projects) > 0:
        raise HTTPException(
            status_code=400,
            detail="Organization has linked projects. Reassign projects before deletion.",
        )
    group_ids = session.exec(
        select(OrgGroup.id).where(OrgGroup.organization_id == organization_id)
    ).all()
    if group_ids:
        session.exec(delete(ProjectSubjectRole).where(ProjectSubjectRole.subject_group_id.in_(group_ids)))
        session.exec(delete(GroupMembership).where(GroupMembership.group_id.in_(group_ids)))
        users_with_primary_group = session.exec(
            select(User).where(User.primary_group_id.in_(group_ids))
        ).all()
        for user in users_with_primary_group:
            user.primary_group_id = None
            user.updated_at = utcnow()
            session.add(user)
        session.exec(delete(OrgGroup).where(OrgGroup.id.in_(group_ids)))
    session.exec(
        delete(OrganizationMembership).where(OrganizationMembership.organization_id == organization_id)
    )
    session.delete(organization)
    session.commit()
    return {"message": "Organization deleted successfully"}


@router.get("/{organization_id}/groups", response_model=GroupsPublic)
def list_organization_groups(
    organization_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> GroupsPublic:
    _require_permission(session, current_user=current_user, permission_key="read_group")
    _ensure_org_exists(session, organization_id)
    groups = session.exec(
        select(OrgGroup)
        .where(OrgGroup.organization_id == organization_id)
        .order_by(OrgGroup.id.asc())
    ).all()
    rows = [
        GroupPublic(
            id=group.id,
            organization_id=group.organization_id,
            name=group.name,
            code=group.code,
            description=group.description,
            parent_group_id=group.parent_group_id,
        )
        for group in groups
    ]
    return GroupsPublic(data=rows, count=len(rows))


@router.get("/{organization_id}/groups/tree", response_model=GroupTreePublic)
def list_organization_groups_tree(
    organization_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> GroupTreePublic:
    _require_permission(session, current_user=current_user, permission_key="read_group")
    _ensure_org_exists(session, organization_id)
    groups = session.exec(
        select(OrgGroup)
        .where(OrgGroup.organization_id == organization_id)
        .order_by(OrgGroup.id.asc())
    ).all()
    roots = _build_group_tree_rows(groups)
    return GroupTreePublic(data=roots, count=len(roots))


@router.post("/{organization_id}/groups", response_model=GroupPublic)
def create_organization_group(
    organization_id: int,
    payload: GroupCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> GroupPublic:
    _require_permission(session, current_user=current_user, permission_key="create_group")
    _ensure_org_exists(session, organization_id)
    _validate_group_parent(
        session,
        group_id=None,
        organization_id=organization_id,
        parent_group_id=payload.parent_group_id,
    )
    now = utcnow()
    legacy_name = payload.name
    if session.exec(select(Department.id).where(Department.name == legacy_name)).first() is not None:
        legacy_name = f"{payload.name} [{organization_id}]"
    legacy_code = payload.code
    if legacy_code and session.exec(select(Department.id).where(Department.code == legacy_code)).first() is not None:
        legacy_code = f"{legacy_code}-{organization_id}"
    legacy_department = Department(
        name=legacy_name,
        code=legacy_code,
        description=payload.description,
        created_at=now,
        updated_at=now,
    )
    session.add(legacy_department)
    session.flush()
    group = OrgGroup(
        organization_id=organization_id,
        name=payload.name,
        code=payload.code,
        description=payload.description,
        parent_group_id=payload.parent_group_id,
        legacy_department_id=legacy_department.id,
        created_at=now,
        updated_at=now,
    )
    session.add(group)
    session.commit()
    session.refresh(group)
    return GroupPublic(
        id=group.id,
        organization_id=group.organization_id,
        name=group.name,
        code=group.code,
        description=group.description,
        parent_group_id=group.parent_group_id,
    )


@router.patch("/{organization_id}/groups/{group_id}", response_model=GroupPublic)
def update_organization_group(
    organization_id: int,
    group_id: int,
    payload: GroupUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> GroupPublic:
    _require_permission(session, current_user=current_user, permission_key="update_group")
    _ensure_org_exists(session, organization_id)
    group = _ensure_group_exists(session, group_id)
    if group.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Group not found in organization")
    if "parent_group_id" in payload.model_fields_set:
        _validate_group_parent(
            session,
            group_id=group.id,
            organization_id=organization_id,
            parent_group_id=payload.parent_group_id,
        )
    group.sqlmodel_update(payload.model_dump(exclude_unset=True))
    group.updated_at = utcnow()
    session.add(group)
    session.commit()
    session.refresh(group)
    return GroupPublic(
        id=group.id,
        organization_id=group.organization_id,
        name=group.name,
        code=group.code,
        description=group.description,
        parent_group_id=group.parent_group_id,
    )


@router.delete("/{organization_id}/groups/{group_id}")
def remove_organization_group(
    organization_id: int,
    group_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    _require_permission(session, current_user=current_user, permission_key="delete_group")
    _ensure_org_exists(session, organization_id)
    group = _ensure_group_exists(session, group_id)
    if group.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Group not found in organization")
    child_groups_count = session.exec(
        select(func.count())
        .select_from(OrgGroup)
        .where(OrgGroup.parent_group_id == group_id)
    ).one()
    if int(child_groups_count) > 0:
        raise HTTPException(
            status_code=400,
            detail="Group has child groups. Reparent or remove them first.",
        )

    session.exec(delete(ProjectSubjectRole).where(ProjectSubjectRole.subject_group_id == group_id))
    session.exec(delete(GroupMembership).where(GroupMembership.group_id == group_id))
    users_with_primary_group = session.exec(
        select(User).where(User.primary_group_id == group_id)
    ).all()
    for user in users_with_primary_group:
        user.primary_group_id = None
        if group.legacy_department_id is not None and user.department_id == group.legacy_department_id:
            user.department_id = None
        user.updated_at = utcnow()
        session.add(user)
    session.delete(group)
    session.commit()
    return {"message": "Group removed from organization"}


@router.get("/groups/{group_id}/members", response_model=GroupMembersPublic)
def list_group_members(
    group_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> GroupMembersPublic:
    _require_permission(session, current_user=current_user, permission_key="read_group")
    _ensure_group_exists(session, group_id)
    memberships = session.exec(
        select(GroupMembership)
        .where(GroupMembership.group_id == group_id)
        .order_by(GroupMembership.id.asc())
    ).all()
    rows: list[GroupMemberPublic] = []
    for membership in memberships:
        user = session.get(User, membership.user_id)
        if user is None:
            continue
        rows.append(
            GroupMemberPublic(
                user_id=user.id,
                user_name=user.full_name or user.email,
                user_email=user.email,
                role_name=membership.role_name or "member",
                is_active=bool(membership.is_active and user.is_active),
            )
        )
    return GroupMembersPublic(data=rows, count=len(rows))


@router.post("/groups/{group_id}/members", response_model=GroupMemberPublic)
def assign_group_member(
    group_id: int,
    payload: GroupMemberAssign,
    session: SessionDep,
    current_user: CurrentUser,
) -> GroupMemberPublic:
    _require_permission(session, current_user=current_user, permission_key="update_group")
    group = _ensure_group_exists(session, group_id)
    user = session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    role_name = _normalize_membership_role(payload.role_name)

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == payload.user_id,
        )
    ).first()
    if membership is None:
        membership = GroupMembership(
            group_id=group_id,
            user_id=payload.user_id,
            role_name=role_name,
            is_active=True,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    else:
        membership.role_name = role_name
        membership.is_active = True
        membership.updated_at = utcnow()
    session.add(membership)

    user.primary_group_id = group_id
    if group.legacy_department_id is not None:
        user.department_id = group.legacy_department_id
    user.updated_at = utcnow()
    session.add(user)

    organization_membership = session.exec(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == group.organization_id,
            OrganizationMembership.user_id == payload.user_id,
        )
    ).first()
    if organization_membership is None:
        organization_membership = OrganizationMembership(
            organization_id=group.organization_id,
            user_id=payload.user_id,
            role_name=role_name,
            is_active=True,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    else:
        organization_membership.role_name = _max_membership_role(
            organization_membership.role_name or "member",
            role_name,
        )
        organization_membership.is_active = True
        organization_membership.updated_at = utcnow()
    session.add(organization_membership)
    session.commit()

    return GroupMemberPublic(
        user_id=user.id,
        user_name=user.full_name or user.email,
        user_email=user.email,
        role_name=membership.role_name or "member",
        is_active=user.is_active,
    )


@router.patch("/groups/{group_id}/members/{user_id}", response_model=GroupMemberPublic)
def update_group_member(
    group_id: int,
    user_id: int,
    payload: GroupMemberUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> GroupMemberPublic:
    _require_permission(session, current_user=current_user, permission_key="update_group")
    group = _ensure_group_exists(session, group_id)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
        )
    ).first()
    if membership is None:
        raise HTTPException(status_code=404, detail="Group membership not found")

    updated_role_name = membership.role_name or "member"
    if "role_name" in payload.model_fields_set and payload.role_name is not None:
        updated_role_name = _normalize_membership_role(payload.role_name)
        membership.role_name = updated_role_name
    if "is_active" in payload.model_fields_set and payload.is_active is not None:
        next_active = bool(payload.is_active)
        membership.is_active = next_active
        if not next_active and user.primary_group_id == group_id:
            user.primary_group_id = None
            if (
                group.legacy_department_id is not None
                and user.department_id == group.legacy_department_id
            ):
                user.department_id = None
            user.updated_at = utcnow()
            session.add(user)
        elif next_active and user.primary_group_id is None:
            user.primary_group_id = group_id
            if group.legacy_department_id is not None:
                user.department_id = group.legacy_department_id
            user.updated_at = utcnow()
            session.add(user)
    membership.updated_at = utcnow()
    session.add(membership)

    organization_membership = session.exec(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == group.organization_id,
            OrganizationMembership.user_id == user_id,
        )
    ).first()
    if organization_membership is not None:
        organization_membership.role_name = _max_membership_role(
            organization_membership.role_name or "member",
            updated_role_name,
        )
        if membership.is_active:
            organization_membership.is_active = True
        organization_membership.updated_at = utcnow()
        session.add(organization_membership)

    session.commit()
    return GroupMemberPublic(
        user_id=user.id,
        user_name=user.full_name or user.email,
        user_email=user.email,
        role_name=membership.role_name or "member",
        is_active=bool(user.is_active and membership.is_active),
    )


@router.delete("/groups/{group_id}/members/{user_id}")
def remove_group_member(
    group_id: int,
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    _require_permission(session, current_user=current_user, permission_key="update_group")
    group = _ensure_group_exists(session, group_id)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
        )
    ).first()
    if membership is not None:
        session.delete(membership)
    if user.primary_group_id == group_id:
        user.primary_group_id = None
        if group.legacy_department_id is not None and user.department_id == group.legacy_department_id:
            user.department_id = None
        user.updated_at = utcnow()
        session.add(user)
    session.commit()
    return {"message": "User removed from group"}
