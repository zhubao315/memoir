import os
import tempfile

TMP = tempfile.mkdtemp(prefix="memoir-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/test.db"
os.environ["LOCAL_STORAGE_DIR"] = f"{TMP}/uploads"
os.environ["ENVIRONMENT"] = "test"
os.environ["AI_PROVIDER"] = "mock"
os.environ["ASR_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def register_and_login(client, username="tester"):
    reg = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "secret123"},
    )
    assert reg.status_code == 200, reg.text
    login = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    assert login.status_code == 200, login.text
    data = login.json()
    return data, {"Authorization": f"Bearer {data['access_token']}"}
