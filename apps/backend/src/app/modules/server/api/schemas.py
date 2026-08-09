"""Schemas HTTP del módulo Server (vertical slice §16 ``modules/server/api``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateServerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    version: str | None = None
    template_id: str | None = None


class StopServerRequest(BaseModel):
    grace: int = Field(default=30, ge=0, le=600)


class RestartServerRequest(BaseModel):
    grace: int = Field(default=30, ge=0, le=600)


class RemoveServerRequest(BaseModel):
    delete_data: bool = False


class ApplyConfigRequest(BaseModel):
    config_rev: int = Field(ge=0)


class ChangeVersionRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64)


class UpdateResourcesRequest(BaseModel):
    """Actualiza CPU/RAM de un servidor (ambos opcionales; mínimo 1 CPU/512 MB)."""

    cpu_cores: float | None = Field(default=None, ge=1, le=64)
    ram_mb: int | None = Field(default=None, ge=512, le=65536)


class ServerResourcesResponse(BaseModel):
    """Recursos efectivos del servidor tras la actualización."""

    cpu_cores: float
    ram_mb: int


class ServerDetailResourcesResponse(BaseModel):
    """Recursos configurados del servidor, expuestos solo en el detalle."""

    cpu_cores: float
    ram_mb: int
    disk_gb: int


class ServerConnectionResponse(BaseModel):
    host: str = Field(description="Host o dominio público donde escucha el servidor")
    port: int = Field(description="Puerto UDP IPv4 del juego en el host")
    port_v6: int = Field(description="Puerto UDP IPv6 del juego en el host")
    rcon_port: int | None = Field(
        default=None,
        description="Puerto RCON/SSH de consola remota (si está habilitado)",
    )
    address: str = Field(description="Dirección Bedrock IPv4 (host:puerto)")


class ServerResponse(BaseModel):
    id: str
    name: str
    state: str
    version: str
    image_ref: str
    runtime_id: str | None = None
    created_at: datetime
    updated_at: datetime
    connection: ServerConnectionResponse


class ServerDetailResponse(ServerResponse):
    """Respuesta de detalle (``GET /servers/{id}``) que añade ``resources``.

    A diferencia de ``ServerResponse`` (usado por el listado ``GET /servers``),
    incluye un objeto ``resources`` con CPU/RAM (leídos del ``RuntimeSpec`` ya
    persistido) y el disco por defecto del panel (ajuste ``limits.default_disk_gb``).
    """

    resources: ServerDetailResourcesResponse
