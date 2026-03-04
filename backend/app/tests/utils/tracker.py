from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils.utils import random_email, random_lower_string


@dataclass
class TrackerUser:
    id: int
    email: str
    password: str


def auth_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        f"{settings.API_V1_STR}/auth/access-token",
        data={"username": email, "password": password},
    )
    if response.status_code != 200:
        # fallback to legacy endpoint for backward compatibility
        response = client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": email, "password": password},
        )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_user_via_api(
    client: TestClient,
    admin_headers: dict[str, str],
    *,
    system_role: str,
    is_superuser: bool = False,
) -> TrackerUser:
    password = f"P@ss-{random_lower_string()[:10]}"
    email = random_email()
    payload = {
        "email": email,
        "password": password,
        "is_active": True,
        "is_superuser": is_superuser,
        "system_role": system_role,
    }
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=admin_headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return TrackerUser(id=data["id"], email=email, password=password)


def create_department_via_api(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    code: str,
) -> int:
    response = client.post(
        f"{settings.API_V1_STR}/departments/",
        headers=headers,
        json={"name": name, "code": code, "description": "test department"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_project_via_api(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    department_id: int | None,
    require_close_comment: bool = True,
    require_close_attachment: bool = False,
) -> int:
    payload = {
        "name": name,
        "description": "test project",
        "department_id": department_id,
        "require_close_comment": require_close_comment,
        "require_close_attachment": require_close_attachment,
        "deadline_yellow_days": 3,
        "deadline_normal_days": 5,
    }
    response = client.post(
        f"{settings.API_V1_STR}/projects/",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def get_project_statuses(client: TestClient, headers: dict[str, str], project_id: int) -> list[dict]:
    response = client.get(
        f"{settings.API_V1_STR}/project-statuses/",
        headers=headers,
        params={"project_id": project_id},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def add_project_member(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_id: int,
    user_id: int,
    role: str,
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/projects/{project_id}/members",
        headers=headers,
        json={
            "project_id": project_id,
            "user_id": user_id,
            "role": role,
            "is_active": True,
        },
    )
    assert response.status_code == 200, response.text


def create_task_via_api(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_id: int,
    status_id: int,
    assignee_id: int,
    controller_id: int | None,
    title: str = "tracker task",
) -> dict:
    payload = {
        "title": title,
        "description": "task description",
        "project_id": project_id,
        "assignee_id": assignee_id,
        "controller_id": controller_id,
        "due_date": "2030-01-05T10:00:00Z",
        "workflow_status_id": status_id,
    }
    response = client.post(
        f"{settings.API_V1_STR}/tasks/",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()
