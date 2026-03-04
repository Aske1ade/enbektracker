from datetime import datetime

from sqlmodel import SQLModel


class WorkBlockBase(SQLModel):
    name: str
    code: str | None = None
    description: str | None = None


class WorkBlockCreate(WorkBlockBase):
    pass


class WorkBlockUpdate(SQLModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None


class WorkBlockPublic(WorkBlockBase):
    id: int
    departments_count: int = 0
    projects_count: int = 0
    managers_count: int = 0
    created_at: datetime
    updated_at: datetime


class WorkBlocksPublic(SQLModel):
    data: list[WorkBlockPublic]
    count: int


class BlockDepartmentLinkCreate(SQLModel):
    department_id: int


class BlockDepartmentLinkPublic(SQLModel):
    department_id: int
    department_name: str | None = None


class BlockDepartmentLinksPublic(SQLModel):
    data: list[BlockDepartmentLinkPublic]
    count: int


class BlockProjectLinkCreate(SQLModel):
    project_id: int


class BlockProjectLinkPublic(SQLModel):
    project_id: int
    project_name: str | None = None


class BlockProjectLinksPublic(SQLModel):
    data: list[BlockProjectLinkPublic]
    count: int


class BlockManagerCreate(SQLModel):
    user_id: int
    is_active: bool = True


class BlockManagerPublic(SQLModel):
    user_id: int
    user_name: str | None = None
    is_active: bool


class BlockManagersPublic(SQLModel):
    data: list[BlockManagerPublic]
    count: int


class ProjectDepartmentsUpdate(SQLModel):
    department_ids: list[int]


class ProjectDepartmentPublic(SQLModel):
    department_id: int
    department_name: str | None = None


class ProjectDepartmentsPublic(SQLModel):
    data: list[ProjectDepartmentPublic]
    count: int
