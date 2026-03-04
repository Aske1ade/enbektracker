from datetime import datetime, timedelta, timezone

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


def test_tracker_desktop_events_lifecycle_poll(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"desk-dep-{random_lower_string()[:8]}",
        code=f"DE_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"desk-proj-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )
    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    status_new_id = next(item["id"] for item in statuses if item["code"] == "new")
    status_in_progress_id = next(item["id"] for item in statuses if item["code"] == "in_progress")

    executor = create_user_via_api(client, superuser_token_headers, system_role="executor")
    controller = create_user_via_api(client, superuser_token_headers, system_role="controller")
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=executor.id,
        role="executor",
    )
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=controller.id,
        role="controller",
    )

    task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title=f"desk-task-{random_lower_string()[:8]}",
    )
    task_id = task["id"]

    due_soon_date = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    update_due_soon = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=superuser_token_headers,
        json={
            "due_date": due_soon_date,
            "workflow_status_id": status_in_progress_id,
        },
    )
    assert update_due_soon.status_code == 200, update_due_soon.text

    overdue_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    update_overdue = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=superuser_token_headers,
        json={"due_date": overdue_date},
    )
    assert update_overdue.status_code == 200, update_overdue.text

    close_response = client.post(
        f"{settings.API_V1_STR}/tasks/{task_id}/close",
        headers=superuser_token_headers,
        json={"comment": "close", "attachment_ids": []},
    )
    assert close_response.status_code == 200, close_response.text

    executor_headers = auth_headers(client, executor.email, executor.password)
    poll_response = client.get(
        f"{settings.API_V1_STR}/desktop-events/poll",
        headers=executor_headers,
        params={"limit": 100},
    )
    assert poll_response.status_code == 200, poll_response.text
    payload = poll_response.json()

    assert "data" in payload
    assert "next_cursor" in payload
    assert "has_more" in payload
    assert "server_time" in payload

    assert payload["data"]
    event_types = {event["event_type"] for event in payload["data"]}
    assert "assign" in event_types
    assert "due_soon" in event_types
    assert "overdue" in event_types
    assert "status_changed" in event_types
    assert "close_requested" in event_types
    assert "close_approved" in event_types

    for event in payload["data"]:
        assert "id" in event
        assert "title" in event
        assert "message" in event
        assert "created_at" in event
        assert event["task_id"] == task_id


def test_tracker_desktop_events_poll_cursor(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"desk2-dep-{random_lower_string()[:8]}",
        code=f"D2_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"desk2-proj-{random_lower_string()[:8]}",
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

    for idx in range(3):
        create_task_via_api(
            client,
            superuser_token_headers,
            project_id=project_id,
            status_id=status_new_id,
            assignee_id=executor.id,
            controller_id=None,
            title=f"desk2-task-{idx}-{random_lower_string()[:6]}",
        )

    executor_headers = auth_headers(client, executor.email, executor.password)
    first_page = client.get(
        f"{settings.API_V1_STR}/desktop-events/poll",
        headers=executor_headers,
        params={"limit": 2},
    )
    assert first_page.status_code == 200, first_page.text
    first_payload = first_page.json()
    assert len(first_payload["data"]) == 2
    assert first_payload["has_more"] is True
    assert first_payload["next_cursor"] is not None

    first_ids = [event["id"] for event in first_payload["data"]]
    second_page = client.get(
        f"{settings.API_V1_STR}/desktop-events/poll",
        headers=executor_headers,
        params={"limit": 2, "cursor": first_payload["next_cursor"]},
    )
    assert second_page.status_code == 200, second_page.text
    second_payload = second_page.json()
    assert second_payload["data"]
    second_ids = [event["id"] for event in second_payload["data"]]

    assert all(event_id > max(first_ids) for event_id in second_ids)


def test_submit_review_notifies_project_manager(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"desk3-dep-{random_lower_string()[:8]}",
        code=f"D3_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"desk3-proj-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )
    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    in_progress_status_id = next(
        (
            item["id"]
            for item in statuses
            if item["code"] in {"in_progress", "new"}
        ),
        statuses[0]["id"],
    )

    executor = create_user_via_api(client, superuser_token_headers, system_role="user")
    controller = create_user_via_api(client, superuser_token_headers, system_role="user")
    manager = create_user_via_api(client, superuser_token_headers, system_role="user")
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=executor.id,
        role="executor",
    )
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=controller.id,
        role="controller",
    )
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=manager.id,
        role="manager",
    )

    task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=in_progress_status_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title=f"desk3-task-{random_lower_string()[:8]}",
    )
    task_id = task["id"]

    executor_headers = auth_headers(client, executor.email, executor.password)
    comment_response = client.post(
        f"{settings.API_V1_STR}/task-comments/",
        headers=executor_headers,
        json={"task_id": task_id, "comment": "Готово к проверке"},
    )
    assert comment_response.status_code == 200, comment_response.text

    submit_review_response = client.post(
        f"{settings.API_V1_STR}/tasks/{task_id}/submit-review",
        headers=executor_headers,
    )
    assert submit_review_response.status_code == 200, submit_review_response.text

    manager_headers = auth_headers(client, manager.email, manager.password)
    poll_response = client.get(
        f"{settings.API_V1_STR}/desktop-events/poll",
        headers=manager_headers,
        params={"limit": 100},
    )
    assert poll_response.status_code == 200, poll_response.text
    payload = poll_response.json()
    manager_task_events = [event for event in payload["data"] if event["task_id"] == task_id]

    assert manager_task_events
    review_events = [
        event
        for event in manager_task_events
        if event["event_type"] == "status_changed"
        and "провер" in event["message"].lower()
    ]
    assert review_events
