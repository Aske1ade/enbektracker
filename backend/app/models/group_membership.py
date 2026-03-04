from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GroupMembership(SQLModel, table=True):
    __tablename__ = "group_membership"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_membership_group_user"),
    )

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="org_group.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    role_name: str = Field(default="member", nullable=False, max_length=64)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    group: "OrgGroup" = Relationship(back_populates="memberships")
    user: "User" = Relationship(back_populates="group_memberships")

