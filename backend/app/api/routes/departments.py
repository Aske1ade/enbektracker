from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.models import Department
from app.repositories import departments as department_repo
from app.schemas.department import (
    DepartmentCreate,
    DepartmentPublic,
    DepartmentsPublic,
    DepartmentUpdate,
)
from app.services import rbac_service

router = APIRouter(prefix="/departments", tags=["departments"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/", response_model=DepartmentsPublic)
def read_departments(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> DepartmentsPublic:
    _ = current_user
    departments, count = department_repo.list_departments(session, skip=skip, limit=limit)
    return DepartmentsPublic(data=[DepartmentPublic.model_validate(d) for d in departments], count=count)


@router.post("/", response_model=DepartmentPublic)
def create_department(
    session: SessionDep,
    current_user: CurrentUser,
    payload: DepartmentCreate,
) -> DepartmentPublic:
    rbac_service.require_manager(current_user)

    department = Department.model_validate(payload)
    department.created_at = utcnow()
    department.updated_at = utcnow()
    created = department_repo.create_department(session, department)
    return DepartmentPublic.model_validate(created)


@router.get("/{department_id}", response_model=DepartmentPublic)
def read_department(
    department_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> DepartmentPublic:
    _ = current_user
    department = department_repo.get_department(session, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return DepartmentPublic.model_validate(department)


@router.patch("/{department_id}", response_model=DepartmentPublic)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> DepartmentPublic:
    rbac_service.require_manager(current_user)

    department = department_repo.get_department(session, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    department.sqlmodel_update(payload.model_dump(exclude_unset=True))
    department.updated_at = utcnow()
    updated = department_repo.update_department(session, department)
    return DepartmentPublic.model_validate(updated)


@router.delete("/{department_id}")
def delete_department(
    department_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    rbac_service.require_manager(current_user)

    department = department_repo.get_department(session, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    department_repo.delete_department(session, department)
    return {"message": "Department deleted successfully"}
