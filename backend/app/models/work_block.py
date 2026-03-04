from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkBlock(SQLModel, table=True):
    __tablename__ = "work_block"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    code: str | None = Field(default=None, unique=True, index=True)
    description: str | None = None
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    departments: list["WorkBlockDepartment"] = Relationship(back_populates="block")
    projects: list["WorkBlockProject"] = Relationship(back_populates="block")
    managers: list["WorkBlockManager"] = Relationship(back_populates="block")
