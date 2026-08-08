"""Entidad ``Server`` (agregado raíz del módulo Server, TDD §5.2, §15.2).

Responsabilidad: identidad, ``RuntimeSpec``, estado normalizado (dominio) y
versión. El dominio **nunca** depende de Infrastructure: la entidad solo usa
el kernel (``RuntimeSpec``, ``ServerState``) y sus propias reglas de estado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.kernel.ports.runtime import RuntimeSpec, ServerState
from app.modules.server.domain.state_machine import assert_can_transition


@dataclass(frozen=True, slots=True)
class ServerId:
    """Value object: identidad del servidor (UUID)."""

    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True)
class Server:
    """Instancia de servidor del panel.

    Campos según TDD §15.2 (sin persistencia): identidad, nombre, spec
    (imagen/tag/versión/env/puertos/recursos), estado y timestamps. Los
    timestamps los provee el caso de uso vía ``TimeProviderPort``.
    """

    id: ServerId
    name: str
    spec: RuntimeSpec
    state: ServerState
    created_at: datetime
    updated_at: datetime
    runtime_id: str | None = None
    desired_config_rev: int | None = None
    applied_config_rev: int | None = None

    @property
    def version(self) -> str:
        """Versión de BDS (deseada/aplicada) del servidor."""
        return self.spec.version

    @property
    def image_ref(self) -> str:
        """Referencia completa ``imagen:tag``.

        Con digest (``tag`` vacío) se devuelve solo la imagen para no emitir
        referencias malformadas tipo ``imagen@sha256:…:``.
        """
        if not self.spec.tag:
            return self.spec.image
        return f"{self.spec.image}:{self.spec.tag}"

    # -- transiciones de estado (invariantes del dominio) -----------------

    def request_start(self) -> None:
        assert_can_transition(self.state, ServerState.STARTING)
        self.state = ServerState.STARTING

    def mark_started(self) -> None:
        assert_can_transition(self.state, ServerState.RUNNING)
        self.state = ServerState.RUNNING

    def request_stop(self) -> None:
        assert_can_transition(self.state, ServerState.STOPPING)
        self.state = ServerState.STOPPING

    def mark_stopped(self) -> None:
        assert_can_transition(self.state, ServerState.STOPPED)
        self.state = ServerState.STOPPED

    def mark_crashed(self) -> None:
        assert_can_transition(self.state, ServerState.CRASHED)
        self.state = ServerState.CRASHED

    def mark_removed(self) -> None:
        assert_can_transition(self.state, ServerState.REMOVED)
        self.state = ServerState.REMOVED

    # -- spec -------------------------------------------------------------

    def update_spec(self, spec: RuntimeSpec) -> None:
        """Sustituye el ``RuntimeSpec`` (config deseada re-renderizada)."""
        self.spec = spec

    def change_version(self, version: str) -> None:
        """Aplica una nueva versión de BDS al spec (copias defensivas)."""
        self.spec = RuntimeSpec(
            **{f: getattr(self.spec, f) for f in self.spec.__dataclass_fields__}
        )
        self.spec.environment = dict(self.spec.environment)
        self.spec.ports = dict(self.spec.ports)
        self.spec.volumes = list(self.spec.volumes)
        self.spec.resources = dict(self.spec.resources)
        self.spec.labels = dict(self.spec.labels)
        self.spec.version = version

    def change_resources(self, *, cpu_cores: float | None, ram_mb: int | None) -> bool:
        """Actualiza CPU/RAM del spec; devuelve True si algo cambió.

        El spec se copia defensivamente (misma política que ``change_version``).
        Las claves del dict ``resources`` son las que consume el runtime
        (``cpus``/``memory_mb``; hallazgo B7: la imagen Bedrock de itzg espera
        ``memory_mb`` en MB).
        """
        current = self.spec.resources
        new_cpus = cpu_cores if cpu_cores is not None else float(current.get("cpus", 0.0))
        new_ram = ram_mb if ram_mb is not None else int(current.get("memory_mb", 0))
        if float(new_cpus) == float(current.get("cpus", 0)) and int(new_ram) == int(
            current.get("memory_mb", 0)
        ):
            return False

        self.spec = RuntimeSpec(
            **{f: getattr(self.spec, f) for f in self.spec.__dataclass_fields__}
        )
        self.spec.resources = dict(current)
        self.spec.resources["cpus"] = float(new_cpus)
        self.spec.resources["memory_mb"] = int(new_ram)
        return True
