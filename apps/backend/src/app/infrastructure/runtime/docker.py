"""Adaptador Docker de ``ServerRuntimePort`` (Blueprint §4.1, FASE A).

Gestiona **un contenedor por servidor** mediante Docker SDK for Python
(docker-py). No se usa ``subprocess`` ni comandos docker por shell.

- En FASE A el adaptador manipulaba un único contenedor
  (``DockerRuntimeSettings.container_name``). Se generalizó (fin de FASE A
  single-container): cada ``server_id`` tiene su propio contenedor cuyo nombre
  es ``{container_prefix}-{server_id}`` (prefijo de
  ``DockerRuntimeSettings.container_prefix``). Ese nombre **es** el
  ``runtime_id`` que se devuelve de ``materialize`` y que el módulo Server
  persiste y pasa a cada método.
- Cada método resuelve el contenedor por ``runtime_id`` vía
  ``client.containers.get(runtime_id)``; ya no hay "el" contenedor gestionado.
  ``NotFound`` se traduce a ``ContainerNotFoundError``.
- ``materialize`` extrae el ``server_id`` del label
  ``bedrockpanel.server_id`` (que siembre deja ``RuntimeSpecFactory.render``).
- El volumen ``{storage.base_path}/{server_id}:/data`` y los puertos ya vienen
  correctamente por servidor en el ``RuntimeSpec`` (no roto en el runtime).
- **No crea clientes Docker**: la construcción queda encapsulada en
  ``DockerClientFactory`` (inyectado por DI); el adaptador solo lo consulta.
- Toda excepción del SDK o del transporte se traduce a errores del kernel
  (§11.1): nunca se propagan ``docker.errors.*``, ``OSError`` ni
  ``requests.exceptions.*`` fuera de Infrastructure.
- Logging estructurado vía ``kernel.logging.get_logger`` (inicio/fin/tiempo/
  errores), sin ``print()``.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable, Iterator
from typing import Any, ParamSpec, TypeVar, cast

from docker.errors import APIError, DockerException, ImageNotFound, NotFound, requests

from app.infrastructure.runtime.client_factory import DockerClientFactory
from app.infrastructure.runtime.settings import DockerRuntimeSettings
from app.infrastructure.runtime.status import RuntimeInspect, RuntimeStatus
from app.kernel.errors import (
    ContainerNotFoundError,
    DockerError,
    DockerTimeoutError,
    ImageNotFoundError,
    PortInUseError,
)
from app.kernel.logging import get_logger
from app.kernel.ports.runtime import RuntimeSpec, RuntimeState

logger = get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

_IMAGE_LOOKUP_OPERATIONS = frozenset({"materialize"})

_DOCKER_STATE_TO_RUNTIME: dict[str, RuntimeState] = {
    "created": RuntimeState.CREATED,
    "running": RuntimeState.RUNNING,
    "restarting": RuntimeState.STARTING,
    "exited": RuntimeState.STOPPED,
    "dead": RuntimeState.DYING,
    "paused": RuntimeState.STOPPED,
}


def _elapsed_ms(started: float) -> float:
    """Milisegundos transcurridos desde ``started`` (perf_counter)."""
    return round((time.perf_counter() - started) * 1000, 2)


def _nano_cpus(cpus: float | None) -> int | None:
    """Convierte fracción de CPUs a nanoCPUs (parámetro del SDK Docker)."""
    return int(cpus * 1_000_000_000) if cpus is not None else None


def _mem_limit(resources: dict[str, Any]) -> str | int | None:
    """Límite de RAM en bytes para Docker (``mem_limit``).

    El ``RuntimeSpec`` guarda la RAM en ``resources["memory_mb"]`` (int MB, el
    formato del factory y del endpoint de recursos). Se convierte a bytes
    (``MB * 1024 * 1024``). Se mantiene la clave legacy ``resources["memory"]``
    (ya en bytes/string) como fallback para no romper consumidores previos.
    """
    memory_mb = resources.get("memory_mb")
    if memory_mb is not None:
        return int(memory_mb) * 1024 * 1024
    return resources.get("memory")


def _cpus_from_nano(nano: int | None) -> float | None:
    """Convierte nanoCPUs del HostConfig a fracción de CPUs."""
    return nano / 1_000_000_000 if nano else None


def _parse_env(env: list[str]) -> dict[str, str]:
    """Convierte la lista ``KEY=value`` de Docker en un dict."""
    result: dict[str, str] = {}
    for item in env:
        key, sep, value = item.partition("=")
        if sep:
            result[key] = value
    return result


def _published_ports(ports: dict[str, Any]) -> dict[str, int]:
    """Extrae puertos publicados ``{"19132/udp": 19132}`` desde inspect."""
    result: dict[str, int] = {}
    for container_port, bindings in ports.items():
        if not bindings:
            continue
        host_port = bindings[0].get("HostPort") if isinstance(bindings, list) else None
        if host_port:
            result[container_port] = int(host_port)
    return result


def _map_docker_state(state: str) -> RuntimeState:
    """Traduce el estado crudo de Docker al ``RuntimeState`` normalizado."""
    return _DOCKER_STATE_TO_RUNTIME.get(state, RuntimeState.STOPPED)


def _translate_docker_exc(exc: Exception, *, operation: str) -> DockerError:
    """Traduce una excepción del SDK Docker a un error del kernel (§11.1)."""
    if isinstance(exc, ImageNotFound):
        return ImageNotFoundError(
            "La imagen del contenedor no está disponible",
            context={"operation": operation},
        )
    if isinstance(exc, NotFound):
        if operation in _IMAGE_LOOKUP_OPERATIONS:
            return ImageNotFoundError(
                "La imagen del contenedor no está disponible",
                context={"operation": operation},
            )
        return ContainerNotFoundError(
            "El contenedor no existe",
            context={"operation": operation},
        )
    if isinstance(exc, APIError):
        status_code = exc.status_code
        if status_code == 403:
            return DockerError(
                "Permisos insuficientes para operar con el daemon de Docker",
                context={
                    "operation": operation,
                    "status_code": status_code,
                    "explanation": str(exc),
                },
            )
        if status_code == 409:
            return PortInUseError(
                "Puerto o nombre de contenedor en uso",
                context={"operation": operation, "status_code": status_code},
            )
        return DockerError(
            f"El daemon de Docker rechazó la operación '{operation}'",
            context={"operation": operation, "status_code": status_code, "explanation": str(exc)},
        )
    if isinstance(exc, DockerException):
        return DockerError(
            f"Fallo del SDK de Docker en '{operation}'",
            context={"operation": operation},
        )
    if isinstance(exc, requests.exceptions.Timeout):
        return DockerTimeoutError(
            f"Tiempo de espera agotado en '{operation}'",
            context={"operation": operation},
            retryable=True,
        )
    if isinstance(exc, requests.exceptions.ConnectionError):
        return DockerError(
            f"No se pudo conectar con el daemon de Docker en '{operation}'",
            context={"operation": operation},
            retryable=True,
        )
    if isinstance(exc, PermissionError):
        return DockerError(
            f"Permisos insuficientes para operar con Docker en '{operation}'",
            context={"operation": operation},
        )
    if isinstance(exc, OSError):
        return DockerError(
            f"Error de transporte con el daemon de Docker en '{operation}'",
            context={"operation": operation},
            retryable=True,
        )
    return DockerError(
        f"Error de runtime en '{operation}'",
        context={"operation": operation},
    )


def _log_failure(exc: DockerError, *, operation: str) -> None:
    """Registra el fallo normalizado con contexto estructurado."""
    extra = {
        "operation": operation,
        "code": exc.code,
        "error_message": exc.message,
    }
    if isinstance(exc, ContainerNotFoundError):
        logger.warning("runtime.not_found", extra=extra)
    else:
        logger.error("runtime.operation_failed", extra=extra)


def _map_docker_errors(func: Callable[P, R]) -> Callable[P, R]:  # noqa: UP047 — PEP 695 incompat con ParamSpec anidado en mypy
    """Decorador: traduce excepciones del SDK Docker a errores del kernel."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except ContainerNotFoundError as exc:
            _log_failure(exc, operation=func.__name__)
            raise
        except DockerError as exc:
            _log_failure(exc, operation=func.__name__)
            raise
        except DockerException as exc:
            mapped = _translate_docker_exc(exc, operation=func.__name__)
            _log_failure(mapped, operation=func.__name__)
            raise mapped from exc
        except requests.exceptions.Timeout as exc:
            mapped = _translate_docker_exc(exc, operation=func.__name__)
            _log_failure(mapped, operation=func.__name__)
            raise mapped from exc
        except requests.exceptions.ConnectionError as exc:
            mapped = _translate_docker_exc(exc, operation=func.__name__)
            _log_failure(mapped, operation=func.__name__)
            raise mapped from exc
        except PermissionError as exc:
            mapped = _translate_docker_exc(exc, operation=func.__name__)
            _log_failure(mapped, operation=func.__name__)
            raise mapped from exc
        except OSError as exc:
            mapped = _translate_docker_exc(exc, operation=func.__name__)
            _log_failure(mapped, operation=func.__name__)
            raise mapped from exc

    return wrapper


class DockerRuntimeAdapter:
    """Adaptador runtime Docker con un contenedor por servidor.

    No hereda ``ServerRuntimePort`` (los Protocol son estructurales). El nombre
    real del contenedor es ``{container_prefix}-{server_id}`` y **coincide** con
    el ``runtime_id`` que devuelve ``materialize`` y que el módulo Server
    persiste. Cada método resuelve su contenedor a partir de ese ``runtime_id``.
    """

    def __init__(
        self,
        settings: DockerRuntimeSettings,
        *,
        docker_client_factory: DockerClientFactory,
    ) -> None:
        self._settings = settings
        self._docker_client_factory = docker_client_factory
        self._docker_client: Any | None = None

    def _client(self) -> Any:
        if self._docker_client is None:
            self._docker_client = self._docker_client_factory.create()
        return self._docker_client

    @staticmethod
    def _container_name(server_id: str, settings: DockerRuntimeSettings) -> str:
        """Nombre real del contenedor de un servidor."""
        return f"{settings.container_prefix}-{server_id}"

    def _get_container(self, runtime_id: str) -> Any:
        """Resuelve el contenedor por ``runtime_id`` (NotFound → kernel)."""
        try:
            return self._client().containers.get(runtime_id)
        except NotFound as exc:
            raise ContainerNotFoundError(
                f"El contenedor '{runtime_id}' no existe",
                context={"runtime_id": runtime_id},
            ) from exc

    @staticmethod
    def _require_runtime_id(runtime_id: str | None) -> str:
        if runtime_id is None:
            raise DockerError(
                "runtime_id requerido: el adaptador es multi-servidor y no hay "
                "'un' contenedor gestionado",
                context={"operation": "resolve"},
            )
        return runtime_id

    def exists(self, runtime_id: str | None = None) -> bool:
        """Comprueba si el contenedor del ``runtime_id`` existe."""
        runtime_id = self._require_runtime_id(runtime_id)
        try:
            self._client().containers.get(runtime_id)
        except NotFound:
            return False
        except DockerException as exc:
            mapped = _translate_docker_exc(exc, operation="exists")
            _log_failure(mapped, operation="exists")
            raise mapped from exc
        except requests.exceptions.Timeout as exc:
            mapped = _translate_docker_exc(exc, operation="exists")
            _log_failure(mapped, operation="exists")
            raise mapped from exc
        except requests.exceptions.ConnectionError as exc:
            mapped = _translate_docker_exc(exc, operation="exists")
            _log_failure(mapped, operation="exists")
            raise mapped from exc
        except PermissionError as exc:
            mapped = _translate_docker_exc(exc, operation="exists")
            _log_failure(mapped, operation="exists")
            raise mapped from exc
        except OSError as exc:
            mapped = _translate_docker_exc(exc, operation="exists")
            _log_failure(mapped, operation="exists")
            raise mapped from exc
        return True

    def is_running(self, runtime_id: str | None = None) -> bool:
        """Devuelve ``True`` solo si el contenedor existe y está ejecutándose."""
        runtime_id = self._require_runtime_id(runtime_id)
        if not self.exists(runtime_id):
            return False
        return self.status(runtime_id).running

    @_map_docker_errors
    def start(self, runtime_id: str | None = None) -> None:
        """Arranca el contenedor; no espera a que el juego responda."""
        runtime_id = self._require_runtime_id(runtime_id)
        started = time.perf_counter()
        logger.info("runtime.start", extra={"container": runtime_id, "phase": "begin"})
        container = self._get_container(runtime_id)
        container.start()
        logger.info(
            "runtime.start",
            extra={"container": runtime_id, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def stop(self, runtime_id: str | None = None, grace: int = 30) -> None:
        """Parada ordenada con espera de ``grace`` segundos; si no, fuerza."""
        runtime_id = self._require_runtime_id(runtime_id)
        started = time.perf_counter()
        logger.info(
            "runtime.stop",
            extra={"container": runtime_id, "phase": "begin", "grace": grace},
        )
        container = self._get_container(runtime_id)
        container.stop(timeout=grace)
        logger.info(
            "runtime.stop",
            extra={"container": runtime_id, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def restart(self, runtime_id: str | None = None, grace: int = 30) -> None:
        """Parada ordenada + arranque del contenedor."""
        runtime_id = self._require_runtime_id(runtime_id)
        started = time.perf_counter()
        logger.info(
            "runtime.restart",
            extra={"container": runtime_id, "phase": "begin", "grace": grace},
        )
        container = self._get_container(runtime_id)
        container.restart(timeout=grace)
        logger.info(
            "runtime.restart",
            extra={"container": runtime_id, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def remove(self, runtime_id: str | None = None, delete_data: bool = False) -> None:
        """Elimina el contenedor del servidor (idempotente); ``delete_data`` no borra el bind mount.

        El volumen es un bind mount ``{base_path}/{server_id}:/data`` que el
        panel no gestiona como volumen Docker; ``delete_data`` se conserva por
        compatibilidad con el protocolo pero el directorio en disco lo limpia la
        capa de storage al eliminar el servidor, no este adaptador (limpieza
        por ``server_id`` fuera del ámbito del runtime).
        """
        runtime_id = self._require_runtime_id(runtime_id)
        if not self.exists(runtime_id):
            return
        started = time.perf_counter()
        logger.info(
            "runtime.remove",
            extra={"container": runtime_id, "phase": "begin", "delete_data": delete_data},
        )
        container = self._get_container(runtime_id)
        container.remove(force=True)
        logger.info(
            "runtime.remove",
            extra={"container": runtime_id, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def status(self, runtime_id: str | None = None) -> RuntimeStatus:
        """Estado normalizado del contenedor como DTO."""
        runtime_id = self._require_runtime_id(runtime_id)
        container = self._get_container(runtime_id)
        return _build_status(container.attrs, runtime_id)

    @_map_docker_errors
    def inspect(self, runtime_id: str | None = None) -> RuntimeInspect:
        """Inspección completa del contenedor normalizada a dominio."""
        runtime_id = self._require_runtime_id(runtime_id)
        container = self._get_container(runtime_id)
        raw = container.attrs
        return _build_inspect(raw, container.name)

    @_map_docker_errors
    def logs(self, runtime_id: str | None = None, *, tail: int = 200) -> str:
        """Últimas ``tail`` líneas de stdout/stderr del contenedor."""
        runtime_id = self._require_runtime_id(runtime_id)
        container = self._get_container(runtime_id)
        raw = container.logs(tail=tail)
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return "".join(chunk.decode("utf-8", errors="replace") for chunk in raw)

    @_map_docker_errors
    def materialize(self, spec: RuntimeSpec) -> str:
        """Crea el contenedor del servidor desde un ``RuntimeSpec`` sin arrancarlo (§4.1).

        Resuelve el ``server_id`` del label ``bedrockpanel.server_id`` y deriva
        el nombre ``{container_prefix}-{server_id}``. Si ya existe un contenedor
        con ese nombre (de ESTE servidor), se elimina y se recrea con el ``spec``
        actual (evita reutilizar un artefacto viejo sin ``EULA``/puertos mal).
        Devuelve el nombre como ``runtime_id``.
        """
        server_id = (spec.labels or {}).get("bedrockpanel.server_id")
        if not server_id:
            raise DockerError(
                "El RuntimeSpec no identifica el server_id (falta label bedrockpanel.server_id)",
                context={"labels": spec.labels},
            )
        runtime_id = self._container_name(server_id, self._settings)
        image_ref = f"{spec.image}:{spec.tag}" if spec.tag else spec.image
        started = time.perf_counter()
        logger.info(
            "runtime.materialize",
            extra={"container": runtime_id, "phase": "begin", "image": image_ref},
        )
        if self.exists(runtime_id):
            logger.info(
                "runtime.materialize",
                extra={"container": runtime_id, "phase": "replace"},
            )
            self.remove(runtime_id, delete_data=False)
        client = self._client()
        client.containers.create(
            image_ref,
            name=runtime_id,
            environment=spec.environment or None,
            ports=spec.ports or None,
            volumes=spec.volumes or None,
            network=spec.network,
            mem_limit=_mem_limit(spec.resources),
            nano_cpus=_nano_cpus(spec.resources.get("cpus")),
            user=spec.user,
            labels=spec.labels or None,
            detach=True,
            stdin_open=spec.stdin_open,
            tty=spec.tty,
        )
        logger.info(
            "runtime.materialize",
            extra={"container": runtime_id, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )
        return runtime_id

    @_map_docker_errors
    def get_state(self, runtime_id: str | None = None) -> RuntimeState:
        """Estado normalizado del runtime (§4.1)."""
        return self.status(runtime_id).status

    @_map_docker_errors
    def get_health(self, runtime_id: str | None = None) -> dict[str, Any]:
        """Salud del runtime y último estado reportado (§4.1)."""
        st = self.status(runtime_id)
        return {
            "container_id": st.container_id,
            "health": st.health,
            "healthy": st.healthy,
            "running": st.running,
        }

    @_map_docker_errors
    def get_resources(self, runtime_id: str | None = None) -> dict[str, Any]:
        """CPU/RAM actuales del proceso (§4.1)."""
        container = self._get_container(self._require_runtime_id(runtime_id))
        stats = container.stats(stream=False) or {}
        memory = stats.get("memory_stats") or {}
        cpu = stats.get("cpu_stats") or {}
        return {
            "memory_usage_bytes": memory.get("usage"),
            "memory_limit_bytes": memory.get("limit"),
            "cpu_total_usage": (cpu.get("cpu_usage") or {}).get("total_usage"),
            "system_cpu_usage": cpu.get("system_cpu_usage"),
            "cpu_percent": None,
        }

    @_map_docker_errors
    def get_exit_code(self, runtime_id: str | None = None) -> int | None:
        """Código de salida del último proceso (§4.1)."""
        container = self._get_container(self._require_runtime_id(runtime_id))
        exit_code = (container.attrs.get("State") or {}).get("ExitCode")
        return int(exit_code) if isinstance(exit_code, int) else None

    @_map_docker_errors
    def stream_logs(self, runtime_id: str | None = None) -> Iterator[bytes]:
        """Stream en vivo de líneas stdout/stderr (cola + streaming) (§4.1).

        ``container.logs(stream=True, follow=True, tail=0)``: el iterador es
        bloqueante sobre el socket del daemon y termina cuando el contenedor se
        detiene/elimina (el daemon cierra el stream). ``tail=0`` hace que el
        stream arranque **solo con líneas nuevas** (desde el attach), sin
        rejugar el historial del contenedor: tras un stop/start la cola de BDS
        conserva líneas viejas de ``Player connected`` de sesiones previas, que
        re-jugadas dispararían ``PLAYER.JOINED`` fantasma y el enforcement de
        bans contra un jugador que no está realmente conectado en el contenedor
        recién arrancado (bug real, change-log §14).
        """
        container = self._get_container(self._require_runtime_id(runtime_id))
        return cast(Iterator[bytes], container.logs(stream=True, follow=True, tail=0))

    @_map_docker_errors
    def send_stdin(self, runtime_id: str, data: str) -> None:
        """Escribe en el stdin del proceso (§4.1)."""
        container = self._get_container(self._require_runtime_id(runtime_id))
        socket = container.attach_socket(params={"stdin": 1, "stdout": 0, "stderr": 0, "stream": 1})
        try:
            raw = socket._sock if hasattr(socket, "_sock") else socket
            raw.sendall(data.encode("utf-8"))
        finally:
            socket.close()

    @_map_docker_errors
    def wait_for(
        self,
        runtime_id: str | None = None,
        condition: str = "running",
        timeout: int = 60,
    ) -> None:
        """Espera una condición del runtime con timeout (§4.1)."""
        runtime_id = self._require_runtime_id(runtime_id)
        supported = {"running", "stopped"}
        if condition not in supported:
            raise DockerError(
                f"Condición no soportada por el adaptador: '{condition}'",
                context={"condition": condition},
            )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition == "running" and self.is_running(runtime_id):
                return
            if condition == "stopped" and (
                not self.exists(runtime_id) or not self.is_running(runtime_id)
            ):
                return
            time.sleep(0.5)
        raise DockerTimeoutError(
            f"Tiempo de espera agotado esperando condición '{condition}'",
            context={"condition": condition, "timeout": timeout},
        )

    @_map_docker_errors
    def signal(self, runtime_id: str, sig: int) -> None:
        """Señal explícita (SIGTERM/SIGKILL) al contenedor (§4.1)."""
        container = self._get_container(self._require_runtime_id(runtime_id))
        container.kill(signal=sig)


def _build_status(raw: dict[str, Any], name: str) -> RuntimeStatus:
    """Construye ``RuntimeStatus`` desde los attrs crudos del contenedor."""
    state = raw.get("State") or {}
    config = raw.get("Config") or {}
    networks = raw.get("NetworkSettings") or {}
    health_info = state.get("Health")
    health = health_info.get("Status") if isinstance(health_info, dict) else None
    healthy = health == "healthy" if health is not None else None
    return RuntimeStatus(
        running=bool(state.get("Running")),
        healthy=healthy,
        container_id=raw.get("Id") or "",
        container_name=name,
        image=config.get("Image") or "",
        image_id=raw.get("Image"),
        created_at=raw.get("Created") or "",
        started_at=state.get("StartedAt") or None,
        status=_map_docker_state(state.get("Status") or "unknown"),
        health=health,
        ports=_published_ports(networks.get("Ports") or {}),
        restart_count=int(raw.get("RestartCount") or 0),
        oom_killed=bool(state.get("OOMKilled")),
    )


def _build_inspect(raw: dict[str, Any], name: str) -> RuntimeInspect:
    """Construye ``RuntimeInspect`` desde los attrs crudos del contenedor."""
    state = raw.get("State") or {}
    config = raw.get("Config") or {}
    host = raw.get("HostConfig") or {}
    return RuntimeInspect(
        status=_build_status(raw, name),
        environment=_parse_env(config.get("Env") or []),
        command=list(config.get("Cmd") or []),
        memory_limit_bytes=host.get("Memory"),
        cpu_limit_cores=_cpus_from_nano(host.get("NanoCpus")),
        restart_policy=(host.get("RestartPolicy") or {}).get("Name"),
        exit_code=state.get("ExitCode"),
    )
