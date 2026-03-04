from fastapi.testclient import TestClient

from app.core.config import settings


def test_tracker_roles_and_permissions_endpoints(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    permissions_response = client.get(
        f"{settings.API_V1_STR}/permissions",
        headers=superuser_token_headers,
    )
    assert permissions_response.status_code == 200, permissions_response.text
    permissions_data = permissions_response.json()
    assert permissions_data["count"] >= 60

    roles_response = client.get(
        f"{settings.API_V1_STR}/roles",
        headers=superuser_token_headers,
    )
    assert roles_response.status_code == 200, roles_response.text
    roles = roles_response.json()["data"]
    assert any(role["key"] == "system_admin" for role in roles)

    system_admin_permissions = client.get(
        f"{settings.API_V1_STR}/roles/system_admin/permissions",
        headers=superuser_token_headers,
    )
    assert system_admin_permissions.status_code == 200
    assert system_admin_permissions.json()["count"] >= 60
