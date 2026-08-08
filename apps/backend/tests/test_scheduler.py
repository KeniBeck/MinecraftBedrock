"""Tests del módulo Scheduler (Fase G paso 15).

Cubre el CRUD de tareas programadas, la validación de cron/payload, el reloj
(``tick``) y la ejecución por tipo, y los handlers de reintentos: ``TASK.FAILED``
(backoff con tope), ``BACKUP.FAILED`` (reconciliación) y ``SERVER.CRASHED``
(política de reinicio). Usa dobles inyectados y el mismo patrón ``Fixture`` +
``Clock`` que el módulo Backup.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.backup.application.results import BackupView
from app.modules.scheduler.application.commands import (
    CreateTaskCommand,
    DeleteTaskCommand,
    RunTaskCommand,
    UpdateTaskCommand,
)
from app.modules.scheduler.application.facade import SchedulerFacade
from app.modules.scheduler.application.use_cases import SchedulerDeps
from app.modules.scheduler.domain.errors import (
    SchedulerValidationError,
    TaskNotFoundError,
    TaskStateError,
)
from app.modules.scheduler.domain.events import (
    TASK_COMPLETED_TOPIC,
    TASK_FAILED_TOPIC,
    TASK_SCHEDULED_TOPIC,
    TASK_STARTED_TOPIC,
)
from app.modules.scheduler.domain.task import ScheduleTask, ScheduleTaskState, ScheduleTaskType
from app.modules.scheduler.infrastructure.memory import InMemorySchedulerRepository
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeSettings, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SERVER_ID = "srv-1"


class Clock:
    """``TimeProviderPort`` con hora avanzable (determinismo en tick/retry)."""

    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


def _backup_view() -> BackupView:
    return BackupView(
        id="bk-1",
        server_id=SERVER_ID,
        world_name="Alpha",
        state="completed",
        size_bytes=1,
        checksum="x",
        entries=[],
        duration_seconds=1,
        protected=False,
        orphaned=False,
        error=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _server_view() -> ServerView:
    return ServerView(
        id=SERVER_ID,
        name="Survival",
        state=ServerState.RUNNING,
        version="1.20.0",
        image_ref="img:latest",
        runtime_id="r1",
        created_at=NOW,
        updated_at=NOW,
        connection=stub_connection(),
    )


class FakeBackupRunner:
    """``BackupRunner`` en memoria que registra llamadas y puede fallar."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail = False

    async def create_backup(self, cmd: Any) -> BackupView:
        self.calls.append(cmd.world_name)
        if self.fail:
            raise RuntimeError("backup falló")
        return _backup_view()


class FakeServerRunner:
    """``ServerRunner`` en memoria que registra reinicios y puede fallar."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail = False

    async def restart(self, cmd: Any) -> ServerView:
        self.calls.append(cmd.server_id)
        if self.fail:
            raise RuntimeError("restart falló")
        return _server_view()


class Fixture:
    """Deps del módulo Scheduler con dobles inyectados."""

    def __init__(self, ids: SequenceIds | None = None) -> None:
        self.bus = InProcessEventBus()
        self.clock = Clock()
        self.repository = InMemorySchedulerRepository()
        self.backup = FakeBackupRunner()
        self.server = FakeServerRunner()
        self.deps = SchedulerDeps(
            repository=self.repository,
            bus=self.bus,
            ids=ids or SequenceIds("t-1", "t-2", "t-3", "t-4", "t-5", "t-6"),
            time=self.clock,
            settings=FakeSettings(),
            backup=self.backup,
            server=self.server,
        )
        self.facade = SchedulerFacade(self.deps)
        self.facade.register_handlers()

        self.started: list[DomainEvent] = []
        self.completed: list[DomainEvent] = []
        self.failed: list[DomainEvent] = []
        self.scheduled: list[DomainEvent] = []
        self.bus.subscribe(TASK_STARTED_TOPIC, self.started.append)
        self.bus.subscribe(TASK_COMPLETED_TOPIC, self.completed.append)
        self.bus.subscribe(TASK_FAILED_TOPIC, self.failed.append)
        self.bus.subscribe(TASK_SCHEDULED_TOPIC, self.scheduled.append)

    async def make_task(
        self,
        task_type: str = "command",
        *,
        cron: str = "* * * * *",
        payload: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> ScheduleTask:
        view = await self.facade.create_task(
            CreateTaskCommand(
                server_id=SERVER_ID,
                name="Task",
                type=task_type,
                cron=cron,
                payload=payload or {},
                max_retries=max_retries,
                actor_id="admin-1",
            )
        )
        task = await self.repository.get_task(view.id)
        assert task is not None
        return task

    async def seed(self, task: ScheduleTask) -> None:
        await self.repository.save_task(task)


# -- crear -------------------------------------------------------------------


async def test_create_calcula_proxima_ejecucion_y_publica() -> None:
    fx = Fixture()
    now = fx.clock.now()

    task = await fx.make_task(payload={"commands": ["say hola"]})

    assert task.state is ScheduleTaskState.ACTIVE
    assert task.type is ScheduleTaskType.COMMAND
    assert task.next_run_at is not None and task.next_run_at > now
    assert task.payload == {"commands": ["say hola"]}
    assert task.cron == "* * * * *"
    assert [e.type for e in fx.scheduled] == ["TASK.SCHEDULED"]


async def test_create_valida_cron_invalido() -> None:
    fx = Fixture()
    with pytest.raises(SchedulerValidationError):
        await fx.facade.create_task(
            CreateTaskCommand(server_id=SERVER_ID, name="T", type="command", cron="not-acron")
        )


async def test_create_command_requiere_comandos() -> None:
    fx = Fixture()
    with pytest.raises(SchedulerValidationError):
        await fx.facade.create_task(
            CreateTaskCommand(server_id=SERVER_ID, name="T", type="command", cron="* * * * *")
        )


async def test_create_backup_requiere_world_name() -> None:
    fx = Fixture()
    with pytest.raises(SchedulerValidationError):
        await fx.facade.create_task(
            CreateTaskCommand(server_id=SERVER_ID, name="T", type="backup", cron="* * * * *")
        )


async def test_create_tipo_invalido_fracasa() -> None:
    fx = Fixture()
    with pytest.raises(SchedulerValidationError):
        await fx.facade.create_task(
            CreateTaskCommand(server_id=SERVER_ID, name="T", type="nope", cron="* * * * *")
        )


async def test_list_y_get_de_tareas() -> None:
    fx = Fixture()
    await fx.make_task(payload={"commands": ["say a"]})

    tasks = await fx.facade.list_tasks(SERVER_ID)
    assert len(tasks) == 1
    detail = await fx.facade.get_task(tasks[0].id)
    assert detail is not None and detail.server_id == SERVER_ID
    assert await fx.facade.get_task("nope") is None


# -- editar / eliminar -------------------------------------------------------


async def test_update_desactiva_y_limpia_next_run() -> None:
    fx = Fixture()
    task = await fx.make_task(payload={"commands": ["say a"]})

    updated = await fx.facade.update_task(
        UpdateTaskCommand(task_id=task.id, name="Renombrada", state="disabled")
    )

    assert updated.name == "Renombrada"
    assert updated.state == "disabled"
    assert updated.next_run_at is None


async def test_update_reactiva_tarea_fallida() -> None:
    fx = Fixture()
    task = await fx.make_task(payload={"commands": ["say a"]})
    await fx.seed(
        ScheduleTask(
            id=task.id,
            server_id=task.server_id,
            name=task.name,
            type=task.type,
            cron=task.cron,
            payload=task.payload,
            state=ScheduleTaskState.FAILED,
            next_run_at=None,
            failures=6,
            max_retries=task.max_retries,
            backoff_seconds=task.backoff_seconds,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    )

    updated = await fx.facade.update_task(
        UpdateTaskCommand(task_id=task.id, state="active", cron=task.cron)
    )

    assert updated.state == "active"
    assert updated.failures == 0
    assert updated.next_run_at is not None


async def test_update_de_tarea_desconocida_fracasa() -> None:
    fx = Fixture()
    with pytest.raises(TaskNotFoundError):
        await fx.facade.update_task(UpdateTaskCommand(task_id="nope", name="X"))


async def test_delete_elimina_y_publica_cancelado() -> None:
    fx = Fixture()
    task = await fx.make_task(payload={"commands": ["say a"]})
    events: list[DomainEvent] = []
    fx.bus.subscribe("task.cancelled", events.append)

    await fx.facade.delete_task(DeleteTaskCommand(task_id=task.id))

    assert await fx.repository.get_task(task.id) is None
    assert [e.type for e in events] == ["TASK.CANCELLED"]


async def test_delete_de_tarea_desconocida_fracasa() -> None:
    fx = Fixture()
    with pytest.raises(TaskNotFoundError):
        await fx.facade.delete_task(DeleteTaskCommand(task_id="nope"))


# -- el reloj ----------------------------------------------------------------


async def test_tick_ejecuta_command_y_publica_started_completed() -> None:
    fx = Fixture()
    task = await fx.make_task(payload={"commands": ["say hola", "say adios"]})
    fx.clock.advance(timedelta(seconds=61))  # "* * * * *" vence

    processed = await fx.facade.tick()

    assert processed == [task.id]
    assert fx.started
    started = fx.started[0]
    assert started.server_id == SERVER_ID
    assert started.payload.get("commands") == ["say hola", "say adios"]
    assert [e.type for e in fx.completed] == ["TASK.COMPLETED"]
    final = await fx.repository.get_task(task.id)
    assert final is not None and final.next_run_at is not None and final.next_run_at > NOW
    assert final.last_result == "ok"
    assert final.failures == 0


async def test_tick_ignora_tarea_no_vencida() -> None:
    fx = Fixture()
    await fx.make_task(cron="0 0 1 1 *", payload={"commands": ["say a"]})

    processed = await fx.facade.tick()

    assert processed == []
    assert fx.started == []
    assert fx.backup.calls == []
    assert fx.server.calls == []


async def test_tick_ejecuta_tarea_backup() -> None:
    fx = Fixture()
    task = await fx.make_task(task_type="backup", payload={"world_name": "Alpha"})
    fx.clock.advance(timedelta(seconds=60))

    await fx.facade.tick()

    assert fx.backup.calls == ["Alpha"]
    assert [e.type for e in fx.completed] == ["TASK.COMPLETED"]
    final = await fx.repository.get_task(task.id)
    assert final is not None and final.last_result == "ok"


async def test_tick_ejecuta_tarea_restart() -> None:
    fx = Fixture()
    task = await fx.make_task(task_type="restart", payload={"grace": 15})
    fx.clock.advance(timedelta(seconds=60))

    await fx.facade.tick()

    assert fx.server.calls == [SERVER_ID]
    assert [e.type for e in fx.completed] == ["TASK.COMPLETED"]
    final = await fx.repository.get_task(task.id)
    assert final is not None and final.state is ScheduleTaskState.ACTIVE


async def test_run_now_ejecuta_manual_fuera_del_cron() -> None:
    fx = Fixture()
    task = await fx.make_task(cron="0 0 1 1 *", payload={"commands": ["say x"]})

    view = await fx.facade.run_task(RunTaskCommand(task_id=task.id))

    assert view.last_result == "ok"
    assert [e.type for e in fx.completed] == ["TASK.COMPLETED"]


async def test_run_now_de_tarea_desactivada_fracasa() -> None:
    fx = Fixture()
    task = await fx.make_task(payload={"commands": ["say x"]})
    await fx.facade.update_task(UpdateTaskCommand(task_id=task.id, state="disabled"))

    with pytest.raises(TaskStateError):
        await fx.facade.run_task(RunTaskCommand(task_id=task.id))


# -- reintentos --------------------------------------------------------------


async def test_fallo_publica_failed_y_reintenta_con_backoff() -> None:
    fx = Fixture()
    fx.backup.fail = True
    task = await fx.make_task(task_type="backup", payload={"world_name": "Alpha"})
    fx.clock.advance(timedelta(seconds=60))

    await fx.facade.tick()

    assert [e.type for e in fx.failed] == ["TASK.FAILED"]
    final = await fx.repository.get_task(task.id)
    assert final is not None
    assert final.failures == 1
    assert final.next_run_at is not None
    # backoff default: 60s * 2^(1-1) = 60s tras el fallo (ahora = NOW+60)
    assert final.next_run_at == fx.clock.now() + timedelta(seconds=60)


async def test_retry_sin_tope_marca_tarea_failed() -> None:
    fx = Fixture()
    fx.server.fail = True
    task = await fx.make_task(task_type="restart", payload={}, max_retries=1)
    fx.clock.advance(timedelta(seconds=60))
    await fx.facade.tick()  # primer fallo, failures=1 <= 1 → backoff
    final = await fx.repository.get_task(task.id)
    assert final is not None and final.state is ScheduleTaskState.ACTIVE

    fx.clock.advance(timedelta(seconds=61))
    await fx.facade.tick()  # segundo fallo, failures=2 > 1 → FAILED
    final = await fx.repository.get_task(task.id)
    assert final is not None and final.state is ScheduleTaskState.FAILED
    assert final.next_run_at is None


async def test_tick_no_reintenta_tarea_desactivada() -> None:
    fx = Fixture()
    await fx.make_task(payload={"commands": ["say x"]})
    fx.clock.advance(timedelta(seconds=60))

    await fx.facade.update_task(UpdateTaskCommand(task_id="t-1", state="disabled"))
    fx.clock.advance(timedelta(seconds=3600))

    processed = await fx.facade.tick()
    assert processed == []


async def test_backup_failed_reconcilia_tarea_reciente() -> None:
    fx = Fixture()
    task = await fx.make_task(task_type="backup", payload={"world_name": "Alpha"})
    await fx.seed(
        ScheduleTask(
            id=task.id,
            server_id=task.server_id,
            name=task.name,
            type=task.type,
            cron=task.cron,
            payload=task.payload,
            state=ScheduleTaskState.ACTIVE,
            next_run_at=task.next_run_at,
            last_run_at=fx.clock.now(),
            failures=1,
            max_retries=task.max_retries,
            backoff_seconds=task.backoff_seconds,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    )

    await fx.bus.publish(
        DomainEvent(
            type="BACKUP.FAILED",
            server_id=SERVER_ID,
            payload={"server_id": SERVER_ID, "error": "disco lleno"},
        )
    )

    final = await fx.repository.get_task(task.id)
    assert final is not None and final.last_result == "disco lleno"


async def test_server_crashed_programa_reinicio_con_backoff() -> None:
    fx = Fixture()
    task = await fx.make_task(task_type="restart", payload={})

    await fx.bus.publish(DomainEvent(type="SERVER.CRASHED", server_id=SERVER_ID, payload={}))

    final = await fx.repository.get_task(task.id)
    assert final is not None
    # crash_retry_seconds default = 60s desde la hora del crash (NOW)
    assert final.next_run_at == NOW + timedelta(seconds=60)
    assert final.state is ScheduleTaskState.ACTIVE
