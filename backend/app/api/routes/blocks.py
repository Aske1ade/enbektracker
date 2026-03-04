from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.models import WorkBlock
from app.repositories import blocks as block_repo
from app.schemas.block import (
    BlockDepartmentLinkCreate,
    BlockDepartmentLinkPublic,
    BlockDepartmentLinksPublic,
    BlockManagerCreate,
    BlockManagerPublic,
    BlockManagersPublic,
    BlockProjectLinkCreate,
    BlockProjectLinkPublic,
    BlockProjectLinksPublic,
    WorkBlockCreate,
    WorkBlockPublic,
    WorkBlocksPublic,
    WorkBlockUpdate,
)
from app.services import rbac_service

router = APIRouter(prefix="/blocks", tags=["blocks"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_public(session: SessionDep, block: WorkBlock) -> WorkBlockPublic:
    departments_count, projects_count, managers_count = block_repo.block_counts(
        session,
        block_id=block.id,
    )
    return WorkBlockPublic(
        id=block.id,
        name=block.name,
        code=block.code,
        description=block.description,
        departments_count=departments_count,
        projects_count=projects_count,
        managers_count=managers_count,
        created_at=block.created_at,
        updated_at=block.updated_at,
    )


@router.get("/", response_model=WorkBlocksPublic)
def read_blocks(
    session: SessionDep,
    current_user: CurrentUser,
) -> WorkBlocksPublic:
    rbac_service.require_manager(current_user)
    blocks = block_repo.list_blocks(session)
    data = [_to_public(session, block) for block in blocks if block.id is not None]
    return WorkBlocksPublic(data=data, count=len(data))


@router.post("/", response_model=WorkBlockPublic)
def create_block(
    payload: WorkBlockCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WorkBlockPublic:
    rbac_service.require_manager(current_user)
    block = block_repo.create_block(
        session,
        WorkBlock(
            name=payload.name,
            code=payload.code,
            description=payload.description,
        ),
    )
    return _to_public(session, block)


@router.get("/{block_id}", response_model=WorkBlockPublic)
def read_block(
    block_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> WorkBlockPublic:
    rbac_service.require_manager(current_user)
    block = block_repo.get_block(session, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    return _to_public(session, block)


@router.patch("/{block_id}", response_model=WorkBlockPublic)
def update_block(
    block_id: int,
    payload: WorkBlockUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> WorkBlockPublic:
    rbac_service.require_manager(current_user)
    block = block_repo.get_block(session, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    block.sqlmodel_update(payload.model_dump(exclude_unset=True))
    block.updated_at = utcnow()
    block = block_repo.update_block(session, block)
    return _to_public(session, block)


@router.delete("/{block_id}")
def delete_block(
    block_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    rbac_service.require_manager(current_user)
    block = block_repo.get_block(session, block_id)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    block_repo.delete_block(session, block_id)
    return {"message": "Block deleted successfully"}


@router.get("/{block_id}/departments", response_model=BlockDepartmentLinksPublic)
def read_block_departments(
    block_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> BlockDepartmentLinksPublic:
    rbac_service.require_manager(current_user)
    data = [
        BlockDepartmentLinkPublic(
            department_id=row.department_id,
            department_name=row.department.name if row.department is not None else None,
        )
        for row in block_repo.list_block_departments(session, block_id=block_id)
    ]
    return BlockDepartmentLinksPublic(data=data, count=len(data))


@router.post("/{block_id}/departments", response_model=BlockDepartmentLinkPublic)
def add_block_department(
    block_id: int,
    payload: BlockDepartmentLinkCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> BlockDepartmentLinkPublic:
    rbac_service.require_manager(current_user)
    row = block_repo.add_block_department(
        session,
        block_id=block_id,
        department_id=payload.department_id,
    )
    name_map = block_repo.get_department_name_map(session)
    return BlockDepartmentLinkPublic(
        department_id=row.department_id,
        department_name=name_map.get(row.department_id),
    )


@router.delete("/{block_id}/departments/{department_id}")
def delete_block_department(
    block_id: int,
    department_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    rbac_service.require_manager(current_user)
    block_repo.remove_block_department(session, block_id=block_id, department_id=department_id)
    return {"message": "Department removed from block"}


@router.get("/{block_id}/projects", response_model=BlockProjectLinksPublic)
def read_block_projects(
    block_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> BlockProjectLinksPublic:
    rbac_service.require_manager(current_user)
    data = [
        BlockProjectLinkPublic(
            project_id=row.project_id,
            project_name=row.project.name if row.project is not None else None,
        )
        for row in block_repo.list_block_projects(session, block_id=block_id)
    ]
    return BlockProjectLinksPublic(data=data, count=len(data))


@router.post("/{block_id}/projects", response_model=BlockProjectLinkPublic)
def add_block_project(
    block_id: int,
    payload: BlockProjectLinkCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> BlockProjectLinkPublic:
    rbac_service.require_manager(current_user)
    row = block_repo.add_block_project(
        session,
        block_id=block_id,
        project_id=payload.project_id,
    )
    name_map = block_repo.get_project_name_map(session)
    return BlockProjectLinkPublic(
        project_id=row.project_id,
        project_name=name_map.get(row.project_id),
    )


@router.delete("/{block_id}/projects/{project_id}")
def delete_block_project(
    block_id: int,
    project_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    rbac_service.require_manager(current_user)
    block_repo.remove_block_project(session, block_id=block_id, project_id=project_id)
    return {"message": "Project removed from block"}


@router.get("/{block_id}/managers", response_model=BlockManagersPublic)
def read_block_managers(
    block_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> BlockManagersPublic:
    rbac_service.require_manager(current_user)
    data = [
        BlockManagerPublic(
            user_id=row.user_id,
            user_name=(row.user.full_name or row.user.email) if row.user is not None else None,
            is_active=row.is_active,
        )
        for row in block_repo.list_block_managers(session, block_id=block_id)
    ]
    return BlockManagersPublic(data=data, count=len(data))


@router.post("/{block_id}/managers", response_model=BlockManagerPublic)
def add_block_manager(
    block_id: int,
    payload: BlockManagerCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> BlockManagerPublic:
    rbac_service.require_manager(current_user)
    row = block_repo.upsert_block_manager(
        session,
        block_id=block_id,
        user_id=payload.user_id,
        is_active=payload.is_active,
    )
    names = block_repo.get_user_display_name_map(session)
    return BlockManagerPublic(
        user_id=row.user_id,
        user_name=names.get(row.user_id),
        is_active=row.is_active,
    )


@router.delete("/{block_id}/managers/{user_id}")
def delete_block_manager(
    block_id: int,
    user_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    rbac_service.require_manager(current_user)
    block_repo.remove_block_manager(session, block_id=block_id, user_id=user_id)
    return {"message": "Manager removed from block"}
