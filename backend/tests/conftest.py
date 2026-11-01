import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as c:
        yield c
    app.state.engine.dispose()


def login(client, username="student"):
    response = client.post("/api/auth/login", json={"username": username, "password": "Demo12345!"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def student(client):
    return login(client)


@pytest.fixture
def teacher(client):
    return login(client, "teacher")
