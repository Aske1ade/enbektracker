from datetime import datetime

from sqlmodel import Field, SQLModel


class OrganizationCreate(SQLModel):
    name: str
    code: str | None = None
    description: str | None = None
    parent_organization_id: int | None = None


class OrganizationUpdate(SQLModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    parent_organization_id: int | None = None


class OrganizationPublic(SQLModel):
    id: int
    name: str
    code: str | None = None
    description: str | None = None
    parent_organization_id: int | None = None
    groups_count: int = 0
    projects_count: int = 0
    managers_count: int = 0
    created_at: datetime
    updated_at: datetime


class OrganizationsPublic(SQLModel):
    data: list[OrganizationPublic]
    count: int


class GroupCreate(SQLModel):
    name: str
    code: str | None = None
    description: str | None = None
    parent_group_id: int | None = None


class GroupUpdate(SQLModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    parent_group_id: int | None = None


class GroupPublic(SQLModel):
    id: int
    organization_id: int | None = None
    name: str
    code: str | None = None
    description: str | None = None
    parent_group_id: int | None = None


class GroupsPublic(SQLModel):
    data: list[GroupPublic]
    count: int


class GroupMemberPublic(SQLModel):
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    role_name: str = "member"
    is_active: bool


class GroupMembersPublic(SQLModel):
    data: list[GroupMemberPublic]
    count: int


class GroupMemberAssign(SQLModel):
    user_id: int
    role_name: str = "member"


class GroupMemberUpdate(SQLModel):
    role_name: str | None = None
    is_active: bool | None = None


class OrganizationMemberPublic(SQLModel):
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    role_name: str = "member"
    is_active: bool


class OrganizationMembersPublic(SQLModel):
    data: list[OrganizationMemberPublic]
    count: int


class OrganizationMemberAssign(SQLModel):
    user_id: int
    role_name: str = "member"


class OrganizationMemberUpdate(SQLModel):
    role_name: str | None = None
    is_active: bool | None = None


class OrganizationTreeNode(SQLModel):
    id: int
    name: str
    code: str | None = None
    parent_organization_id: int | None = None
    children: list["OrganizationTreeNode"] = Field(default_factory=list)


class OrganizationTreePublic(SQLModel):
    data: list[OrganizationTreeNode]
    count: int


class GroupTreeNode(SQLModel):
    id: int
    organization_id: int
    name: str
    code: str | None = None
    parent_group_id: int | None = None
    children: list["GroupTreeNode"] = Field(default_factory=list)


class GroupTreePublic(SQLModel):
    data: list[GroupTreeNode]
    count: int
