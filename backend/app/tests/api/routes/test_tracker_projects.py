from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils.tracker import create_department_via_api, create_project_via_api, get_project_statuses
from app.tests.utils.utils import random_lower_string


def test_tracker_projects_crud_and_default_statuses(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    dep_name = f"dep-{random_lower_string()[:8]}"
    dep_code = f"DEP_{random_lower_string()[:6]}"
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=dep_name,
        code=dep_code,
    )

    project_name = f"proj-{random_lower_string()[:8]}"
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=project_name,
        department_id=department_id,
        require_close_comment=True,
        require_close_attachment=True,
    )

    list_response = client.get(
        f"{settings.API_V1_STR}/projects/",
        headers=superuser_token_headers,
        params={"page": 1, "page_size": 10},
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    listed_ids = {item["id"] for item in payload["data"]}
    assert project_id in listed_ids
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert payload["total"] >= payload["count"]
    listed = next(item for item in payload["data"] if item["id"] == project_id)
    assert listed["owner_name"]
    assert listed["department_name"] == dep_name
    assert "members_count" in listed
    assert "tasks_count" in listed

    read_response = client.get(
        f"{settings.API_V1_STR}/projects/{project_id}",
        headers=superuser_token_headers,
    )
    assert read_response.status_code == 200
    read_data = read_response.json()
    assert read_data["name"] == project_name
    assert read_data["require_close_attachment"] is True
    assert read_data["owner_name"]
    assert read_data["department_name"] == dep_name
    assert "members_count" in read_data
    assert "tasks_count" in read_data

    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    assert len(statuses) >= 4
    codes = {status["code"] for status in statuses}
    assert {"new", "in_progress", "blocked", "done"}.issubset(codes)

    update_response = client.patch(
        f"{settings.API_V1_STR}/projects/{project_id}",
        headers=superuser_token_headers,
        json={"description": "updated", "deadline_yellow_days": 2},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "updated"
    assert update_response.json()["deadline_yellow_days"] == 2

    delete_response = client.delete(
        f"{settings.API_V1_STR}/projects/{project_id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Project deleted successfully"
