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


def test_tracker_rbac_matrix(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"rbac-dep-{random_lower_string()[:8]}",
        code=f"RB_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"rbac-proj-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )
    statuses = get_project_statuses(client, superuser_token_headers, project_id)
    status_new_id = next(item["id"] for item in statuses if item["code"] == "new")
    status_review_id = next(item["id"] for item in statuses if item["code"] == "in_progress")

    executor = create_user_via_api(client, superuser_token_headers, system_role="executor")
    controller = create_user_via_api(client, superuser_token_headers, system_role="controller")
    manager = create_user_via_api(client, superuser_token_headers, system_role="manager")
    admin = create_user_via_api(
        client,
        superuser_token_headers,
        system_role="admin",
        is_superuser=True,
    )

    outsider = create_user_via_api(client, superuser_token_headers, system_role="executor")

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

    executor_headers = auth_headers(client, executor.email, executor.password)
    controller_headers = auth_headers(client, controller.email, controller.password)
    manager_headers = auth_headers(client, manager.email, manager.password)
    admin_headers = auth_headers(client, admin.email, admin.password)
    outsider_headers = auth_headers(client, outsider.email, outsider.password)

    task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title="rbac-task",
    )
    task_id = task["id"]

    patch_payload = {
        "due_date": "2030-01-07T10:00:00Z",
        "workflow_status_id": status_review_id,
    }

    executor_patch = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=executor_headers,
        json=patch_payload,
    )
    assert executor_patch.status_code == 403

    controller_patch = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=controller_headers,
        json=patch_payload,
    )
    assert controller_patch.status_code == 200

    manager_patch = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=manager_headers,
        json={"due_date": "2030-01-08T10:00:00Z", "workflow_status_id": status_new_id},
    )
    assert manager_patch.status_code == 200

    admin_patch = client.patch(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=admin_headers,
        json={"due_date": "2030-01-09T10:00:00Z", "workflow_status_id": status_review_id},
    )
    assert admin_patch.status_code == 200

    # close permissions
    executor_task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title="rbac-close-executor-task",
    )
    executor_close = client.post(
        f"{settings.API_V1_STR}/tasks/{executor_task['id']}/close",
        headers=executor_headers,
        json={"comment": "executor close", "attachment_ids": []},
    )
    assert executor_close.status_code == 200

    controller_task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title="rbac-close-controller-task",
    )
    controller_close = client.post(
        f"{settings.API_V1_STR}/tasks/{controller_task['id']}/close",
        headers=controller_headers,
        json={"comment": "controller close", "attachment_ids": []},
    )
    assert controller_close.status_code == 200

    manager_task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title="rbac-close-manager-task",
    )
    manager_close = client.post(
        f"{settings.API_V1_STR}/tasks/{manager_task['id']}/close",
        headers=manager_headers,
        json={"comment": "manager close", "attachment_ids": []},
    )
    assert manager_close.status_code == 200

    admin_task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=controller.id,
        title="rbac-close-admin-task",
    )
    admin_close = client.post(
        f"{settings.API_V1_STR}/tasks/{admin_task['id']}/close",
        headers=admin_headers,
        json={"comment": "admin close", "attachment_ids": []},
    )
    assert admin_close.status_code == 200

    # visibility checks
    outsider_project_list = client.get(
        f"{settings.API_V1_STR}/projects/",
        headers=outsider_headers,
    )
    assert outsider_project_list.status_code == 200
    outsider_ids = {item["id"] for item in outsider_project_list.json()["data"]}
    assert project_id not in outsider_ids

    outsider_task = client.get(
        f"{settings.API_V1_STR}/tasks/{task_id}",
        headers=outsider_headers,
    )
    assert outsider_task.status_code == 403

    outsider_tasks = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=outsider_headers,
        params={"project_id": project_id, "page": 1, "page_size": 20},
    )
    assert outsider_tasks.status_code == 200
    outsider_payload = outsider_tasks.json()
    assert outsider_payload["total"] == 0
    assert outsider_payload["count"] == 0

    manager_projects = client.get(
        f"{settings.API_V1_STR}/projects/",
        headers=manager_headers,
    )
    assert manager_projects.status_code == 200
    manager_ids = {item["id"] for item in manager_projects.json()["data"]}
    assert project_id in manager_ids

    admin_projects = client.get(
        f"{settings.API_V1_STR}/projects/",
        headers=admin_headers,
    )
    assert admin_projects.status_code == 200
    admin_ids = {item["id"] for item in admin_projects.json()["data"]}
    assert project_id in admin_ids

    manager_tasks = client.get(
        f"{settings.API_V1_STR}/tasks/",
        headers=manager_headers,
        params={"project_id": project_id, "page": 1, "page_size": 20},
    )
    assert manager_tasks.status_code == 200
    assert manager_tasks.json()["total"] >= 1
