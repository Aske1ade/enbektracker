from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationMembership(SQLModel, table=True):
    __tablename__ = "organization_membership"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_membership_org_user",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        index=True,
    )
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    role_name: str = Field(default="member", nullable=False, max_length=64)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    organization: "Organization" = Relationship(back_populates="memberships")
    user: "User" = Relationship(back_populates="organization_memberships")

