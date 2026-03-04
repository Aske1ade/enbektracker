from typing import Literal

from sqlmodel import Field, SQLModel


class AdminDesktopEventsTestRequest(SQLModel):
    mode: Literal["single", "full"] = "full"


class AdminDesktopEventsTestResponse(SQLModel):
    user_id: int
    mode: Literal["single", "full"]
    created_count: int
    event_ids: list[int]


class AdminTaskPolicyPublic(SQLModel):
    allow_backdated_creation: bool


class AdminTaskPolicyUpdate(SQLModel):
    allow_backdated_creation: bool


class AdminDesktopAgentPublic(SQLModel):
    configured: bool
    source: Literal["uploaded", "local_path", "redirect_url", "none"]
    file_name: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    uploaded_at: str | None = None


class AdminDesktopAgentUploadResult(AdminDesktopAgentPublic):
    pass


class AdminAccessOrganizationMembership(SQLModel):
    organization_id: int
    organization_name: str | None = None
    role_name: str
    is_active: bool


class AdminAccessGroupMembership(SQLModel):
    group_id: int
    group_name: str | None = None
    organization_id: int | None = None
    organization_name: str | None = None
    role_name: str
    is_active: bool
    is_primary: bool = False
    is_direct_membership: bool = True


class AdminAccessProjectMembership(SQLModel):
    project_id: int
    project_name: str | None = None
    organization_id: int | None = None
    organization_name: str | None = None
    role: str
    is_active: bool


class AdminAccessProjectRoleAssignment(SQLModel):
    project_id: int
    project_name: str | None = None
    organization_id: int | None = None
    organization_name: str | None = None
    role_key: str
    role_title: str | None = None
    subject_type: Literal["user", "group"]
    subject_user_id: int | None = None
    subject_group_id: int | None = None
    subject_group_name: str | None = None
    is_active: bool


class AdminAccessibleProject(SQLModel):
    project_id: int
    project_name: str
    organization_id: int | None = None
    organization_name: str | None = None
    reasons: list[str] = Field(default_factory=list)


class AdminUserAccessMapPublic(SQLModel):
    user_id: int
    email: str
    full_name: str | None = None
    system_role: str
    is_superuser: bool
    primary_group_id: int | None = None
    primary_group_name: str | None = None
    user_group_ids: list[int] = Field(default_factory=list)
    managed_group_ids: list[int] = Field(default_factory=list)
    managed_organization_ids: list[int] = Field(default_factory=list)
    organizations: list[AdminAccessOrganizationMembership] = Field(default_factory=list)
    groups: list[AdminAccessGroupMembership] = Field(default_factory=list)
    project_memberships: list[AdminAccessProjectMembership] = Field(default_factory=list)
    project_role_assignments: list[AdminAccessProjectRoleAssignment] = Field(
        default_factory=list
    )
    accessible_projects: list[AdminAccessibleProject] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AdminTaskBulkDeleteRequest(SQLModel):
    project_id: int | None = None
    group_id: int | None = None
    organization_id: int | None = None
    include_completed: bool = True


class AdminTaskBulkDeleteResponse(SQLModel):
    matched_tasks: int
    deleted_tasks: int


class AdminTaskBulkSetControllerRequest(SQLModel):
    controller_id: int
    project_id: int | None = None
    group_id: int | None = None
    organization_id: int | None = None
    include_completed: bool = True


class AdminTaskBulkSetControllerResponse(SQLModel):
    matched_tasks: int
    updated_tasks: int
