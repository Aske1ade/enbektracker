from fastapi.testclient import TestClient

from app.core.config import settings


def test_admin_task_policy_defaults_and_update(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    get_response = client.get(
        f"{settings.API_V1_STR}/admin/task-policy",
        headers=superuser_token_headers,
    )
    assert get_response.status_code == 200, get_response.text
    initial = get_response.json()
    assert "allow_backdated_creation" in initial
    assert initial["overdue_desktop_reminders_enabled"] is True
    assert initial["overdue_desktop_reminder_interval_minutes"] == 2

    update_response = client.put(
        f"{settings.API_V1_STR}/admin/task-policy",
        headers=superuser_token_headers,
        json={
            "allow_backdated_creation": True,
            "overdue_desktop_reminders_enabled": False,
            "overdue_desktop_reminder_interval_minutes": 15,
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["allow_backdated_creation"] is True
    assert updated["overdue_desktop_reminders_enabled"] is False
    assert updated["overdue_desktop_reminder_interval_minutes"] == 15

    read_back_response = client.get(
        f"{settings.API_V1_STR}/admin/task-policy",
        headers=superuser_token_headers,
    )
    assert read_back_response.status_code == 200, read_back_response.text
    read_back = read_back_response.json()
    assert read_back["allow_backdated_creation"] is True
    assert read_back["overdue_desktop_reminders_enabled"] is False
    assert read_back["overdue_desktop_reminder_interval_minutes"] == 15


def test_admin_task_policy_interval_validation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    too_low_response = client.put(
        f"{settings.API_V1_STR}/admin/task-policy",
        headers=superuser_token_headers,
        json={
            "allow_backdated_creation": False,
            "overdue_desktop_reminders_enabled": True,
            "overdue_desktop_reminder_interval_minutes": 1,
        },
    )
    assert too_low_response.status_code == 422, too_low_response.text
    assert "Интервал повторных desktop-напоминаний" in too_low_response.json()["detail"]

    too_high_response = client.put(
        f"{settings.API_V1_STR}/admin/task-policy",
        headers=superuser_token_headers,
        json={
            "allow_backdated_creation": False,
            "overdue_desktop_reminders_enabled": True,
            "overdue_desktop_reminder_interval_minutes": 121,
        },
    )
    assert too_high_response.status_code == 422, too_high_response.text
    assert "Интервал повторных desktop-напоминаний" in too_high_response.json()["detail"]
