from datetime import datetime

from sqlmodel import SQLModel


class DepartmentBase(SQLModel):
    name: str
    code: str | None = None
    description: str | None = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(SQLModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None


class DepartmentPublic(DepartmentBase):
    id: int
    created_at: datetime
    updated_at: datetime


class DepartmentsPublic(SQLModel):
    data: list[DepartmentPublic]
    count: int
