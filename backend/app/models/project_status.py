
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(SQLModel, table=True):
    __tablename__ = "project_status"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_status_name"),
        UniqueConstraint("project_id", "order", name="uq_project_status_order"),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", nullable=False, index=True)
    name: str
    code: str | None = Field(default=None, index=True)
    color: str | None = None
    order: int = Field(default=0)
    is_default: bool = False
    is_final: bool = False
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    project: "Project" = Relationship(back_populates="statuses")
    tasks: list["Task"] = Relationship(back_populates="workflow_status")


