
from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Department(SQLModel, table=True):
    __tablename__ = "department"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    code: str | None = Field(default=None, unique=True, index=True)
    description: str | None = None
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    users: list["User"] = Relationship(back_populates="department")
    projects: list["Project"] = Relationship(back_populates="department")
    project_links: list["ProjectDepartment"] = Relationship(
        back_populates="department"
    )
    block_links: list["WorkBlockDepartment"] = Relationship(
        back_populates="department"
    )

