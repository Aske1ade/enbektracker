from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrgGroup(SQLModel, table=True):
    __tablename__ = "org_group"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_org_group_org_name"),
        UniqueConstraint("organization_id", "code", name="uq_org_group_org_code"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        index=True,
    )
    name: str = Field(index=True)
    code: str | None = Field(default=None, index=True)
    description: str | None = None
    parent_group_id: int | None = Field(
        default=None,
        foreign_key="org_group.id",
        index=True,
    )
    legacy_department_id: int | None = Field(
        default=None,
        foreign_key="department.id",
        unique=True,
        index=True,
    )
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    organization: "Organization" = Relationship(back_populates="groups")
    legacy_department: Optional["Department"] = Relationship()
    memberships: list["GroupMembership"] = Relationship(back_populates="group")
    primary_users: list["User"] = Relationship(back_populates="primary_group")
    project_assignments: list["ProjectSubjectRole"] = Relationship(
        back_populates="subject_group"
    )
