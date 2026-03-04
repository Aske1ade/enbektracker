from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.api.deps import CurrentUser, SessionDep
from app.schemas.report import DisciplineRowsPublic
from app.services import report_service, rbac_service
from app.services.task_service import refresh_deadline_flags_for_open_tasks

router = APIRouter(prefix="/reports", tags=["reports"])


def _viewer_scope_user_ids(session: SessionDep, current_user: CurrentUser) -> set[int] | None:
    _ = session
    if rbac_service.is_system_admin(current_user):
        return None
    return {int(current_user.id)}


def _refresh_deadline_state(session: SessionDep) -> None:
    refresh_deadline_flags_for_open_tasks(session)


@router.get("/tasks")
def get_tasks_report(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
    workflow_status_id: int | None = None,
    overdue_only: bool = False,
) -> list[dict]:
    _refresh_deadline_state(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    viewer_user_ids = _viewer_scope_user_ids(session, current_user)
    rows = report_service.build_task_report_rows(
        session,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        department_id=department_id,
        assignee_id=assignee_id,
        workflow_status_id=workflow_status_id,
        overdue_only=overdue_only,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    return [row.model_dump() for row in rows]


@router.get("/tasks/export.csv")
def export_tasks_report_csv(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
    workflow_status_id: int | None = None,
    overdue_only: bool = False,
    template: str = "full",
    columns: str | None = Query(default=None),
) -> Response:
    _refresh_deadline_state(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    viewer_user_ids = _viewer_scope_user_ids(session, current_user)
    rows = report_service.build_task_report_rows(
        session,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        department_id=department_id,
        assignee_id=assignee_id,
        workflow_status_id=workflow_status_id,
        overdue_only=overdue_only,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    data = report_service.to_csv(
        rows,
        template=template,
        columns=report_service.parse_report_columns(columns),
    )
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tasks-report.csv"'},
    )


@router.get("/tasks/export.xlsx")
def export_tasks_report_xlsx(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
    workflow_status_id: int | None = None,
    overdue_only: bool = False,
    template: str = "full",
    columns: str | None = Query(default=None),
    column_widths: str | None = Query(default=None),
) -> Response:
    _refresh_deadline_state(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    viewer_user_ids = _viewer_scope_user_ids(session, current_user)

    rows = report_service.build_task_report_rows(
        session,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        department_id=department_id,
        assignee_id=assignee_id,
        workflow_status_id=workflow_status_id,
        overdue_only=overdue_only,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    data = report_service.to_xlsx(
        rows,
        template=template,
        columns=report_service.parse_report_columns(columns),
        column_widths=report_service.parse_report_column_widths(column_widths),
    )
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="tasks-report.xlsx"'},
    )


@router.get("/discipline", response_model=DisciplineRowsPublic)
def get_discipline_report(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
) -> DisciplineRowsPublic:
    _refresh_deadline_state(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    viewer_user_ids = _viewer_scope_user_ids(session, current_user)
    rows = report_service.build_task_report_rows(
        session,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        department_id=department_id,
        assignee_id=assignee_id,
        overdue_only=True,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    discipline_rows = report_service.build_discipline_rows(rows)
    return DisciplineRowsPublic(data=discipline_rows, count=len(discipline_rows))


@router.get("/discipline/export.xlsx")
def export_discipline_xlsx(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
) -> Response:
    _refresh_deadline_state(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    viewer_user_ids = _viewer_scope_user_ids(session, current_user)
    rows = report_service.build_task_report_rows(
        session,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        department_id=department_id,
        assignee_id=assignee_id,
        overdue_only=True,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    discipline_rows = report_service.build_discipline_rows(rows)
    data = report_service.discipline_to_xlsx(discipline_rows)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="discipline-report.xlsx"'},
    )


@router.get("/discipline/export.docx")
def export_discipline_docx(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    department_id: int | None = None,
    assignee_id: int | None = None,
) -> Response:
    _refresh_deadline_state(session)
    can_view_all = rbac_service.is_system_admin(current_user)
    project_ids = None if can_view_all else rbac_service.get_accessible_project_ids(
        session, user=current_user
    )
    viewer_user_ids = _viewer_scope_user_ids(session, current_user)
    rows = report_service.build_task_report_rows(
        session,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        department_id=department_id,
        assignee_id=assignee_id,
        overdue_only=True,
        project_ids=project_ids,
        viewer_user_ids=viewer_user_ids,
    )
    discipline_rows = report_service.build_discipline_rows(rows)
    data = report_service.discipline_to_docx(discipline_rows)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="discipline-report.docx"'},
    )
