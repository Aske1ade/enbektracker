from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils.tracker import (
    add_project_member,
    create_department_via_api,
    create_project_via_api,
    create_task_via_api,
    create_user_via_api,
    get_project_statuses,
)
from app.tests.utils.utils import random_lower_string


def test_tracker_tasks_crud_history_and_close_policy(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"tasks-dep-{random_lower_string()[:8]}",
        code=f"TD_{random_lower_string()[:6]}",
    )

    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"tasks-proj-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=True,
        require_close_attachment=True,
    )

    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    status_by_code = {item["code"]: item["id"] for item in statuses}
    status_new_id = status_by_code["new"]
    status_review_id = status_by_code["in_progress"]

    executor = create_user_via_api(
        client,
        superuser_token_headers,
        system_role="executor",
    )
    controller = create_user_via_api(
        client,
        superuser_token_headers,
        system_role="controller",
    )

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
        title=f"task-{random_lower_string()[:8]}",
    )
    task_id = task["id"]
    assert "computed_deadline_state" in task
    assert "is_overdue" in task
    assert "workflow_status_name" in task

    read_response = client.get(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=superuser_token_headers,
    )
    assert read_response.status_code == 200
    assert read_response.json()["workflow_status_name"]

    second_executor = create_user_via_api(
        client,
        superuser_token_headers,
        system_role="executor",
    )
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_id,
        user_id=second_executor.id,
        role="executor",
    )

    patch_response = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=superuser_token_headers,
        json={
            "due_date": "2030-01-06T10:00:00Z",
            "workflow_status_id": status_review_id,
            "assignee_id": second_executor.id,
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["assignee_id"] == second_executor.id
    assert patched["workflow_status_id"] == status_review_id
    assert patched["workflow_status_name"]

    comment_response = client.post(
        f"{settings.API_V1_STR}/task-comments/",
        headers=superuser_token_headers,
        json={"task_id": task_id, "comment": "integration comment"},
    )
    assert comment_response.status_code == 200

    upload_response = client.post(
        f"{settings.API_V1_STR}/task-attachments/upload",
        headers=superuser_token_headers,
        params={"task_id": task_id},
        files={"file": ("evidence.txt", b"integration-attachment", "text/plain")},
    )
    assert upload_response.status_code == 200, upload_response.text
    attachment_id = upload_response.json()["id"]

    download_response = client.get(
        f"{settings.API_V1_STR}/task-attachments/{attachment_id}/download",
        headers=superuser_token_headers,
    )
    assert download_response.status_code == 200, download_response.text
    assert download_response.headers["content-type"].startswith("text/plain")
    assert "attachment; " in download_response.headers["content-disposition"]
    assert download_response.content == b"integration-attachment"

    close_without_attachment = client.post(
        f"{settings.API_V1_STR}/tasks/{task_id}/close",
        headers=superuser_token_headers,
        json={"comment": "close attempt", "attachment_ids": []},
    )
    assert close_without_attachment.status_code == 400
    assert "Attachment is required" in close_without_attachment.json()["detail"]

    close_ok = client.post(
        f"{settings.API_V1_STR}/tasks/{task_id}/close",
        headers=superuser_token_headers,
        json={"comment": "close ok", "attachment_ids": [attachment_id]},
    )
    assert close_ok.status_code == 200, close_ok.text
    closed = close_ok.json()
    assert closed["closed_at"] is not None

    history_response = client.get(
        f"{settings.API_V1_STR}/tasks/{task_id}/history",
        headers=superuser_token_headers,
    )
    assert history_response.status_code == 200
    actions = {item["action"] for item in history_response.json()["data"]}
    assert "created" in actions
    assert "updated" in actions
    assert "due_date_changed" in actions
    assert "status_changed" in actions
    assert "assignee_changed" in actions
    assert "comment_added" in actions
    assert "attachment_added" in actions
    assert "closed" in actions

    delete_response = client.delete(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 200


def test_tracker_task_attachment_validation_limits(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"attach-dep-{random_lower_string()[:8]}",
        code=f"AD_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"attach-proj-{random_lower_string()[:8]}",
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
    task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=None,
        title=f"attach-task-{random_lower_string()[:8]}",
    )
    task_id = task["id"]

    # Enforce tiny max size to deterministically hit 413 in test.
    monkeypatch.setattr(settings, "ATTACHMENTS_MAX_SIZE_MB", 0)
    too_big = client.post(
        f"{settings.API_V1_STR}/task-attachments/upload",
        headers=superuser_token_headers,
        params={"task_id": task_id},
        files={"file": ("big.txt", b"x", "text/plain")},
    )
    assert too_big.status_code == 413
    assert too_big.json()["detail"].startswith("Attachment is too large")

    # Restore size and reject by MIME type with 422.
    monkeypatch.setattr(settings, "ATTACHMENTS_MAX_SIZE_MB", 10)
    monkeypatch.setattr(settings, "ATTACHMENTS_ALLOWED_CONTENT_TYPES", ["image/png"])
    bad_type = client.post(
        f"{settings.API_V1_STR}/task-attachments/upload",
        headers=superuser_token_headers,
        params={"task_id": task_id},
        files={"file": ("note.txt", b"text", "text/plain")},
    )
    assert bad_type.status_code == 422
    assert bad_type.json()["detail"] == "Attachment content type is not allowed"

    # Filename sanitation + content type normalization.
    monkeypatch.setattr(settings, "ATTACHMENTS_ALLOWED_CONTENT_TYPES", ["text/plain"])
    sanitized = client.post(
        f"{settings.API_V1_STR}/task-attachments/upload",
        headers=superuser_token_headers,
        params={"task_id": task_id},
        files={"file": ("../../evil name?.txt", b"text", "text/plain; charset=utf-8")},
    )
    assert sanitized.status_code == 200, sanitized.text
    payload = sanitized.json()
    assert payload["file_name"] == "evil_name_.txt"
    assert payload["content_type"] == "text/plain"

    invalid_name = client.post(
        f"{settings.API_V1_STR}/task-attachments/upload",
        headers=superuser_token_headers,
        params={"task_id": task_id},
        files={"file": ("...", b"text", "text/plain")},
    )
    assert invalid_name.status_code == 422
    assert invalid_name.json()["detail"] == "Attachment file name is invalid"


def test_tracker_tasks_list_row_ready_and_pagination(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"list-dep-{random_lower_string()[:8]}",
        code=f"LD_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"list-proj-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )
    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    status_new_id = next(item["id"] for item in statuses if item["code"] == "new")

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

    create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title=f"list-task-1-{random_lower_string()[:6]}",
    )
    create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title=f"list-task-2-{random_lower_string()[:6]}",
    )

    response = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=superuser_token_headers,
        params={
            "project_id": project_id,
            "page": 1,
            "page_size": 1,
            "sort_by": "created_at",
            "sort_order": "asc",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(["data", "count", "total", "page", "page_size"]).issubset(payload.keys())
    assert payload["count"] == 1
    assert payload["total"] >= 2
    assert payload["page"] == 1
    assert payload["page_size"] == 1

    row = payload["data"][0]
    assert row["project_name"]
    assert row["assignee_name"]
    assert row["controller_name"]
    assert row["status_name"]
    assert row["workflow_status_name"]
    assert row["updated_at"]
