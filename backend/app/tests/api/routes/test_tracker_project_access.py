from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils.tracker import (
    auth_headers,
    create_project_via_api,
    create_user_via_api,
    get_project_statuses,
)
from app.tests.utils.utils import random_lower_string


def test_project_access_via_group_assignment(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    create_org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=superuser_token_headers,
        json={
            "name": f"org-{random_lower_string()[:8]}",
            "code": f"ORG_{random_lower_string()[:6]}",
            "description": "test organization",
        },
    )
    assert create_org.status_code == 200, create_org.text
    organization_id = create_org.json()["id"]

    create_group = client.post(
        f"{settings.API_V1_STR}/organizations/{organization_id}/groups",
        headers=superuser_token_headers,
        json={
            "name": f"group-{random_lower_string()[:8]}",
            "code": f"GR_{random_lower_string()[:6]}",
            "description": "test group",
        },
    )
    assert create_group.status_code == 200, create_group.text
    group_id = create_group.json()["id"]

    user = create_user_via_api(
        client,
        superuser_token_headers,
        system_role="user",
        is_superuser=False,
    )
    assign_group_member = client.post(
        f"{settings.API_V1_STR}/organizations/groups/{group_id}/members",
        headers=superuser_token_headers,
        json={"user_id": user.id},
    )
    assert assign_group_member.status_code == 200, assign_group_member.text

    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"project-{random_lower_string()[:8]}",
        department_id=None,
        require_close_comment=False,
        require_close_attachment=False,
    )
    set_group_access = client.put(
        f"{settings.API_V1_STR}/projects/{project_id}/access/groups",
        headers=superuser_token_headers,
        json={
            "assignments": [
                {
                    "group_id": group_id,
                    "role_key": "contributor",
                    "is_active": True,
                }
            ]
        },
    )
    assert set_group_access.status_code == 200, set_group_access.text

    user_headers = auth_headers(client, user.email, user.password)
    projects_response = client.get(
        f"{settings.API_V1_STR}/projects/",
        headers=user_headers,
    )
    assert projects_response.status_code == 200, projects_response.text
    project_ids = {item["id"] for item in projects_response.json()["data"]}
    assert project_id in project_ids

    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    status_new_id = next(item["id"] for item in statuses if item["code"] == "new")
    create_task = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=user_headers,
        json={
            "title": "group-assigned-task",
            "description": "created via group project role",
            "project_id": project_id,
            "assignee_id": user.id,
            "controller_id": None,
            "due_date": "2030-01-05T10:00:00Z",
            "workflow_status_id": status_new_id,
        },
    )
    assert create_task.status_code == 200, create_task.text

