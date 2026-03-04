from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(SQLModel, table=True):
    __tablename__ = "organization"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    code: str | None = Field(default=None, index=True, unique=True)
    description: str | None = None
    is_global: bool = Field(default=False, nullable=False)
    parent_organization_id: int | None = Field(
        default=None,
        foreign_key="organization.id",
        index=True,
    )
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    groups: list["OrgGroup"] = Relationship(back_populates="organization")
    memberships: list["OrganizationMembership"] = Relationship(
        back_populates="organization"
    )
    projects: list["Project"] = Relationship(back_populates="organization")
