from fastapi.testclient import TestClient

from app.core.config import settings
from app.tests.utils.tracker import create_user_via_api
from app.tests.utils.utils import random_lower_string


def test_tracker_organizations_and_groups_crud(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    org_name = f"org-{random_lower_string()[:8]}"
    create_org = client.post(
        f"{settings.API_V1_STR}/organizations/",
        headers=superuser_token_headers,
        json={
            "name": org_name,
            "code": f"ORG_{random_lower_string()[:5]}",
            "description": "test organization",
        },
    )
    assert create_org.status_code == 200, create_org.text
    organization = create_org.json()
    organization_id = organization["id"]

    list_orgs = client.get(
        f"{settings.API_V1_STR}/organizations/",
        headers=superuser_token_headers,
    )
    assert list_orgs.status_code == 200
    assert any(item["id"] == organization_id for item in list_orgs.json()["data"])

    create_group = client.post(
        f"{settings.API_V1_STR}/organizations/{organization_id}/groups",
        headers=superuser_token_headers,
        json={
            "name": f"group-{random_lower_string()[:8]}",
            "code": f"GR_{random_lower_string()[:5]}",
            "description": "test group",
        },
    )
    assert create_group.status_code == 200, create_group.text
    group = create_group.json()
    group_id = group["id"]

    list_groups = client.get(
        f"{settings.API_V1_STR}/organizations/{organization_id}/groups",
        headers=superuser_token_headers,
    )
    assert list_groups.status_code == 200
    assert any(item["id"] == group_id for item in list_groups.json()["data"])

    user = create_user_via_api(client, superuser_token_headers, system_role="executor")
    assign_member = client.post(
        f"{settings.API_V1_STR}/organizations/groups/{group_id}/members",
        headers=superuser_token_headers,
        json={"user_id": user.id},
    )
    assert assign_member.status_code == 200, assign_member.text

    list_members = client.get(
        f"{settings.API_V1_STR}/organizations/groups/{group_id}/members",
        headers=superuser_token_headers,
    )
    assert list_members.status_code == 200
    assert any(row["user_id"] == user.id for row in list_members.json()["data"])

    remove_member = client.delete(
        f"{settings.API_V1_STR}/organizations/groups/{group_id}/members/{user.id}",
        headers=superuser_token_headers,
    )
    assert remove_member.status_code == 200

    remove_group = client.delete(
        f"{settings.API_V1_STR}/organizations/{organization_id}/groups/{group_id}",
        headers=superuser_token_headers,
    )
    assert remove_group.status_code == 200

    delete_org = client.delete(
        f"{settings.API_V1_STR}/organizations/{organization_id}",
        headers=superuser_token_headers,
    )
    assert delete_org.status_code == 200
