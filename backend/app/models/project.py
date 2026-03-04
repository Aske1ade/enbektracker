
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    __tablename__ = "project"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    icon: str | None = Field(default=None, max_length=255)
    description: str | None = None
    organization_id: int | None = Field(default=None, foreign_key="organization.id")
    department_id: int | None = Field(default=None, foreign_key="department.id")
    created_by_id: int | None = Field(default=None, foreign_key="user.id")

    require_close_comment: bool = True
    require_close_attachment: bool = False

    deadline_yellow_days: int = 3
    deadline_normal_days: int = 5

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    organization: Optional["Organization"] = Relationship(back_populates="projects")
    department: Optional["Department"] = Relationship(back_populates="projects")
    creator: Optional["User"] = Relationship(
        back_populates="created_projects",
        sa_relationship_kwargs={"foreign_keys": "Project.created_by_id"},
    )
    members: list["ProjectMember"] = Relationship(back_populates="project")
    statuses: list["ProjectStatus"] = Relationship(back_populates="project")
    tasks: list["Task"] = Relationship(back_populates="project")
    project_departments: list["ProjectDepartment"] = Relationship(
        back_populates="project"
    )
    block_links: list["WorkBlockProject"] = Relationship(back_populates="project")
    subject_roles: list["ProjectSubjectRole"] = Relationship(back_populates="project")
