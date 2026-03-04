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


def test_tracker_dashboard_summary_schema(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/dashboards/summary",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_tasks" in data
    assert "deadline_in_time_count" in data
    assert "deadline_overdue_count" in data
    assert "closed_in_time_count" in data
    assert "closed_overdue_count" in data
    assert "top_executors" in data
    assert "top_overdue_executors" in data


def test_tracker_calendar_summary_schema(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/calendar/summary",
        headers=superuser_token_headers,
        params={"date_from": "2030-01-01", "date_to": "2030-01-31"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    if payload["data"]:
        row = payload["data"][0]
        assert "day" in row
        assert "total_count" in row
        assert "overdue_count" in row
        assert "in_time_count" in row
        assert "closed_count" in row
        assert "day_state" in row
        assert "max_deadline_state" in row


def test_tracker_dashboard_status_distribution_merges_same_state_names(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"dist-dep-{random_lower_string()[:8]}",
        code=f"DS_{random_lower_string()[:6]}",
    )
    project_a_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"dist-proj-a-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )
    project_b_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"dist-proj-b-{random_lower_string()[:8]}",
        department_id=department_id,
        require_close_comment=False,
        require_close_attachment=False,
    )
    statuses_a = get_project_statuses(client, superuser_token_headers, project_a_id)
    statuses_b = get_project_statuses(client, superuser_token_headers, project_b_id)
    status_a_in_progress = next(
        item["id"] for item in statuses_a if item["code"] == "in_progress"
    )
    status_b_in_progress = next(
        item["id"] for item in statuses_b if item["code"] == "in_progress"
    )

    executor = create_user_via_api(client, superuser_token_headers, system_role="executor")
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_a_id,
        user_id=executor.id,
        role="executor",
    )
    add_project_member(
        client,
        superuser_token_headers,
        project_id=project_b_id,
        user_id=executor.id,
        role="executor",
    )

    create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_a_id,
        status_id=status_a_in_progress,
        assignee_id=executor.id,
        controller_id=None,
        title=f"dist-task-a-{random_lower_string()[:8]}",
    )
    create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_b_id,
        status_id=status_b_in_progress,
        assignee_id=executor.id,
        controller_id=None,
        title=f"dist-task-b-{random_lower_string()[:8]}",
    )

    response = client.get(
        f"{settings.API_V1_STR}/dashboards/distributions",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    statuses = response.json()["statuses"]
    in_progress_rows = [row for row in statuses if row["status_name"] == "В работе"]
    assert len(in_progress_rows) == 1
    assert in_progress_rows[0]["count"] >= 2


def test_tracker_dashboard_trends_and_calendar_day_schema(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    department_id = create_department_via_api(
        client,
        superuser_token_headers,
        name=f"cal-dep-{random_lower_string()[:8]}",
        code=f"CL_{random_lower_string()[:6]}",
    )
    project_id = create_project_via_api(
        client,
        superuser_token_headers,
        name=f"cal-proj-{random_lower_string()[:8]}",
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
    created_task = create_task_via_api(
        client,
        superuser_token_headers,
        project_id=project_id,
        status_id=status_new_id,
        assignee_id=executor.id,
        controller_id=None,
        title=f"cal-task-{random_lower_string()[:8]}",
    )

    trends_response = client.get(
        f"{settings.API_V1_STR}/dashboards/trends",
        headers=superuser_token_headers,
        params={
            "period": "day",
            "date_from": "2030-01-01",
            "date_to": "2030-01-31",
        },
    )
    assert trends_response.status_code == 200, trends_response.text
    trends_payload = trends_response.json()
    assert trends_payload["period"] == "day"
    assert "data" in trends_payload
    if trends_payload["data"]:
        trend_row = trends_payload["data"][0]
        assert "bucket_start" in trend_row
        assert "total_tasks" in trend_row
        assert "in_time_tasks" in trend_row
        assert "overdue_tasks" in trend_row
        assert "closed_tasks" in trend_row
        assert "closed_in_time_tasks" in trend_row

    day_response = client.get(
        f"{settings.API_V1_STR}/calendar/day",
        headers=superuser_token_headers,
        params={"date": "2030-01-05", "project_id": project_id},
    )
    assert day_response.status_code == 200, day_response.text
    day_payload = day_response.json()
    assert day_payload["day"] == "2030-01-05"
    assert day_payload["count"] >= 1
    assert "data" in day_payload
    row = next((item for item in day_payload["data"] if item["id"] == created_task["id"]), None)
    assert row is not None
    assert row["project_name"]
    assert row["status_name"]
    assert "assignee_name" in row
    assert "controller_name" in row
