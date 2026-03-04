from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: int | None = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="role.id", nullable=False, index=True)
    permission_id: int = Field(foreign_key="permission.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    role: "Role" = Relationship(back_populates="permission_links")
    permission: "Permission" = Relationship(back_populates="role_links")

