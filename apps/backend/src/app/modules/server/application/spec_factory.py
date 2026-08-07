"""Render del ``RuntimeSpec`` desde la config deseada (Blueprint §3.2, §6.1, §16.3).

Responsabilidad del módulo Server: traducir la config deseada a una
``RuntimeSpec`` materializable. Los defaults vienen de ``SettingsPort``; el env
ya mapeado llega de la facade Configuration (``DesiredConfig``). La asignación
de puertos se hace desde un pool con detección de conflicto (hallazgo B7:
``ENABLE_LAN_VISIBILITY=false`` salvo configuración explícita).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from pathlib import Path

from app.kernel.ports.runtime import RuntimeSpec
from app.kernel.ports.settings import SettingsPort
from app.modules.server.application.ports import DesiredConfig
from app.modules.server.domain.errors import ServerPortExhaustedError


def _port_range(start: int, end: int) -> tuple[int, ...]:
    if start > end:
        raise ValueError(f"Rango de puertos inválido: {start} > {end}")
    return tuple(range(start, end + 1))


def _local_bedrock_binary_exists(data_dir: Path, version: str) -> bool:
    """Devuelve True si el volumen ya contiene un binario Bedrock local.

    En ese caso, el runtime usa ``VERSION=EXISTING`` para evitar una descarga
    innecesaria que puede fallar en entornos con problemas de TLS/SSL.

    La detección es robusta frente a diferencias de versión: si el directorio
    ya tiene un binario Bedrock válido, se reutiliza aunque el nombre no
    coincida exactamente con la versión solicitada por el endpoint.
    """
    if not data_dir.exists():
        return False

    bedrock_candidates = [
        f"bedrock_server-{version}",
        "bedrock_server",
        "bedrock_server.exe",
    ]
    if any((data_dir / candidate).exists() for candidate in bedrock_candidates):
        return True

    for path in data_dir.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith("bedrock_server") or path.name.startswith("bedrock-server"):
            return True
    return False


def _candidate_data_dirs(base_path: str | Path, server_id: str) -> list[Path]:
    """Devuelve rutas de datos probables para el servidor.

    Prioriza el storage configurado del panel, pero también detecta un árbol de
    datos del proyecto (por ejemplo ``data/`` en la raíz del repo) cuando ya
    existe allí el binario Bedrock, incluso si el proceso se inicia desde otra
    carpeta.
    """
    base = Path(base_path)
    candidates: list[Path] = [base / server_id, base]

    start_points = [Path(__file__).resolve(), Path.cwd(), base]
    for start in start_points:
        for path in [start, *start.parents]:
            if path.name == "data":
                candidates.append(path)
            else:
                candidates.append(path / "data")
                candidates.append(path / server_id)
                candidates.append(path / "data" / server_id)

    seen: dict[Path, None] = {}
    ordered: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen[resolved] = None
        ordered.append(resolved)
    return ordered


def _discover_server_data_dir(base_path: str | Path, server_id: str, version: str) -> Path:
    """Elige la ruta de datos con binario local si está disponible."""
    for candidate in _candidate_data_dirs(base_path, server_id):
        if candidate.exists() and _local_bedrock_binary_exists(candidate, version):
            return candidate
    return Path(base_path) / server_id


def build_port_allocator(settings: SettingsPort) -> PortAllocator:
    """Construye el allocator desde ``SettingsPort`` (pool real, no vacío por defecto)."""
    game_start = int(settings.get("server.port_pool.start", 19132))
    game_end = int(settings.get("server.port_pool.end", 19181))
    rcon_start = int(settings.get("server.rcon_port_pool.start", 25632))
    rcon_end = int(settings.get("server.rcon_port_pool.end", 25681))
    return PortAllocator(
        game_pool=_port_range(game_start, game_end),
        rcon_pool=_port_range(rcon_start, rcon_end),
    )


class PortAllocator:
    """Asigna puerto de juego + RCON desde pools separados, evitando ocupados."""

    def __init__(
        self,
        *,
        game_default: int = 19132,
        rcon_default: int = 25575,
        game_pool: Iterable[int] = (),
        rcon_pool: Iterable[int] = (),
    ) -> None:
        self._game_default = game_default
        self._rcon_default = rcon_default
        self._game_pool = tuple(game_pool)
        self._rcon_pool = tuple(rcon_pool)

    def allocate(self, occupied: Collection[int] = ()) -> tuple[int, int]:
        """Devuelve ``(game_port, rcon_port)`` libres. Lanza si el pool se agota."""
        used = set(occupied)
        game = self._first_free_game(self._game_candidates(), used)
        if game is None:
            raise ServerPortExhaustedError("Pool de puertos de juego agotado")
        reserved = used | {game, game + 1}
        rcon = self._first_free(self._rcon_candidates(), reserved)
        if rcon is None:
            raise ServerPortExhaustedError("Pool de puertos RCON agotado")
        return game, rcon

    def _game_candidates(self) -> Sequence[int]:
        if self._game_pool:
            return self._game_pool
        return (self._game_default,)

    def _rcon_candidates(self) -> Sequence[int]:
        if self._rcon_pool:
            return (self._rcon_default, *self._rcon_pool)
        return (self._rcon_default,)

    @staticmethod
    def _first_free_game(candidates: Iterable[int], used: set[int]) -> int | None:
        for port in candidates:
            if port not in used and (port + 1) not in used:
                return port
        return None

    @staticmethod
    def _first_free(candidates: Iterable[int], used: set[int]) -> int | None:
        for port in candidates:
            if port not in used:
                return port
        return None


class RuntimeSpecFactory:
    """Compone una ``RuntimeSpec`` con defaults de Settings + env de Configuration."""

    def __init__(self, settings: SettingsPort, allocator: PortAllocator | None = None) -> None:
        self._settings = settings
        self._allocator = allocator if allocator is not None else build_port_allocator(settings)

    def render(
        self,
        server_id: str,
        name: str,
        desired: DesiredConfig,
        *,
        occupied_ports: Collection[int] = (),
    ) -> RuntimeSpec:
        image = self._settings.get(
            "server.image",
            "itzg/minecraft-bedrock-server"
            "@sha256:fd46bd30e7c729eacfeea81bca4a62e7c5957f387f1e377da4d03c66f9a76f3d",
        )
        tag = self._settings.get("server.tag", "")
        timezone = self._settings.get("server.timezone", "Etc/UTC")
        base_path = self._settings.get("storage.base_path", "/var/lib/bedrockpanel")
        server_data_dir = _discover_server_data_dir(base_path, server_id, desired.version)

        game_port, rcon_port = self._allocator.allocate(occupied_ports)

        environment = dict(desired.environment)
        # Obligatorio para itzg/minecraft-bedrock-server (abort sin EULA=TRUE).
        environment.setdefault("EULA", "TRUE")
        version_value = desired.version
        if _local_bedrock_binary_exists(server_data_dir, desired.version):
            version_value = "EXISTING"
        environment.setdefault("VERSION", version_value)
        environment.setdefault("TZ", timezone)
        environment.setdefault(
            "ONLINE_MODE",
            self._settings.get("server.online_mode", "false"),
        )
        environment.setdefault(
            "ENABLE_LAN_VISIBILITY",
            self._settings.get("server.enable_lan_visibility", "true"),
        )
        environment.setdefault(
            "ALLOW_LIST",
            self._settings.get("server.allow_list", "false"),
        )

        return RuntimeSpec(
            image=image,
            tag=tag,
            version=desired.version,
            environment=environment,
            # Bedrock = RakNet UDP; RCON/SSH de mc-server-runner = TCP.
            ports={
                "19132/udp": game_port,
                "19133/udp": game_port + 1,
                "25575/tcp": rcon_port,
            },
            volumes=[f"{server_data_dir}:/data"],
            resources={
                "memory_mb": int(self._settings.get("server.resources.memory_mb", 2048)),
                "cpus": float(self._settings.get("server.resources.cpus", 2.0)),
            },
            network=None,
            user=self._settings.get("server.user", "root"),
            labels={
                "bedrockpanel.server_id": server_id,
                "bedrockpanel.server_name": name,
            },
            stdin_open=True,
            tty=False,
        )
