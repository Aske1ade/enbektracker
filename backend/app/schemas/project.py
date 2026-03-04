from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.enums import ProjectMemberRole


class ProjectBase(SQLModel):
    name: str
    icon: str | None = Field(default=None, max_length=255)
    description: str | None = None
    organization_id: int | None = None
    department_id: int | None = None
    block_id: int | None = None
    require_close_comment: bool = True
    require_close_attachment: bool = False
    deadline_yellow_days: int = 3
    deadline_normal_days: int = 5


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(SQLModel):
    name: str | None = None
    icon: str | None = Field(default=None, max_length=255)
    description: str | None = None
    organization_id: int | None = None
    department_id: int | None = None
    block_id: int | None = None
    require_close_comment: bool | None = None
    require_close_attachment: bool | None = None
    deadline_yellow_days: int | None = None
    deadline_normal_days: int | None = None


class ProjectPublic(ProjectBase):
    id: int
    created_by_id: int | None = None
    owner_name: str | None = None
    organization_name: str | None = None
    department_name: str | None = None
    department_names: list[str] = Field(default_factory=list)
    block_name: str | None = None
    members_count: int | None = None
    member_user_ids: list[int] = Field(default_factory=list)
    tasks_count: int | None = None
    created_at: datetime
    updated_at: datetime


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int
    total: int | None = None
    page: int | None = None
    page_size: int | None = None


class ProjectMemberBase(SQLModel):
    user_id: int
    role: ProjectMemberRole = ProjectMemberRole.EXECUTOR
    is_active: bool = True


class ProjectMemberCreate(ProjectMemberBase):
    project_id: int


class ProjectMemberUpdate(SQLModel):
    role: ProjectMemberRole | None = None
    is_active: bool | None = None


class ProjectMemberPublic(ProjectMemberBase):
    id: int
    project_id: int
    user_name: str | None = None
    user_email: str | None = None


class ProjectMembersPublic(SQLModel):
    data: list[ProjectMemberPublic]
    count: int


class ProjectAccessUserAssign(SQLModel):
    user_id: int
    role_key: str
    is_active: bool = True


class ProjectAccessUsersReplace(SQLModel):
    assignments: list[ProjectAccessUserAssign] = Field(default_factory=list)


class ProjectAccessUserPublic(SQLModel):
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    role_key: str
    role_title: str
    is_active: bool


class ProjectAccessUsersPublic(SQLModel):
    data: list[ProjectAccessUserPublic]
    count: int


class ProjectAccessGroupAssign(SQLModel):
    group_id: int
    role_key: str
    is_active: bool = True


class ProjectAccessGroupsReplace(SQLModel):
    assignments: list[ProjectAccessGroupAssign] = Field(default_factory=list)


class ProjectAccessGroupPublic(SQLModel):
    group_id: int
    group_name: str | None = None
    organization_id: int | None = None
    role_key: str
    role_title: str
    is_active: bool


class ProjectAccessGroupsPublic(SQLModel):
    data: list[ProjectAccessGroupPublic]
    count: int


class ProjectStatusBase(SQLModel):
    name: str
    code: str | None = None
    color: str | None = None
    order: int = 0
    is_default: bool = False
    is_final: bool = False


class ProjectStatusCreate(ProjectStatusBase):
    project_id: int


class ProjectStatusUpdate(SQLModel):
    name: str | None = None
    code: str | None = None
    color: str | None = None
    order: int | None = None
    is_default: bool | None = None
    is_final: bool | None = None


class ProjectStatusPublic(ProjectStatusBase):
    id: int
    project_id: int


class ProjectStatusesPublic(SQLModel):
    data: list[ProjectStatusPublic]
    count: int
