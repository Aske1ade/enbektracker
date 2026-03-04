
from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(SQLModel, table=True):
    __tablename__ = "role"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str | None = None
    is_system: bool = True
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    permission_links: list["RolePermission"] = Relationship(back_populates="role")
    project_assignments: list["ProjectSubjectRole"] = Relationship(
        back_populates="role"
    )
