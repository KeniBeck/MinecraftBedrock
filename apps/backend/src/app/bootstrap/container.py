"""Composición de dependencias (TDD §16 ``bootstrap``).

Punto único de inyección de dependencias (Blueprint §1.1). En FASE A se
registra el adaptador Docker por su tipo concreto; en FASE B se compone el
módulo Server: repositorio en memoria, bus en proceso y facade pública. Desde
la FASE A paso 2 (corrección) los repositorios durmables (Postgres) reemplazan
a los de memoria en producción; las implementaciones en memoria se conservan
para tests.

``DockerRuntimeAdapter`` es estructuralmente un ``ServerRuntimePort`` desde el
ajuste de ``stream_logs`` → ``Iterator[bytes]`` (change-log §9); no se necesita
``cast`` en este boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.bootstrap.config import Settings, get_settings
from app.infrastructure.backups.local import LocalBackupStore
from app.infrastructure.common.ids import UuidIdGenerator
from app.infrastructure.common.settings import EnvSettingsAdapter
from app.infrastructure.common.time import SystemTimeProvider
from app.infrastructure.db.session import Database, DatabaseSettings
from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.parsers.player_join_detector import PlayerJoinDetector
from app.infrastructure.parsers.save_detector import SaveDetector
from app.infrastructure.runtime import (
    DockerFromEnvClientFactory,
    DockerRuntimeAdapter,
    DockerRuntimeSettings,
)
from app.infrastructure.storage import LocalServerStorageResolver
from app.kernel.ports.runtime import ServerRuntimePort
from app.modules.backup.application.facade import BackupFacade
from app.modules.backup.application.use_cases import BackupDeps
from app.modules.backup.infrastructure.postgres_repository import PostgresBackupRepository
from app.modules.configuration.application.facade import ConfigurationFacade
from app.modules.configuration.domain.property_schema import PropertySchema
from app.modules.configuration.infrastructure.postgres_repository import (
    PostgresConfigurationRepository,
)
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.domain.events import CONSOLE_OUTPUT_TOPIC
from app.modules.console.infrastructure.postgres_store import PostgresConsoleLogStore
from app.modules.console.infrastructure.reconcile import ConsoleStreamReconciler
from app.modules.console.infrastructure.stream import ConsoleLogStream
from app.modules.console.infrastructure.stream_manager import ConsoleStreamManager
from app.modules.iam.application.facade import IamFacade
from app.modules.iam.application.use_cases import IamDeps
from app.modules.iam.infrastructure.audit_store import PostgresAuditStore
from app.modules.iam.infrastructure.password import Argon2PasswordHasher
from app.modules.iam.infrastructure.postgres_repository import PostgresIamRepository
from app.modules.iam.infrastructure.sessions import PostgresSessionStore
from app.modules.iam.infrastructure.tokens import JwtTokenService
from app.modules.monitoring.application.facade import MonitoringFacade
from app.modules.monitoring.application.polling import StatusPoller
from app.modules.monitoring.infrastructure.memory import InMemoryMetricSampleStore
from app.modules.monitoring.infrastructure.poller import BackgroundPoller
from app.modules.monitoring.infrastructure.raknet_probe import RakNetStatusProbe
from app.modules.notification.application.facade import NotificationFacade
from app.modules.notification.application.rate_limiter import RateLimitConfig
from app.modules.notification.infrastructure.postgres_event_log_repository import (
    PostgresEventLogRepository,
)
from app.modules.permission.application.facade import PermissionFacade
from app.modules.permission.application.use_cases import PermissionDeps
from app.modules.player.application.facade import PlayerFacade
from app.modules.player.application.use_cases import PlayerDeps
from app.modules.player.infrastructure.postgres_repository import (
    PostgresPlayerBanRepository,
    PostgresPlayerRepository,
)
from app.modules.scheduler.application.facade import SchedulerFacade
from app.modules.scheduler.application.use_cases import SchedulerDeps
from app.modules.scheduler.infrastructure.poller import SchedulerPoller
from app.modules.scheduler.infrastructure.postgres_repository import (
    PostgresSchedulerTaskRepository,
)
from app.modules.server.application.facade import ServerFacade
from app.modules.server.application.ports import ConfigurationReader
from app.modules.server.application.spec_factory import (
    RuntimeSpecFactory,
    build_port_allocator,
)
from app.modules.server.application.use_cases import ServerDeps
from app.modules.server.domain.repository import ServerRepositoryPort
from app.modules.server.infrastructure.postgres_repository import PostgresServerRepository
from app.modules.template.application.facade import TemplateFacade
from app.modules.template.application.use_cases import TemplateDeps
from app.modules.template.infrastructure.postgres_repository import PostgresTemplateRepository
from app.modules.template.infrastructure.store import TemplateArchiveStore
from app.modules.template.infrastructure.world import WorldFacadeGateway
from app.modules.world.application.facade import WorldFacade
from app.modules.world.application.use_cases import WorldDeps
from app.modules.world.infrastructure.postgres_repository import PostgresWorldRepository


@dataclass(frozen=True, slots=True)
class Container:
    """Contenedor de dependencias registradas en el bootstrap."""

    settings: Settings
    database: Database
    docker_runtime: DockerRuntimeAdapter
    event_bus: InProcessEventBus
    server_facade: ServerFacade
    server_repository: ServerRepositoryPort
    console_facade: ConsoleFacade
    console_stream: ConsoleLogStream
    iam_facade: IamFacade
    player_facade: PlayerFacade
    permission_facade: PermissionFacade
    world_facade: WorldFacade
    backup_facade: BackupFacade
    monitoring_facade: MonitoringFacade
    scheduler_facade: SchedulerFacade
    template_facade: TemplateFacade
    notification_facade: NotificationFacade
    console_stream_reconciler: ConsoleStreamReconciler | None = None
    monitoring_poller: BackgroundPoller | None = None
    scheduler_poller: SchedulerPoller | None = None


def build_container() -> Container:
    """Construye el contenedor de dependencias del panel."""
    settings = get_settings()
    database = Database(
        DatabaseSettings(
            url=settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            echo=settings.db_echo,
        )
    )
    session_factory = database.session_factory()
    runtime_settings = DockerRuntimeSettings()
    docker_client_factory = DockerFromEnvClientFactory(timeout=runtime_settings.docker_timeout)
    docker_runtime = DockerRuntimeAdapter(
        runtime_settings,
        docker_client_factory=docker_client_factory,
    )

    event_bus = InProcessEventBus()
    server_repository = PostgresServerRepository(session_factory)
    settings_port = EnvSettingsAdapter(settings)
    ids = UuidIdGenerator()
    time = SystemTimeProvider()
    port_allocator = build_port_allocator(settings_port)
    spec_factory = RuntimeSpecFactory(settings_port, port_allocator)
    configuration_repository = PostgresConfigurationRepository(session_factory)
    configuration_facade = ConfigurationFacade(
        repository=configuration_repository,
        schema=PropertySchema(),
        bus=event_bus,
        settings=settings_port,
        time=time,
    )
    configuration: ConfigurationReader = configuration_facade

    runtime_port: ServerRuntimePort = docker_runtime

    deps = ServerDeps(
        repository=server_repository,
        runtime=runtime_port,
        bus=event_bus,
        ids=ids,
        time=time,
        settings=settings_port,
        configuration=configuration,
        spec_factory=spec_factory,
    )
    server_facade = ServerFacade(
        repository=server_repository,
        configuration=configuration,
        spec_factory=spec_factory,
        deps=deps,
    )
    server_facade.register_handlers()

    console_store = PostgresConsoleLogStore(
        session_factory,
        max_lines=int(settings_port.get("console.buffer_max_lines", 1000)),
    )
    console_deps = ConsoleDeps(
        server=server_facade,
        runtime=runtime_port,
        bus=event_bus,
        time=time,
        settings=settings_port,
        ids=ids,
        store=console_store,
    )
    command_queue = CommandQueue(runtime=runtime_port, bus=event_bus, time=time)
    output_router = ConsoleOutputRouter(store=console_store, bus=event_bus)
    console_facade = ConsoleFacade(deps=console_deps, queue=command_queue, router=output_router)
    console_facade.register_handlers()

    save_detector = SaveDetector(bus=event_bus)
    event_bus.subscribe(CONSOLE_OUTPUT_TOPIC, save_detector)

    player_join_detector = PlayerJoinDetector(bus=event_bus)
    event_bus.subscribe(CONSOLE_OUTPUT_TOPIC, player_join_detector)

    console_stream = ConsoleLogStream(runtime=runtime_port, store=console_store, bus=event_bus)
    stream_manager = ConsoleStreamManager(
        stream=console_stream,
        server=console_deps.server,
        bus=event_bus,
    )
    stream_manager.subscribe()

    console_stream_reconciler = ConsoleStreamReconciler(
        manager=stream_manager,
        server=console_deps.server,
        runtime=runtime_port,
    )

    iam_repository = PostgresIamRepository(session_factory)
    iam_sessions = PostgresSessionStore(session_factory)
    iam_audit = PostgresAuditStore(session_factory)
    iam_deps = IamDeps(
        repository=iam_repository,
        sessions=iam_sessions,
        audit=iam_audit,
        hasher=Argon2PasswordHasher(),
        tokens=JwtTokenService(settings_port),
        bus=event_bus,
        ids=ids,
        time=time,
        settings=settings_port,
    )
    iam_facade = IamFacade(iam_deps)
    iam_facade.register_handlers()

    player_repository = PostgresPlayerRepository(session_factory)
    player_ban_repository = PostgresPlayerBanRepository(session_factory)
    player_deps = PlayerDeps(
        repository=player_repository,
        ban_repository=player_ban_repository,
        console=console_facade,
        bus=event_bus,
        ids=ids,
        time=time,
        settings=settings_port,
    )
    player_facade = PlayerFacade(player_deps)
    player_facade.register_handlers()

    permission_deps = PermissionDeps(
        storage=LocalServerStorageResolver(spec_factory),
        console=console_facade,
        server=server_facade,
        bus=event_bus,
    )
    permission_facade = PermissionFacade(permission_deps)
    permission_facade.register_handlers()

    world_repository = PostgresWorldRepository(session_factory)
    world_deps = WorldDeps(
        repository=world_repository,
        storage=LocalServerStorageResolver(spec_factory),
        console=console_facade,
        server=console_deps.server,
        bus=event_bus,
        ids=ids,
        time=time,
    )
    world_facade = WorldFacade(world_deps)
    world_facade.register_handlers()

    storage_base = str(settings_port.get("storage.base_path", "/var/lib/bedrockpanel"))
    backup_base = str(settings_port.get("backup.base_path", f"{storage_base}/backups"))
    backup_repository = PostgresBackupRepository(session_factory)
    backup_deps = BackupDeps(
        repository=backup_repository,
        storage=LocalServerStorageResolver(spec_factory),
        store=LocalBackupStore(backup_base),
        console=console_facade,
        server=server_facade,
        bus=event_bus,
        ids=ids,
        time=time,
        settings=settings_port,
    )
    backup_facade = BackupFacade(backup_deps)
    backup_facade.register_handlers()

    template_repository = PostgresTemplateRepository(session_factory)
    template_root = f"{storage_base}/templates"
    template_deps = TemplateDeps(
        repository=template_repository,
        storage=LocalServerStorageResolver(spec_factory),
        world=WorldFacadeGateway(world_facade),
        config=configuration_facade,
        archive=TemplateArchiveStore(template_root),
        ids=ids,
        time=time,
        settings=settings_port,
    )
    template_facade = TemplateFacade(template_deps)

    monitoring_store = InMemoryMetricSampleStore()
    status_poller = StatusPoller(
        server=server_facade,
        runtime=runtime_port,
        probe=RakNetStatusProbe(),
        store=monitoring_store,
        time=time,
        settings=settings_port,
    )
    monitoring_facade = MonitoringFacade(
        status_poller,
        poll_interval=float(settings_port.get("monitoring.poll_interval_seconds", 5.0)),
    )
    background_poller = BackgroundPoller(
        monitoring_facade,
        interval=monitoring_facade.poll_interval,
    )

    scheduler_repository = PostgresSchedulerTaskRepository(session_factory)
    scheduler_deps = SchedulerDeps(
        repository=scheduler_repository,
        bus=event_bus,
        ids=ids,
        time=time,
        settings=settings_port,
        backup=backup_facade,
        server=server_facade,
    )
    scheduler_facade = SchedulerFacade(scheduler_deps)
    scheduler_facade.register_handlers()
    scheduler_poller = SchedulerPoller(
        scheduler_facade,
        interval=float(settings_port.get("scheduler.poll_interval_seconds", 5.0)),
    )

    noti_event_log = PostgresEventLogRepository(session_factory)
    notification_facade = NotificationFacade.build(
        access=iam_facade.access_control,
        event_log=noti_event_log,
        ids=ids,
        time=time,
        rate_config=RateLimitConfig(
            rate_per_second=float(settings_port.get("notification.rate_per_second", 100.0)),
            burst=int(settings_port.get("notification.burst", 100)),
        ),
        resume_limit=int(settings_port.get("notification.resume_limit", 1000)),
    )
    event_bus.subscribe("*", notification_facade.dispatcher.handler())

    return Container(
        settings=settings,
        database=database,
        docker_runtime=docker_runtime,
        event_bus=event_bus,
        server_facade=server_facade,
        server_repository=server_repository,
        console_facade=console_facade,
        console_stream=console_stream,
        iam_facade=iam_facade,
        player_facade=player_facade,
        permission_facade=permission_facade,
        world_facade=world_facade,
        backup_facade=backup_facade,
        monitoring_facade=monitoring_facade,
        monitoring_poller=background_poller,
        scheduler_facade=scheduler_facade,
        scheduler_poller=scheduler_poller,
        console_stream_reconciler=console_stream_reconciler,
        template_facade=template_facade,
        notification_facade=notification_facade,
    )
