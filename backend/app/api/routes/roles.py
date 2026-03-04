from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.permissions import ROLE_TITLES
from app.models import Permission, Role, RolePermission
from app.schemas.permission import (
    PermissionPublic,
    PermissionsPublic,
    RolePublic,
    RolesPublic,
)
from app.services import rbac_service

router = APIRouter(tags=["rbac"])


def _require_read_role(session: SessionDep, current_user: CurrentUser) -> None:
    rbac_service.require_permission(
        session,
        user=current_user,
        permission_key="read_role",
    )


@router.get("/permissions", response_model=PermissionsPublic)
def list_permissions(
    session: SessionDep,
    current_user: CurrentUser,
) -> PermissionsPublic:
    _require_read_role(session, current_user)
    permissions = session.exec(select(Permission).order_by(Permission.key.asc())).all()
    rows = [PermissionPublic(key=permission.key, name=permission.name) for permission in permissions]
    return PermissionsPublic(data=rows, count=len(rows))


@router.get("/roles", response_model=RolesPublic)
def list_roles(
    session: SessionDep,
    current_user: CurrentUser,
) -> RolesPublic:
    _require_read_role(session, current_user)
    roles = session.exec(select(Role).order_by(Role.name.asc())).all()
    permission_counts = {
        int(row[0]): int(row[1])
        for row in session.exec(
            select(RolePermission.role_id, func.count(RolePermission.id))
            .group_by(RolePermission.role_id)
        ).all()
    }
    rows = [
        RolePublic(
            key=role.name,
            title=ROLE_TITLES.get(role.name, role.name),
            permissions_count=permission_counts.get(role.id, 0),
        )
        for role in roles
    ]
    return RolesPublic(data=rows, count=len(rows))


@router.get("/roles/{role_key}/permissions", response_model=PermissionsPublic)
def list_role_permissions(
    role_key: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> PermissionsPublic:
    _require_read_role(session, current_user)
    role = session.exec(select(Role).where(Role.name == role_key)).first()
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    permissions = session.exec(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role.id)
        .order_by(Permission.key.asc())
    ).all()
    rows = [PermissionPublic(key=permission.key, name=permission.name) for permission in permissions]
    return PermissionsPublic(data=rows, count=len(rows))

