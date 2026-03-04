from fastapi.testclient import TestClient

from app.core.config import settings


def test_tracker_auth_access_token_success(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/auth/access-token",
        data={
            "username": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]


def test_tracker_auth_access_token_wrong_password(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/auth/access-token",
        data={"username": settings.FIRST_SUPERUSER, "password": "wrong-password"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"


def test_tracker_health_check(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert response.status_code == 200
    assert response.json() is True
