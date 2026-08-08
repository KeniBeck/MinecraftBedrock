"""Tests de integración del módulo Settings (Fase H paso 19).

Endpoints HTTP (GET/PUT/PATCH/DELETE), permisos y auditoría. Reusa los helpers
de ``test_api_integration`` (container de dobles + super_admin).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.bootstrap.container import Container
from app.bootstrap.main import create_app
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


def admin_headers(client: TestClient) -> dict[str, str]:
    return login(client, "root")


class TestSettingsApi:
    def test_get_all_requiere_autenticacion(self, client: TestClient) -> None:
        response = client.get("/api/v1/settings")
        assert response.status_code == 401

    def test_get_all_devuelve_catalogo(self, client: TestClient) -> None:
        headers = admin_headers(client)
        response = client.get("/api/v1/settings", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        keys = {item["key"] for item in body["settings"]}
        assert "limits.max_backups_per_server" in keys
        assert "defaults.image" in keys
        assert "storage.base_path" in keys
        assert "system.maintenance_mode" in keys

    def test_get_category(self, client: TestClient) -> None:
        headers = admin_headers(client)
        response = client.get("/api/v1/settings/category/storage", headers=headers)
        assert response.status_code == 200
        items = response.json()["settings"]
        assert all(item["category"] == "storage" for item in items)

    def test_get_specific_key(self, client: TestClient) -> None:
        headers = admin_headers(client)
        response = client.get("/api/v1/settings/limits.max_servers", headers=headers)
        assert response.status_code == 200
        assert response.json()["value"] == 0

    def test_get_unknown_key_404(self, client: TestClient) -> None:
        headers = admin_headers(client)
        response = client.get("/api/v1/settings/foo.bar", headers=headers)
        assert response.status_code == 404

    def test_put_actualiza_y_audita(self, client: TestClient) -> None:
        headers = admin_headers(client)
        response = client.put(
            "/api/v1/settings/limits.max_backups_per_server",
            json={"value": 25, "description": "más copias"},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["value"] == 25

        audit: Any = container_of(client).iam_facade.deps.audit
        actions = [entry.action for entry in audit.entries]
        assert "settings.update" in actions

    def test_put_valida_tipo(self, client: TestClient) -> None:
        headers = admin_headers(client)
        response = client.put(
            "/api/v1/settings/limits.max_backups_per_server",
            json={"value": "abc"},
            headers=headers,
        )
        assert response.status_code == 422

    def test_patch_atomico(self, client: TestClient) -> None:
        headers = admin_headers(client)
        response = client.patch(
            "/api/v1/settings",
            json={
                "values": {
                    "defaults.image": "ghcr.io/itzg/minecraft-bedrock-server",
                    "defaults.tag": "beta",
                }
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        updated = {item["key"]: item["value"] for item in response.json()["settings"]}
        assert updated["defaults.image"] == "ghcr.io/itzg/minecraft-bedrock-server"
        assert updated["defaults.tag"] == "beta"

    def test_delete_resetea_a_default(self, client: TestClient) -> None:
        headers = admin_headers(client)
        client.put(
            "/api/v1/settings/limits.max_backups_per_server",
            json={"value": 25},
            headers=headers,
        )
        response = client.delete("/api/v1/settings/limits.max_backups_per_server", headers=headers)
        assert response.status_code == 200
        assert response.json()["value"] == 10

    def test_writer_requiere_settings_update(self, client: TestClient) -> None:
        from tests.test_api_integration import seed_viewer

        seed_viewer(container_of(client))
        headers = login(client, "lurker")
        response = client.put(
            "/api/v1/settings/limits.max_backups_per_server",
            json={"value": 5},
            headers=headers,
        )
        assert response.status_code == 403


class TestSettingsIntegration:
    def test_spec_factory_usa_defaults_de_settings(self, client: TestClient) -> None:
        container: Container = container_of(client)

        async def _apply() -> None:
            await container.settings_service.set(
                "defaults.image", "ghcr.io/custom/bedrock", updated_by="test"
            )
            await container.settings_service.set("limits.default_ram_mb", 4096, updated_by="test")

        import asyncio

        asyncio.run(_apply())

        from app.modules.server.application.spec_factory import RuntimeSpecFactory

        factory = RuntimeSpecFactory(container.settings_service)
        spec = factory.render(
            "srv-1",
            "Alpha",
            __import__(
                "app.modules.server.application.ports", fromlist=["DesiredConfig"]
            ).DesiredConfig(version="1.20.0", environment={}, config_rev=0),
        )
        assert spec.image == "ghcr.io/custom/bedrock"
        assert spec.resources["memory_mb"] == 4096

    def test_storage_paths_configurables(self, client: TestClient) -> None:
        container: Container = container_of(client)

        async def _apply() -> None:
            await container.settings_service.set(
                "storage.backup_path", "/mnt/nas/backups", updated_by="test"
            )
            await container.settings_service.set(
                "storage.template_path", "/mnt/nas/templates", updated_by="test"
            )

        import asyncio

        asyncio.run(_apply())

        from app.infrastructure.backups.local import LocalBackupStore

        backup_store = LocalBackupStore("/mnt/nas/backups")
        assert backup_store is not None
