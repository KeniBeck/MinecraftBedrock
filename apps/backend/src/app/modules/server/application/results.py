"""Vistas de salida de los use cases (proyecciones, Blueprint §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.kernel.ports.runtime import RuntimeSpec, ServerState
from app.kernel.ports.settings import SettingsPort


@dataclass(frozen=True, slots=True)
class ServerConnectionView:
    """Datos para conectar clientes Bedrock al servidor en el host del panel."""

    host: str
    port: int
    port_v6: int
    rcon_port: int | None = None

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


def _mapped_port(ports: dict[str, int], *keys: str, default: int | None = None) -> int | None:
    """Lee el puerto host desde claves con o sin protocolo (``19132`` / ``19132/udp``)."""
    for key in keys:
        if key in ports:
            return int(ports[key])
    return default


def connection_from_spec(spec: RuntimeSpec, settings: SettingsPort) -> ServerConnectionView:
    """Proyecta host público + puertos mapeados del ``RuntimeSpec``."""
    host = str(settings.get("server.public_host", "localhost"))
    game_port = _mapped_port(spec.ports, "19132/udp", "19132", default=19132) or 19132
    game_port_v6 = (
        _mapped_port(spec.ports, "19133/udp", "19133", default=game_port + 1) or game_port + 1
    )
    rcon_port = _mapped_port(spec.ports, "25575/tcp", "25575")
    return ServerConnectionView(
        host=host,
        port=game_port,
        port_v6=game_port_v6,
        rcon_port=rcon_port,
    )


def stub_connection(
    *,
    host: str = "localhost",
    port: int = 19132,
    port_v6: int = 19133,
    rcon_port: int | None = 25575,
) -> ServerConnectionView:
    """Conexión de prueba para dobles que no materializan ``RuntimeSpec``."""
    return ServerConnectionView(host=host, port=port, port_v6=port_v6, rcon_port=rcon_port)


@dataclass(frozen=True, slots=True)
class ServerView:
    """Proyección del servidor para consumidores (nunca la entidad cruda)."""

    id: str
    name: str
    state: ServerState
    version: str
    image_ref: str
    runtime_id: str | None
    created_at: datetime
    updated_at: datetime
    connection: ServerConnectionView
