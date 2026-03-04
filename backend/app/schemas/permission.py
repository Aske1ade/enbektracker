from sqlmodel import SQLModel


class PermissionPublic(SQLModel):
    key: str
    name: str


class PermissionsPublic(SQLModel):
    data: list[PermissionPublic]
    count: int


class RolePublic(SQLModel):
    key: str
    title: str
    permissions_count: int


class RolesPublic(SQLModel):
    data: list[RolePublic]
    count: int
