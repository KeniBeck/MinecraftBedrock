"""Tests de integración HTTP de 2FA, API keys y auditoría (Fase H paso 18).

Reusa los helpers y el container de dobles de ``test_api_integration``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.bootstrap.main import create_app
from app.modules.iam.infrastructure.memory import InMemoryIamRepository
from tests.test_api_integration import (
    container_of,
    login,
    make_container,
    seed_admin,
)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """App FastAPI con el container de dobles + super_admin sembrado."""
    container = make_container(storage_root=tmp_path / "storage")
    seed_admin(container)
    app = create_app(container=container)
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client: TestClient) -> dict[str, str]:
    return login(client, "root")


def iam_store(client: TestClient) -> InMemoryIamRepository:
    facade: Any = container_of(client).iam_facade
    store = facade.deps.repository
    assert isinstance(store, InMemoryIamRepository)
    return store


class TestTwoFactorFlow:
    def test_enable_genera_secreto_y_uri(self, client: TestClient) -> None:
        headers = auth_headers(client)
        response = client.post("/api/v1/auth/2fa/enable", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["secret"]) == 32
        assert body["provisioning_uri"].startswith("otpauth://totp/")
        assert len(body["backup_codes"]) == 10

    def test_confirm_activa_y_login_exige_2fa(self, client: TestClient) -> None:
        headers = auth_headers(client)
        enabled = client.post("/api/v1/auth/2fa/enable", headers=headers).json()
        code = pyotp.TOTP(enabled["secret"]).now()
        response = client.post("/api/v1/auth/2fa/verify", json={"code": code}, headers=headers)
        assert response.status_code == 204

        login_response = client.post(
            "/api/v1/auth/login", json={"username": "root", "password": "s3cret!pw"}
        )
        assert login_response.status_code == 200
        body = login_response.json()
        assert body["requires_2fa"] is True
        assert body["temp_token"]

    def test_verify_2fa_login_devuelve_tokens(self, client: TestClient) -> None:
        headers = auth_headers(client)
        enabled = client.post("/api/v1/auth/2fa/enable", headers=headers).json()
        code = pyotp.TOTP(enabled["secret"]).now()
        client.post("/api/v1/auth/2fa/verify", json={"code": code}, headers=headers)
        challenge = client.post(
            "/api/v1/auth/login", json={"username": "root", "password": "s3cret!pw"}
        ).json()
        response = client.post(
            "/api/v1/auth/verify-2fa",
            json={"temp_token": challenge["temp_token"], "code": code},
        )
        assert response.status_code == 200, response.text
        assert response.json()["access_token"]

    def test_verify_2fa_login_codigo_invalido_401(self, client: TestClient) -> None:
        headers = auth_headers(client)
        enabled = client.post("/api/v1/auth/2fa/enable", headers=headers).json()
        code = pyotp.TOTP(enabled["secret"]).now()
        client.post("/api/v1/auth/2fa/verify", json={"code": code}, headers=headers)
        challenge = client.post(
            "/api/v1/auth/login", json={"username": "root", "password": "s3cret!pw"}
        ).json()
        response = client.post(
            "/api/v1/auth/verify-2fa",
            json={"temp_token": challenge["temp_token"], "code": "000000"},
        )
        assert response.status_code == 401

    def test_2fa_endpoints_requieren_autenticacion(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/2fa/enable")
        assert response.status_code == 401


class TestApiKeyEndpoints:
    def test_crear_listar_rotar_revocar(self, client: TestClient) -> None:
        headers = auth_headers(client)
        created = client.post(
            "/api/v1/iam/api-keys",
            json={"name": "ci", "scopes": ["server.list"]},
            headers=headers,
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["material"].startswith("sk_live_")

        listed = client.get("/api/v1/iam/api-keys", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        rotated = client.post(f"/api/v1/iam/api-keys/{body['id']}/regenerate", headers=headers)
        assert rotated.status_code == 200
        assert rotated.json()["material"] != body["material"]

        revoked = client.delete(f"/api/v1/iam/api-keys/{body['id']}", headers=headers)
        assert revoked.status_code == 204
        assert client.get("/api/v1/iam/api-keys", headers=headers).json() == []

    def test_api_key_autentica_via_x_api_key(self, client: TestClient) -> None:
        headers = auth_headers(client)
        created = client.post(
            "/api/v1/iam/api-keys",
            json={"name": "ci", "scopes": ["server.view"]},
            headers=headers,
        ).json()
        response = client.get("/api/v1/servers", headers={"X-API-Key": created["material"]})
        assert response.status_code == 200, response.text

    def test_api_key_sin_scope_rechazada(self, client: TestClient) -> None:
        headers = auth_headers(client)
        created = client.post(
            "/api/v1/iam/api-keys",
            json={"name": "ci", "scopes": []},
            headers=headers,
        ).json()
        response = client.post(
            "/api/v1/servers",
            json={"name": "S"},
            headers={"X-API-Key": created["material"]},
        )
        assert response.status_code == 403

    def test_api_key_invalida_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/servers", headers={"X-API-Key": "sk_live_invalida"})
        assert response.status_code == 401


class TestAuditVerify:
    def test_cadena_limpia_devuelve_valid_true(self, client: TestClient) -> None:
        headers = auth_headers(client)
        response = client.get("/api/v1/iam/audit/verify", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["valid"] is True
        assert body["errors"] == []

    def test_verify_requiere_admin(self, client: TestClient) -> None:
        from tests.test_api_integration import seed_viewer

        seed_viewer(container_of(client))
        headers = login(client, "lurker")
        response = client.get("/api/v1/iam/audit/verify", headers=headers)
        assert response.status_code == 403
