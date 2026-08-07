# Change Log — Architecture Review v1.0

> **Fecha**: 2026-08-05
> **Alcance**: revisión final de la documentación del proyecto *BedrockPanel*.
> **Reglas cumplidas**: sin funcionalidades nuevas, sin cambio de alcance, sin modificar la
> arquitectura aprobada. El `technical-design.md` (TDD) permanece **intacto**.

---

## 1. Correcciones directas — `implementation-blueprint.md`

| Hallazgo | Sección(es) afectada(s) | Motivo del cambio | Referencia |
|---|---|---|---|
| **A1** | §1.3 (matriz), §3.2 (Server), §3.3 (World), §3.7 (Configuration) | Eliminada la dependencia circular `Server ↔ Configuration` y la `D` de *World → Configuration*: Server lee config deseada vía facade (unidireccional) y la aplicación se hace por evento `CONFIG.CHANGED`; activar/level-name por `WORLD.ACTIVATED`. | Architecture Review v1.0, hallazgo A1 |
| **A2** | §1.3 (matriz), §3.5 (Player) | Eliminada la dependencia circular `Player ↔ Permission`: Player ya no depende de Permission (solo evento `PLAYER.OPERATOR_CHANGED`); Permission conserva la facade `Player` para XUID (unidireccional). | Architecture Review v1.0, hallazgo A2 |
| **M1** | §4.1 (contrato `ServerRuntimePort`) | Documentado el mapeo explícito entre `RuntimeState` (infraestructura) y `ServerState` (dominio); el dominio jamás ve `RuntimeState` en crudo. | Architecture Review v1.0, hallazgo M1 |
| **M5** | §1.3 (matriz), §3.5 (Player) | Player ahora depende de `Console facade` (ban/unban/kick), su mecanismo real de ejecución de bans en-juego. | Architecture Review v1.0, hallazgo M5 |
| **B5** | §3.11 (Template) | Excepción documentada de forma explícita: operaciones de plantilla síncronas request/response, sin eventos; Notification no difunde resultados de plantilla (futuro `TEMPLATE.*` vía ADR). | Architecture Review v1.0, hallazgo B5 |
| **B6** | §3.13 (Settings) | Eliminada la alternativa ambigua "si aplica"; Settings no publica eventos de dominio, los cambios se auditan vía IAM. | Architecture Review v1.0, hallazgo B6 |
| **B7** | §6.1 (Creación) | Nota multi-instancia: `ENABLE_LAN_VISIBILITY=false` por defecto en el `RuntimeSpec` para evitar binds 19132/19133 y conflictos. | Architecture Review v1.0, hallazgo B7 |

> Consistencia adicional: §3.3 (World) declara `Console facade` para el export con `save hold`,
> alineando la matriz con el flujo ya definido en §7.6. No añade funcionalidad.

---

## 2. Nuevo documento — `docs/adr.md` (ADR-001 … ADR-009)

| ADR | Hallazgo | Estado | Motivo del cambio |
|---|---|---|---|
| ADR-001 | **M2** | Proposed | Calendarización del Outbox durable: Fase A solo bus en proceso; outbox en Fase 2 (alineado al TDD §7.1/§17). |
| ADR-002 | **M3** | Proposed | Gateway WebSocket mínimo en Fases B/D; capacidades avanzadas en Fase H (cumple el MVP del TDD §17). |
| ADR-003 | **M4** | Accepted | `last_ip` enmascarada por defecto + setting `player.store_full_ip` (privacidad vs TDD §15.5). |
| ADR-004 | **M6** | Proposed | `ConfigProfile` ampliado: `applied`, `applied_at`, `version` + historial `config_history` (TDD §15.2/§15.9). |
| ADR-005 | **B1** | Proposed | Catálogo de eventos con una sola fuente (blueprint §9 canónico; TDD §7.2 → referencia + test de paridad). |
| ADR-006 | **B2** | Accepted | Eliminado el kind de backup `auto-mvp` (concepto huérfano en TDD §8.1). |
| ADR-007 | **B3** | Accepted | Auditoría como sub-API de IAM (`/iam/audit`); no es módulo/dominio propio (TDD §12). |
| ADR-008 | **B4** | Accepted | Notación del mapa de dependencias: flechas = "depende de"; Template corregida (TDD §5.3). |
| ADR-009 | **B8** | Accepted | Formato canónico de `allowlist.json` con `ignoresPlayerLimit` opcional (análisis §2.5/§6.4). |

> Los ADR *Accepted* documentan decisiones aceptadas cuyo reflejo en el TDD/análisis queda
> programado para la siguiente versión de esos documentos (inmutables en esta revisión).

---

## 3. Documentos NO modificados

| Documento | Estado | Motivo |
|---|---|---|
| `technical-design.md` (TDD) | **Intacto** | Inmutable por decisión del proyecto; los hallazgos que le afectan se registran en ADR. |
| `analisis-proyecto-base.md` | **Intacto** (salvo correcciones previas A1/A2 de la revisión anterior) | Los hallazgos pendientes (B8) se registran en ADR-009. |

---

## 4. Pendientes para considerar Architecture Release Candidate v1.0

1. Resolver/aceptar los ADR **Proposed** (ADR-001, ADR-002, ADR-004, ADR-005) y aplicar su
   impacto en el blueprint cuando se acepten.
2. Aplicar en la siguiente versión del TDD las actualizaciones referidas en ADR-003…ADR-009.
3. Validar la consistencia final de §9 (catálogo) y §1.3 (matriz) tras los cambios.

---

## 5. FASE A — Registro de decisiones de implementación

> **Fecha**: 2026-08-06
> **Alcance**: implementación de la FASE A (`ServerRuntimePort` → `DockerRuntimeAdapter`,
> un único contenedor, docker-py). El `implementation-blueprint.md` **no** se modifica; las
> decisiones de implementación se registran aquí.

| Decisión | Detalle |
|---|---|
| **Contrato §4.1 intacto** | `ServerRuntimePort` no se extiende. Los 10 métodos de la FASE A (`start`/`stop`/`restart`/`status`/`exists`/`is_running`/`logs`/`remove`/`create_if_missing`/`inspect`) viven en la clase concreta `DockerRuntimeAdapter`. |
| **Adapter implementa §4.1** | `DockerRuntimeAdapter` implementa además los 13 métodos del contrato (`materialize`, `get_state`, `get_health`, `get_resources`, `get_exit_code`, `stream_logs`, `send_stdin`, `wait_for`, `signal`) de forma **estructural** (no hereda el Protocol). |
| **`runtime_id` opcional** | En FASE A (contenedor único) los `runtime_id` de los métodos §4.1 son opcionales: si se omiten o coinciden con `Settings.container_name`, se opera sobre el contenedor gestionado; si difieren → `ContainerNotFoundError`. `send_stdin`/`signal` mantienen `runtime_id` obligatorio (posicional con segundo parámetro requerido). |
| **DTOs en Infrastructure** | `RuntimeStatus` y `RuntimeInspect` viven en `infrastructure/runtime/status.py` (sin tipos del SDK Docker). |
| **`stream_logs` divergencia de tipado** | El Protocol declara `BinaryIO`; el adapter devuelve `Iterator[bytes]` (lo que docker-py produce). Se reconcilia en la Fase B cuando Console consuma el port. |
| **Mapeo de errores** | `docker.errors.*` → kernel (§11.1): `NotFound`→`ContainerNotFoundError`, `ImageNotFound`/404-en-create→`ImageNotFoundError`, `APIError 409`→`PortInUseError`, `APIError 403`→`DockerError` (permisos), timeout→`DockerTimeoutError`, conexión→`DockerError` retryable. |
| **Volúmenes** | `data_volume`→`/data` y `world_volume`→`/data/worlds` (montajes por defecto; vacíos se omiten). |
| **Integración opt-in** | Marker `integration`; por defecto excluidas (`addopts = -m 'not integration'`); se saltan si el daemon no responde o no hay red. |
| **mypy + docker-py** | docker-py 7.2 no distribuye `py.typed`; override `ignore_missing_imports` para `docker.*` (único consumidor: el adapter). |

---

## 6. FASE A — Archivos creados/modificados

### Creados
| Archivo | Contenido |
|---|---|
| `apps/backend/src/app/infrastructure/runtime/settings.py` | `DockerRuntimeSettings` (Pydantic Settings, prefijo `BEDROCK_PANEL_DOCKER_`). |
| `apps/backend/src/app/infrastructure/runtime/status.py` | DTOs `RuntimeStatus` y `RuntimeInspect`. |
| `apps/backend/src/app/infrastructure/runtime/docker.py` | `DockerRuntimeAdapter` (docker-py). |
| `apps/backend/tests/test_runtime.py` | Pruebas unitarias con mocks (35 casos). |
| `apps/backend/tests/test_runtime_integration.py` | Pruebas de integración (opt-in, daemon real). |

### Modificados
| Archivo | Cambio |
|---|---|
| `apps/backend/src/app/infrastructure/runtime/__init__.py` | Re-exporta adapter, settings y DTOs. |
| `apps/backend/src/app/bootstrap/container.py` | DI: `Container.docker_runtime` + `build_container()` (sin singletons). |
| `apps/backend/pyproject.toml` | Marker `integration`, `addopts` de exclusión, `filterwarnings` de starlette/httpx, override mypy para `docker.*`. |

### Sin cambios (por regla)
| Archivo | Motivo |
|---|---|
| `kernel/ports/runtime.py` (contrato §4.1) | Decisión registrada en §5. |
| `kernel/errors.py`, `technical-design.md`, `implementation-blueprint.md` | Inmutables en esta fase. |

---

## 7. Hardening FASE A — registro de cambios

> **Fecha**: 2026-08-06
> **Alcance**: endurecimiento de la FASE A para dejarla lista para producción
> desde el punto de vista arquitectónico. Sin funcionalidades nuevas; el
> contrato §4.1 y el TDD **no** se modifican.

### Cambios
| # | Cambio | Motivo | Impacto | Compatibilidad |
|---|---|---|---|---|
| 1 | Nuevo `infrastructure/runtime/client_factory.py`: `DockerClientFactory` (Protocol) + `DockerFromEnvClientFactory` (encapsula `docker.from_env()` / `DockerClient(base_url=…)`, `timeout` y `version`). | El adapter **nunca** crea clientes directamente; la construcción queda aislada y mockeable; permite endpoints tcp/ssh/unix y futuras implementaciones (podman, etc.). | `DockerRuntimeAdapter` ya no llama a `docker.from_env()`. | Retrocompatible: `DockerRuntimeAdapter` solo cambia el constructor (ver #4). |
| 2 | Traducción de errores de construcción en el factory: `DockerException`→`DockerError` (detecta `PermissionError` en la cadena `__cause__`/`__context__`/`args` → `retryable=False`), `PermissionError` nativo→`DockerError` no retryable, `OSError`→`DockerError` retryable. | El constructor de `DockerClient` es *eager* (negocia la versión de la API al instanciar) y docker-py envuelve el `PermissionError` del socket en `DockerException`. | Errores de init normalizados y no retryable cuando son de permisos. | Sin cambios de API. |
| 3 | `docker.py` ahora recibe `docker_client_factory: DockerClientFactory` (inyectado) y cachea el cliente en `_client()`. | Requisito de DI: el adapter depende de la interfaz, no de la implementación. | Cliente creado una sola vez (lazy). | **Constructor cambiado**: `docker_client=` → `docker_client_factory=`; afecta a `container.py` y tests (actualizados). |
| 4 | Loggers vía `kernel.logging.get_logger(__name__)` (namespace `app.*`) en vez de `logging.getLogger`. | Centraliza la política §12; el adapter no configura sus propios loggers. | Los eventos de runtime se emiten bajo `app.infrastructure.runtime.docker`. | Sin cambios de API. |
| 5 | DTOs: campo `oom_killed: bool` en `RuntimeStatus` (poblado desde `State.OOMKilled`; `RuntimeInspect` lo hereda vía `status`). | Auditoría de OOM (requisito del hardening): el daemon no lanza excepción por OOM; se expone en el estado. | `RuntimeStatus` gana un campo obligatorio al instanciarse (construcción posicional). | Para consumidores posicionales es breaking; se documenta como evolución del DTO de FASE A (aún sin consumidores externos). |
| 6 | `_translate_docker_exc`/`_map_docker_errors`/`exists()` cubren `PermissionError` y `OSError` nativos (tras `requests.*`, que son subclases de `OSError`). | Ninguna excepción del transporte escapa de Infrastructure. | `PermissionError`→`DockerError` no retryable; `OSError`→`DockerError` retryable. | Sin cambios de API. |
| 7 | `DockerRuntimeSettings.docker_timeout: int = 300` (env `BEDROCK_PANEL_DOCKER_DOCKER_TIMEOUT`). | El timeout del cliente Docker es configurable y el DI lo usa. | Cliente con timeout explícito (antes default de docker-py). | Nuevo campo con default; retrocompatible. |
| 8 | DI (`container.py`): `build_container()` construye `DockerFromEnvClientFactory(timeout=runtime_settings.docker_timeout)` e inyecta el factory. | Registro por DI sin singletons. | — | Sin cambios de API. |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ · `uv run mypy --strict` ✅ (107 archivos) · `uv run pytest -q` ✅ (45 passed, 1 deselected).
- Capas: Infrastructure no importa Application; Domain no importa Infrastructure; kernel sin dependencias internas de app.
- Único `docker.from_env()` en producción: dentro del factory (y el probe del fixture de integración).

### Pendiente / deuda
- La integración real con daemon se ejecutará en un host con acceso (aquí se salta por `PermissionError` en el socket).
- ~~`stream_logs` → `Iterator[bytes]` vs `BinaryIO` del Protocol~~ → resuelto en §9 (corrección previa al Paso 7).
- Si la auditoría de DTOs exigiera tipado posicional estable, valorar `kw_only=True` o defaults en una revisión posterior (propuesta, sin tocar TDD).

---

## 8. FASE B — paso 6: Módulo Server (núcleo) — registro de decisiones

> **Fecha**: 2026-08-06
> **Alcance**: construcción del núcleo del módulo Server (dominio + casos de
> uso + facade + eventos + tests) conforme al Blueprint §3.2, §6 y §16.3. El
> TDD no se modifica; el paso se cierra aquí sin avanzar a Console (paso 7).
> Esta fase crea además el bus en proceso compartido y adaptadores comunes de
> ids/time/settings que usarán los siguientes módulos.

### Decisiones de implementación
| # | Decisión | Detalle |
|---|---|---|
| 1 | `ServerState` no se re-declara en el dominio | Ya existe en `kernel/ports/runtime.py` (StrEnum §16.3). El dominio lo consume; la máquina de estados (`state_machine.py`) valida transiciones y lanza `SERVER.INVALID_STATE`. |
| 2 | `RuntimeState` nunca llega en crudo al dominio | `domain/state_mapping.py` es el único punto de traducción runtime→dominio. La detección de `crashed` es contextual: salida **no solicitada** (`requested_stop=False`) desde `stopped`/`absent` → crash (TDD §6.2). |
| 3 | Entidad con transiciones validadas + use cases que coordinan | La entidad `Server` valida cada transición (`assert_can_transition`); los use cases coordinan puertos. Servidor anémico en el buen sentido: identidad/spec/estado, sin lógica de infraestructura. |
| 4 | Facade pública = `lifecycle`, `applyConfig`, `changeVersion` | Blueprint §3.2. `mark_started`/`mark_crashed` quedan expuestos para el futuro Monitoring (probe §6.2); son transiciones de estado, no comandos de usuario. |
| 5 | `applyConfig` NO invoca a Configuration | Entrada por evento `CONFIG.CHANGED` (handler → `ApplyConfigUseCase`). El módulo solo **lee** la config deseada vía `ConfigurationReader` (puerto de aplicación) — unidireccional, §3.2. |
| 6 | `ConfigurationReader` y `TemplateReader` como puertos internos | El módulo no importa la facade Configuration (aún es esqueleto). El bootstrap registra `DefaultConfigurationReader` (config vacía + versión default de Settings) como placeholder hasta la Fase D (paso 10, Configuration). |
| 7 | Recreación = parar (si corre) → materialize → arrancar, serializada | `OperationGuard` (en proceso) rechaza operaciones concurrentes sobre el mismo servidor (§6.4/§16.3). `_recreate` preserva el estado si no estaba corriendo (STOPPED sigue STOPPED). |
| 8 | RuntimeSpec renderizado por `RuntimeSpecFactory` | Defaults desde SettingsPort (imagen, tag, TZ, storage, recursos) + env de Configuration + asignación de puertos desde pool con detección de conflicto (`PortAllocator`, §16.3) + hallazgo B7: `ENABLE_LAN_VISIBILITY=false` por defecto. |
| 9 | `InProcessEventBus` compartido en `infrastructure/events` | ADR-001: difusión síncrona en `publish`, `consume` no-op (sin outbox, Fase 2). Temas §10.3: `server.*` comodín, `config.changed`/`world.activated` exactos. |
| 10 | `InMemoryServerRepository` en `modules/server/infrastructure` | Núcleo sin BBDD; implementación durable (SQLite/Postgres) llegará con el storage del panel. `SERVER.NOT_FOUND` para get requerido. |
| 11 | `DockerRuntimeAdapter` cumple estructuralmente `ServerRuntimePort` | Tras alinear `stream_logs` (§9), la asignación directa `runtime_port: ServerRuntimePort = docker_runtime` pasa `mypy --strict` sin `cast`. |
| 12 | Adaptadores comunes: ids/time/settings | `UuidIdGenerator` (UUID v4 portable; kernel prefiere v7 → Python 3.14), `SystemTimeProvider`, `EnvSettingsAdapter` (puente a `Settings`/env hasta Fase H). |
| 13 | ADR-010 promovido a **Accepted** | Refuerza la decisión de factory del lado del adaptador. |
| 14 | Restart no duplica eventos | Reiniciar desde `stopped`/`crashed` no re-publica `SERVER.STOPPED`; solo `SERVER.STARTING`. |

### Archivos
| Archivo | Descripción |
|---|---|
| `modules/server/domain/{errors,state_machine,state_mapping,events,server,repository}.py` | Dominio: errores `SERVER.*`, máquina de estados, mapeo runtime, eventos, entidad `Server`+`ServerId`, puerto `ServerRepositoryPort`. |
| `modules/server/application/{ports,commands,results,spec_factory,use_cases,queries,handlers,facade}.py` | Aplicación: puertos `ConfigurationReader`/`TemplateReader`, comandos, vistas, factory de spec, 9 use cases, queries, handlers `CONFIG.CHANGED`/`WORLD.ACTIVATED`, facade pública. |
| `modules/server/infrastructure/{repository,config}.py` | Repo en memoria y `DefaultConfigurationReader`. |
| `infrastructure/events/bus.py` | `InProcessEventBus` compartido (Fase B). |
| `infrastructure/common/{settings,ids,time}.py` | Adaptadores `SettingsPort`/`IdGeneratorPort`/`TimeProviderPort`. |
| `bootstrap/container.py` | Wire de `ServerFacade` + handlers + bus + repo. |
| `tests/{conftest,test_inprocess_event_bus,test_server_state_machine,test_server_state_mapping,test_server_entity,test_server_use_cases,test_server_handlers,test_server_facade}.py` | 58 tests nuevos (total 105). |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ · `uv run mypy --strict` ✅ (135 archivos) · `uv run pytest -q` ✅ (105 passed, 1 deselected).
- Capas: Domain no importa Application/Infrastructure; Application no importa Infrastructure; sin `cast` en el boundary de DI (§9).

### Pendiente / deuda
- `TemplateReader` sin implementación ni uso todavía (se cableará con la facade Template en su fase).
- Persistencia durable del agregado `Server` (hoy en memoria).
- Monitoring (probe/`StatusProbePort`) será quien confirme `running` y registre crashes en producción; hoy existen `mark_started`/`mark_crashed` en la facade.
- Backups/Notification reaccionarán a `SERVER.*` cuando existan sus módulos.
- **No avanzar al paso 7 (Console)** sin confirmación del usuario.

---

## 8.1. Corrección de implementación — arranque con binario Bedrock local

> **Fecha**: 2026-08-06
> **Alcance**: ajuste menor del paso 6 del módulo Server (runtime-spec) para
> evitar descargas innecesarias al arrancar Bedrock cuando ya existe el binario
> local en el volumen `/data`. No modifica el contrato §4.1 ni el TDD; se trata
> de una corrección de comportamiento dentro de la fase ya implementada.

| Cambio | Motivo | Impacto | Compatibilidad |
|---|---|---|---|
| `RuntimeSpecFactory` detecta `bedrock_server-<version>` o `bedrock_server` en rutas de datos probables y fija `VERSION=EXISTING` | Evitar que el contenedor intente descargar de nuevo el servidor cuando el binario ya está presente y así reducir fallos por descarga/SSL | El runtime usa el binario local existente y no fuerza una descarga en arranque | Sin cambios de API ni de arquitectura; el resto del flujo sigue igual |

### Verificación
- `uv run pytest tests/test_server_use_cases.py tests/test_port_allocator.py` ✅ (22 passed)

---

## 8.2. Corrección de implementación — modo offline/local y exposición en nube

> **Fecha**: 2026-08-06
> **Alcance**: endurecimiento del runtime Bedrock para uso local y para
> despliegues que luego se expongan en la nube mediante proxy/túnel. No cambia
> el contrato §4.1 ni el TDD; solo ajusta el comportamiento del `RuntimeSpec`.

| Cambio | Motivo | Impacto | Compatibilidad |
|---|---|---|---|
| `RuntimeSpecFactory` deja por defecto `ONLINE_MODE=false` y `ENABLE_LAN_VISIBILITY=true` | Evitar que el servidor dependa de Minecraft Services al arrancar y hacer que el servidor sea más accesible desde la LAN/local network | El servidor arranca en modo local/privado y es visible para clientes Bedrock en la red local | Sin cambios de API; el valor puede seguir sobreescribirse desde settings si se necesita un comportamiento distinto |
| Documentación de exposición en nube | Explicar que Bedrock requiere UDP `19132/19133` y que un proxy web estándar no es suficiente para gameplay | El despliegue en nube solo es viable con un túnel/forwarding que preserve UDP | Compatible con el flujo actual; no modifica la arquitectura |
| Recurso configurable | Permitir ajustar `server.resources.memory_mb` y `server.resources.cpus` para mundos pesados o arranques lentos | Mejor rendimiento si el mundo o el historial de datos crece | Sin cambios de API; solo ajustes de settings |

### Verificación
- `uv run pytest tests/test_server_use_cases.py tests/test_port_allocator.py` ✅ (24 passed)

---

## 9. Correcciones previas al Paso 7 (Console)

> **Fecha**: 2026-08-06
> **Alcance**: alinear el contrato ``ServerRuntimePort`` con la implementación
> real de FASE A y corregir la atribución de fase de Configuration. Cambio de
> tipado únicamente; no altera comportamiento ni el resto del contrato.

### Cambios
| # | Cambio | Motivo | Impacto |
|---|---|---|---|
| 1 | `kernel/ports/runtime.py` §4.1: `stream_logs(self, runtime_id: str) -> Iterator[bytes]` (era `BinaryIO`). | El adaptador ya produce `Iterator[bytes]` (`container.logs(stream=True, …)` de docker-py); el `BinaryIO` era un tipo incorrecto en el contrato. | Cambio de firma del contrato; sin cambios de comportamiento. Consumidores del puerto (Console) usarán `Iterator[bytes]`. |
| 2 | `bootstrap/container.py`: eliminado `cast(ServerRuntimePort, docker_runtime)`. | Tras el ajuste, `DockerRuntimeAdapter` es estructuralmente `ServerRuntimePort` (verificado con `mypy --strict`: asignación directa sin errores). | Se retira el único `cast` de la DI. |
| 3 | `runtime_id` opcionales del adapter: **compatibles, sin cambios en el Protocol**. | El Protocol declara `runtime_id: str` (obligatorio); el adapter usa `runtime_id: str | None = None` (decisión FASE A: opcional si coincide con `Settings.container_name`). Los tipos de parámetros son contravariantes: un implementador que acepta `str \| None` cubre toda llamada con `str`. Solo `stream_logs` rompía la conformidad (por el tipo de retorno). | Sin cambios en el contrato; se documenta la conformidad por contravariance. |
| 4 | `DefaultConfigurationReader` / change-log §8.6: "hasta la Fase C" → "hasta la Fase D". | Configuration es el paso 10 (Fase D); la Fase C es solo IAM (Blueprint §2). | Corrección de documentación/comentario. |
| 5 | change-log §8.10 y `repository.py`: referencia a "storage (Fase C)" → "storage del panel". | La Fase C es solo IAM; la persistencia durable no tiene fase asignada explícita en el Blueprint. | Corrección de documentación/comentario. |
| 6 | Cobertura: `test_stream_logs_returns_iterador_de_bytes` en `test_runtime.py`; fake de tests alineado a `Iterator[bytes]`. | Verificar el retorno corregido del contrato. | 106 tests en total. |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ · `uv run mypy --strict` ✅ (135 archivos) · `uv run pytest -q` ✅ (106 passed, 1 deselected).
- Confirmado: `ServerRuntimePort` ya no requiere `cast` para `DockerRuntimeAdapter` (asignación directa en `container.py` sin `mypy` errores).

---

## 10. FASE B — paso 7: Módulo Console — registro de decisiones

> **Fecha**: 2026-08-06
> **Alcance**: construcción del módulo Console (dominio + casos de uso + facade
> + adaptador de streaming + parser declarativo + tests) conforme al Blueprint
> §3.8, §6 y §16.9. Reutiliza `ServerRuntimePort` (sin `cast`, §9) y la facade
> Server solo en modo lectura. No avanza a IAM (paso 8) sin confirmación.

### Decisiones de implementación
| # | Decisión | Detalle |
|---|---|---|
| 1 | Errores `CONSOLE.*` reutilizados del kernel (§11.1) | La taxonomía ya vivía en `kernel/errors.py` (Blueprint §11.1); `domain/errors.py` la re-exporta como único punto de importación del módulo. No se crearon códigos nuevos. |
| 2 | Entidad mínima `ConsoleLog` (buffer anillo) | Líneas con `seq` monótono y límite configurable (`console.buffer_max_lines`, default 1000). El `seq` habilita streaming idempotente: `since(after_seq)` / `tail(count)` con semántica `count<=0 → []`. |
| 3 | Cola por servidor con prioridad (`CommandQueue`) | `heapq` por servidor ordenado por `(CommandPriority.order, seq)` + `asyncio.Lock` por servidor (mismo criterio de serialización que `OperationGuard`; aquí **no se rechaza**, se encola: concurrencia de comandos es normal). `await asyncio.sleep(0)` antes del drenado agrupa las suscripciones del mismo tick para que la prioridad reordene el batch. |
| 4 | Console no valida comandos | Solo comprueba identidad/estado del servidor (facade Server read-only): no corre → `CONSOLE.SERVER_OFFLINE`; vacío → `CONSOLE.COMMAND_REJECTED` (defensivo). El contenido no se interpreta. |
| 5 | `ServerConsoleReader` como puerto de aplicación | Protocol de solo lectura devuelto por `ServerFacade.get_server` (conformidad estructural). Console nunca modifica Server. |
| 6 | Streaming = router + suscripción con cursor | `ConsoleOutputRouter` reparte `CONSOLE.OUTPUT` con backpressure (cola acotada; si está llena se descarta la línea entrante, el cursor resincroniza). `ConsoleSubscription.stream()` reproduce el buffer desde `after_seq` (acotado al `high_water_mark` capturado al suscribir) y sigue en vivo sin duplicados. |
| 7 | Adaptador de streaming `ConsoleLogStream` | Consume `ServerRuntimePort.stream_logs` (`Iterator[bytes]`), normaliza líneas (UTF-8 `errors="replace"`, quita `\r`, descarta vacías/solo-espacios) y publica un `CONSOLE.OUTPUT` por línea. `runtime_id=None` → `CONSOLE.UNAVAILABLE`. |
| 8 | `WORLD.SAVED` por parser declarativo externo | `infrastructure/parsers/save_detector.py` (path del Blueprint §5.2) es un consumidor de `console.output`: reconoce patrones de guardado completado y publica `WORLD.SAVED` sin interpretar semántica. No confunde `save hold`/`save resume`. |
| 9 | `TASK.STARTED` cableado de forma defensiva | `TaskStartedHandler` lee `commands` (lista o string único) del payload y los envía con prioridad NORMAL; sin `server_id` o sin comandos no hace nada. No falla aunque Scheduler (Fase G) aún no exista. |
| 10 | Buffer en memoria (`InMemoryConsoleLogStore`) | Mismo criterio que `InMemoryServerRepository`: durabilidad con el storage general (Fase C). El puerto es `async` para swap futuro sin tocar consumidores. |
| 11 | Parsers y stream NO auto-iniciados | El stream del contenedor se expone en `Container.console_stream` pero su ciclo de vida (arrancar/parar con `SERVER.*`) se cableará cuando exista el supervisor de tareas (Fase H/operaciones). |

### Archivos
| Archivo | Descripción |
|---|---|
| `modules/console/domain/{errors,events,command,console_log,repository}.py` | Re-exporta `CONSOLE.*`, factory de eventos (`CONSOLE.COMMAND_SENT`/`CONSOLE.OUTPUT`/`WORLD.SAVED`), `CommandPriority`, agregado `ConsoleLog`+`ConsoleLine`, puerto `ConsoleLogStorePort`. |
| `modules/console/application/{ports,commands,results,queue,streaming,use_cases,handlers,facade}.py` | `ServerConsoleReader`, `SendCommand`, `CommandAck`/`BufferView`, `CommandQueue` (cola con prioridad), router+suscripción de streaming, `ConsoleDeps` + 3 use cases, `TaskStartedHandler`, facade pública. |
| `modules/console/infrastructure/{buffer,stream}.py` | `InMemoryConsoleLogStore` y `ConsoleLogStream` (runtime → buffer + `CONSOLE.OUTPUT`). |
| `infrastructure/parsers/save_detector.py` | Parser declarativo de líneas de guardado → `WORLD.SAVED` (Blueprint §5.2/§7.3). |
| `bootstrap/container.py` | Wiring de Console: store, cola, router, facade, parser y stream; `Container` gana `console_facade` y `console_stream`. |
| `tests/{conftest,test_console_log,test_console_use_cases,test_console_handlers,test_console_facade,test_console_stream}.py` | `FakeServerReader`, `FakeRuntime` ampliado (`stdin_writes`, `log_lines`) + 34 tests nuevos. |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ · `uv run mypy --strict` ✅ (156 archivos) · `uv run pytest -q` ✅ (**140 passed**, 1 deselected; antes 106 → +34).
- Capas: Domain no importa Application/Infrastructure; Application no importa Infrastructure; Console importa Server solo vía `ServerConsoleReader` (read-only).
- Wire del contenedor verificado: topics suscritos `config.changed`, `world.activated` (Server) + `console.output`, `task.started` (Console).

### Pendiente / deuda
- **Hallazgo C1 (verificar con BDS real)**: los patrones de línea de guardado del `SaveDetector` (`save complete`, `saved the game`, `autosave complete/finished`) son conservadores; el formato exacto de BDS bedrock debe confirmarse en un host real (mismo criterio que el hallazgo B7).
- Ciclo de vida del stream (arrancar/parar con `SERVER.*`) pendiente del supervisor de tareas (Fase H).
- `WORLD.SAVED` aún sin consumidores (Backup/Notification llegarán en sus fases).
- **No avanzar al paso 8 (Fase C — IAM)** sin confirmación del usuario.

---

## 11. FASE A — paso 2 (corrección): capa de persistencia + migración de Server y Console

> **Fecha**: 2026-08-06
> **Alcance**: implementación del paso 2 de Fase A que quedó pendiente (Bluepring
> §2): Postgres + SQLAlchemy async + Alembic con migraciones por módulo, patrón de
> repositorios. Se migran los módulos **Server** y **Console** de los repositorios
> en memoria a Postgres sin tocar los puertos de dominio ni las capas. IAM (paso 8)
> queda intacto; nacerá directamente sobre Postgres. El paso 3 (módulo Settings) se
> **difiere** (ver decisión 6) y se documenta, no se implementa en silencio.

### Decisiones de implementación
| # | Decisión | Detalle |
|---|---|---|
| 1 | Driver **`psycopg` v3** (async) en lugar de `asyncpg` | Una misma URL `postgresql+psycopg://` sirve para Alembic (síncrono) y para la app (`create_async_engine`); `alembic.ini` y `BEDROCK_PANEL_DATABASE_URL` no cambian. Pool con `pool_pre_ping` y parámetros configurables por env. |
| 2 | Migraciones **por módulo** con prefijo de tabla | `0001_server_servers` (Server) y `0002_console_lines` (Console) como revisiones independientes; `iam_*` llegará con la Fase C. `env.py` reescrito a async y registra los modelos de cada módulo en `target_metadata` (autogenerate consistente: el DDL compilado de los modelos coincide con el SQL de las migraciones). |
| 3 | `PostgresServerRepository` con **upsert** (`ON CONFLICT (id) DO UPDATE`) | El agregado `Server` es la autoridad del estado; cada operación usa una sesión del pool (una sesión por operación). `RuntimeSpec` se serializa a `jsonb` con columnas desnormalizadas `image`/`tag`/`version` para consulta (TDD §15.2). La serialización vive aislada (`serialization.py`) y es testeable sin BBDD. |
| 4 | **`ConsoleLogWriter`** (nuevo contrato de infraestructura) sobre el puerto de dominio | El path de escritura (stream → buffer) necesita `append`, que el puerto `ConsoleLogStorePort` no declara. Se añade un Protocol **en infraestructura** (no se toca el puerto de dominio); la aplicación sigue dependiendo del puerto. `ConsoleLogStream` usa el writer; `InMemoryConsoleLogStore` lo implementa (test unitarios intactos). |
| 5 | Console: **retención acotada y agresiva en DB** (criterio explícito) | La salida de consola es telemetría transitoria, no auditoría. El buffer caliente sigue siendo el anillo en memoria (misma semántica de streaming); `PostgresConsoleLogStore` persiste cada línea con su `seq` y recorta (`DELETE`) periódicamente las filas antiguas al límite (`console.buffer_max_lines`, default 1000). La rehidratación usa `ConsoleLog.from_records`, que preserva `seq` y continúa la numeración tras reinicio (streaming idempotente por cursor). No se persiste el histórico completo. |
| 6 | **Settings real (paso 3 de Fase A) DIFERIDO** — reportado como decisión | `EnvSettingsAdapter` sigue siendo el puente temporal. Razones: el módulo Settings (tabla `Setting` + defaults globales + cambios solo-admin) es un módulo con API/auditoría que pertenece a su propio paso/Fase H; crearlo aquí sería premature. Lo que **sí** se hace ahora: la configuración de conexión (URL + pool) es config propia del bootstrap (`BEDROCK_PANEL_DATABASE_URL` + `db_*` en `bootstrap/config.py`), que no es el módulo Settings sino la config de infraestructura del backend. |
| 7 | Conexión perezosa | `Database` construye el engine sin abrir socket; `build_container()` y el arranque de la app funcionan sin BBDD. El ciclo de vida (`dispose`) se cableará con el shutdown de la app (paso de operaciones). |
| 8 | Implementaciones en memoria **se conservan** | `InMemoryServerRepository` e `InMemoryConsoleLogStore` se mantienen para tests (los tests de facade/use cases siguen usándolas); el wiring de producción ahora inyecta las Postgres. |

### Archivos
| Archivo | Descripción |
|---|---|
| `infrastructure/db/session.py` | `Database` + `DatabaseSettings`: engine async (psycopg), `async_sessionmaker`, pool configurable, `dispose`. |
| `infrastructure/db/alembic/env.py` | Migraciones online async; registra modelos por módulo. |
| `infrastructure/db/alembic/versions/0001_server_servers.py` | Tabla del agregado `Server` (prefijo `server_*`). |
| `infrastructure/db/alembic/versions/0002_console_lines.py` | Tabla de líneas de consola (prefijo `console_*`). |
| `modules/server/infrastructure/{models,serialization,postgres_repository}.py` | `ServerRow`, mapeo `Server` ↔ fila (jsonb + desnormalizados), `PostgresServerRepository`. |
| `modules/console/infrastructure/{store,models,postgres_store}.py` | `ConsoleLogWriter`, `ConsoleLineRow`, `PostgresConsoleLogStore` (persistencia + retención acotada). |
| `modules/console/domain/console_log.py` | Añade `ConsoleLog.from_records` (rehidratación con `seq` continuo). |
| `modules/console/infrastructure/{buffer,stream}.py` | `InMemoryConsoleLogStore.append`; stream pasa a usar `ConsoleLogWriter`. |
| `bootstrap/container.py` | `Container` gana `database`; `server_repository` tipado al puerto; wiring → Postgres. |
| `bootstrap/config.py` | Campos `database_url` y pool (`db_*`). |
| `pyproject.toml` | Dep `psycopg[binary]>=3.2`. |
| `tests/` | Unitarios: `test_console_log` (+from_records), `test_console_store`, `test_server_serialization`. Integración opt-in: `test_server_postgres_repository_integration.py`, `test_console_postgres_store_integration.py` + fixture `db_session_factory` (drop/create por test). |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ · `uv run mypy --strict` ✅ (169 archivos).
- `uv run pytest -q` ✅ (**151 passed**, 10 deselected; antes 140 → +11 unitarios).
- `uv run pytest -m integration` ✅ **9 passed, 1 skipped** (runtime/Docker sin daemon) ejecutados contra **Postgres real** (cluster temporal `initdb` en localhost:5433): round-trip de Server (save/get/upsert/list), console (append/hydrate/retención/servidores independientes) y **Alembic upgrade head / downgrade base** validados end-to-end. Sin BBDD disponible: 10 skipped limpio (verificado antes de arrancar el cluster).
- Capas intactas: Domain no importa Infrastructure ni SQLAlchemy; `ConsoleLogStorePort` y `ServerRepositoryPort` sin cambios (migración de implementación, no de contrato). Tests existentes de Server/Console sin cambios y en verde.
- Hallazgo de fixture corregido durante validación: `create_all`/`drop_all` deben ir en `engine.begin()` (commit) — con `engine.connect()` el DDL se revertía y las tablas nunca existían.

### Pendiente / deuda
- **Paso 3 de Fase A (módulo Settings)**: diferido (decisión 6); `EnvSettingsAdapter` sigue como puente.
- **Outbox sobre Postgres (paso 5 de Fase A)**: no forma parte de este encargo; la infra de eventos sigue in-process (ADR-001).
- Ciclo de vida del `Database` (`dispose`, `alembic upgrade` en arranque/CI) pendiente de operaciones (Fase H).
- Batching de inserts de consola (optimización de volumen, p. ej. vía outbox) si el per-línea no escala — documentado como deuda, no implementado.
- **No avanzar al paso 8 (Fase C — IAM)** sin confirmación del usuario.

## 12. Paso operativo — Postgres real vía Docker (dev local)

> **Fecha**: 2026-08-06
> **Alcance**: paso operativo de infraestructura local (no Fase A/B/C): levantar un
> Postgres persistente con Docker para conectar el backend de desarrollo, aplicar las
> migraciones de la Fase A paso 2 (secciones 11/9) contra una BBDD real y verificar.
> El acceso al daemon Docker no está disponible desde el entorno de trabajo; el
> **usuario** levantó el contenedor y yo (agente) ejecuté la verificación y documentación.

### Qué se hizo
- **Usuario**: añadió el servicio `postgres` a `docker-compose.dev.yml` (imagen `postgres:16`,
  `container_name: bedrockpanel-postgres`, host port **5433**, volumen `bedrockpanel-pgdata`)
  y creó `apps/backend/.env` con `BEDROCK_PANEL_DATABASE_URL` real.
- **Agente** (sin tocar Docker):
  - Confirmó que `Settings` (pydantic, `env_file=".env"`) carga la URL de `.env`
    (override verificado: host `localhost`, puerto **5433**, db `bedrockpanel`).
  - Ejecutó `alembic upgrade head` contra la BBDD real → aplicadas `0001_server_servers` y
    `0002_console_lines` (cabecera `0002_console_lines`).
  - Verificó con conexión real (SQLAlchemy async + `information_schema.tables`): existen
    `server_servers`, `console_lines` y `alembic_version`.
  - Validó `build_container()` contra la base real: `server_repository` es
    `PostgresServerRepository` y el store de consola (facade/stream) es `PostgresConsoleLogStore`.
  - Hizo un roundtrip real de persistencia por el store del container: `append` de 2 líneas y
    `get` rehidratado con `seq` continuo (los `seq` 0–5 corresponden a los tres intentos
    acumulados en BBDD antes de la limpieza → rehidratación desde disco correcta). Filas de
    prueba borradas al terminar (BBDD queda limpia).
  - Creó `apps/backend/.env.example` (placeholders, sin credenciales reales; gitignore ya lo
    excluye de `.env.*` con `!.env.example`, por lo que se versiona).

### Hallazgo (reportado, no improvisado)
- `Settings` carga `.env` automáticamente (pydantic-settings), pero **`alembic/env.py` NO lee
  `.env`**: usa `os.getenv("BEDROCK_PANEL_DATABASE_URL")` del proceso. Para ejecutar migraciones
  contra la BBDD de `.env` se inyectó la URL desde `Settings` en el entorno del proceso (sin
  imprimir credenciales). No se alteró el código.

### Credenciales
- La contraseña real solo vive en `apps/backend/.env` (no versionado). En esta entrada se usa
  placeholder; no se documenta el valor.

### Verificación
- Migraciones aplicadas y verificables: `alembic_version = 0002_console_lines`.
- Roundtrip de persistencia real OK y limpio.
- No se avanzó a la Fase C (IAM); queda a la espera de confirmación del usuario.

## 13. Fase C — paso 8: módulo IAM (mínimo viable)

> **Fecha**: 2026-08-06
> **Alcance**: primer corte del módulo IAM sobre Postgres real: dominio (roles base,
> usuarios, membresías), aplicación (use cases de auth, RBAC+ACL, auditoría, handlers),
> infraestructura (argon2id, JWT+refresh opaco, sesiones y audit en Postgres), migración
> `0003_iam_tables`, wiring en container y tests. Queda diferido a Fase H: auditoría
> tamper-evident, 2FA, API keys y matriz de permisos por acción.

### Qué se hizo
- **Kernel**: `AccessControlPort.authenticate/authorize` ahora **async** (persisten en
  Postgres). Sin consumidores previos en `src/` ni `tests/` (cambio de contrato documentado
  en el propio módulo). Dependencias solo del kernel + `SettingsPort`/`EventBusPort`/
  `TimeProviderPort`/`IdGeneratorPort`.
- **Dominio** (`modules/iam/domain/`): `errors.py` (códigos `AUTH.*`/`IAM.*`),
  `role.py` (`BuiltinRole`: super_admin(4) > admin(3) > operator(2) > viewer(1), `Role`,
  `ServerMembership`), `user.py` (`User`, `UserStatus.ACTIVE/SUSPENDED`), `events.py`
  (`AUTH.LOGIN_SUCCESS/FAILED`, `IAM.USER_CREATED`, `IAM.USER_ROLE_CHANGED` + topics de
  incidentes), `repository.py` (`IamRepositoryPort` async).
- **Aplicación** (`modules/iam/application/`): `ports.py` (hasher, tokens, sesiones, audit),
  `commands.py`/`results.py`, `use_cases.py` (create/login/refresh rotativo/logout/assign),
  `access.py` (**`AccessControlService`**: RBAC global + ACL por servidor; admins globales
  acceden a cualquier servidor; operador/viewer solo a servidores con membresía, y la
  membresía es autoritativa para ese servidor — least privilege), `handlers.py` (audit
  defensivo: nunca corta el bus), `facade.py`.
- **Infraestructura** (`modules/iam/infrastructure/`): `password.py` (**argon2id**, verify
  sin excepciones), `tokens.py` (**JWT HS256** + refresh opaco con hash SHA-256, TTL/secret/
  issuer vía Settings), `postgres_repository.py`, `sessions.py`, `audit_store.py`,
  `memory.py` (solo tests), `models.py` (tablas `iam_*` **sin FKs a `server_servers`** para
  desacoplar bounded contexts).
- **Migración** `0003_iam_tables.py`: `iam_users`, `iam_user_roles`, `iam_server_memberships`,
  `iam_sessions` (índice único `token_hash`), `iam_audit_logs`; downgrade en orden inverso.
- **Corrección diferida desde §12**: `alembic/env.py` ahora lee `Settings.database_url`
  (pydantic carga `.env`) — misma fuente de verdad, sin duplicar parseo; **`alembic upgrade
  head` funciona sin inyección manual** (verificado end-to-end).
- **Wiring** `container.py`: `iam_facade` con `IamDeps` y `register_handlers()`.
- **Deps**: `argon2-cffi>=23.1`, `PyJWT>=2.8` (uv lock/sync, 55 paquetes).

### Hallazgos
- **Ambigüedad del design §14.2**: "Operador: operaciones sobre servidores asignados" vs.
  el modelo "nivel efectivo = max(global, membresía)". Se resolvió con **least privilege**
  (membresía autoritativa por servidor para operador/viewer; admins globales sin restricción)
  y se documentó en `access.py` y en la matriz de tests. Candidato a revisión en Fase H.
- **Fixture de integración**: default `panel:panel@localhost:5432/panel_test` inalcanzable;
  se creó la BBDD `panel_test` en la instancia real (5433) usando el superusuario del
  contenedor (`bedrockpanel`, creado vía `POSTGRES_USER`). No se tocó Docker.

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ · `uv run mypy --strict` ✅
  (196 archivos).
- `uv run pytest -q` ✅ **206 passed**, 15 deselected (antes **151 passed**, 10 deselected
  → **+55 unitarios** de IAM).
- `uv run pytest -m integration` con `BEDROCK_PANEL_TEST_DATABASE_URL=...panel_test` ✅
  **14 passed, 1 skipped** (runtime/Docker sin daemon): 9 previos + **5 nuevos** de IAM
  (roundtrip usuario, roles+membresías, login argon2 real, sesiones revocables, audit log).
  Drop/create de tablas por test; BBDD de test queda limpia.
- `alembic upgrade head` ✅ aplicada `0003_iam_tables` (cabecera confirmada) contra la BBDD
  dev real (5433); las 5 tablas `iam_*` verificadas, vacías (0 filas).
- Capas intactas: Domain no importa Infrastructure; `AccessControlPort` pasó a async sin
  romper consumidores; tests previos de Server/Console en verde.

### Pendiente / deuda
- **No conectado a endpoints HTTP**: `AccessControlPort` no se usa en rutas todavía (fuera
  de este paso).
- Diferido a Fase H: auditoría tamper-evident (cadena de hash), 2FA, API keys, matriz de
  permisos por acción, lockout/rate-limit (§14.4), sesión ligada a IP/UA (§14.1).
- `panel_test` (5433) queda disponible para próximas iteraciones de integración.
- **No avanzar al paso 9 (Fase D — Monitoring)** sin confirmación del usuario.

---

## 14. Corrección — `PortAllocator` sin pool real y puertos no liberados al eliminar

> **Fecha**: 2026-08-06
> **Alcance**: corrección de un hallazgo detectado en pruebas manuales (no es un paso de
> fase nuevo). El `PortAllocator` se instanciaba con `pool=()` por defecto, dejando solo
> un puerto de juego (19132 + 19133) y uno RCON (25575) en todo el sistema; un segundo
> servidor agotaba el pool al instante. Además, eliminar un servidor vía API cambiaba su
> estado a `removed` pero `_occupied_ports` seguía contando sus puertos (soft delete sin
> liberación), impidiendo reutilizarlos.

### Cambios
| # | Cambio | Motivo |
|---|---|---|
| 1 | `bootstrap/config.py`: `server_port_pool_start/end` (default 19132–19181) y `server_rcon_port_pool_start/end` (default 25632–25681, sin solapamiento con juego). | Pool configurable por env (`BEDROCK_PANEL_SERVER_PORT_POOL_*`, `BEDROCK_PANEL_SERVER_RCON_PORT_POOL_*`). |
| 2 | `EnvSettingsAdapter`: claves con puntos (`server.port_pool.start`) resuelven atributos snake de `Settings`. | Mismo mecanismo que el resto de ajustes vía `SettingsPort`. |
| 3 | `spec_factory.py`: pools de juego y RCON separados; `build_port_allocator(settings)`; cada puerto de juego reserva también `port+1` (IPv6). | Evita colisiones multi-instancia y el pool vacío. |
| 4 | `container.py`: `PortAllocator` construido con el pool real antes de `RuntimeSpecFactory`. | DI explícita; producción no usa el default vacío. |
| 5 | `use_cases._occupied_ports`: excluye servidores en estado `REMOVED`. | Liberar puertos al eliminar (soft delete) sin borrar fila. |
| 6 | `tests/test_port_allocator.py`: 2+ servidores con puertos distintos; eliminar y reutilizar puerto base. | Regresión del hallazgo manual. |

### Verificación
- `uv run pytest tests/test_port_allocator.py -q` ✅
- Tests existentes de Server sin regresión.

### Ampliación (misma corrección)
- **`ServerResponse.connection`**: la API devuelve `host`, `port`, `port_v6`, `rcon_port` y
  `address` (`host:port`) proyectados desde el `RuntimeSpec` + `server.public_host`
  (`BEDROCK_PANEL_SERVER_PUBLIC_HOST`, default `localhost`).

---

## 15. Paso de cierre Fase C/D1 — Vertical slice HTTP/WS de los módulos (IAM, Server, Console)

> **Fecha**: 2026-08-06
> **Alcance**: cierre de Fase C/D1. Se registró la app FastAPI con los routers de los tres
> módulos construidos hasta ahora (IAM, Server, Console) bajo `Settings.api_prefix`, el mapeo
> central de errores dominio→HTTP y la authN/authZ compartida en `bootstrap/`, más el WS mínimo
> por servidor de Console (ADR-002). Esta entrada documenta un trabajo ya implementado en la
> sesión anterior y que faltaba registrar en el change-log.

### Qué se hizo
- **`bootstrap/main.py`**: `create_app(container=None)` compone el `Container` de producción o
  acepta uno inyectado (tests); registra `iam_router`/`server_router`/`console_router` bajo
  `Settings.api_prefix`; `register_exception_handlers` (AppError → status, validación Pydantic
  → 422, catch-all → 500 con forma `{"detail": {"code", "message", "context"}}`); lifespan solo
  hace `database.dispose()` en shutdown; endpoint raíz `/` con identidad del panel.
- **`bootstrap/security.py`**: authN/AuthZ compartida reusada por los tres módulos —
  `get_current_user` (Bearer → `Identity`), `require_action` (recurso panel, admin global+),
  `require_server_action` (ACL por servidor) y `ws_identity` (token por query/header en
  handshake WS). Errores con la misma forma que `errors.py`.
- **Vertical slice `modules/*/api`**: IAM (`/auth/login`, `/auth/refresh`, `/auth/logout`,
  usuarios, roles, membresías), Server (`/servers` CRUD + start/stop/restart/remove +
  `connection` proyectada) y Console (`/console/commands`, `/console/buffer`). Schemas
  Pydantic en `api/schemas.py`; sin lógica de negocio en la API.
- **WS mínimo por servidor (ADR-002)**: `/servers/{server_id}/console/ws` con authN por token
  en el handshake (4401) y authZ por membresía (4403); envelope §13.2 `{event, server_id?,
  scope, payload, ts, seq}` con `scope="console"`, eventos `CONSOLE.OUTPUT`, resume básico por
  `after_seq` y cierre limpio vía `race` con `websocket.receive()`.
- **`tests/test_api_integration.py`**: suite de integración HTTP/WS con `Container` de dobles
  (repositorios en memoria, runtime fake, fakes de hasher/tokens/hora/ids) — login, ciclo de
  vida completo de servidor vía HTTP, RBAC/ACL (viewer sin membresía → 403), comandos consola,
  buffer y WS (4401/4403, replay desde `after_seq`).
- **ADR-002**: promovido a **Accepted** (el WS mínimo ya está implementado); el diseño usa
  **canal por servidor** en lugar del endpoint único `/ws` del TDD §13.1 (deferido a Fase H);
  queda anotado que el TDD §13.1 se actualizará en su próxima revisión.

### Verificación (en el estado en que se encontró, antes de la limpieza de baseline)
- `uv run pytest -q` → **231 passed, 1 failed** (15 deselected). El fallo es
  `tests/test_server_entity.py::test_version_es_la_del_spec` (ver §16).
- `uv run ruff check .` → 17 errores; `uv run mypy --strict` → 8 errores (mismos archivos de la
  sesión anterior; ver §16).

### Pendiente / deuda
- **Baseline rojo** (image_ref, ruff, mypy) dejado por la sesión anterior: corregido en §16.
- No avanzar al paso 9 (Fase D — Monitoring) hasta dejar el baseline en verde.

---

## 16. Corrección de baseline — image_ref, ruff, mypy y pytest en verde

> **Fecha**: 2026-08-06
> **Alcance**: limpieza del baseline rojo heredado de la sesión anterior (ver §15). Sin
> funcionalidades nuevas; se corrige lo que ya estaba implementado.

### Cambios
| # | Cambio | Motivo |
|---|---|---|
| 1 | `modules/server/domain/server.py`: `image_ref` devuelve solo la imagen cuando `tag` está vacío. | Con digest (`tag=""`, producción) emitía la referencia malformada `imagen@sha256:…:`; la entidad ahora se alinea con el caso real. |
| 2 | `tests/test_server_entity.py`: constante `DIGEST_IMAGE`, `make_server` con `image=DIGEST_IMAGE, tag=""`. | El test de `image_ref` dejó de asumir `imagen:tag`. |
| 3 | `infrastructure/runtime/settings.py`, `modules/configuration/infrastructure/reader.py`: líneas largas reformateadas. | `ruff` E501. |
| 4 | `tests/test_phase_d_config_monitoring.py`: anotaciones `mypy` completas en fakes y `DummySettings`. | `mypy --strict`. |
| 5 | `tests/test_runtime.py`: constante `BEDROCK_IMAGE` extraída. | Deduplicación + `mypy`. |
| 6 | `tests/test_server_use_cases.py`: `import pathlib` (F821), líneas de `monkeypatch` reformateadas, `ruff --fix` de imports. | `ruff`/`mypy`. |
| 7 | `tests/test_port_allocator.py`: `OperationGuard` importado de `app.modules.server.application.use_cases`. | Import inválido desde otro test. |
| 8 | `modules/server/application/spec_factory.py` (~176-179): sangría rota del default de `image`/`tag`. | `ruff format --check` lo detectó. |

### Verificación (conteos antes → después)
- `uv run pytest -q` → **231 passed, 1 failed** → **232 passed, 15 deselected, 6 warnings**.
- `uv run ruff check .` → 17 errores → **All checks passed**.
- `uv run mypy --strict` → 8 errores → **Success: no issues found in 210 source files**.
- `uv run ruff format --check .` → 1 archivo → **210 files already formatted**.
- `tests/test_phase_d_config_monitoring.py` pasa (4 tests): el supuesto de fallo previo era
  incorrecto — el test ya era válido con `BedrockConfigurationReader`.

---

## 17. FASE D — Pasos 9 y 10: Monitoring y Configuration

> **Fecha**: 2026-08-06
> **Alcance**: implementación de los pasos 9 (Monitoring) y 10 (Configuration) de la Fase D
> (vertical slice completo del panel). El `technical-design.md` (TDD) permanece **intacto**;
> las decisiones que afectan al TDD se registran en ADR.

### Paso 9 — Monitoring (estado en vivo + métricas por WS)

**Qué se hizo**
- **Dominio** (`modules/monitoring/domain/`): `MetricSample` (value object inmutable: status
  online/offline, latency, players, cpu, ram_mb, disk_mb, ts), `MetricSampleStorePort` (async,
  append-only por servidor) y `SampleStatus`.
- **Aplicación** (`application/`): `StatusPoller` — una pasada de poll por servidor que sondea
  `StatusProbePort` (ping RakNet, independiente del runtime) + `ServerRuntimePort`
  (`get_state`/`get_resources`), **reconcilia** con la facade de Server
  (`mark_started`/`mark_crashed` según la máquina de estados, ignorando `ServerStateError`) y
  registra la muestra en el store; `poll_all` escalonado omite servidores `REMOVED`.
  `MonitoringFacade` (poll_server / poll_all, intervalo por Settings).
- **Infraestructura** (`infrastructure/`): `InMemoryMetricSampleStore` (buffer circular
  acotado; la tabla Postgres queda para Fase E/H), `BackgroundPoller` (bucle de fondo del
  lifespan, no corre bajo `TestClient`). `RakNetStatusProbe` existente sin cambios.
- **API** (`modules/monitoring/api/`): WS mínimo por servidor `GET
  /servers/{server_id}/monitoring/ws` (ADR-002): authN por token en el handshake (4401),
  authZ por membresía (4403, `server.status.read` en `READ_ACTIONS`), snapshot inmediato y
  después cada `poll_interval` (5 s, TDD §13.3) con envelope §13.2 `SERVER.STATE` y
  `scope="monitoring"`. **El snapshot es transporte, no se publica en el bus** (sin telemetría
  nueva; los eventos de estado los publica Server).
- **Wiring**: `Container` con `monitoring_facade` y `monitoring_poller` (default `None` en
  tests); `bootstrap/main.py` registra `monitoring_router` y arranca/para el poller en el
  lifespan; `Settings` con `monitoring.poll_interval_seconds` y `monitoring.probe_timeout`.

**Tests** (+10): unitarios del poller (confirmar arranque, crash solo con runtime muerto, sin
crash si el runtime sigue vivo, no reconciliar servidor recién creado, status offline, store
acotado, `poll_all` omite eliminados) e integración WS (4401, 4403, snapshot `SERVER.STATE`).

### Paso 10 — Configuration (ConfigProfile + CONFIG.CHANGED)

**Qué se hizo**
- **Dominio** (`modules/configuration/domain/`): `ConfigProfile` (properties deseado +
  `config_rev` + `applied`/`applied_at`/`version`, ADR-004), `ConfigChange` (historial
  append-only), `PropertySchema` (mapeo propiedad→env y validación, §16.8), `events.py`
  (`CONFIG.CHANGED` → topic `config.changed`), `ConfigurationRepositoryPort`.
- **Aplicación** (`application/facade.py`): `ConfigurationFacade` — implementa el protocolo
  `ConfigurationReader` que consume Server (vista de solo lectura: profile → `DesiredConfig`
  con env proyectado y revisión; defaults si no hay perfil) y `update_properties`
  (valida → persiste perfil con revisión+1 → historial → publica `CONFIG.CHANGED` con
  `{server_id, config_rev:int}`; sin cambios no publica).
- **Infraestructura** (`infrastructure/`): `PostgresConfigurationRepository`
  (`config_profiles` upsert + `config_history` append-only), `InMemoryConfigurationRepository`
  (tests), modelos `config_*`, serialización; `BedrockConfigurationReader` refactorizado para
  reusar `PropertySchema` (conserva su API).
- **Migración** `0004_configuration_tables.py`: tablas `config_profiles` y `config_history`
  (PK compuesta server_id+config_rev en historial); **head único** (0001→0002→0003→0004).
- **Wiring**: `container.py` reemplaza `DefaultConfigurationReader` (placeholder, eliminado)
  por `ConfigurationFacade` con repositorio Postgres real detrás del mismo puerto
  `ConfigurationReader`; Server aplica los cambios por evento `CONFIG.CHANGED` (unidireccional,
  §3.2).

**Tests** (+10): unitarios del facade (defaults sin perfil, proyección a env, revisión,
evento con payload/actor, no-op sin cambios, validación `max-players<=40`, historial, preserva
`applied`, integración Server: `CONFIG.CHANGED` → `ApplyConfigUseCase` con
`desired_config_rev`/`applied_config_rev`=1) e integración Postgres opt-in (roundtrip + upsert
del perfil, historial append-only).

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (231 archivos) · `uv run mypy
  --strict` ✅ (230 archivos tras eliminar el placeholder).
- `uv run pytest -q` ✅ **252 passed, 17 deselected** (15 base + 2 integración Configuration
  opt-in), 6 warnings (JWT key corta en tests, pre-existente).
- `uv run alembic heads` ✅ `0004_configuration_tables (head)` — cadena única
  0001→0002→0003→0004.

### Pendiente / deuda
- **MetricSample sin tabla Postgres** (decisión del usuario): el blueprint §5.3/§11.3 prevé
  `MetricSample` en Postgres; la tabla queda diferida a Fase E/H (el puerto es `async` y el
  store en memoria es intercambiable).
- **Sin API REST de Configuration** (solo facade + evento): el endpoint `PATCH
  /servers/{id}/configuration` y la gestión de packs quedan para una iteración posterior
  (blueprint §3.7 facade `applyProperties`/`installPack`/`removePack`).
- **ADR-004 sigue Proposed**; esta implementación sigue su decisión (perfil + `applied`/
  `applied_at`/`version` + historial). Promoverlo a Accepted en una revisión de docs.
- **ADR-005 Proposed**: sin test de paridad del catálogo todavía.
- No avanzar al paso 11 (Fase D) sin confirmación del usuario.


