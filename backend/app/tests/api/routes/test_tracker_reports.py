from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils.tracker import (
    add_project_member,
    auth_headers,
    create_department_via_api,
    create_project_via_api,
    create_task_via_api,
    create_user_via_api,
    get_project_statuses,
)
from app.tests.utils.utils import random_lower_string


def test_tracker_reports_export_csv_xlsx(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"reports-dep-{random_lower_string()[:8]}",
        code=f"RD_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"reports-proj-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )

    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    status_new_id = next(item["id"] for item in statuses if item["code"] == "new")

    executor = create_user_via_api(client, superuser_token_headers, system_role="executor")
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=executor.id,
        role="executor",
    )

    create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=None,
        title="report-source-task",
    )

    csv_response = client.get(
        f"{settings.API_V1_STR}/reports/tasks/export.csv",
        headers=superuser_token_headers,
        params={"project_id": project_id},
    )
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "ID задачи,Наименование задачи,Проект" in csv_response.text

    xlsx_response = client.get(
        f"{settings.API_V1_STR}/reports/tasks/export.xlsx",
        headers=superuser_token_headers,
        params={"project_id": project_id},
    )
    assert xlsx_response.status_code == 200
    assert (
        xlsx_response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(xlsx_response.content) > 0

    discipline_response = client.get(
        f"{settings.API_V1_STR}/reports/discipline",
        headers=superuser_token_headers,
        params={"project_id": project_id},
    )
    assert discipline_response.status_code == 200
    assert "data" in discipline_response.json()

    discipline_docx = client.get(
        f"{settings.API_V1_STR}/reports/discipline/export.docx",
        headers=superuser_token_headers,
        params={"project_id": project_id},
    )
    assert discipline_docx.status_code == 200
    assert (
        discipline_docx.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(discipline_docx.content) > 0


def test_tracker_reports_xlsx_available_for_regular_user_with_project_access(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"reports-user-dep-{random_lower_string()[:8]}",
        code=f"RUD_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"reports-user-proj-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )
    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    status_new_id = next(item["id"] for item in statuses if item["code"] == "new")

    regular_user = create_user_via_api(client, superuser_token_headers, system_role="user")
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=regular_user.id,
        role="executor",
    )

    create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=regular_user.id,
        controller_id=None,
        title="report-regular-user-task",
    )

    user_headers = auth_headers(client, regular_user.email, regular_user.password)
    xlsx_response = client.get(
        f"{settings.API_V1_STR}/reports/tasks/export.xlsx",
        headers=user_headers,
        params={"project_id": project_id},
    )
    assert xlsx_response.status_code == 200, xlsx_response.text
    assert (
        xlsx_response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(xlsx_response.content) > 0
