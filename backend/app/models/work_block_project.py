from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkBlockProject(SQLModel, table=True):
    __tablename__ = "work_block_project"
    __table_args__ = (
        UniqueConstraint(
            "block_id",
            "project_id",
            name="uq_work_block_project_block_project",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    block_id: int = Field(foreign_key="work_block.id", nullable=False, index=True)
    project_id: int = Field(foreign_key="project.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    block: "WorkBlock" = Relationship(back_populates="projects")
    project: "Project" = Relationship(back_populates="block_links")
