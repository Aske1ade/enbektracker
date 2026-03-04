from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.calendar import (
    CalendarDayDrilldown,
    CalendarScope,
    CalendarSummary,
    CalendarViewMode,
    CalendarViewPublic,
)
from app.services import rbac_service
from app.services.calendar_service import build_calendar_day, build_calendar_summary, build_calendar_view
from app.services.task_service import refresh_deadline_flags_for_open_tasks

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _resolve_calendar_scope(
    session: SessionDep,
    *,
    current_user: CurrentUser,
) -> tuple[bool, set[int] | None, set[int] | None]:
    can_view_all = rbac_service.is_system_admin(current_user)
    if can_view_all:
        return True, None, None
    project_ids = rbac_service.get_accessible_project_ids(session, user=current_user)
    viewer_user_ids = rbac_service.get_task_viewer_user_ids(
        session,
        user=current_user,
        project_ids=project_ids,
    )
    return False, project_ids, viewer_user_ids


@router.get("/summary", response_model=CalendarSummary)
def get_calendar_summary(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
) -> CalendarSummary:
    refresh_deadline_flags_for_open_tasks(session)
    _, project_ids, viewer_user_ids = _resolve_calendar_scope(
        session,
        current_user=current_user,
    )
    if project_id is not None and project_ids is not None and project_id not in project_ids:
        raise HTTPException(status_code=403, detail="No access to requested project")
    start = date_from or date.today()
    end = date_to or (start + timedelta(days=30))
    return build_calendar_summary(
        session,
        date_from=start,
        date_to=end,
        project_id=project_id,
        department_id=department_id,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )


@router.get("/day", response_model=CalendarDayDrilldown)
def get_calendar_day(
    session: SessionDep,
    current_user: CurrentUser,
    day: date = Query(alias="date"),
    project_id: int | None = None,
    department_id: int | None = None,
) -> CalendarDayDrilldown:
    refresh_deadline_flags_for_open_tasks(session)
    _, project_ids, viewer_user_ids = _resolve_calendar_scope(
        session,
        current_user=current_user,
    )
    if project_id is not None and project_ids is not None and project_id not in project_ids:
        raise HTTPException(status_code=403, detail="No access to requested project")
    return build_calendar_day(
        session,
        day=day,
        project_id=project_id,
        department_id=department_id,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )


@router.get("/view", response_model=CalendarViewPublic)
def get_calendar_view(
    session: SessionDep,
    current_user: CurrentUser,
    day: date | None = Query(default=None, alias="date"),
    mode: CalendarViewMode = Query(default=CalendarViewMode.MONTH),
    scope: CalendarScope = Query(default=CalendarScope.PROJECT),
    project_id: int | None = None,
    department_id: int | None = None,
) -> CalendarViewPublic:
    refresh_deadline_flags_for_open_tasks(session)
    _, project_ids, viewer_user_ids = _resolve_calendar_scope(
        session,
        current_user=current_user,
    )
    enforce_project_ids = project_ids if scope == CalendarScope.PROJECT else None
    if project_id is not None and enforce_project_ids is not None and project_id not in enforce_project_ids:
        raise HTTPException(status_code=403, detail="No access to requested project")
    anchor = day or date.today()

    return build_calendar_view(
        session,
        anchor=anchor,
        mode=mode,
        scope=scope,
        project_id=project_id,
        department_id=department_id,
        project_ids=enforce_project_ids,
        viewer_user_id=current_user.id,
        viewer_user_ids=viewer_user_ids,
    )
