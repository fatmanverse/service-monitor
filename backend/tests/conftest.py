import os

import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "true"
os.environ["SCHEDULER_ENABLED"] = "false"

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        app_secret="test-secret-for-service-monitor",
        initial_admin_username="admin",
        initial_admin_password="admin123",
        scheduler_enabled=False,
        testing=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_headers(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

