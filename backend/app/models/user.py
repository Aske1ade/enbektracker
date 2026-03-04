
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel

from app.models.enums import SystemRole, sa_str_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    is_active: bool = True
    is_superuser: bool = False
    must_change_password: bool = False
    full_name: str | None = None
    hashed_password: str
    system_role: SystemRole = Field(
        default=SystemRole.USER,
        sa_column=Column(sa_str_enum(SystemRole, "systemrole"), nullable=False),
    )
    primary_group_id: int | None = Field(default=None, foreign_key="org_group.id")
    department_id: int | None = Field(default=None, foreign_key="department.id")
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)

    items: list["Item"] = Relationship(back_populates="owner")
    primary_group: Optional["OrgGroup"] = Relationship(back_populates="primary_users")
    department: Optional["Department"] = Relationship(back_populates="users")

    created_projects: list["Project"] = Relationship(
        back_populates="creator",
        sa_relationship_kwargs={"foreign_keys": "Project.created_by_id"},
    )
    project_memberships: list["ProjectMember"] = Relationship(back_populates="user")

    assigned_tasks: list["Task"] = Relationship(
        back_populates="assignee",
        sa_relationship_kwargs={"foreign_keys": "Task.assignee_id"},
    )
    created_tasks: list["Task"] = Relationship(
        back_populates="creator",
        sa_relationship_kwargs={"foreign_keys": "Task.creator_id"},
    )
    controlled_tasks: list["Task"] = Relationship(
        back_populates="controller",
        sa_relationship_kwargs={"foreign_keys": "Task.controller_id"},
    )

    task_comments: list["TaskComment"] = Relationship(back_populates="author")
    task_attachments: list["TaskAttachment"] = Relationship(back_populates="uploader")
    task_history_entries: list["TaskHistory"] = Relationship(back_populates="actor")
    task_assignee_links: list["TaskAssignee"] = Relationship(back_populates="user")
    notifications: list["Notification"] = Relationship(back_populates="user")
    block_memberships: list["WorkBlockManager"] = Relationship(
        back_populates="user"
    )
    organization_memberships: list["OrganizationMembership"] = Relationship(
        back_populates="user"
    )
    group_memberships: list["GroupMembership"] = Relationship(back_populates="user")
    project_subject_roles: list["ProjectSubjectRole"] = Relationship(
        back_populates="subject_user"
    )
