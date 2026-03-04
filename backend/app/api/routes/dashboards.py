from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.dashboard import DashboardDistributions, DashboardSummary, DashboardTrendsPublic
from app.services import rbac_service
from app.services.dashboard_service import (
    build_dashboard_distributions,
    build_dashboard_summary,
    build_dashboard_trends,
)
from app.services.task_service import refresh_deadline_flags_for_open_tasks

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


def _resolve_scoped_project_ids(
    session: SessionDep,
    *,
    can_view_all: bool,
    base_project_ids: set[int] | None,
    project_id: int | None,
    department_id: int | None,
) -> set[int] | None:
    scoped_project_ids = None if can_view_all else set(base_project_ids or set())

    if department_id is not None:
        group_ids = rbac_service.get_group_descendant_ids(
            session,
            group_id=department_id,
        )
        if not group_ids:
            group_ids = {department_id}
        department_project_ids = rbac_service.get_project_ids_for_group_ids(
            session,
            group_ids=group_ids,
        )
        if scoped_project_ids is None:
            scoped_project_ids = department_project_ids
        else:
            scoped_project_ids &= department_project_ids

    if project_id is not None:
        if scoped_project_ids is None:
            scoped_project_ids = {project_id}
        else:
            if project_id not in scoped_project_ids:
                raise HTTPException(status_code=403, detail="No access to the project")
            scoped_project_ids = {project_id}

    return scoped_project_ids


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    session: SessionDep,
    current_user: CurrentUser,
    top_limit: int = Query(default=5),
    scope_mode: str = Query(default="managed"),
    project_id: int | None = Query(default=None, ge=1),
    department_id: int | None = Query(default=None, ge=1),
) -> DashboardSummary:
    if top_limit not in {5, 10}:
        raise HTTPException(status_code=422, detail="top_limit must be 5 or 10")
    if scope_mode not in {"managed", "personal"}:
        raise HTTPException(
            status_code=422,
            detail="scope_mode must be 'managed' or 'personal'",
        )
    refresh_deadline_flags_for_open_tasks(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    base_project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    project_ids = _resolve_scoped_project_ids(
        session,
        can_view_all=can_view_all,
        base_project_ids=base_project_ids,
        project_id=project_id,
        department_id=department_id,
    )
    can_use_extended_scope = rbac_service.can_use_extended_dashboard_scope(
        session,
        user=current_user,
        project_ids=project_ids,
    )
    resolved_scope_mode = scope_mode if can_use_extended_scope else "personal"
    viewer_user_ids = rbac_service.get_dashboard_viewer_user_ids(
        session,
        user=current_user,
        scope_mode=resolved_scope_mode,
        project_ids=project_ids,
    )
    summary = build_dashboard_summary(
        session,
        top_limit=top_limit,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    summary.scope_mode = resolved_scope_mode
    summary.can_use_extended_scope = can_use_extended_scope
    return summary


@router.get("/distributions", response_model=DashboardDistributions)
def get_dashboard_distributions(
    session: SessionDep,
    current_user: CurrentUser,
    scope_mode: str = Query(default="managed"),
    project_id: int | None = Query(default=None, ge=1),
    department_id: int | None = Query(default=None, ge=1),
) -> DashboardDistributions:
    if scope_mode not in {"managed", "personal"}:
        raise HTTPException(
            status_code=422,
            detail="scope_mode must be 'managed' or 'personal'",
        )
    refresh_deadline_flags_for_open_tasks(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    base_project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    project_ids = _resolve_scoped_project_ids(
        session,
        can_view_all=can_view_all,
        base_project_ids=base_project_ids,
        project_id=project_id,
        department_id=department_id,
    )
    can_use_extended_scope = rbac_service.can_use_extended_dashboard_scope(
        session,
        user=current_user,
        project_ids=project_ids,
    )
    resolved_scope_mode = scope_mode if can_use_extended_scope else "personal"
    viewer_user_ids = rbac_service.get_dashboard_viewer_user_ids(
        session,
        user=current_user,
        scope_mode=resolved_scope_mode,
        project_ids=project_ids,
    )
    return build_dashboard_distributions(
        session,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )


@router.get("/trends", response_model=DashboardTrendsPublic)
def get_dashboard_trends(
    session: SessionDep,
    current_user: CurrentUser,
    period: str = Query(default="week"),
    scope_mode: str = Query(default="managed"),
    project_id: int | None = Query(default=None, ge=1),
    department_id: int | None = Query(default=None, ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
) -> DashboardTrendsPublic:
    if scope_mode not in {"managed", "personal"}:
        raise HTTPException(
            status_code=422,
            detail="scope_mode must be 'managed' or 'personal'",
        )
    refresh_deadline_flags_for_open_tasks(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    base_project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    project_ids = _resolve_scoped_project_ids(
        session,
        can_view_all=can_view_all,
        base_project_ids=base_project_ids,
        project_id=project_id,
        department_id=department_id,
    )
    can_use_extended_scope = rbac_service.can_use_extended_dashboard_scope(
        session,
        user=current_user,
        project_ids=project_ids,
    )
    resolved_scope_mode = scope_mode if can_use_extended_scope else "personal"
    viewer_user_ids = rbac_service.get_dashboard_viewer_user_ids(
        session,
        user=current_user,
        scope_mode=resolved_scope_mode,
        project_ids=project_ids,
    )
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=30))
    if start > end:
        raise HTTPException(status_code=422, detail="date_from must be less than or equal to date_to")
    return build_dashboard_trends(
        session,
        period=period,
        date_from=start,
        date_to=end,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
