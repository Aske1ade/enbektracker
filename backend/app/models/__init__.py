from sqlmodel import Field, SQLModel

from app.models.demo_seed_entity import DemoSeedEntity
from app.models.desktop_event import DesktopEvent
from app.models.department import Department
from app.models.discipline_certificate_template import DisciplineCertificateTemplate
from app.models.enums import (
    DesktopEventType,
    NotificationType,
    ProjectAccessSubjectType,
    ProjectMemberRole,
    SystemRole,
    TaskDeadlineState,
    TaskHistoryAction,
    TaskUrgencyState,
)
from app.models.group_membership import GroupMembership
from app.models.item import Item
from app.models.notification import Notification
from app.models.org_group import OrgGroup
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.permission import Permission
from app.models.project import Project
from app.models.project_department import ProjectDepartment
from app.models.project_member import ProjectMember
from app.models.project_subject_role import ProjectSubjectRole
from app.models.project_status import ProjectStatus
from app.models.report_template import ReportTemplate
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.task import Task
from app.models.task_assignee import TaskAssignee
from app.models.task_attachment import TaskAttachment
from app.models.task_comment import TaskComment
from app.models.task_history import TaskHistory
from app.models.user import User
from app.models.system_setting import SystemSetting
from app.models.work_block import WorkBlock
from app.models.work_block_department import WorkBlockDepartment
from app.models.work_block_manager import WorkBlockManager
from app.models.work_block_project import WorkBlockProject


# Shared properties
# TODO replace email str with EmailStr when sqlmodel supports it
class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    is_active: bool = True
    is_superuser: bool = False
    must_change_password: bool = False
    full_name: str | None = None
    system_role: SystemRole = SystemRole.USER
    primary_group_id: int | None = None
    department_id: int | None = None


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str


# TODO replace email str with EmailStr when sqlmodel supports it
class UserRegister(SQLModel):
    email: str
    password: str
    full_name: str | None = None


# Properties to receive via API on update, all are optional
# TODO replace email str with EmailStr when sqlmodel supports it
class UserUpdate(UserBase):
    email: str | None = None  # type: ignore
    password: str | None = None
    system_role: SystemRole | None = None
    primary_group_id: int | None = None
    department_id: int | None = None


# TODO replace email str with EmailStr when sqlmodel supports it
class UserUpdateMe(SQLModel):
    full_name: str | None = None
    email: str | None = None


class UpdatePassword(SQLModel):
    current_password: str
    new_password: str


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: int
    can_assign_tasks: bool | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str
    description: str | None = None


# Properties to receive on item creation
class ItemCreate(ItemBase):
    title: str


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = None  # type: ignore


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: int
    owner_id: int


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: int | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str


__all__ = [
    "Department",
    "DemoSeedEntity",
    "DesktopEvent",
    "DesktopEventType",
    "DisciplineCertificateTemplate",
    "GroupMembership",
    "Item",
    "ItemBase",
    "ItemCreate",
    "ItemPublic",
    "ItemsPublic",
    "ItemUpdate",
    "Message",
    "NewPassword",
    "Notification",
    "NotificationType",
    "OrgGroup",
    "Organization",
    "OrganizationMembership",
    "Permission",
    "Project",
    "ProjectDepartment",
    "ProjectMember",
    "ProjectAccessSubjectType",
    "ProjectMemberRole",
    "ProjectSubjectRole",
    "ProjectStatus",
    "ReportTemplate",
    "Role",
    "RolePermission",
    "SystemRole",
    "Task",
    "TaskAssignee",
    "TaskAttachment",
    "TaskComment",
    "TaskDeadlineState",
    "TaskHistory",
    "TaskHistoryAction",
    "TaskUrgencyState",
    "Token",
    "TokenPayload",
    "UpdatePassword",
    "User",
    "UserBase",
    "UserCreate",
    "UserPublic",
    "UserRegister",
    "UsersPublic",
    "UserUpdate",
    "UserUpdateMe",
    "SystemSetting",
    "WorkBlock",
    "WorkBlockDepartment",
    "WorkBlockManager",
    "WorkBlockProject",
]
