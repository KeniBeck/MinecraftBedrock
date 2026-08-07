"""Adaptador Docker de ``ServerRuntimePort`` (Blueprint §4.1, FASE A).

Gestiona un **único** contenedor Minecraft Bedrock mediante Docker SDK for
Python (docker-py). No se usa ``subprocess`` ni comandos docker por shell.

- El nombre del contenedor sale de ``DockerRuntimeSettings.container_name``;
  no hay valores hardcodeados.
- Implementa los métodos de ``ServerRuntimePort`` (§4.1) de forma estructural
  (no hereda el Protocol; ver change-log). Los ``runtime_id`` son opcionales y,
  si se omiten o coinciden con el contenedor gestionado, se opera sobre él.
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

_IMAGE_LOOKUP_OPERATIONS = frozenset({"create_if_missing", "materialize"})

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


def _cpus_from_nano(nano: int | None) -> float | None:
    """Convierte nanoCPUs del HostConfig a fracción de CPUs."""
    return nano / 1_000_000_000 if nano else None


def _restart_policy(policy: str) -> dict[str, Any]:
    """Normaliza ``restart_policy`` (p. ej. ``on-failure:3``) al formato Docker."""
    if ":" in policy:
        name, count = policy.split(":", 1)
        return {"Name": name, "MaximumRetryCount": int(count)}
    return {"Name": policy}


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
    """Adaptador runtime sobre un único contenedor Docker (FASE A).

    No hereda ``ServerRuntimePort`` (los Protocol son estructurales); los
    métodos con ``runtime_id`` lo aceptan opcional: si se omite o coincide con
    el contenedor gestionado por Settings, se opera sobre él.
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

    def _container(self) -> Any:
        client = self._client()
        try:
            return client.containers.get(self._settings.container_name)
        except NotFound as exc:
            raise ContainerNotFoundError(
                f"El contenedor '{self._settings.container_name}' no existe",
                context={"container_name": self._settings.container_name},
            ) from exc

    def _validate_runtime_id(self, runtime_id: str | None) -> None:
        if runtime_id is not None and runtime_id != self._settings.container_name:
            raise ContainerNotFoundError(
                f"El runtime '{runtime_id}' no corresponde al contenedor gestionado",
                context={
                    "runtime_id": runtime_id,
                    "container_name": self._settings.container_name,
                },
            )

    def _volumes(self) -> list[str]:
        volumes: list[str] = []
        if self._settings.data_volume:
            volumes.append(f"{self._settings.data_volume}:/data")
        if self._settings.world_volume:
            volumes.append(f"{self._settings.world_volume}:/data/worlds")
        return volumes

    def _remove_volumes(self) -> None:
        client = self._client()
        for volume_name in (self._settings.data_volume, self._settings.world_volume):
            if not volume_name:
                continue
            try:
                client.volumes.get(volume_name).remove(force=True)
            except NotFound:
                continue

    def exists(self) -> bool:
        """Comprueba si el contenedor gestionado existe (FASE A)."""
        try:
            self._client().containers.get(self._settings.container_name)
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
        self._validate_runtime_id(runtime_id)
        if not self.exists():
            return False
        return self.status().running

    @_map_docker_errors
    def create_if_missing(self) -> None:
        """Crea el contenedor (con Settings) si aún no existe (FASE A)."""
        if self.exists():
            return
        client = self._client()
        name = self._settings.container_name
        started = time.perf_counter()
        logger.info("runtime.create", extra={"container": name, "phase": "begin"})
        client.containers.create(
            self._settings.image,
            name=name,
            ports=self._settings.ports or None,
            volumes=self._volumes() or None,
            network=self._settings.network,
            restart_policy=_restart_policy(self._settings.restart_policy),
            mem_limit=self._settings.memory_limit,
            nano_cpus=_nano_cpus(self._settings.cpu_limit),
            detach=True,
            stdin_open=True,
            tty=True,
        )
        logger.info(
            "runtime.create",
            extra={"container": name, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def start(self, runtime_id: str | None = None) -> None:
        """Arranca el contenedor; no espera a que el juego responda."""
        self._validate_runtime_id(runtime_id)
        name = self._settings.container_name
        started = time.perf_counter()
        logger.info("runtime.start", extra={"container": name, "phase": "begin"})
        container = self._container()
        container.start()
        logger.info(
            "runtime.start",
            extra={"container": name, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def stop(self, runtime_id: str | None = None, grace: int = 30) -> None:
        """Parada ordenada con espera de ``grace`` segundos; si no, fuerza."""
        self._validate_runtime_id(runtime_id)
        name = self._settings.container_name
        started = time.perf_counter()
        logger.info("runtime.stop", extra={"container": name, "phase": "begin", "grace": grace})
        container = self._container()
        container.stop(timeout=grace)
        logger.info(
            "runtime.stop",
            extra={"container": name, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def restart(self, runtime_id: str | None = None, grace: int = 30) -> None:
        """Parada ordenada + arranque del contenedor."""
        self._validate_runtime_id(runtime_id)
        name = self._settings.container_name
        started = time.perf_counter()
        logger.info("runtime.restart", extra={"container": name, "phase": "begin", "grace": grace})
        container = self._container()
        container.restart(timeout=grace)
        logger.info(
            "runtime.restart",
            extra={"container": name, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def remove(self, runtime_id: str | None = None, delete_data: bool = False) -> None:
        """Elimina el contenedor (idempotente); ``delete_data`` borra los volúmenes."""
        self._validate_runtime_id(runtime_id)
        if not self.exists():
            return
        name = self._settings.container_name
        started = time.perf_counter()
        logger.info(
            "runtime.remove",
            extra={"container": name, "phase": "begin", "delete_data": delete_data},
        )
        container = self._container()
        container.remove(force=True)
        if delete_data:
            self._remove_volumes()
        logger.info(
            "runtime.remove",
            extra={"container": name, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )

    @_map_docker_errors
    def status(self, runtime_id: str | None = None) -> RuntimeStatus:
        """Estado normalizado del contenedor como DTO (FASE A)."""
        self._validate_runtime_id(runtime_id)
        container = self._container()
        return _build_status(container.attrs, self._settings.container_name)

    @_map_docker_errors
    def inspect(self, runtime_id: str | None = None) -> RuntimeInspect:
        """Inspección completa del contenedor normalizada a dominio (FASE A)."""
        self._validate_runtime_id(runtime_id)
        container = self._container()
        raw = container.attrs
        return _build_inspect(raw, self._settings)

    @_map_docker_errors
    def logs(self, runtime_id: str | None = None, *, tail: int = 200) -> str:
        """Últimas ``tail`` líneas de stdout/stderr del contenedor (FASE A)."""
        self._validate_runtime_id(runtime_id)
        container = self._container()
        raw = container.logs(tail=tail)
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return "".join(chunk.decode("utf-8", errors="replace") for chunk in raw)

    @_map_docker_errors
    def materialize(self, spec: RuntimeSpec) -> str:
        """Crea el contenedor desde un ``RuntimeSpec`` sin arrancarlo (§4.1).

        Si ya existe un contenedor con el mismo nombre (FASE A: uno solo), se
        elimina y se recrea con el ``spec`` actual — evita reutilizar un
        artefacto viejo sin ``EULA``/puertos incorrectos.
        """
        name = self._settings.container_name
        image_ref = f"{spec.image}:{spec.tag}" if spec.tag else spec.image
        started = time.perf_counter()
        logger.info(
            "runtime.materialize",
            extra={"container": name, "phase": "begin", "image": image_ref},
        )
        if self.exists():
            logger.info(
                "runtime.materialize",
                extra={"container": name, "phase": "replace"},
            )
            self.remove(name, delete_data=False)
        client = self._client()
        client.containers.create(
            image_ref,
            name=name,
            environment=spec.environment or None,
            ports=spec.ports or None,
            volumes=spec.volumes or None,
            network=spec.network,
            mem_limit=spec.resources.get("memory"),
            nano_cpus=_nano_cpus(spec.resources.get("cpus")),
            user=spec.user,
            labels=spec.labels or None,
            detach=True,
            stdin_open=spec.stdin_open,
            tty=spec.tty,
        )
        logger.info(
            "runtime.materialize",
            extra={"container": name, "phase": "end", "elapsed_ms": _elapsed_ms(started)},
        )
        return name

    @_map_docker_errors
    def get_state(self, runtime_id: str | None = None) -> RuntimeState:
        """Estado normalizado del runtime (§4.1)."""
        self._validate_runtime_id(runtime_id)
        return self.status().status

    @_map_docker_errors
    def get_health(self, runtime_id: str | None = None) -> dict[str, Any]:
        """Salud del runtime y último estado reportado (§4.1)."""
        self._validate_runtime_id(runtime_id)
        st = self.status()
        return {
            "container_id": st.container_id,
            "health": st.health,
            "healthy": st.healthy,
            "running": st.running,
        }

    @_map_docker_errors
    def get_resources(self, runtime_id: str | None = None) -> dict[str, Any]:
        """CPU/RAM actuales del proceso (§4.1). Sin deltas en FASE A."""
        self._validate_runtime_id(runtime_id)
        container = self._container()
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
        self._validate_runtime_id(runtime_id)
        container = self._container()
        exit_code = (container.attrs.get("State") or {}).get("ExitCode")
        return int(exit_code) if isinstance(exit_code, int) else None

    @_map_docker_errors
    def stream_logs(self, runtime_id: str | None = None) -> Iterator[bytes]:
        """Stream en vivo de líneas stdout/stderr (cola + streaming) (§4.1).

        ``container.logs(stream=True, follow=True, tail="all")``: el iterador
        es bloqueante sobre el socket del daemon y termina cuando el contenedor
        se detiene/elimina (el daemon cierra el stream). El consumo se hace en
        un hilo worker dentro de ``ConsoleLogStream.consume`` para no bloquear
        el event loop (change-log §20).
        """
        self._validate_runtime_id(runtime_id)
        container = self._container()
        return cast(Iterator[bytes], container.logs(stream=True, follow=True, tail="all"))

    @_map_docker_errors
    def send_stdin(self, runtime_id: str, data: str) -> None:
        """Escribe en el stdin del proceso (§4.1; mínimo en FASE A)."""
        self._validate_runtime_id(runtime_id)
        container = self._container()
        socket = container.attach_socket(params={"stdin": 1, "stdout": 0, "stderr": 0})
        try:
            stream = socket.makefile("w")
            stream.write(data)
            stream.flush()
            stream.close()
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
        self._validate_runtime_id(runtime_id)
        supported = {"running", "stopped"}
        if condition not in supported:
            raise DockerError(
                f"Condición no soportada por el adaptador: '{condition}'",
                context={"condition": condition},
            )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition == "running" and self.is_running():
                return
            if condition == "stopped" and (not self.exists() or not self.is_running()):
                return
            time.sleep(0.5)
        raise DockerTimeoutError(
            f"Tiempo de espera agotado esperando condición '{condition}'",
            context={"condition": condition, "timeout": timeout},
        )

    @_map_docker_errors
    def signal(self, runtime_id: str, sig: int) -> None:
        """Señal explícita (SIGTERM/SIGKILL) al contenedor (§4.1)."""
        self._validate_runtime_id(runtime_id)
        container = self._container()
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


def _build_inspect(raw: dict[str, Any], settings: DockerRuntimeSettings) -> RuntimeInspect:
    """Construye ``RuntimeInspect`` desde los attrs crudos del contenedor."""
    state = raw.get("State") or {}
    config = raw.get("Config") or {}
    host = raw.get("HostConfig") or {}
    return RuntimeInspect(
        status=_build_status(raw, settings.container_name),
        environment=_parse_env(config.get("Env") or []),
        command=list(config.get("Cmd") or []),
        memory_limit_bytes=host.get("Memory"),
        cpu_limit_cores=_cpus_from_nano(host.get("NanoCpus")),
        restart_policy=(host.get("RestartPolicy") or {}).get("Name"),
        exit_code=state.get("ExitCode"),
    )
