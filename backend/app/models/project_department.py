from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectDepartment(SQLModel, table=True):
    __tablename__ = "project_department"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "department_id",
            name="uq_project_department_project_department",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", nullable=False, index=True)
    department_id: int = Field(foreign_key="department.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    project: "Project" = Relationship(back_populates="project_departments")
    department: "Department" = Relationship(back_populates="project_links")
