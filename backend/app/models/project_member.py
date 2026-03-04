
from datetime import datetime, timezone

from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import ProjectMemberRole, sa_str_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_member"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", nullable=False, index=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    role: ProjectMemberRole = Field(
        default=ProjectMemberRole.EXECUTOR,
        sa_column=Column(
            sa_str_enum(ProjectMemberRole, "projectmemberrole"),
            nullable=False,
        ),
    )
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    project: "Project" = Relationship(back_populates="members")
    user: "User" = Relationship(back_populates="project_memberships")

