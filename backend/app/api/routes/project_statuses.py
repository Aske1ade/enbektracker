from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import ProjectStatus
from app.repositories import project_statuses as status_repo
from app.schemas.project import (
    ProjectStatusCreate,
    ProjectStatusPublic,
    ProjectStatusesPublic,
    ProjectStatusUpdate,
)
from app.services import rbac_service

router = APIRouter(prefix="/project-statuses", tags=["project-statuses"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/", response_model=ProjectStatusesPublic)
def read_project_statuses(
    session: SessionDep,
    current_user: CurrentUser,
    project_id: int | None = None,
    catalog: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> ProjectStatusesPublic:
    if project_id is not None:
        rbac_service.require_project_access(session, project_id=project_id, user=current_user)
        statuses, count = status_repo.list_project_statuses(
            session,
            project_id=project_id,
            skip=skip,
            limit=limit,
        )
        return ProjectStatusesPublic(
            data=[ProjectStatusPublic.model_validate(s) for s in statuses],
            count=count,
        )

    statement = select(ProjectStatus)
    if not rbac_service.is_system_admin(current_user):
        accessible_project_ids = rbac_service.get_accessible_project_ids(
            session,
            user=current_user,
        )
        if not accessible_project_ids:
            return ProjectStatusesPublic(data=[], count=0)
        statement = statement.where(ProjectStatus.project_id.in_(sorted(accessible_project_ids)))
    statement = statement.order_by(ProjectStatus.order.asc(), ProjectStatus.id.asc())
    statuses = session.exec(statement).all()

    if not catalog:
        sliced = statuses[skip : skip + limit]
        return ProjectStatusesPublic(
            data=[ProjectStatusPublic.model_validate(s) for s in sliced],
            count=len(statuses),
        )

    dedup_map: dict[str, ProjectStatus] = {}
    for status_obj in statuses:
        dedup_key = (status_obj.code or "").strip().lower() or status_obj.name.strip().lower()
        current = dedup_map.get(dedup_key)
        if current is None:
            dedup_map[dedup_key] = status_obj
            continue
        # Keep the most representative status by stable ordering.
        if (
            status_obj.order < current.order
            or (status_obj.order == current.order and status_obj.id < current.id)
        ):
            dedup_map[dedup_key] = status_obj

    deduped = sorted(
        dedup_map.values(),
        key=lambda item: (item.order, item.name.lower(), item.id),
    )
    sliced = deduped[skip : skip + limit]
    return ProjectStatusesPublic(
        data=[ProjectStatusPublic.model_validate(s) for s in sliced],
        count=len(deduped),
    )


@router.post("/", response_model=ProjectStatusPublic)
def create_project_status(
    session: SessionDep,
    current_user: CurrentUser,
    payload: ProjectStatusCreate,
) -> ProjectStatusPublic:
    rbac_service.require_project_controller_or_manager(
        session,
        project_id=payload.project_id,
        user=current_user,
    )

    status_obj = ProjectStatus.model_validate(payload)
    status_obj.created_at = utcnow()
    status_obj.updated_at = utcnow()
    created = status_repo.create_project_status(session, status_obj)
    return ProjectStatusPublic.model_validate(created)


@router.patch("/{status_id}", response_model=ProjectStatusPublic)
def update_project_status(
    status_id: int,
    payload: ProjectStatusUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProjectStatusPublic:
    status_obj = status_repo.get_project_status(session, status_id)
    if not status_obj:
        raise HTTPException(status_code=404, detail="Project status not found")

    rbac_service.require_project_controller_or_manager(
        session,
        project_id=status_obj.project_id,
        user=current_user,
    )

    status_obj.sqlmodel_update(payload.model_dump(exclude_unset=True))
    status_obj.updated_at = utcnow()

    updated = status_repo.update_project_status(session, status_obj)
    return ProjectStatusPublic.model_validate(updated)


@router.delete("/{status_id}")
def delete_project_status(
    status_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    status_obj = status_repo.get_project_status(session, status_id)
    if not status_obj:
        raise HTTPException(status_code=404, detail="Project status not found")

    rbac_service.require_project_manager(
        session,
        project_id=status_obj.project_id,
        user=current_user,
    )

    status_repo.delete_project_status(session, status_obj)
    return {"message": "Project status deleted successfully"}
