"""Test del endpoint raíz del esqueleto (requisito de la tarea esqueleto)."""

from fastapi.testclient import TestClient

from app.main import app


def test_root_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "BedrockPanel"
    assert body["version"]
    assert body["status"] == "ok"


def test_docs_available() -> None:
    with TestClient(app) as client:
        response = client.get("/docs")

    assert response.status_code == 200
