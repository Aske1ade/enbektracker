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


def test_tracker_error_response_contract_and_conflict_codes(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    missing_task = client.get(
        f"{settings.API_V1_STR}/tasks/999999999",
        headers=superuser_token_headers,
    )
    assert missing_task.status_code == 404
    missing_payload = missing_task.json()
    assert missing_payload["code"] == "http_404"
    assert missing_payload["request_id"]

    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"err-dep-{random_lower_string()[:8]}",
        code=f"ER_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"err-proj-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )

    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    status_new_id = next(item["id"] for item in statuses if item["code"] == "new")

    executor = create_user_via_api(client, superuser_token_headers, system_role="executor")
    outsider = create_user_via_api(client, superuser_token_headers, system_role="executor")

    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=executor.id,
        role="executor",
    )

    duplicate_member = client.post(
        f"{settings.API_V1_STR}/projects/{project_id}/members",
        headers=superuser_token_headers,
        json={
            "project_id": project_id,
            "user_id": executor.id,
            "role": "executor",
            "is_active": True,
        },
    )
    assert duplicate_member.status_code == 409
    dup_payload = duplicate_member.json()
    assert dup_payload["code"] == "http_409"
    assert dup_payload["request_id"]

    task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=None,
        title="error-contract-task",
    )

    outsider_headers = auth_headers(client, outsider.email, outsider.password)
    forbidden = client.get(
        f"{settings.API_V1_STR}/tasks/{task['id']}",
        headers=outsider_headers,
    )
    assert forbidden.status_code == 403
    forbidden_payload = forbidden.json()
    assert forbidden_payload["code"] == "http_403"
    assert forbidden_payload["request_id"]
