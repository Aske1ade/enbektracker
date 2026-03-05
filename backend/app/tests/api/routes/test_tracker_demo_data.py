from fastapi.testclient import TestClient

from app.core.config import settings


def test_tracker_admin_demo_data_toggle(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    disable_response = client.put(
        f"{settings.API_V1_STR}/admin/demo-data",
        headers=superuser_token_headers,
        json={"enabled": False},
    )
    assert disable_response.status_code == 200, disable_response.text
    assert disable_response.json()["enabled"] is False

    enable_response = client.put(
        f"{settings.API_V1_STR}/admin/demo-data",
        headers=superuser_token_headers,
        json={"enabled": True},
    )
    assert enable_response.status_code == 200, enable_response.text
    enable_data = enable_response.json()
    assert enable_data["enabled"] is True
    assert enable_data["users_count"] >= 6
    assert enable_data["projects_count"] >= 3
    assert enable_data["tasks_count"] >= 12
    assert enable_data["credentials"]
    assert enable_data["credentials"][0]["password"]

    special_task_response = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=superuser_token_headers,
        params={
            "search": "Касательно Единого Социального Фонда",
            "include_completed": True,
            "page": 1,
            "page_size": 50,
        },
    )
    assert special_task_response.status_code == 200, special_task_response.text
    special_rows = special_task_response.json()["data"]
    assert special_rows
    special_task = next(
        (
            row
            for row in special_rows
            if "Касательно Единого Социального Фонда" in str(row.get("title") or "")
        ),
        None,
    )
    assert special_task is not None
    assert special_task["is_overdue"] is True
    assert str(special_task["due_date"]).startswith("2026-03-04")

    status_response = client.get(
        f"{settings.API_V1_STR}/admin/demo-data",
        headers=superuser_token_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["enabled"] is True

    cleanup_response = client.put(
        f"{settings.API_V1_STR}/admin/demo-data",
        headers=superuser_token_headers,
        json={"enabled": False},
    )
    assert cleanup_response.status_code == 200, cleanup_response.text
    cleanup_data = cleanup_response.json()
    assert cleanup_data["enabled"] is False
    assert cleanup_data["users_count"] == 0
    assert cleanup_data["projects_count"] == 0
    assert cleanup_data["tasks_count"] == 0

    relogin_response = client.post(
        f"{settings.API_V1_STR}/auth/access-token",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert relogin_response.status_code == 200, relogin_response.text


def test_tracker_admin_send_desktop_events_test(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    me_response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=superuser_token_headers,
    )
    assert me_response.status_code == 200, me_response.text
    user_id = me_response.json()["id"]

    full_response = client.post(
        f"{settings.API_V1_STR}/admin/users/{user_id}/desktop-events/test",
        headers=superuser_token_headers,
        json={"mode": "full"},
    )
    assert full_response.status_code == 200, full_response.text
    full_data = full_response.json()
    assert full_data["user_id"] == user_id
    assert full_data["mode"] == "full"
    assert full_data["created_count"] == 7
    assert len(full_data["event_ids"]) == 7

    single_response = client.post(
        f"{settings.API_V1_STR}/admin/users/{user_id}/desktop-events/test",
        headers=superuser_token_headers,
        json={"mode": "single"},
    )
    assert single_response.status_code == 200, single_response.text
    single_data = single_response.json()
    assert single_data["mode"] == "single"
    assert single_data["created_count"] == 1
    assert len(single_data["event_ids"]) == 1
