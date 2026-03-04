from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.core.permissions import PERMISSIONS, ROLE_DESCRIPTIONS, ROLE_TO_PERMISSIONS
from app.models import Permission, Role, RolePermission


def sync_permission_catalog(session: Session) -> None:
    try:
        role_by_name: dict[str, Role] = {}
        for role_key, role_description in ROLE_DESCRIPTIONS.items():
            role = session.exec(select(Role).where(Role.name == role_key)).first()
            if role is None:
                role = Role(name=role_key, description=role_description, is_system=True)
                session.add(role)
                session.flush()
            role_by_name[role_key] = role

        permission_by_key: dict[str, Permission] = {}
        for permission_key, permission_name in PERMISSIONS:
            permission = session.exec(
                select(Permission).where(Permission.key == permission_key)
            ).first()
            if permission is None:
                permission = Permission(key=permission_key, name=permission_name)
                session.add(permission)
                session.flush()
            permission_by_key[permission_key] = permission

        existing_links = {
            (int(row[0]), int(row[1]))
            for row in session.exec(
                select(RolePermission.role_id, RolePermission.permission_id)
            ).all()
        }
        for role_key, permission_keys in ROLE_TO_PERMISSIONS.items():
            role = role_by_name.get(role_key)
            if role is None or role.id is None:
                continue
            for permission_key in permission_keys:
                permission = permission_by_key.get(permission_key)
                if permission is None or permission.id is None:
                    continue
                pair = (role.id, permission.id)
                if pair in existing_links:
                    continue
                session.add(RolePermission(role_id=role.id, permission_id=permission.id))
                existing_links.add(pair)

        session.commit()
    except SQLAlchemyError:
        session.rollback()

