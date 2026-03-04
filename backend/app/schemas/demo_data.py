from sqlmodel import Field, SQLModel

from app.models.enums import SystemRole


class DemoDataCredential(SQLModel):
    email: str
    full_name: str | None = None
    username: str | None = None
    system_role: SystemRole
    department_name: str | None = None
    organization_names: list[str] = Field(default_factory=list)
    group_names: list[str] = Field(default_factory=list)
    group_roles: list[str] = Field(default_factory=list)
    password: str


class DemoDataSummary(SQLModel):
    enabled: bool
    marker: str
    is_locked: bool = False
    users_count: int
    departments_count: int
    projects_count: int
    tasks_count: int
    credentials: list[DemoDataCredential]


class DemoDataToggleRequest(SQLModel):
    enabled: bool
    admin_password: str | None = None


class DemoDataLockRequest(SQLModel):
    is_locked: bool
