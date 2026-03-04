from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import ProjectAccessSubjectType, sa_str_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectSubjectRole(SQLModel, table=True):
    __tablename__ = "project_subject_role"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "role_id",
            "subject_type",
            "subject_user_id",
            "subject_group_id",
            name="uq_project_subject_role",
        ),
        CheckConstraint(
            "("
            "subject_type = 'user' AND subject_user_id IS NOT NULL AND subject_group_id IS NULL"
            ") OR ("
            "subject_type = 'group' AND subject_group_id IS NOT NULL AND subject_user_id IS NULL"
            ")",
            name="ck_project_subject_role_subject_ref",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", nullable=False, index=True)
    role_id: int = Field(foreign_key="role.id", nullable=False, index=True)
    subject_type: ProjectAccessSubjectType = Field(
        default=ProjectAccessSubjectType.USER,
        sa_column=Column(
            sa_str_enum(ProjectAccessSubjectType, "projectaccesssubjecttype"),
            nullable=False,
        ),
    )
    subject_user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    subject_group_id: int | None = Field(default=None, foreign_key="org_group.id", index=True)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    project: "Project" = Relationship(back_populates="subject_roles")
    role: "Role" = Relationship(back_populates="project_assignments")
    subject_user: "User" = Relationship(back_populates="project_subject_roles")
    subject_group: "OrgGroup" = Relationship(back_populates="project_assignments")

