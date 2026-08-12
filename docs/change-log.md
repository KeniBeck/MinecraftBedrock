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

## 18. FASE E — paso 11: Módulo Player

> **Fecha**: 2026-08-06
> **Alcance**: parser declarativo de join/leave en Console (Pieza 1) + módulo Player completo
> (Pieza 2: dominio/aplicación/infraestructura/migración `0005_player_tables`/wiring/tests).
> El `technical-design.md` (TDD) permanece **intacto**; solo ADR + change-log registran
> decisiones.

### Pieza 1 — Parser declarativo en Console

- **`infrastructure/parsers/player_join_detector.py`**: `PlayerJoinDetector`, consumidor de
  `CONSOLE_OUTPUT_TOPIC` (mismo patrón que `save_detector.py`). Reconoce por regex
  (case-insensitive) las líneas `Player connected: <name>, xuid: <xuid>`,
  `Player disconnected: <name>, xuid: <xuid>` y `Player timed out: <name>, xuid: <xuid>`
  (timed-out → `PLAYER.LEFT`), y publica `PLAYER.JOINED`/`PLAYER.LEFT` con payload
  `{server_id, name, xuid}`. **Requiere XUID** en la línea; si falta, la línea se ignora.
- **Responsabilidad limitada**: el parser solo reconoce el patrón y publica; **no interpreta
  semántica de negocio**. `PLAYER.JOINED`/`PLAYER.LEFT` los publica Console (según §9.2);
  el módulo Player solo los **consume**.
- **Hallazgo — formato de BDS no confirmado**: los patrones de línea se basan en salida típica
  de BDS (`Player connected: <name>, xuid: <xuid>`), pero **no se ha verificado contra una
  consola real**. Mismo criterio que el hallazgo C1 del catálogo de comandos: se asume un
  formato, se aísla en el parser y se valida con pruebas de caja negra contra BDS real en el
  paso de verificación final. El parser está diseñado para ajustar solo la regex si difiere.

### Pieza 2 — Módulo Player (§3.5)

- **Dominio** (`modules/player/domain/`):
  - `errors.py`: `PlayerValidationError` (`PLAYER.INVALID_PAYLOAD`),
    `PlayerNotFoundError` (`PLAYER.NOT_FOUND`).
  - `player.py`: `Player` frozen (xuid, name, first_seen_at, last_seen_at, playtime_seconds,
    created_at, updated_at).
  - `session.py`: `PlaySession` (id, server_id, xuid, joined_at, left_at, reason,
    playtime_seconds, `elapsed_seconds`) y `SessionEndReason.LEFT/ABORTED`. **Las sesiones
    abortadas (fin desconocido) no acumulan playtime.**
  - `events.py`: `PLAYER.BANNED` (topic `player.banned`), que **publica** el módulo; y
    `PLAYER.JOINED`/`PLAYER.LEFT`/`PLAYER.OPERATOR_CHANGED` (topics `player.*`), que
    **consume**.
  - `repository.py`: `PlayerRepositoryPort` (get_player, get_player_by_name, save_player,
    get_open_session, save_session, list_open_sessions, list_sessions).
- **Aplicación** (`modules/player/application/`):
  - `use_cases.py`: `ResolvePlayerUseCase.cache` (upsert del jugador; refresca nombre y
    last_seen), `JoinPlayerUseCase.join` (idempotente si ya hay sesión abierta),
    `LeavePlayerUseCase.leave` (cierra con `LEFT` y acumula playtime; **defensivo**: sin sesión
    abierta devuelve `None` sin lanzar), `CleanPresenceUseCase.clean` (en `SERVER.STARTED`:
    aborta las sesiones abiertas sin acumular playtime), `BanPlayerUseCase.ban`
    (`ban <name>` + publica `PLAYER.BANNED` solo si Console acepta el comando),
    `UnbanPlayerUseCase.unban` (`unban <xuid>`), `KickPlayerUseCase.kick` (`kick <name>`).
    Dependencias: `PlayerDeps` (repository, `ConsoleFacade`, bus, ids, time, settings).
  - `handlers.py`: `PlayerJoinedHandler`, `PlayerLeftHandler`, `ServerStartedHandler`
    (limpieza de presencia), `OperatorChangedHandler` (solo consistencia, sin lógica). Todos
    **defensivos**: payload inválido o sin `server_id` → no-op.
  - `facade.py`: `PlayerFacade` con **superficie pública mínima** (§3.5): `resolve_xuid`
    (gamertag→XUID, para Permission en Fase F), `find_player` y `register_handlers`.
- **Infraestructura** (`modules/player/infrastructure/`):
  - `models.py` + `serialization.py`: `PlayerRow` (`player_players`: xuid String(64) PK,
    name, fechas, playtime) y `PlaySessionRow` (`player_sessions`: id String(36) PK,
    server_id/xuid indexados, joined/left_at, reason, playtime). **Sin FKs** a otros bounded
    contexts.
  - `postgres_repository.py`: `PostgresPlayerRepository` con upserts
    (`pg_insert.on_conflict_do_update`); `get_player_by_name` devuelve el jugador con
    `last_seen_at` más reciente (el gamertag nunca es identidad única, §16.6).
  - `memory.py`: `InMemoryPlayerRepository` para tests.
- **Migración** `0005_player_tables.py`: tablas `player_players` y `player_sessions` +
  índices; **head único** (0001→0002→0003→0004→0005).
- **Wiring**: `container.py` suscribe `PlayerJoinDetector` a `CONSOLE_OUTPUT_TOPIC` (junto a
  `SaveDetector`), añade `player_facade: PlayerFacade` con `PostgresPlayerRepository` real +
  `ConsoleFacade` (ban/unban/kick **reusan** la facade de Console existente); `alembic/env.py`
  y `tests/conftest.py` registran los models de Player; `make_container` de tests usa el repo
  en memoria.

**Tests** (+29 unitarios + 4 integración opt-in): detector (7: joined/left/timed-out, ignora
líneas no relacionadas y sin XUID, requiere server_id, case-insensitive), use cases (15: caché
nueva/refresca/vacía, join abre/idempotente, leave cierra con playtime 90 s y acumula 150 s
entre sesiones/defensivo, clean aborta 2 sin playtime y no afecta a otros servidores, ban con
`PLAYER.BANNED` completo + actor_id, ban desconocido→`PLAYER.NOT_FOUND`, unban/kick por
comando, xuid vacío→`PLAYER.INVALID_PAYLOAD`), handlers (7: abrir/cerrar, payloads inválidos
ignorados, `SERVER.STARTED` limpia, `OPERATOR_CHANGED` sin efecto, topics suscritos) e
integración Postgres (4: roundtrip+upsert, `get_player_by_name` más reciente, sesiones
open/close/presencia por servidor, `list_sessions` desc).

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (250 archivos) · `uv run mypy
  --strict` ✅ (250 archivos, incluye los tests del paso).
- `uv run pytest -q` ✅ **281 passed, 21 deselected** (252 previos + 29 unitarios Player; los 4
  de integración Player opt-in), 6 warnings (JWT key corta en tests, pre-existente).
- Integración opt-in contra Postgres real (Docker 5433, DB `panel_test`, rol
  `bedrockpanel`): **21 passed** (17 previos + 4 Player).
- `uv run alembic upgrade head` aplicado sobre la BBDD dev real (5433/bedrockpanel):
  0003→0004→0005. `uv run alembic heads` ✅ `0005_player_tables (head)` — cadena única
  0001→0002→0003→0004→0005. Tablas `player_players`/`player_sessions` creadas.

### Pendiente / deuda
- **Formato de líneas de BDS sin confirmar** (hallazgo): validar contra consola real en el paso
  de verificación final (mismo criterio que C1); si difiere, solo cambia la regex del parser.
- **Sin API REST de Player**: la facade queda lista (resolveXuid/findPlayer) pero **no se
  conectó a HTTP**; los endpoints de jugadores/sesiones/bans quedan para el paso de cierre
  (igual que IAM/Server/Console en Fase D). **Sin tabla de bans** aún: el ban se registra vía
  comando de Console + evento `PLAYER.BANNED`; persistir el estado de ban queda pendiente.
- **Sin API HTTP de Console** aún (paso 7 la dejó sin REST): parsers publican eventos pero
  la lectura de líneas por HTTP/WS queda para una iteración posterior.
- No avanzar al paso 12 (World) sin confirmación del usuario.

## 19. Corrección — Ciclo de vida del stream de Console (deuda §10 decisión 11)

> **Fecha**: 2026-08-06
> **Alcance**: cerrar la deuda de la decisión 11 — `console_stream`
> (`ConsoleLogStream`) se exponía en el `Container` pero nunca se iniciaba, por
> lo que ningún parser declarativo (`SaveDetector`, `PlayerJoinDetector`) recibía
> líneas reales. **Mínimo necesario**: atar el arranque/parada del stream a los
> eventos `SERVER.*` ya publicados. No es el supervisor de tareas de Fase H.

### Qué se hizo
- **`ConsoleStreamManager`** (`modules/console/infrastructure/stream_manager.py`):
  gestor de ciclo de vida del stream con **una tarea `asyncio.Task` por
  `server_id`**:
  - `SERVER.STARTED` → resuelve el `runtime_id` vía `ServerConsoleReader`
    (facade Server **solo lectura**, mismo puerto que usa Console) y lanza una
    tarea de fondo que ejecuta `ConsoleLogStream.consume(server_id, runtime_id)`.
  - `SERVER.STOPPED`/`SERVER.CRASHED`/`SERVER.REMOVED` → cancela la tarea del
    servidor y la espera (`suppress(CancelledError)`); si la tarea ya terminó
    sola, no queda estado residual.
  - **Defensivo**: sin `server_id`, sin runtime (`runtime_id=None`) o servidor
    desconocido → no-op; si la tarea muere con error se loguea y se limpia
    (`finally`), sin tumbar el proceso ni dejar consumidores huérfanos.
- **Multi-stream verificado**: `ConsoleLogStream.consume` es **sin estado por
  invocación** (solo recibe `server_id`+`runtime_id`); una tarea por servidor
  sostiene varios streams concurrentes **sin cambios en el adaptador** (test
  `test_varios_servidores_conviven_y_se_paran_independientes`).
- **Parada limpia sobre servidor eliminado**: `SERVER.REMOVED` cancela la tarea
  (no queda un consumidor intentando leer logs de un contenedor que ya no
  existe); cubierto por `test_server_removed_detiene_el_stream_sin_consumidor_orfano`.
- **Wiring**: `build_container` crea el gestor con `console_deps.server` +
  `console_stream` y lo suscribe al bus; `make_container` (tests de API) lo
  replica para que producción y tests se comporten igual.

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (252 archivos) ·
  `uv run mypy --strict` ✅ (252 archivos).
- `uv run pytest -q` ✅ **291 passed, 21 deselected** (281 previos + **10**
  unitarios del gestor), 6 warnings (JWT key corta en tests, pre-existente).
- Integración opt-in contra Postgres real (5433/panel_test): **21 passed**
  (sin cambios respecto al paso 11 — el gestor no toca persistencia).

### Hallazgo — el stream de Docker no es en vivo (`follow=False`)
- El adaptador `DockerRuntimeAdapter.stream_logs` usa
  `container.logs(stream=True, follow=False, tail="all")` (testado en
  `test_runtime.py`), es decir, **vuelca el histórico de líneas de una vez y
  termina**: es "cola", no "cola + streaming" como describe el contrato §4.1.
- **Consecuencia**: aunque el gestor ya arranca el stream en `SERVER.STARTED`,
  ese volcado único captura el *tail* del arranque y la tarea termina; las
  líneas posteriores (p. ej. un `Player connected` de un jugador que entra
  después de arrancar) **no llegan** a los parsers. El cableado por sí solo
  **no puebla** `player_players`/`player_sessions` en vivo.
- **Por qué no se arregló aquí**: pasar a `follow=True` convierte el iterador en
  un generador **bloqueante** sobre el socket, y `consume` lo itera de forma
  síncrona dentro de la tarea asyncio — congelaría el event loop del panel entre
  líneas. Hacerlo bien requiere un **boundary asíncrono** (iterar el stream en un
  hilo trabajador / `asyncio.to_thread`) en el adaptador de streaming: un cambio
  mayor que **no se improvisa** en esta corrección (mismo criterio que la
  instrucción de detenerse y reportar hallazgos).
- **Opciones para decidir** (siguiente paso, fuera de esta corrección):
  1. Dejar `follow=False` (el stream captura solo el tail al arrancar) — sirve
     para registrar el arranque pero **no** para jugadores en vivo.
  2. Cambiar el adaptador a `follow=True` + hilo de lectura por servidor —
     objetivo real ("cola + streaming"); requiere una corrección dedicada.

### Cómo verificar manualmente (documentado, no ejecutado aquí)
1. Panel arriba (BBDD dev 5433) → arrancar un servidor por el panel
   (publica `SERVER.STARTED`; el gestor inicia el stream).
2. Comprobar en `pgAdmin`/`psql`: `select count(*) from console_lines;` sube con
   las líneas del arranque (el buffer se puebla con el volcado inicial).
3. Conectarse a Minecraft y hacer `/say hola` / entrar: mientras el adaptador
   siga en `follow=False`, las líneas nuevas **no** aparecerán (hallazgo
   anterior); con la opción 2 aparecerán y
   `player_players`/`player_sessions` se poblarán al conectarse.

### Pendiente / deuda
- **Decidir el `follow` del adaptador Docker** (hallazgo anterior): el cableado
  del gestor queda listo y probado para ambos casos; falta la corrección del
  adaptador de streaming (hilo/`to_thread`) para el flujo en vivo.
- El supervisor de tareas genérico de Fase H sigue fuera de alcance.
- No avanzar al paso 12 (World) sin confirmación del usuario.

## 20. Corrección — Adaptador de streaming en vivo (`follow=True` + boundary asíncrono)

> **Fecha**: 2026-08-06
> **Alcance**: cerrar el hallazgo §19. `DockerRuntimeAdapter.stream_logs` pasa a
> `container.logs(stream=True, follow=True, tail="all")` (cola + streaming), y el
> boundary asíncrono necesario se resuelve moviendo la lectura del generador
> bloqueante de docker-py a un **hilo trabajador** que publica líneas en el event
> loop. El contrato `ServerRuntimePort.stream_logs` (`Iterator[bytes]`) **no
> cambia**; `ConsoleStreamManager` (§19) se reutiliza tal cual.

### Qué se hizo
- **`DockerRuntimeAdapter.stream_logs`** (`infrastructure/runtime/docker.py`):
  `follow=False` → `follow=True`. El iterador ahora es un generador **bloqueante**
  sobre el socket; termina cuando el daemon cierra el stream al detener/eliminar
  el contenedor. Docstring actualizado con el nuevo comportamiento.
- **`ConsoleLogStream.consume`** (`modules/console/infrastructure/stream.py`):
  boundary asíncrono con **hilo trabajador `daemon`** por invocación
  (`console-stream-{server_id}`):
  - El hilo itera `stream_logs(runtime_id)` y entrega cada línea al loop con
    `loop.call_soon_threadsafe` sobre un `asyncio.Queue`; el consumidor de la
    corrutina las normaliza y publica como `CONSOLE.OUTPUT`.
  - Centinela `_EOF` para terminación ordenada; **excepciones del runtime viajan
    por la cola y se re-lanzan en la corrutina**, de modo que
    `ConsoleStreamManager._run` las loguea y limpia el estado (`finally`), igual
    que antes.
  - Normalización/`_iter_lines` intactas (los tests unitarios existentes siguen
    pasando).
- **Tests** (`tests/test_console_stream_live.py`, 3 nuevos):
  - `test_consume_no_bloquea_el_event_loop`: runtime bloqueante con
    `reader_started`/`stream_stopped`/`reader_exited`; llega "primera", el ticker
    sigue latiendo mientras el stream espera y "ultima" llega al liberar — **el
    event loop nunca se congela**.
  - `test_cancelar_detiene_la_lectura_sin_colgarse`: cancelar la tarea no cuelga
    el loop; el hilo sale solo cuando el stream se agota (ver hallazgo).
  - `test_consume_propaga_errores_del_runtime`: `ExplodingRuntime` → el
    `RuntimeError` se propaga a la corrutina.
- `tests/test_runtime.py`: `test_stream_logs_returns_iterador_de_bytes` actualizado
  a `follow=True`.

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (253 archivos) ·
  `uv run mypy --strict` ✅ (253 archivos).
- `uv run pytest -q` ✅ **294 passed, 21 deselected** (291 previos + **3** del
  boundary), 6 warnings (JWT key corta en tests, pre-existente).
- **Prueba real end-to-end ejecutada** (daemon Docker 29.7.1): contenedor
  `alpine:3.20` real que emite 3 líneas estilo BDS en vivo (join de Steve a los
  3s, join de Alex a los 11s, left de Steve a los 19s) → adaptador real
  `follow=True` → `ConsoleLogStream` → `PlayerJoinDetector` → `PlayerFacade` →
  **Postgres dev (5433)**:
  - `console_lines`: **3** líneas (el stream capturó en vivo lo emitido *después*
    de conectar, no un volcado previo).
  - `player_players`: Steve (first_seen 01:42:23, playtime **15s**) y Alex
    (first_seen 01:42:31, playtime 0 — sesión abierta).
  - `player_sessions`: Steve cerrada en 01:42:39 con playtime **15s** y
    reason `left`; Alex abierta (`left_at` NULL). El pipeline completo puebla
    las tablas en vivo.

### Hallazgo — cancelar la tarea no interrumpe el hilo de lectura
- La tarea asyncio se cancela al instante (`await queue.get()` se interrumpe),
  pero el **hilo trabajador no se puede interrumpir a la fuerza** mientras el
  generador espera el próximo byte del socket docker-py; sale solo cuando Docker
  cierra el stream al detener/eliminar el contenedor (o el servidor muere solo).
- **Decisión**: documentarlo como comportamiento esperado, no forzar nada frágil.
  El hilo es `daemon=True`, así que **no bloquea el shutdown del proceso**; y al
  parar el servidor, el stream se cierra y el hilo termina. El test
  `test_cancelar_detiene_la_lectura_sin_colgarse` verifica que el loop no cuelga
  y deja constancia de que el hilo termina solo cuando el stream se agota.
- **Deuda**: el formato de línea real de BDS (mensaje exacto del join/left y
  entrega por líneas del log de BDS con el panel y un cliente Minecraft real)
  sigue **pendiente de verificación manual** — el end-to-end de esta corrección
  usó líneas sintéticas con el formato documentado del parser.

### Cómo verificar manualmente (documentado, no ejecutado aquí)
1. Panel arriba (BBDD dev 5433) → arrancar un servidor por el panel.
2. `select count(*) from console_lines;` sube con cada línea que BDS emite
   **en vivo** (ya no es un volcado único).
3. Conectarse a Minecraft: `player_players`/`player_sessions` se pueblan al
   entrar; `player_sessions.left_at`/`playtime_seconds`/`reason` al salir.
   Comparar el mensaje real de BDS con el formato del parser
   (`Player connected: <nombre>, xuid: <xuid>`).

### Pendiente / deuda
- Verificación manual con un **cliente Minecraft real** y el formato exacto de
  línea de BDS (deuda del hallazgo).
- El supervisor de tareas genérico de Fase H sigue fuera de alcance.
- No avanzar al paso 12 (World) sin confirmación del usuario.

## 21. Corrección — El stream no arrancaba en producción: probe RakNet inválido + XUID con coma

> **Fecha**: 2026-08-07
> **Alcance**: bug real reportado ("ConsoleStreamManager no arranca el stream en
> producción": `console_lines` no crecía pese a un jugador conectado). La causa
> raíz **no era el wiring** (que estaba correcto en `build_container`) sino una
> **cadena gated por el probe**: BDS quedaba `starting` para siempre y por eso
> `SERVER.STARTED` nunca se publicaba. De paso se encontró un **segundo bug
> real** en el parser (XUID con coma en la línea de disconnect de BDS).

### Evidencia del bug (producción, servidor real `bedrock-panel-server`)
1. `docker logs bedrock-panel-server`: `Server started.` y
   `Player connected: CrafterTec, xuid: 2535473172645342` reales.
2. BBDD: `server_servers.state = 'starting'` (nunca `running`), `console_lines = 3`
   (solo las líneas sintéticas de §20; ni una línea real).
3. `RakNetStatusProbe.probe('localhost', 19132)` → `OFFLINE` (timeout 2s), pese a
   que el puerto está publicado (`docker port` → `19132/udp`) y un ping RakNet
   bien formado responde en **0.5 ms**.

### Cadena causal demostrada
- El wiring de producción **sí** suscribe el gestor (`container.py:173-178`,
  `stream_manager.subscribe()`), y los temas coinciden (`event.type.lower()` =
  `server.started`).
- Pero `SERVER.STARTED` solo lo publica `MarkStartedUseCase` (use_cases.py:187),
  que solo invoca `StatusPoller._reconcile` (polling.py:127) **cuando el probe
  responde online**.
- El probe enviaba `\x01\x00` — un paquete **malformado** (RakNet `unconnected
  ping` exige `0x01 + timestamp(8) + magic(16) + GUID(8)`); BDS lo ignora → el
  probe siempre devolvía `offline` → el servidor quedaba `starting` → sin
  `SERVER.STARTED` → el gestor jamás arrancaba el stream → `console_lines`
  congelado en 3.

### Qué se hizo
- **Probe corregido** (`monitoring/infrastructure/raknet_probe.py`): envía un
  `ID_UNCONNECTED_PING` válido (`0x01` + timestamp big-endian + magic
  `00ffff00fefefefefdfdfdfd12345678` + GUID cero). Verificado contra el servidor
  real: **ONLINE 1.5 ms**.
- **Observabilidad del gestor** (`stream_manager.py`): logs explícitos al recibir
  `SERVER.STARTED`, al descartar por stream ya activo, al faltar runtime y al
  arrancar la tarea (server_id + runtime_id) — rastro visible en los logs del
  panel (permanente, útil para futuras depuraciones).
- **Segundo bug real corregido** (`parsers/player_join_detector.py`): la línea
  real de BDS es `Player disconnected: X, xuid: <xuid>, pfid: <...>` — el
  `\S+` capturaba la coma y creaba un jugador basura (`xuid = "2535473172645342,"`
  visto en `player_players`). Los regex pasan a `(?P<xuid>\d+)` (XUID decimal).
- **Tests**: `test_raknet_probe_*` ahora validan el paquete enviado
  (id 0x01, longitud 33, magic en offset 9); nuevo
  `test_left_detector_captura_xuid_con_sufijo_pfid`.

### Evidencia de la corrección (producción, con `--reload`)
1. Tras guardar el fix, el panel recargó y el poller confirmó online →
   `server_servers.state = 'running'` (antes `starting`).
2. `SERVER.STARTED` → el gestor arrancó el stream → `console_lines` pasó de
   **3 → 50** con las **líneas reales** del contenedor (historial completo vía
   `tail="all"` + seguimiento en vivo): `Server started.`, versiones, join y
   disconnect reales de CrafterTec.
3. `player_players` se pobló con el XUID real `2535473172645342` y
   `player_sessions` con su sesión.
4. El stream **sigue activo** en vivo (la cola del log de BDS aparece en
   `console_lines`).

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (253 archivos) ·
  `uv run mypy --strict` ✅ (253 archivos).
- `uv run pytest -q` ✅ **295 passed, 21 deselected** (294 + 1 test del parser).

### Pendiente / deuda
- La fila basura del parser (`xuid` con coma) se limpió de la BBDD dev; la
  sesión huérfana de la línea mal parseada también. La corrección aplica a
  líneas nuevas.
- Confirmar el formato de `Player timed out` real (mismo patrón `\d+` cubierto).
- El supervisor de tareas genérico de Fase H sigue fuera de alcance.

## 22. FASE E — paso 12: Módulo World + adaptador de storage con validación de rutas

> **Fecha**: 2026-08-07
> **Alcance**: cierre de la Fase E. Por un lado el **adaptador
> `LocalServerStorage`** del puerto `ServerStoragePort` (árbol `worlds/` de un
> servidor sobre filesystem local) con una **superficie de seguridad real**:
> ninguna operación puede salir de la raíz. Por otro el **módulo World**
> completo (dominio, aplicación, infraestructura, migración y wiring) con la
> API funcional: crear, importar (`.mcworld`/tar.gz), exportar (con `save
> hold`/`save resume`), duplicar, eliminar, activar (excluyente) y reconciliar
> la metadata con el volumen.

### Adaptador `LocalServerStorage`
- **Validación estricta de rutas** en `_resolve` (mismo rigor que
  `_validate_runtime_id` de Docker): rechaza rutas absolutas, `..` en cualquier
  componente, symlinks que resuelvan fuera de la raíz (también en rutas aún no
  existentes vía `resolve(strict=False)`), separadores de Windows (`\`) y
  unidades de Windows (`C:`) — esta última capa es **defensa-in-depth**: en
  POSIX `..\windows` o `C:/windows` no son traversal/absolutas de verdad, pero
  se rechazan igual para que el contrato sea idéntico en cualquier plataforma.
- **Snapshots como streams** (un mundo pesa cientos de MB): `world_snapshot`
  empaqueta a zip `.mcworld` en un fichero temporal (el caller lo cierra) y
  `write_snapshot` extrae zip/tar.gz validando cada miembro contra Zip Slip
  (rutas absolutas, `..`, tar con symlink/hardlink → `STORAGE` error) y con
  soporte para el directorio envolvente común de los `.mcworld` (`_strip_wrapper`).
- **Locks**: `asyncio.Lock` por `scope` en la instancia (exclusión mutua en
  proceso). El resolver `LocalServerStorageResolver` cachea una instancia por
  `server_id` precisamente porque los locks viven en la instancia.
- **Raíz compartida con el mount**: `RuntimeSpecFactory.data_dir(server_id)`
  (ahora público) devuelve la misma ruta que el volumen `/data` — sin rutas
  paralelas (§22).

### Módulo World
- **Dominio**: entidad `World` (id, server_id, name, level_name, size_bytes,
  activated, created_at, updated_at); errores `WORLD.INVALID_PAYLOAD /
  NOT_FOUND / ALREADY_EXISTS / CORRUPT / ACTIVE_IN_USE`; eventos `WORLD.CREATED
  / IMPORTED / EXPORTED / DUPLICATED / DELETED / ACTIVATED` con `world_event()`.
- **Aplicación**: 7 use cases.
  - `create`: metadata + `levelname.txt` (BDS genera el `level.dat` real en el
    primer arranque con ese level-name; el panel solo siembra el name file).
  - `import_`: extrae el snapshot, exige `level.dat` (mínimo de validez) y si no
    está **limpia lo extraído** y falla con `WORLD.CORRUPT`.
  - `export`: bajo el lock del storage, si el servidor corre pide `save hold`
    antes de empaquetar y `save resume` al terminar. Los comandos de save son
    **best-effort** (decisión §22): si Console los rechaza el snapshot se
    exporta igual y puede quedar menos consistente (documentado).
  - `duplicate`: clona vía snapshot→restauración con rollback si el clon no
    tiene `level.dat`.
  - `delete`: el mundo **activo no se puede eliminar** (`WORLD.ACTIVE_IN_USE`);
    primero hay que activar otro. El borrado del filesystem pasa por aquí (el
    `sync` nunca borra metadata).
  - `activate`: **excluyente por servidor** (`deactivate_worlds` + upsert).
  - `sync`: reconcilia metadata con el volumen; crea metadata de mundos con
    `level.dat` que el panel aún no conoce (`activated=False`).
- **Infraestructura**: `world_metadata` (migración `0006_world_tables`, índice
  por `server_id`), `PostgresWorldRepository` (upsert, `delete()`, `update()`
  atómico para deactivar), `InMemoryWorldRepository` para tests.
- **Handlers**: World consume `SERVER.VERSION_CHANGED` solo por consistencia
  (defensivo, nunca corta el bus).

### Decisión §22 — `config_rev` opcional y activación de mundo
- `ApplyConfigCommand.config_rev` pasa a `int | None = None`
  (`None` = "reaplicar sin cambiar la revisión") y `ApplyConfigUseCase` solo
  actualiza `desired/applied` si llega revisión. `WORLD.ACTIVATED` **no lleva**
  `config_rev`: la revisión de Configuration la conserva Configuration; el
  handler de Server la trata como reaplicación sin cambio de revisión.
  `_optional_config_rev(event)` tolera payload sin `config_rev` o no entero.
- Test clave: `test_world_activated_sin_config_rev_no_pisa_la_revision`
  (config_rev previo 5 se conserva tras reaplicar por activación de mundo).

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (274 archivos) ·
  `uv run mypy --strict .` ✅ (274 archivos).
- `uv run pytest -q` ✅ **355 passed, 24 deselected** (antes 325/21):
  +26 use cases World, +3 handlers World; los +3 deselected son la integración
  opt-in contra Postgres real (`test_world_postgres_integration.py`, requiere
  `BEDROCK_PANEL_TEST_DATABASE_URL`). 30 tests del storage (
  `tests/test_local_storage.py`): traversal, rutas absolutas, symlinks, Zip
  Slip, envolvente `.mcworld`, tar.gz, locks.
- Cadena alembic: `0005_player_tables -> 0006_world_tables (head)`.

### Pendiente / deuda
- **Validación NBT de `level.dat` fuera de alcance del MVP** (§22): World solo
  exige la existencia del fichero; el `level_name` real lo lee BDS.
- **Lock distribuido** para multi-instancia no resuelto en el MVP (locks en
  proceso); limitación señalada en el adaptador.
- No avanzar al paso 13 (Backup) sin confirmación del usuario.

---

## 23. Paso 13 — módulo Backup (Fase F)

Alcance confirmado por el usuario: compresión **tar+zstd** con `zstandard`,
gatillos **manual + pre-restore** (el programado queda diseñado para consumir
`TASK.STARTED` en Fase G, paso 15 Scheduler) y granularidad **por mundo**.
Backup **no depende del módulo World** (matriz §1.3): el mundo se direcciona por
el directorio `worlds/<nombre>` (decisión §22; el §7.4 habla de `world_id`, pero
importarlo violaría la matriz).

### Puerto y adaptador
- `BackupStorePort` ya existía en `kernel/ports/backups.py` (put/get/delete/
  exists/list/verify con streams); **reutilizado sin cambios**.
- **`ServerStoragePort.move(rel_from, rel_to)`** añadido al contrato e
  implementado en `LocalServerStorage`: ambas rutas pasan por `_resolve`,
  origen debe existir, destino no, `mkdir` del padre + `rename` (swap atómico
  para la restauración). Validación `PurePath` con defensa-in-depth (mismo
  criterio que §22: separadores/rutas de Windows también en POSIX).
- `LocalBackupStore` (nuevo `app/infrastructure/backups/local.py`): artefactos
  bajo `{root}/{ref}`, `ref` validada contra traversal (no vacía, no absoluta,
  sin `..`, sin `\`), `verify` recalcula SHA-256 en streaming.

### Formato de artefacto (`application/archive.py`)
- `bedrockpanel-backup/v1`: `tar.zst` cuyo **primer** miembro es
  `manifest.json` (format/world/entries/created_at) y el segundo
  `world.mcworld` (zip del árbol del mundo de `world_snapshot`).
- **Python 3.13 no soporta `tarfile` con zstd nativo** (llega en 3.14): se
  envuelve el tar con `zstandard.ZstdCompressor(...).stream_writer` +
  `FLUSH_FRAME` para escribir; para leer se descomprime el artefacto a un
  `tempfile.TemporaryFile` seekable y se abre con `tarfile mode="r:"`
  (el lector de zstd no permite seek hacia atrás).
- SHA-256 del artefacto completo **en streaming**, guardado en el registro
  (BBDD). El manifiesto **no** se autoreferencia (imposible en una sola pasada
  de streaming); lista las entradas del nivel, que es lo que §8.2 usa para
  validar (`level.dat`).

### Use cases (`BackupDeps`: repository, storage, store, console, server, bus,
ids, time, settings)
- **create**: valida mundo (existe + nombre limpio), registro `RUNNING` +
  `BACKUP.STARTED`, lock `backup:{server_id}`, `save hold`/`save resume`
  best-effort solo si el servidor corre (mismo criterio que World export,
  §22), snapshot → artefacto → `store.put`; éxito → `COMPLETED` +
  `BACKUP.COMPLETED` (size/checksum); fallo → `FAILED` + `BACKUP.FAILED`.
- **restore**: solo estados `COMPLETED`; `BACKUP.RESTORE_STARTED`; si el
  servidor corre, `stop`; `store.verify(checksum)` (fallo → registro
  `CORRUPT` + `BackupCorruptError`); extracción a `staging/{backup_id}`,
  `_require_valid_manifest` (entries con `level.dat`), **snapshot pre-restore
  protegido** si el mundo existía, `remove` + `move(staging → worlds/<nombre>)`;
  éxito → `BACKUP.RESTORE_COMPLETED` + `start` si estaba corriendo; fallo →
  rollback al pre-restore (best-effort) y `BACKUP.RESTORE_FAILED` (el servidor
  queda detenido). El pre-restore se registra como backup `protected=True`.
- **prune**: retención keep-last-N por mundo (default 10), respeta `protected`
  y omite estado `DELETED`; borra artefacto + registro + `BACKUP.DELETED`.
- **validate**: checksum + manifiesto con `level.dat` → `BACKUP.VALIDATED`;
  cualquier fallo → registro `CORRUPT` + `BackupCorruptError`.

### Eventos
- Publica `BACKUP.STARTED/PROGRESS/COMPLETED/FAILED/RESTORE_STARTED/
  RESTORE_COMPLETED/RESTORE_FAILED/DELETED/VALIDATED` (9; topics
  `backup.*`). Consume `WORLD.DELETED` (`WorldDeletedHandler` → `mark_orphaned`,
  defensivo). `TASK.STARTED` (backup programado) queda reservado para Fase G.

### Infraestructura
- `backup_backups` (migración `0007_backup_tables`, índice por `server_id`),
  `PostgresBackupRepository` (upsert con `pg_insert`, listado desc por
  `created_at` con filtro de mundo y límite, `mark_orphaned` como UPDATE
  atómico) e `InMemoryBackupRepository` para tests.
- Wiring: `BackupFacade` en el `AppContainer` y bloque en `build_container`
  (`PostgresBackupRepository`, `LocalBackupStore` en
  `backup.base_path` default `{storage_base}/backups`, `console_facade` y
  `server_facade`); `alembic/env.py` y `tests/conftest.py` registran los
  modelos.

### Decisión §23 — restauración y verificación
- La verificación de checksum (paso previo a cualquier extracción) **no publica
  `BACKUP.RESTORE_FAILED`**: marca el registro `CORRUPT` y lanza
  `BackupCorruptError` (el evento de fallo de restauración queda para errores
  de staging/swap, donde el servidor ya fue detenido y hay que notificar).
- El branch de rollback (`swapped=True`) es **defensivo**: con el swap como
  última operación atómica de `_stage_and_swap`, no hay ruta de ejecución que
  falle después; se conserva por robustez ante fallos del adaptador.

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (294 archivos) ·
  `uv run mypy --strict .` ✅ (294 archivos).
- `uv run pytest -q` ✅ **398 passed, 28 deselected** (antes 355/24):
  +27 use cases + handlers Backup, +12 `LocalBackupStore`; los +4 deselected
  son la integración opt-in contra Postgres real
  (`test_backup_postgres_integration.py`, requiere
  `BEDROCK_PANEL_TEST_DATABASE_URL`).
- Cadena alembic: `0006_world_tables -> 0007_backup_tables (head)`.

### Pendiente / deuda
- **Gatillo programado** (`TASK.STARTED`) pendiente de la Fase G (Scheduler,
  paso 15); `BACKUP.PROGRESS` definido pero aún sin emisor (snapshots sin
  progreso incremental en el MVP).
- **Guard de concurrencia** (`BackupInProgressError` definido en el dominio)
  sin emisor aún: el lock `backup:{server_id}` protege las operaciones de
  storage, pero no rechaza backups simultáneos del mismo servidor a nivel de
  registro.
- **Lock distribuido** y **backup remoto (S3)** en Fase 2 (mismo criterio que
  §22).
- No avanzar al paso 14 (Permission) sin confirmación del usuario.


## 24. Paso de cierre — API HTTP de World/Player/Backup (vertical slice §16)

Cierre del paso 1-13 del TDD §16: los tres módulos que quedaban sin HTTP se
exponen vía REST con el mismo patrón que IAM/Server/Console (`modules/*/api`
con `schemas.py` + `router.py`, auth compartida de `bootstrap/security.py`,
mapeo central de errores de `bootstrap/errors.py` y facades intactas). Solo
traducción request → comando y resultado → respuesta; sin reglas de negocio en
la API (Blueprint §4.7).

### Decisiones confirmadas por el usuario
- **Rol de las operaciones destructivas** (world.delete, backup.restore —
  sobrescribe el mundo actual — y backup.delete): **operator por servidor**
  (`require_server_action`), consistente con el precedente `server.delete`.
  No se exige admin global; una matriz por acción es Fase H.
- **Player ban/unban/kick**: se exponen vía API ahora, ampliando la facade
  pública con los use cases del Paso 11 (`player.manage`, operator+).

### Decisión §24 — consistencia del export de World
- `ExportWorldResult` y `ExportWorldUseCase` ganan el campo **`consistent`**
  (pendiente del Paso 12): `True` si el servidor estaba detenido o `save hold`
  fue aceptado por Console; `False` si corría y el `save hold` falló
  (best-effort, §22). `_best_effort_save` ahora devuelve `bool`. La respuesta
  HTTP del export lleva la cabecera `X-BedrockPanel-Consistent` (el cuerpo es
  el artefacto binario) y `WORLD.EXPORTED` incluye `consistent` en el payload.

### Decisiones §24 — descargas, tamaño de subida y delete de backup
- **Streaming de artefactos grandes** (export de mundo y download de backup):
  `StreamingResponse` con generador que cierra el stream al terminar; nunca se
  carga el mundo/backup en memoria. `BackupFacade.download` abre el artefacto
  y devuelve `BackupDownload(backup, stream)`.
- **Límite de import de mundos**: `MultiPartParser.max_part_size` (Starlette)
  solo limita campos, no los archivos que spolea a disco → límite explícito
  `Settings.world_max_import_bytes` (default 2 GiB, `BEDROCK_PANEL_...`),
  validado en el router al leer el `UploadFile` (413 `WORLD.IMPORT_TOO_LARGE`).
- **Delete individual de backup**: nuevo `DeleteBackupUseCase` +
  `DeleteBackupCommand` + `BackupFacade.delete_backup`; borra artefacto +
  registro y publica `BACKUP.DELETED`. Los backups **protegidos** se rechazan
  (422 `BACKUP.INVALID_PAYLOAD`), mismo criterio que prune.
- **Player por servidor**: los endpoints player son scoped a `server_id` para
  reusar `require_server_action` (lectura ≥ viewer, gestión ≥ operator).

### Endpoints
- **World** (`/servers/{server_id}/worlds`): list, create, import (multipart
  `file` + `name`), sync, `/{name}/export` (zip `.mcworld`), `/{name}/duplicate`,
  `/{name}/activate`, delete. Acciones: `world.list/view/export` lectura,
  `world.create/import/sync/duplicate/activate/delete` escritura.
- **Backup** (`/servers/{server_id}/backups`): create, list (filtro por mundo y
  límite), `/{backup_id}`, `/{backup_id}/restore`, `/{backup_id}/validate`,
  `/{backup_id}/download` (tar.zst), `/{backup_id}` (delete), prune. Acciones:
  `backup.list/view/download` lectura; `backup.create/restore/validate/delete/
  prune` escritura. Todo backup se resuelve con verificación de `server_id`
  (404 sin filtrar existencia).
- **Player** (`/servers/{server_id}/players`): `search?name=` (resolveXuid),
  `online` (presencia), `/{xuid}` (findPlayer), `/{xuid}/sessions`,
  `/{xuid}/ban|unban|kick` (202, acuse de Console). Acciones: `player.list/view/
  sessions/online` lectura; `player.manage` escritura.
- `READ_ACTIONS` ampliado con `world.export`, `backup.view`, `backup.download`,
  `player.view`, `player.sessions`, `player.online`.

### Facades (sin tocar su lógica interna)
- **World**: `ExportWorldResult.consistent` + `_best_effort_save → bool`.
- **Backup**: `download` y `delete_backup` (nuevos; `DeleteBackupUseCase`).
- **Player**: `list_sessions`, `online_players`, `ban`, `unban`, `kick`
  (reusan los use cases del Paso 11).

### Infraestructura
- Dependencia `python-multipart` añadida (`pyproject.toml`) para `Form`/`File`.
- `bootstrap/main.py` registra los routers World/Player/Backup bajo
  `Settings.api_prefix`; los `Container` ya exponían las tres facades.

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (300 archivos) ·
  `uv run mypy --strict .` ✅ (300 archivos).
- `uv run pytest -q` ✅ **414 passed, 28 deselected** (antes 398/28):
  +16 tests HTTP de integración (World 8, Backup 4, Player 4) en
  `test_api_integration.py`, incluyendo import/export multipart con streaming,
  límite de tamaño (413), restore de backup, prune por retención, presencia/
  sesiones y ban/unban/kick.

### Pendiente / deuda
- **Scheduler (paso 15)** y **Permission (paso 14)**: no avanzar sin
  confirmación del usuario.

---

## 25. Corrección — `WORLD.ACTIVATED` no recreaba el contenedor

### Síntoma (reportado en runtime real)
- `POST /servers/{id}/worlds/{name}/activate` responde 200 y la metadata de
  World queda `activated=true`, pero el contenedor **nunca se recrea**:
  `docker inspect` muestra un `Created` anterior a la llamada, el servidor
  sigue sirviendo el mundo viejo y el env del contenedor no lleva
  `LEVEL_NAME` ni `SERVER_NAME`.

### Causa raíz
- La cadena `World → WORLD.ACTIVATED → Server` existía pero **no transportaba
  el mundo activado**: `WorldActivatedHandler` solo reenviaba `server_id` y
  descartaba el `name` del payload. `ApplyConfigUseCase` re-renderizaba el
  spec desde la config deseada de Configuration (que la activación de un mundo
  no toca), así que el spec no cambiaba, `_spec_changed` era `False` y el
  contenedor no se recreaba.
- Además `LEVEL_NAME`/`SERVER_NAME` solo se emiten si vienen de la config
  deseada de Configuration; la activación de un mundo nunca los poblaba.

### Decisión §25 — el `name` del mundo activado se inyecta como `LEVEL_NAME`
- `ApplyConfigCommand` gana el campo `level_name: str | None = None`
  (directorio del mundo activado, el `name` de `WORLD.ACTIVATED`).
- `WorldActivatedHandler` propaga `event.payload["name"]` al comando
  (`_optional_level_name`); mantiene `config_rev=None` (decisión §22).
- `ApplyConfigUseCase` inyecta `LEVEL_NAME=<level_name>` en la config deseada
  **antes** de renderizar el spec: si cambia respecto al spec actual, recrea
  (parar si corre → materializar → arrancar si tocaba). Sin `level_name`
  conserva el comportamiento previo (p. ej. `CONFIG.CHANGED`).

### Archivos
- `apps/backend/src/app/modules/server/application/commands.py`
- `apps/backend/src/app/modules/server/application/handlers.py`
- `apps/backend/src/app/modules/server/application/use_cases.py`
- `apps/backend/tests/test_server_handlers.py`, `apps/backend/tests/test_server_use_cases.py`

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (300 archivos) ·
  `uv run mypy --strict .` ✅ (300 archivos).
- `uv run pytest -q` ✅ **418 passed, 28 deselected** (antes 414/28):
  +4 tests (handler inyecta `LEVEL_NAME` y recrea, payload sin `name` conserva
  el actual, use case con `level_name` inyecta env y recrea, use case sin
  `level_name` no inyecta).
- Pendiente de verificación en runtime real: repetir el ciclo crear mundo →
  activar y confirmar en el contenedor `Created` renovado + `LEVEL_NAME`
  correcto (criterio del informe de bug).

---

## 26. Corrección — `sync` de World no actualizaba mundos ya conocidos

### Síntoma (reportado en runtime real)
- Un mundo creado a mano en el volumen ("Mundo Nuevo Test1", ~988K en disco)
  queda con `size_bytes = 0` en `world_metadata` tras **dos**
  `POST /servers/{id}/worlds/sync` (ambas responden 201 sin error).

### Causa raíz
- `ScanWorldsUseCase.sync` era solo "descubridor": para cada directorio con
  `level.dat`, `if name in tracked: continue` descartaba todo mundo ya
  conocido, así que los campos derivables del disco (`size_bytes`,
  `level_name`) solo se aplicaban al crear la metadata. `list_worlds()` del
  storage ya devolvía el tamaño real; el use case simplemente no lo usaba para
  filas existentes.

### Decisión §26 — `sync` es un reconciliador completo
- Por cada mundo del filesystem: si no hay metadata → se crea (`activated=False`,
  como antes); si ya existe → se refrescan `level_name` y `size_bytes` desde el
  disco vía `replace` (nuevo helper `_refreshed_world`), preservando `id`,
  `activated`, `created_at` y solo tocando `updated_at` cuando algo cambió
  (idempotente: un `sync` sin cambios no escribe).
- El return pasa de "solo los nuevos" a **el listado reconciliado completo**
  (creados + refrescados), para que el cliente obtenga el estado fresco en la
  misma respuesta.
- **Declaración explícita de alcance**: `sync` **sigue siendo manual** — no se
  auto-dispara con `WORLD.SAVED`. Motivos: (a) `WORLD.SAVED` lo publica el
  `SaveDetector` del módulo Console y no está cableado a World, lo que añadiría
  una dependencia de eventos nueva sin pedido; (b) el reconcilio es barato,
  idempotente y el panel ya puede invocarlo cuándo quiera; (c) la activación
  (`WORLD.ACTIVATED`, corregida en §25) ya refresca el contenedor en el ciclo
  de vida. Si en el futuro se quiere refresco automático de tamaño, será una
  decisión de producto documentada aparte (nuevo suscriptor de `WORLD.SAVED`).
- No borra metadata de mundos que ya no están en disco (el borrado sigue
  pasando por `DeleteWorldUseCase`); un mundo sin `level.dat` simplemente no se
  reconcilia.

### Archivos
- `apps/backend/src/app/modules/world/application/use_cases.py`
  (`ScanWorldsUseCase.sync`, helper `_refreshed_world`)
- `apps/backend/src/app/modules/world/application/facade.py` (docstring de `sync`)
- `apps/backend/tests/test_world_use_cases.py`

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (300 archivos) ·
  `uv run mypy --strict .` ✅ (300 archivos).
- `uv run pytest -q` ✅ **421 passed, 28 deselected** (antes 418/28): +3 tests
  (refresca `size_bytes` de un mundo conocido, preserva identidad/activación al
  refrescar, refresca `level_name` desde `levelname.txt`). Siguen verdes
  `test_sync_no_duplica_metadata_existente` y el sync vía HTTP.
- Reproducción del bug en tests sin Docker: mundo con metadata y `size_bytes`
  desactualizado → `sync` → `size_bytes` = real del disco (confirmado en
  `world_metadata` del repositorio y en la respuesta de `sync`).

---

## 8. Fix `CONSOLE.STDIN_WRITE` — `SocketIO` no expone `.makefile()`

> **Fecha**: 2026-08-07
> **Issue**: Al enviar comandos via `POST /servers/{id}/players/{xuid}/ban`, el
> endpoint fallaba con error `CONSOLE.STDIN_WRITE`. El contenedor Docker estaba
> sano y corriendo.

### Causa raíz
`container.attach_socket()` en docker-py devuelve un `socket.SocketIO`, **no**
un `socket.socket` real. `SocketIO` no expone el método `.makefile("w")`, por lo
que `send_stdin` en `DockerRuntimeAdapter` lanzaba un `AttributeError`. Este era
capturado por `_map_docker_errors`, traducido a `DockerError`, y luego envuelto
como `StdinWriteError(CONSOLE.STDIN_WRITE)` en `CommandQueue`.

### Fix
- **Archivo**: `apps/backend/src/app/infrastructure/runtime/docker.py:541-552`
- **Cambio**: Se reemplazó el bloque `socket.makefile("w")` / `.write()` /
  `.flush()` / `.close()` por acceso directo al socket subyacente via
  `socket._sock` (con fallback al propio `socket` si no tiene `_sock`) y
  `raw.sendall(data.encode("utf-8"))`.

```python
# Antes
stream = socket.makefile("w")
stream.write(data)
stream.flush()
stream.close()

# Después
raw = socket._sock if hasattr(socket, "_sock") else socket
raw.sendall(data.encode("utf-8"))
```

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅
- `uv run pytest -q` ✅ **421 passed, 28 deselected**

### Nota posterior (2026-08-07)
El fix inicial evitó el `AttributeError` pero no cerraba correctamente la
conexión HTTP subyacente del wrapper `SocketIO` de docker-py, lo que provocaba
`ValueError: I/O operation on closed file` y que el comando nunca llegara al
proceso del contenedor. Se confirmó que `finally: socket.close()` (sobre el
wrapper `SocketIO` original, no solo sobre `_sock`) ya estaba presente y en la
posición correcta envolviendo todo el bloque `try`. La estructura actual es
correcta: `try: sendall → finally: socket.close()`.

### Nota adicional (2026-08-07) — `stream: 1`
Faltaba el parámetro `"stream": 1` en los `params` de `attach_socket()`. Sin
él la API de Docker podía no dejar la conexión en modo hijacked bidireccional,
haciendo que `sendall()` no lanzara error pero el dato nunca llegara al
proceso del contenedor como una línea de stdin real.

```python
# Antes
params={"stdin": 1, "stdout": 0, "stderr": 0}

# Después
params={"stdin": 1, "stdout": 0, "stderr": 0, "stream": 1}
```

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅
- `uv run pytest -q` ✅ **421 passed, 28 deselected**

---

## 9. Módulo Permission — implementación completa (Blueprint §3.6)

> **Fecha**: 2026-08-07
> **Alcance**: Paso 14 del blueprint. Allowlist, niveles de permiso
> (operator/member/visitor), APIs HTTP y PUB/SUB de eventos.

### Archivos creados

| Archivo | Contenido |
|---|---|
| `modules/permission/domain/entities.py` | `AllowlistEntry`, `PermissionEntry`, `PermissionLevel` Enum |
| `modules/permission/domain/errors.py` | `PermissionValidationError`, `PermissionNotFoundError` |
| `modules/permission/domain/events.py` | `player_operator_changed()` factory + constantes |
| `modules/permission/application/ports.py` | `PermissionStorageResolver` (Protocol) |
| `modules/permission/application/use_cases.py` | `add_to_allowlist`, `remove_from_allowlist`, `list_allowlist`, `set_permission_level`, `remove_permission`, `list_permissions` |
| `modules/permission/application/facade.py` | `PermissionFacade` |
| `modules/permission/application/handlers.py` | `AllowlistXuidResolver` (consume `PLAYER.JOINED`) |
| `modules/permission/api/schemas.py` | `AllowlistEntryResponse`, `SetPermissionRequest`, etc. |
| `modules/permission/api/router.py` | Endpoints bajo `/servers/{id}/permissions` |
| `tests/test_permission_use_cases.py` | 23 tests unitarios |

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `bootstrap/container.py` | `Container` + `permission_facade`; wiring de `PermissionDeps` |
| `bootstrap/main.py` | Registro del router de Permission |
| `tests/test_api_integration.py` | `permission_facade` en `make_container` |

### Funcionalidades

- **Allowlist**: CRUD sobre `allowlist.json` vía `ServerStoragePort` + comando
  `allowlist add/remove` vía Console cuando el servidor corre.
- **Permisos**: CRUD sobre `permissions.json` + comandos `op`/`deop`.
- **Eventos**: `PLAYER.OPERATOR_CHANGED` publicado en `set_permission_level` y
  `remove_permission`.
- **Handler**: `PLAYER.JOINED` → autocompleta XUID en entradas de allowlist
  pendientes (defensivo, solo loguea si falla).
- **API REST**: endpoints con auth (`permission.write`/`permission.read`):
  `POST/DELETE/GET /allowlist`, `PUT/DELETE /operators/{xuid}`.

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (310 archivos)
- `uv run pytest -q` ✅ **444 passed, 28 deselected** (antes 421/28): +23 tests.

---

## 10. Exposición del toggle ALLOW_LIST en Permission

> **Fecha**: 2026-08-07
> **Alcance**: Endpoint para activar/desactivar la allowlist (`ALLOW_LIST`) y
> recrear el contenedor vía evento `PERMISSION.ALLOWLIST_TOGGLED`.

### Decisión de diseño
El mecanismo de `CONFIG.CHANGED` no es reutilizable de forma directa: el
`ConfigChangedHandler` reaplica la config deseada que lee de Configuration, y
Permission **no persiste** en Configuration (no tiene su facade de escritura);
la env `ALLOW_LIST` no llegaría al spec. Se añade el evento simple
`PERMISSION.ALLOWLIST_TOGGLED` con payload `{server_id, enabled}` y se replica
el patrón de `WORLD.ACTIVATED`/`LEVEL_NAME`: el handler de Server pasa
`allow_list: bool | None` al `ApplyConfigCommand` y el use case inyecta
`ALLOW_LIST=<true/false>` en el spec antes de renderizar (recreación incluida
si el spec cambió).

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/permission/domain/events.py` | `ALLOWLIST_TOGGLED`, `ALLOWLIST_TOGGLED_TOPIC` + factory `allowlist_toggled()` |
| `modules/permission/application/use_cases.py` | `set_allowlist_enabled()` publica el evento (con `actor_id`) |
| `modules/permission/application/facade.py` | `PermissionFacade.set_allowlist_enabled` |
| `modules/permission/api/schemas.py` | `SetAllowlistEnabledRequest {enabled: bool}` |
| `modules/permission/api/router.py` | `PUT /servers/{server_id}/permissions/allowlist-enabled` (204, auth `permission.write`/operator+) |
| `modules/server/application/commands.py` | `ApplyConfigCommand.allow_list: bool | None` |
| `modules/server/application/handlers.py` | `AllowlistToggledHandler` + `_optional_allow_list()` |
| `modules/server/application/use_cases.py` | `ApplyConfigUseCase` inyecta `ALLOW_LIST=<true/false>` |
| `modules/server/domain/events.py` | `ALLOWLIST_TOGGLED_TOPIC = "permission.allowlist_toggled"` |
| `modules/server/application/facade.py` | Suscripción del `AllowlistToggledHandler` |
| `tests/test_permission_use_cases.py` | +2 tests del use case |
| `tests/test_server_handlers.py` | +3 tests del handler |

### Funcionalidades

- **Endpoint** `PUT /servers/{server_id}/permissions/allowlist-enabled` con
  body `{"enabled": true}` (mismo auth `permission.write`, operator+).
- **Evento** `PERMISSION.ALLOWLIST_TOGGLED` (`{server_id, enabled}`) publicado
  por Permission y consumido por Server para recrear el contenedor.
- **Spec**: `ALLOW_LIST=true/false` inyectado antes de renderizar, mismo patrón
  que `LEVEL_NAME` (sin tocar `config_rev`).

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (310 archivos)
- `uv run pytest -q` ✅ **449 passed, 28 deselected** (antes 444/28): +5 tests.

---

## 11. Sistema de bans persistentes — globales y por servidor (ADR-011)

> **Fecha**: 2026-08-07
> **Alcance**: Reemplaza el ban/unban de solo-consola (sin persistencia) por
> bans durables en `player_global_bans`/`player_server_bans`, con enforcement en
> `PLAYER.JOINED` y kick inmediato al banear a un jugador online. Migración
> Alembic `0008_player_ban_tables`.

### Decisión de diseño

- **Dos agregados, dos tablas** (ADR-011): `GlobalBan`/`player_global_bans`
  (decisión panel-wide, unicidad sobre `lower(gamertag)`) y
  `ServerBan`/`player_server_bans` (atado a `server_id`, unicidad sobre
  `(server_id, lower(gamertag))`). **`player_players` no se toca**: es
  identidad global por XUID sin `server_id` (discrepancia con TDD §15.5
  documentada en ADR-012).
- **Enforcement**: `BanEnforcementHandler` en `PLAYER.JOINED` chequea global
  primero (xuid fiable, fallback gamertag case-insensitive cuando el XUID es
  `0`/ausente — "ban blando" en offline), luego por servidor; respeta
  `expires_at` vencido. El kick va por el mismo puerto Console que usan
  `Backup`/`Permission` (`SendCommand` → `ConsoleFacade`).
- **Kick inmediato**: el `POST /servers/{server_id}/players/{player_id}/ban`
  expulsa en el mismo request si hay `PlaySession` abierta
  (`_kick_best_effort`, no rompe el request si el server no corre).
- **Endpoints**: `POST /players/bans/global` + `DELETE /players/bans/global/{ban_id}`
  (admin global, `require_action("player.ban.global")`) y
  `POST/DELETE /servers/{server_id}/players/{player_id}/ban`
  (operator+, ACL por servidor, `permission.write`). El viejo `POST .../ban` y
  `POST .../unban` (solo-consola) quedan **removidos/reemplazados**; `/kick`
  se mantiene igual.
- **Eventos**: `PLAYER.BANNED`/`PLAYER.UNBANNED` (topics `player.banned`/
  `player.unbanned`) publicados por los use cases al crear/quitar un ban.

### Archivos creados

| Archivo | Contenido |
|---|---|
| `infrastructure/db/alembic/versions/0008_player_ban_tables.py` | Crea `player_global_bans` y `player_server_bans` + índices de unicidad |
| `modules/player/domain/bans.py` | `GlobalBan`, `ServerBan`, `BanScope`, `normalize_gamertag`, `is_valid_xuid`, `kick_command` |
| `tests/test_player_ban_enforcement.py` | 8 tests del enforcement (xuid, fallback, case-insensitive, vencido, por servidor, precedencia) |

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/player/domain/events.py` | `PLAYER.UNBANNED` + factories `player_banned`/`player_unbanned` (payload scope + identidad) |
| `modules/player/domain/repository.py` | `PlayerBanRepositoryPort` (global + por servidor) |
| `modules/player/application/commands.py` | `BanPlayerGloballyCommand`, `UnbanPlayerGloballyCommand`, `BanPlayerOnServerCommand`, `UnbanPlayerOnServerCommand` |
| `modules/player/application/use_cases.py` | `BanPlayerGloballyUseCase`, `UnbanPlayerGloballyUseCase`, `BanPlayerOnServerUseCase`, `UnbanPlayerOnServerUseCase` + `_is_online`/`_kick_best_effort` |
| `modules/player/application/handlers.py` | `BanEnforcementHandler` (enforcement en `PLAYER.JOINED`) |
| `modules/player/application/facade.py` | Facade de bans + suscripción del `BanEnforcementHandler` |
| `modules/player/application/results.py` | `GlobalBanView`, `ServerBanView` + proyecciones |
| `modules/player/api/router.py` | Endpoints de bans globales y por servidor; remueve `POST /ban` y `POST /unban` de consola |
| `modules/player/api/schemas.py` | `GlobalBanRequest`, `GlobalBanResponse`, `BanPlayerRequest` |
| `modules/player/infrastructure/models.py` | `GlobalBanRow`, `ServerBanRow` + índices `uq_*` |
| `modules/player/infrastructure/postgres_repository.py` | `PostgresPlayerBanRepository` (upsert + delete con rowcount) |
| `modules/player/infrastructure/serialization.py` | Proyecciones de bans row ↔ entidad |
| `modules/player/infrastructure/memory.py` | `InMemoryPlayerBanRepository` (test) |
| `bootstrap/container.py` | Wiring de `PostgresPlayerBanRepository` + `ban_repository` en `PlayerDeps` |
| `tests/test_player_use_cases.py` | +8 tests de use cases de bans (persistencia, eventos, kick inmediato) |
| `tests/test_api_integration.py` | Tests de endpoints de ban (204/404/403, admin global vs viewer) |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (313 archivos)
- `uv run pytest -q` ✅ **466 passed, 30 deselected** (antes 449/28): +17 tests.

---

## 12. Race condition en el kick — reintento con backoff si BDS aún no tiene al jugador

> **Fecha**: 2026-08-07
> **Origen**: **prueba manual real**, no tests. Al banear a un jugador que se
> acaba de conectar, BDS tardaba ~5s entre `Player connected` y `Player Spawned`
> (handshake/descarga de resource packs). El `kick` enviado en `PLAYER.JOINED`
> fallaba con `No targets matched selector` porque el jugador aún no es un
> target seleccionable, y **no había reintento**: el jugador se quedaba dentro.
> Reproducido en dos conexiones distintas (primera conexión del server y una
> reconexión), comportamiento consistente.

### Decisión de diseño

- **Console no expone el resultado de un comando**: `send_command` solo devuelve
  un acuse de escritura en stdin (`CommandAck`). Se añade
  `ConsoleFacade.send_command_and_observe(cmd, *, window_s)` que envía el comando
  y observa la salida de consola en la ventana siguiente (`ConsoleObservation`:
  acuse + líneas). Console sigue sin interpretar negocio: devuelve las líneas
  crudas y quien consume decide.
- **Reintento en Player** (`kick_with_retry` en `modules/player/application/use_cases.py`):
  envía `kick <gamertag> [reason]`, observa la salida `window_s`; si aparece el
  patrón de error (`no targets matched selector` / `could not find player`,
  case-insensitive) reintenta con backoff corto `(0.5, 1.0, 1.5, 2.0, 2.0)s`
  hasta agotar `len(backoff) + 1` intentos. Si la ventana cierra sin error → se
  confirma éxito y se detiene (no se reintenta a ciegas ni en bucle infinito).
- **Fallo visible**: al agotar los intentos se loguea estructurado
  `player.ban_kick_failed` con `server_id`, `gamertag`, `reason`, `attempts`,
  `command` — en vez de fallar en silencio.
- **Aplicado en los tres flujos de kick** que comparten la lógica de envío:
  `BanEnforcementHandler` (PLAYER.JOINED), `BanPlayerOnServerUseCase` (kick
  inmediato al banear a un online, `_kick_best_effort`) y `KickPlayerUseCase`
  (kick manual `POST .../kick`).

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/console/application/results.py` | `ConsoleObservation` (ack + líneas observadas) |
| `modules/console/application/facade.py` | `send_command_and_observe(cmd, *, window_s)` |
| `modules/player/application/use_cases.py` | `kick_with_retry` + constantes de backoff/patrones; `KickPlayerUseCase.kick` y `_kick_best_effort` usan el reintento |
| `modules/player/application/handlers.py` | `BanEnforcementHandler._enforce` usa `kick_with_retry` |
| `tests/test_player_kick_retry.py` | Nuevo: reintento-then-success, sin error sin reintento, agotamiento + log |
| `tests/test_console_facade.py` | +1 test de `send_command_and_observe` (captura salida en la ventana) |
| `tests/test_player_ban_enforcement.py` | Fixture autouse: ventana/backoff mínimos para no ralentizar |
| `tests/test_player_use_cases.py` | Ídem |
| `tests/test_api_integration.py` | Ídem |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (314 archivos)
- `uv run pytest -q` ✅ **470 passed, 30 deselected** (antes 466/30): +4 tests.

---

## 13. Self-deadlock del enforcement + enforcement fantasma al arrancar el stream

> **Fecha**: 2026-08-07
> **Origen**: **prueba real**, no tests. Dos bugs encontrados juntos en
> producción:
> - **Bug A — enforcement fantasma**: al reiniciar el servidor, el stream
>   arrancaba con `tail="all"`, que rejugaba el historial completo del contenedor
>   (incluidas líneas viejas de `Player connected` de la sesión anterior). Cada
>   línea rejugada disparaba un `PLAYER.JOINED` fantasma → `BanEnforcementHandler`
>   → kick a un jugador que no estaba realmente conectado en el contenedor nuevo
>   ("No targets matched selector").
> - **Bug B — el retry no corría**: en la conexión real solo se enviaba 1 kick
>   y se logueaba `player.ban_kick_confirmed` a pesar del error de BDS.

### Causa raíz (única, la que el prompt sospechaba)

La detección de éxito/error **sí** mira `observation.lines`, pero **la ventana de
observación nunca podía ver la salida**: `BanEnforcementHandler` corre inline
dentro de la cadena de `bus.publish(console_output(...))` de
`ConsoleLogStream.consume` (el `PLAYER.JOINED` lo publica `PlayerJoinDetector`,
que es un handler de `CONSOLE.OUTPUT`). Cuando `send_command_and_observe` espera
la respuesta del kick, el consumidor del stream está **bloqueado en el mismo
`bus.publish`** y no puede leer la respuesta desde la cola del worker → la
ventana siempre queda vacía → `_kick_output_failed` siempre `False` → "confirmed"
→ sin reintento. Esto explica el "confirmed a pesar del error" de ambos bugs.

### Fix

- **`BanEnforcementHandler`** (`modules/player/application/handlers.py`): el kick
  se ejecuta en un **task de fondo** (`asyncio.create_task`) con tracking de
  tareas pendientes (`wait_pending`). El `PLAYER.JOINED` se procesa inline (abre
  sesión) pero el kick ya no bloquea al consumidor del stream: la respuesta de
  BDS llega a la ventana de observación y el retry corre.
- **`PlayerFacade`**: guarda la referencia al handler y expone
  `await_ban_enforcement()` para tests (espera los kicks en curso).
- **`DockerRuntimeAdapter.stream_logs`** (`infrastructure/runtime/docker.py`):
  `tail="all"` → `tail=0`. El stream arranca **solo con líneas nuevas**, sin
  rejugar el historial del contenedor tras un stop/start. Elimina el
  `PLAYER.JOINED` fantasma (Bug A) y la duplicación de líneas en el buffer.

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/player/application/handlers.py` | Enforcement en task de fondo + `wait_pending` |
| `modules/player/application/facade.py` | Guarda el handler + `await_ban_enforcement()` |
| `infrastructure/runtime/docker.py` | `stream_logs` con `tail=0` (sin replay de historial) |
| `tests/test_player_enforcement_deadlock.py` | **Nuevo**: reproduce el self-deadlock con el flujo real (stream task + detector + enforcement); falla antes del fix y pasa después |
| `tests/test_player_ban_enforcement.py` | Harness espera el enforcement pendiente tras `join()` |
| `tests/test_player_kick_retry.py` | Ídem |
| `tests/test_api_integration.py` | `seed_player` espera el enforcement pendiente |
| `tests/test_runtime.py` | `stream_logs` ahora usa `tail=0` |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (315 archivos)
- `uv run pytest -q` ✅ **472 passed, 30 deselected** (antes 470/30): +2 tests.

**El test nuevo reproduce el bug**: con el handler inline (pre-fix) el
`test_player_enforcement_deadlock.py` falla (solo 1 kick, la ventana de
observación se queda vacía por el self-deadlock); con el fix pasa (el enforcement
observa el error y reintenta). Verificado ejecutando la suite con el handler
revertido.

---

## 14. Retry infinito en el auto-kick del enforcement de bans

> **Fecha**: 2026-08-07
> **Origen**: **prueba real**, no tests. En los logs aparecía
> `player.ban_kick_failed` seguido de `player.ban_enforced` repitiéndose cada
> 10-30s indefinidamente, incluso **minutos después** de que el jugador baneado
> se desconectara (BDS logueaba `Player disconnected`, sin reconexión posterior).
> Cada intento fallido generaba `No targets matched selector` en BDS y una
> excepción `ValueError: I/O operation on closed file` del lado del panel
> (acumulación de sockets HTTP mal cerrados).

### Causa raíz

`kick_with_retry` reintentaba el kick tras un fallo **sin verificar si el
jugador seguía conectado** y con un tope demasiado alto (6 intentos): aunque el
jugador ya no estuviera en `player_sessions` (sesión cerrada con `left_at`), el
loop seguía enviando `kick` contra un target inexistente. Con el enforcement
re-disparándose sobre `PLAYER.JOINED` repetidos, el ciclo completo se repetía
cada ~10s (6 intentos × ventana de observación + backoff) indefinidamente. La
acumulación de sockets no era una ruta distinta: el kick usa el único path
corregido (`ConsoleFacade.send_command` → `SendCommandUseCase` →
`CommandQueue` → `DockerRuntimeAdapter.send_stdin`, que ya tiene `stream: 1` y
`finally: socket.close()`, change-log §8); eran los cientos de `attach_socket`
abiertos por los reintentos sin fin los que se acumulaban.

### Fix

- **`kick_with_retry`** (`modules/player/application/use_cases.py`):
  - **Antes de cada reintento** se verifica el estado real de conexión del
    jugador (`player_sessions` con `left_at IS NULL` para ese servidor, vía
    `_is_online`). Si ya se desconectó → se corta el retry y se loguea
    `player.ban_kick_aborted` (info), sin más envíos.
  - **Tope de intentos**: `KICK_MAX_ATTEMPTS = 3` (antes
    `len(KICK_RETRY_BACKOFF_SECONDS) + 1 = 6`) con backoff — no un loop sin fin.
  - Ahora recibe el `xuid` para poder comprobar la presencia (los callers pasan
    `player.xuid` / `cmd.player_id`).
- **`BanEnforcementHandler._enforce`** (`modules/player/application/handlers.py`):
  verifica `_is_online` antes de intentar el kick; si el jugador ya no está
  conectado loguea `player.ban_skip_offline` y no expulsa (nada que expulsar).
- **Socket**: confirmado que el kick usa el mismo `send_stdin` corregido (§8);
  sin cambios de ruta. El tope de intentos y el corte por desconexión eliminan
  la acumulación de sockets.

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/player/application/use_cases.py` | `kick_with_retry`: verifica presencia antes de cada reintento + `KICK_MAX_ATTEMPTS=3`; `_kick_best_effort`/`KickPlayerUseCase` pasan `xuid` |
| `modules/player/application/handlers.py` | `_enforce` verifica `_is_online` antes de expulsar |
| `tests/test_player_kick_retry.py` | Test: retry se corta si el jugador se desconecta; agotamiento ajustado a 3 |
| `tests/test_player_use_cases.py` | +2 tests de `kick_with_retry`: tope de intentos y corte por desconexión |
| `tests/test_player_enforcement_deadlock.py` | Agotamiento ajustado a `KICK_MAX_ATTEMPTS` |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (315 archivos)
- `uv run pytest -q` ✅ **475 passed, 30 deselected** (antes 472/30): +3 tests.

Los tests nuevos confirman que el retry se detiene al detectar que el jugador ya
no está conectado (1 solo kick) y que hay un tope de intentos (3).

---

## 15. Módulo Scheduler (Fase G) — tareas programadas recurrentes (§3.9)

> **Fecha**: 2026-08-07
> **Ámbito**: módulo completo `modules/scheduler` (dominio, aplicación, infra,
> API, migración) + wiring + tests. Ya existían consumidores esperando estos
> eventos: `TaskStartedHandler` de Console (paso 7) escucha `TASK.STARTED` con
> comandos en el payload (defensivo) y el gatillo programado de Backup (paso 13)
> quedó diferido explícitamente a este paso.

### Reutilización y decisiones

- **Cron parsing**: `croniter>=6` añadida a `pyproject.toml` (no existía una
  librería de cron; no se reinventa el parser). `application/cron.next_after`
  valida la expresión y calcula la próxima ocurrencia timezone-aware (UTC).
- **El "reloj"**: se reutiliza el **patrón** del `BackgroundPoller` de Monitoring
  (paso 9): `SchedulerPoller` (bucle asíncrono en `infrastructure/poller.py`)
  llama a `facade.tick()` cada `scheduler.poll_interval_seconds`; se arranca en
  el lifespan junto al poller de Monitoring. Los tests no arrancan el bucle
  (llaman a `tick` directamente), mismo criterio que Monitoring.
- **Política de reinicio ante `SERVER.CRASHED`**: verificado que ni Monitoring
  ni Server reintentan un arranque tras crash (Server solo registra
  `mark_crashed`). Por tanto **sí** le corresponde a Scheduler decidir cuándo
  reintentar: `ServerCrashedHandler` adelanta la próxima ejecución de las tareas
  `restart` activas del servidor a `ahora + scheduler.crash_retry_seconds`.
- **Ejecutores**: Scheduler no reimplementa lo que ya hacen (matriz §1.3): los
  facades Server/Backup/Console actúan vía puertos estructurales
  (`application/ports.py`). Las tareas `command` publican `TASK.STARTED` con
  `{"server_id", "commands"}` (el handler de Console lo consume); `backup` →
  `create_backup`; `restart` → `restart`.

### Entregables

- **Dominio** (`domain/`): `ScheduleTask` (id, tipo, cron, payload, estado,
  `next_run_at`, historial de reintentos `failures`/`max_retries`/
  `backoff_seconds`), tipos/estados `StrEnum`, errores `TASK.*`
  (`TASK.NOT_FOUND`, `TASK.INVALID_PAYLOAD`, `TASK.INVALID_STATE`), eventos y
  puerto de repositorio.
- **Aplicación** (`application/`): CRUD (`Create/Update/Delete`), `RunTask`,
  y `SchedulerEngine` (el reloj: `tick` ejecuta lo vencido y publica
  `TASK.STARTED`/`COMPLETED`). Handlers consumidos:
  `TaskFailedHandler` (`TASK.FAILED` → retry con backoff exponencial, tope
  `max_retries`), `ScheduledBackupFailedHandler` (`BACKUP.FAILED` → reconcilia
  `last_result`, no reintenta), `ServerCrashedHandler`.
- **Eventos**: publica `TASK.SCHEDULED/STARTED/COMPLETED/FAILED/CANCELLED`;
  consume `TASK.FAILED` (sus propios reintentos), `BACKUP.FAILED`,
  `SERVER.CRASHED`.
- **Infraestructura**: `SchedulerTaskRow` (`scheduler_tasks`), memoria, Postgres
  (upsert), serialización, `SchedulerPoller`.
- **API**: CRUD en `/servers/{id}/schedule/tasks` (+ `POST .../{task_id}/run`).
  `task.list`/`task.view` entran en `READ_ACTIONS` (lectura viewer+); el resto
  es escritura (operator+).
- **Migración**: `0009_scheduler_tables` (`down_revision=0008_player_ban_tables`;
  alembic head única). `conftest.py` registra los modelos del módulo.
- **Wiring**: `container.py` (facade + poller), `main.py` (router + poller en el
  lifespan), `config.py` (`scheduler.*`), `SchedulerDeps` inyecta Server/Backup
  y el reloj.

### La señal `TASK.STARTED` → Console

El flujo que estaba "esperando": una tarea programada `command` dispara
`TASK.STARTED` con `commands`; el `TaskStartedHandler` de Console (paso 7) lo
escucha y encola los comandos. Confirmado por test: el payload publicado incluye
`server_id` y la lista de comandos del contrato.

### Archivos modificados/añadidos (resumen)

| Archivo | Cambio |
|---|---|
| `pyproject.toml` | `+ croniter>=6` (y `types-croniter` en dev) |
| `modules/scheduler/domain/{task,events,errors,repository}.py` | Dominio |
| `modules/scheduler/application/{commands,results,ports,cron,use_cases,facade,handlers}.py` | Aplicación |
| `modules/scheduler/infrastructure/{models,memory,postgres_repository,serialization,poller}.py` | Infraestructura |
| `modules/scheduler/api/{schemas,router}.py` | API HTTP |
| `infrastructure/db/.../0009_scheduler_tables.py` | Migración (`scheduler_tasks`) |
| `bootstrap/{config,container,main}.py`, `bootstrap/errors.py` | Wiring + settings |
| `modules/iam/.../access.py` | `READ_ACTIONS` += `task.list/view` |
| `tests/conftest.py`, `tests/test_api_integration.py` | Modelos + Container del test |
| `tests/test_scheduler.py` | **22 tests** del módulo |
| `docs/change-log.md` | Esta entrada |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (335 archivos)
- `uv run mypy --strict .` ✅ (335 archivos)
- `uv run pytest -q` ✅ **497 passed, 30 deselected** (antes 475/30): **+22 tests**.
- `uv run alembic heads` → `0009_scheduler_tables (head)` (cadena lineal).

Los tests confirman: CRUD + validación de cron/payload, el reloj ejecuta por tipo
(command/backup/restart), `run_now` manual, reintento con backoff y tope
`max_retries`, desactivación/reactivación, y los tres handlers consumidos
(`TASK.FAILED`, `BACKUP.FAILED`, `SERVER.CRASHED`).

---

## 16. Kick inmediato en el ban global cuando el jugador está online

> **Fecha**: 2026-08-07
> **Origen**: **prueba real**, no tests. Un jugador con un ban **global** y una
> sesión abierta seguía jugando hasta reconectarse: el enforcement solo corre en
> `PLAYER.JOINED`, que no se dispara para quien ya está dentro. El descrito por
> servidor (`ban_on_server`) ya expulsaba al instante (§12, `_kick_best_effort`),
> pero el **global** (`BanPlayerGloballyUseCase.ban`) solo persistía el estado y
> publicaba `PLAYER.BANNED`; el kick quedaba diferido a la siguiente entrada.

### Causa raíz

El `BanPlayerGloballyUseCase.ban` no expulsaba en vivo: a diferencia del ban por
servidor (que sabe el `server_id` y usa `_is_online` + `_kick_best_effort`), el
ban global no tiene ámbito de servidor y no había forma de localizar la sesión
abierta del jugador en repositorio: `get_open_session`/`list_open_sessions` son
por servidor y `list_sessions` devuelve historial (no solo abiertas).

### Fix

- **Dominio** (`domain/repository.py`): nuevo método de puerto
  `list_open_sessions_by_xuid(xuid)` → sesiones abiertas del jugador en cualquier
  servidor (`left_at` nulo).
- **Infra**: implementado en `InMemoryPlayerRepository` y
  `PostgresPlayerRepository` (único query por `xuid` + `left_at IS NULL`).
- **`BanPlayerGloballyUseCase.ban`** (`application/use_cases.py`): tras persistir
  el ban, si se conoce el `xuid` localiza las sesiones abiertas y expulsa al
  jugador de cada servidor vía `_kick_best_effort` (mismo kick best-effort que el
  ban por servidor — el ban ya está persistido, un fallo de un servidor no rompe
  el request ni impide expulsar del resto). Si el jugador está offline (`xuid`
  ausente o sin sesión abierta) no expulsa nada y el `BanEnforcementHandler` en
  `PLAYER.JOINED` cubre futuras entradas (comportamiento actual).

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/player/domain/repository.py` | Puerto + `list_open_sessions_by_xuid(xuid)` |
| `modules/player/infrastructure/memory.py` | Implementación del nuevo método |
| `modules/player/infrastructure/postgres_repository.py` | Implementación del nuevo método |
| `modules/player/application/use_cases.py` | `_kick_global_sessions` + kick inmediato en `ban_globally` (cuando `xuid` conocido) |
| `tests/test_player_global_ban_immediate_kick.py` | **Nuevo**: kick inmediato al banear a un online; desde cada sesión abierta; offline no expulsa |

### Verificación
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (336 archivos)
- `uv run pytest -q` ✅ **500 passed, 30 deselected** (antes 497/30): +3 tests.

Los tests nuevos confirman: ban global expulsa al instante a un jugador online
(`kick Steve spam`), lo expulsa de cada servidor con sesión abierta, y no intenta
nada cuando el jugador está offline (lo cubre `PLAYER.JOINED`). El ban por
servidor ya expulsaba al instante (§12) — sin cambios en esa ruta.

---

## 17. Reconciliar streams de Console al arrancar el panel

> **Fecha**: 2026-08-07
> **Origen**: **prueba real**, no tests. Tras un restart del backend, el stream
> de un servidor `running` dejaba de capturar líneas nuevas: una reconexión real
> de un jugador nunca llegó a `console_lines` aunque el stream seguía sumando
> otras líneas del contenedor. Identificado antes (§19) y diferido; aquí se
> difiere el cierre: reconciliación al arranque.

### Causa raíz

Los streams se arrancan **solo** vía el evento `SERVER.STARTED`
(`ConsoleStreamManager`). Al reiniciar el panel, los servidores que ya estaban
`running` no vuelven a emitir `SERVER.STARTED` (el contenedor no se reinició),
así que nadie arranca su consumidor de logs y las líneas nuevas quedan sin
consumidor, aunque el resto del ciclo de vida del servidor siga bien.

### Fix

- **Reconciler** (`modules/console/infrastructure/reconcile.py`): nuevo
  `ConsoleStreamReconciler.reconcile()`. Consulta los servidores con estado
  persistido `running`, y para cada uno verifica contra el runtime real
  (`get_state(...) == running`) que el contenedor sigue corriendo; solo
  entonces arranca su stream vía `ConsoleStreamManager.ensure_stream` (mismo
  efecto que un recién llegado `SERVER.STARTED`). Si el contenedor real ya no
  corre, **no fuerza nada**: lo reconcilia el próximo ciclo del poller de
  Monitoreo (evita condiciones de carrera con la reconciliación).
- **`ConsoleStreamManager`** (`modules/console/infrastructure/stream_manager.py`):
  se extrae `ensure_stream(server_id)` público e idempotente reutilizado tanto
  por `SERVER.STARTED` como por el reconciler.
- **Ports**: `ServerConsoleReader` gana `list_servers()` (lectura). `FakeServerReader`
  de conftest lo implementa.
- **Wiring**: `Container` expone `console_stream_reconciler`; el lifespan de
  `main.py` lo ejecuta al arrancar, antes de levantar los pollers.

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/console/application/ports.py` | `ServerConsoleReader.list_servers()` |
| `modules/console/infrastructure/stream_manager.py` | `ensure_stream()` público, reutilizado por `SERVER.STARTED` |
| `modules/console/infrastructure/reconcile.py` | **Nuevo** `ConsoleStreamReconciler` |
| `bootstrap/container.py` | `console_stream_reconciler` en el `Container` |
| `bootstrap/main.py` | `reconcile()` al inicio del lifespan |
| `tests/conftest.py` | `FakeServerReader.list_servers()` |
| `tests/test_console_stream_reconcile.py` | **Nuevo**: 4 tests del reconciler |

---

## 18. Motivo (reason) en el kick del ban por servidor

> **Fecha**: 2026-08-07
> **Origen**: prueba real manual (celular). El ban global ya muestra un diálogo
> con el motivo en el cliente Bedrock; el ban por servidor mandaba el kick sin
> razón, dejando solo pantalla negra.

### Causa raíz

`ban_on_server`/`_kick_best_effort` sí enrutan `reason` hacia `kick_command`
(que produce `kick <name> [reason]`), pero cuando el payload del ban llega sin
`reason` (`BanPlayerOnServerCommand.reason = None`) el comando quedaba como
`kick <name>` → el cliente no mostraba motivo.

### Fix

- **`BanPlayerOnServerUseCase.ban`** (`modules/player/application/use_cases.py`):
  el kick del ban por servidor usa `cmd.reason or SERVER_BAN_KICK_DEFAULT_REASON`
  (`"Baneado del servidor"`) para que el comando siempre lleve motivo. El ban
  global no cambia (`kick_command` y el resto de rutas intactos).

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/player/application/use_cases.py` | constante `SERVER_BAN_KICK_DEFAULT_REASON` + fallback en `ban_on_server` |
| `tests/test_player_use_cases.py` | Test: kick del ban por servidor sin reason usa el motivo por defecto |

### Verificación (ambas tareas)
- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (338 archivos)
- `uv run pytest -q` ✅ **505 passed, 30 deselected** (antes 500/30): +5 tests
  (4 reconciler + 1 reason por defecto).

Los tests nuevos confirman: el reconciler arranca el stream de un servidor
> running real, lo omite si el contenedor no corre y es idempotente; y el ban
> por servidor incluye el motivo en el comando de kick ("Baneado del servidor").
> Tarea 1 y Tarea 2 se prueban en el sistema real por el usuario (restart del
> panel y celular, respectivamente).

## 19. Fase G — paso 16: módulo Template (`módulo Template`)

> **Fecha**: 2026-08-07
> **Origen**: planificación de fases (paso 16 del blueprint). Segundo módulo
> síncrono del proyecto (junto a Scheduler, aunque este conserva eventos);
> véase hallazgo B5 del blueprint.

### Qué añade

Plantillas ``.mctemplate`` (zip): capturar el estado de un servidor (mundo
activo + config) y reproducirlo (aplicarlo) sobre otro servidor existente,
más listar/consultar/eliminar. Es un módulo **síncrono** (request/response, sin
que publique ni consuma eventos).

### Decisiones de implementación

- **Formato zip** para el artefacto (mismo enfoque que ``.mcworld`` de World,
  no zstd de Backup). Cada miembro se valida por nombre exacto contra el
  conjunto esperado (`manifest.json`, `world_name.txt`, `config.json`,
  `world.mcworld`): artefacto malformado o con path traversal → `TEMPLATE.CORRUPT`.
- **Reuso de storage**: `ServerStorageResolver`/`LocalServerStorage` leen el
  mundo activo (`world_snapshot`) y lo restauran (`write_snapshot` validando
  `level.dat`); el artefacto vive en `{storage.base_path}/templates`
  (`{template_id}.mctemplate`) heredando la misma validación de rutas.
- **Mundo activo**: se determina consultando **World** (`WorldGateway` port →
  adapter sobre `WorldFacade.list_worlds`, filtrando `activated=true`), **no**
  desde Configuration. Configuration está vacía de origen (no existe API REST de
  Configuration todavía, deuda del paso 10) y el mundo activo real se gestiona
  en World (`world_metadata.activated`) e inyecta al RuntimeSpec vía
  `WORLD.ACTIVATED` (§25). El blueprint §3.11 declara World entre las deps de
  Template ("reutiliza Server + World + Configuration"); el patrón de puerto
  estructural sobre otra facade replica el que ya usa Scheduler.
- **Config**: `ConfigurationGateway` (adapter = `ConfigurationFacade`) para leer
  el perfil al capturar y reaplicar `level-name=<mundo destino>` al reproducir.
- **Síncrono**: `TemplateFacade` expone capture/apply/list/get/delete y
  `default_template() -> None` (satisface el protocolo `TemplateReader` que
  predefine Server para creación futura; aún sin uso).
- **Errores**: `TEMPLATE.NOT_FOUND` 404 · `TEMPLATE.VALIDATION`/`TEMPLATE.CORRUPT`
  422 · `TEMPLATE.EXISTS` 409 (mundo destino ocupado).
- **Auth**: endpoints reutilizan `require_server_action`; `template.list`/
  `template.view` en `READ_ACTIONS`; el resto es escritura (operator+).
- **Sin FK** a `server_servers` (contextos acotados, igual que Backup/
  Scheduler/Player).

### Archivos creados/modificados

| Archivo | Cambio |
|---|---|
| `modules/template/domain/{template,errors,repository}.py` | Entidad, errores, port del repositorio |
| `modules/template/application/{commands,results,ports,use_cases,facade}.py` | Capa aplicación (síncrona); puerto `WorldGateway` |
| `modules/template/infrastructure/{archive,store,world,models,serialization,memory,postgres_repository}.py` | Artefacto zip, store + adapter `WorldFacadeGateway` con validación de rutas, repo Postgres/en memoria |
| `modules/template/api/{schemas,router}.py` | Vertical slice HTTP |
| `infrastructure/db/alembic/versions/0010_template_tables.py` | Tabla `template_templates` (unique `name`) |
| `bootstrap/container.py` | Scaffold `TemplateDeps` (con `world=WorldFacadeGateway(world_facade)`) + `TemplateFacade` en el `Container` |
| `bootstrap/main.py` | Registro del router `template_router` |
| `modules/iam/application/access.py` | `template.list`, `template.view` en `READ_ACTIONS` |
| `tests/test_template_use_cases.py` | Suite del módulo (archive, capturar, aplicar, listar, borrar); mundo activo vía `FakeWorldGateway` |
| `tests/test_api_integration.py` | Container de dobles + `template_facade` |

### Verificación

- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (357 archivos)
- `uv run pytest -q` ✅ **527 passed, 30 deselected** (antes 526/30): mundo
  activo resuelto desde World (+1 test).

## 20. Fin de FASE A single-container — `DockerRuntimeAdapter` multi-servidor

> **Fecha**: 2026-08-08
> **Origen**: prueba real con `Template.apply`. El adaptador Docker gestionaba
> un único contenedor físico (FASE A) y nunca se generalizó, aunque
> `ServerRuntimePort` ya estaba diseñado para `runtime_id` por servidor.

### Síntoma

`docker inspect bedrock-panel-server` mostraba un bind mount fijo
(`/home/andresdev/Services/minecraft-bedrock/data:/data`) sin `server_id`,
que no coincidía con el patrón `{storage.base_path}/{server_id}:/data` que
arma `RuntimeSpecFactory.render()`. Un `apply` de plantilla escribía el mundo
en el storage correcto (`{base_path}/{server_id}/worlds/...`), pero el
contenedor realmente corriendo seguía siendo el viejo (volumen fijo, distinto,
invisible para la API). **No era un bug de Template**: era que el runtime jamás
recreaba el contenedor con el volumen de ESE `server_id`.

### Causa raíz

- `materialize(spec)` usaba `self._settings.container_name` (fijo, ignorando el
  `server_id` del spec) y, si existía el contenedor de ese nombre, lo borraba y
  recreaba → materializar CUALQUIER servidor destruía el contenedor de CUALQUIER
  otro que estuviera corriendo (solo podía haber uno de verdad).
- `_validate_runtime_id(runtime_id)` rechazaba todo `runtime_id` que no
  coincidiera con el único nombre fijo → el propio código impedía operar sobre
  más de un contenedor por diseño.

### Fix

- **Nombrado por servidor**: el nombre real del contenedor es
  `{container_prefix}-{server_id}`, y **coincide con el `runtime_id`** que
  `materialize` devuelve y persiste el módulo Server. El `server_id` sale
  del label `bedrockpanel.server_id` que deja `RuntimeSpecFactory.render()`.
- **Todos los métodos** resuelven su contenedor por `runtime_id`
  (`client.containers.get(runtime_id)`); se eliminó `_validate_runtime_id`
  como guardia restrictiva. Si llega `None`, `_require_runtime_id` lanza un
  error claro (multi-servidor: no "hay" un contenedor que adivinar).
- **`materialize`** borra/recrea solo el contenedor de ESE `server_id`; dos
  servers distintos coexisten. Dos servers = dos contenedores Docker.
- **Se eliminó código huérfano de FASE A**: `create_if_missing`, `_volumes`,
  `_remove_volumes`. El flujo real de creación siempre iba por `materialize` con
  un `RuntimeSpec` (imagen/puertos/volúmenes por server), así que
  `create_if_missing` y los campos `image`/`network`/`ports`/`memory_limit`/
  `cpu_limit`/`restart_policy`/`data_volume`/`world_volume` de
  `DockerRuntimeSettings` quedaron obsoletos: se eliminaron. Quedan
  `container_prefix` (renombrado desde `container_name`) y `docker_timeout`.
  `remove(delete_data=True)` ya no borra volúmenes Docker (el bind mount
  `{base_path}/{server_id}` lo limpia la capa de storage, no el runtime).

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `infrastructure/runtime/docker.py` | Adaptador N-servidores: `_container_name`, `_get_container(runtime_id)`, `_require_runtime_id`, `materialize` por server_id; quitados `_validate_runtime_id`, `create_if_missing`, `_volumes`, `_remove_volumes` |
| `infrastructure/runtime/settings.py` | `container_name`→`container_prefix`; quitados `image`/`network`/`ports`/`memory_limit`/`cpu_limit`/`restart_policy`/`data_volume`/`world_volume` |
| `infrastructure/runtime/__init__.py` | Docstring multi-servidor |
| `tests/test_runtime.py` | Reescrito con fake `{runtime_id: contenedor}`; tests coexisten dos servers, parar/borrar uno no toca al otro, replace del mismo server |
| `tests/test_runtime_integration.py` | `materialize`/`runtime_id` por server + coexistencia real |
| `tests/test_api_integration.py` | Construcción del adaptador con settings reducidas (compatible) |

### Verificación

- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (357 archivos)
- `uv run pytest -q` ✅ **524 passed, 31 deselected** (antes 527/30): -7 tests
  huérfanos de `create_if_missing`/`_remove_volumes` borrados + tests
  N-servidores sumados; la integración (deselected) de runtime ahora son 2
  tests.

### Limpieza manual del contenedor huérfano (host de Deyler)

El contenedor real `bedrock-panel-server` quedó con el volumen fijo del dev-setup
original. Debe pararse/borrarse manualmente (sin `delete_data`, su volumen es un
bind mount fijo que el panel no gestiona):

```bash
docker stop bedrock-panel-server && docker rm bedrock-panel-server
```

El próximo `start`/`materialize` de cada `Server` real creará su propio
contenedor limpio con el nombre (`bedrock-panel-{server_id}`) y el volumen
(`{storage.base_path}/{server_id}:/data`) correctos.

**Nota sobre el server `1295e5ef-08e6-452a-94bd-4f697129426b`**: NO existe una
carpeta propia en `/var/lib/bedrockpanel/` para ese `server_id` (el host solo
tiene los dirs de otros servers y `templates/`). Dado que nunca pasó por
`materialize()` con un volumen correcto, ese servidor en particular puede
necesitar **recrearse desde cero** tras el fix (su mundo real vivía en el bind
mount fijo del contenedor viejo, que se queda sin mapear). Vale la pena
verificarlo en el sistema real antes de borrar nada.

### Relación con síntoma de esta sesión

- **Template.apply** (bug fantasma que desencadenó esto): confirmado que el
  código de Template escribió el mundo en el storage correcto; el contenedor
  erra el mapeado por ser el viejo fijo. Con este fix el runtime recrea el
  contenedor [del servidor] con el volumen acertado.
- **Concurrency/reconcile/streams**: sin regresión funcional; `stream_logs`,
  `get_state`, `send_stdin`, `wait_for` ya pasaban `runtime_id` (el módulo
  Console/Server siempre lo tiene persistido tras `materialize`).

## 21. Corrección — `_candidate_data_dirs` mezclaba el storage de todos los servers

> **Fecha**: 2026-08-08
> **Origen**: prueba manual con dos servers (`v1`, `v2`). Al arrancarlos,
> ambos terminaron con el MISMO bind mount
> (`/home/andresdev/Services/minecraft-bedrock/data`), y `v1` entró en
> "Level corruption detected, disconnecting clients and shutting down server"
> al conectar un jugador: dos procesos BDS escribiendo la misma LevelDB a la
> vez.

### Causa raíz

`_candidate_data_dirs(base_path, server_id)` generaba candidatos SIN
`server_id` en la ruta:

```python
candidates = [base / server_id, base]          # base sin server_id

for start in start_points:
    for path in [start, *start.parents]:
        if path.name == "data":
            candidates.append(path)             # sin server_id
        else:
            candidates.append(path / "data")    # sin server_id
            candidates.append(path / server_id)
            candidates.append(path / "data" / server_id)
```

`_discover_server_data_dir` devuelve el primer candidato que exista y ya tenga
el binario Bedrock. Como el repo conserva `data/bedrock_server-1.26.40.8` de
pruebas viejas, cualquier candidato genérico (el `base` pelado, o cualquier
`path/"data"` que resuelva a esa carpeta) "gana" para CUALQUIER servidor nuevo
porque ya tiene el binario. Resultado: todos los servers que pasaban por ese
candidato apuntaban al mismo volumen físico, tanto el del contenedor
(`render()`) como el storage de `World` (`data_dir()`), porque ambos delegan en
la misma función.

### Fix

Todo candidato debe terminar SIEMPRE en `/{server_id}`; nunca se reutiliza una
carpeta compartida sin el `server_id` en la ruta. El atajo de dev de "reusar el
binario ya descargado" sigue existiendo, pero es por servidor:

```python
def _candidate_data_dirs(base_path: str | Path, server_id: str) -> list[Path]:
    base = Path(base_path)
    candidates: list[Path] = [base / server_id]

    start_points = [Path(__file__).resolve(), Path.cwd(), base]
    for start in start_points:
        for path in [start, *start.parents]:
            if path.name == "data":
                candidates.append(path / server_id)
            else:
                candidates.append(path / "data" / server_id)
    return candidates
```

Si ningún candidato tiene todavía el binario (server nuevo de verdad), cae al
default de `_discover_server_data_dir` (`Path(base_path) / server_id`), que ya
estaba bien.

### Impacto de datos existente

En el host de Deyler, `v1`, `v2` y probablemente otros servers creados hoy
comparten el bind mount corrupto `/home/andresdev/Services/minecraft-bedrock/
data`. Después del fix, cada uno apunta a `{storage.base_path}/{server_id}`,
una carpeta que NO existe todavía para ninguno (descargarán el binario de nuevo
desde cero; el mundo de `v1` quedó corrupto). **No hay nada que migrar
automáticamente ni vale la pena intentarlo**: los servers de prueba de hoy
deben recrearse limpios (parar/borrar contenedor + el volumen viejo compartido,
recrear desde el panel).

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `modules/server/application/spec_factory.py` | `_candidate_data_dirs` solo genera candidatos que terminan en `/{server_id}` |
| `tests/test_server_use_cases.py` | Tests de binario local movidos a `data/{server_id}/`; nuevos `test_candidate_data_dirs_siempre_incluye_server_id` y `test_render_v1_v2_no_comparten_volumen` |

### Verificación

- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (357 archivos)
- `uv run pytest -q` ✅ **526 passed, 31 deselected** (antes 524/31): +2 tests
  del fix (invariante de candidatos + volúmenes distintos para `v1`/`v2`).

## 22. Fase H — paso 17: módulo Notification y gateway WebSocket (`/ws`)

> **Fecha**: 2026-08-08
> **Origen**: el frontend necesitaba un único canal en tiempo real para eventos
> de todos los dominios (servidor, consola, mundo, backup, tarea, IAM/AUTH,
> sistema) con reenvío de eventos perdidos tras reconexión. Se sustituye el
> concepto de "WS mínimo por servidor" por un gateway único (Blueprint §3.12,
> TDD §13) sin romper los WS por servidor ya existentes.

### Alcance

- `GET /ws` acepta la conexión, valida el token (query `?token=` o header
  `Authorization`, vía `ws_identity`) y cierra con `4401` si no autentica.
- Mensajes JSON del cliente: `subscribe`, `unsubscribe`, `resume`, `pong`.
  Un mensaje malformado cierra con `4408`; una acción desconocida responde
  `NOTI.UNKNOWN_ACTION`; una suscripción inválida, `NOTI.INVALID_SUBSCRIPTION`.
- Canales: `global`, `server:{id}` y `user:{id}`. La suscripción a
  `server:{id}` se autoriza con IAM `AccessControlPort.authorize`
  (`server.view`, RBAC global + membresía); `global` y `user:{id}` (propio)
  están abiertos.
- `seq` global monótono asignado en publicación (secuencia Postgres
  `noti_event_seq`; en memoria, contador) y persistido en el `EventLog`
  append-only. `resume(last_seq, channels)` reenvía `seq > last_seq` por
  canal, ordenado, hasta `notification.resume_limit` (1000); si el backlog
  excede, responde `NOTI.RESUME_TOO_LARGE`.
- Buffer de salida por conexión (máx. 1000): eventos de consola usan
  `drop-oldest`; los críticos (`SERVER.*`, `BACKUP.*`, `WORLD.*`, `TASK.*`)
  marcan la conexión para cerrar (backpressure, TDD §13.2).
- Rate limiting por conexión: token-bucket desde
  `notification.rate_per_second` (100.0) y `notification.burst` (100).

### Implementación

| Archivo | Contenido |
|---|---|
| `modules/notification/domain/events.py` | Constantes de scope, `InvalidSubscriptionError`, `parse_channel` |
| `modules/notification/domain/subscription.py` | `Channel`, `ChannelAuthorizer` (decide vía `AccessControlPort`) |
| `modules/notification/domain/repository.py` | `EventLogEntry`, `EventLogRepositoryPort` (`next_seq`/`append`/`get_events_since`/`latest_seq`) |
| `modules/notification/application/connection_manager.py` | `ClientConnection` (buffer + `enqueue` con política drop/critical), `ConnectionManager` |
| `modules/notification/application/rate_limiter.py` | Token bucket (`RateLimitConfig`, `TokenBucketRateLimiter`) |
| `modules/notification/application/event_dispatcher.py` | `EventDispatcher` (asigna `seq`, persiste, difunde), `resolve_channels`, `serialize_envelope` |
| `modules/notification/application/resume_handler.py` | `ResumeHandler` (mezcla por `seq` con `limit`/`exceeded`) |
| `modules/notification/application/facade.py` | `NotificationFacade` (open/close, subscribe/unsubscribe, resume) |
| `modules/notification/infrastructure/models.py` | `NotificationEventLogRow` (índice `(scope, server_id, seq)`) |
| `modules/notification/infrastructure/memory.py` | `InMemoryEventLogRepository` (contador, filtrado+orden, `seed`/`clear` para tests) |
| `modules/notification/infrastructure/postgres_event_log_repository.py` | `PostgresEventLogRepository` (`nextval` de `noti_event_seq`, append-only) |
| `modules/notification/api/router.py` | `@router.websocket("/ws")` + tareas `_pump`/`_sender`, handlers |
| `infrastructure/db/alembic/versions/0011_noti_event_log.py` | Migración de la tabla `noti_event_log` (depende de `0010_template_tables`) |
| `infrastructure/events/bus.py` | Soporte de suscripción `"*"` (wildcard) al `InProcessEventBus` |
| `bootstrap/container.py` / `bootstrap/main.py` / `bootstrap/config.py` | Wiring del facade, inclusión del router y nuevos settings `notification_*` |

### Decisiones

- `seq` único y global (secuencia única) en vez de por canal: simplifica el
  resume por `seq` (TDD §13.4); el filtro por canal se aplica después de
  consultar el `EventLog`.
- Enrutado: `server_id` presente → `server:{id}`; si no, el scope del
  `event_type` (SERVER/CONSOLE/WORLD/PLAYER/BACKUP/TASK/CONFIG → `server`,
  IAM/AUTH → `user:{actor_id}`, resto → `global`).
- `EventDispatcher.handler()` envuelve la publicación en `try/except`: un
  fallo del `EventLog` nunca rompe el bus (se loguea y continúa).
- El único cambio al bus existente es el wildcard `"*"`; no se modifica la TDD.
- Las suscripciones y buffers son en memoria por conexión (se pierden al
  desconectar → `resume`); la persistencia es solo el `EventLog`.

### Tests

- `tests/test_notification_connection_manager.py` (7): buffer, drop-oldest,
  cierre por evento crítico, suscripciones, broadcast por canal(es).
- `tests/test_notification_rate_limiter.py` (4): token-bucket (gasto, recarga,
  burst, consumo completo).
- `tests/test_notification_event_dispatcher.py` (8): enrutado a canal, `seq`
  en `EventLog`, broadcast, `resolve_channels` y resiliencia del bus.
- `tests/test_notification_resume.py` (5): reenvío por `seq`, filtro por
  servidor, límite/`exceeded`, mezcla multi-canal, `last_seq` actual.
- `tests/test_notification_subscription.py` (7): nombres canónicos, canales
  inválidos, autorización global/user propio/ajeno/server con y sin membresía.
- `tests/test_notification_ws_integration.py` (8): handshake 4401 (sin token /
  inválido), subscribe global, rechazo sin membresía, super_admin puede,
  JSON inválido → 4408, resume con y sin `last_seq`.
- El `make_container` de `tests/test_api_integration.py` construye el
  `NotificationFacade` con `InMemoryEventLogRepository` y registra el wildcard.

### Verificación

- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (376 archivos)
- `uv run pytest -q` ✅ **565 passed, 31 deselected** (antes 526/31): +39 tests
  del módulo Notification (7 + 4 + 8 + 5 + 7 + 8).

## 23. Fase H — paso 18: IAM completo (matriz de permisos, 2FA, API keys, auditoría tamper-evident)

> **Fecha**: 2026-08-08
> **Origen**: el paso 17 dejó IAM con auth JWT, roles base y ACL por servidor,
> pero sin matriz de permisos por acción (TDD §14.2), sin 2FA, sin API keys y
> con auditoría básica (sin cadena de hash). Este paso completa el módulo según
> el blueprint §3.1/§16.2.

### 1. Matriz de permisos por acción

- Catálogo de códigos organizado por categoría en
  `modules/iam/domain/permissions.py`: `PERMISSION_CODES` (65 códigos),
  `READ_ACTIONS` (vista), `WRITE_ACTIONS` (operator) y `PANEL_ACTIONS`
  (ámbito panel, solo admin/super_admin). La matriz `ROLE_PERMISSIONS` asigna:
  viewer → solo lectura; operator → lectura + escritura sobre servidores;
  admin/super_admin → todo el catálogo.
- `AccessControlService.authorize(identity, action, resource)` evalúa:
  1. `super_admin`/`admin` global → siempre autorizado.
  2. Ámbito panel (`resource is None`/`"panel"`): la acción debe estar en
     `PANEL_ACTIONS` y concedida por el rol global (equivale a admin global).
  3. Ámbito servidor (`server:{id}` o `{server_id}`): el rol de la membresía
     debe conceder la acción.
- Persistencia: tablas `iam_permissions` + `iam_role_permissions` sembradas en
  la migración 0012; `PermissionRepositoryPort` (Postgres + en memoria con la
  matriz estática de fallback). `require_action`/`require_server_action` ya
  usaban los códigos: ahora se validan contra la matriz.

### 2. Auditoría tamper-evident

- `iam_audit_logs` gana `prev_hash` y `hash`: `prev_hash` = hash del registro
  anterior (global); `hash` = SHA-256 de
  `f"{prev_hash}|{id}|{actor_id}|{action}|{resource_id}|{created_at}|{result}"`.
- `PostgresAuditStore`/`InMemoryAuditStore` calculan la cadena al guardar y
  exponen `verify()` (devuelve la lista de errores; vacío = íntegra).
- Endpoint `GET /iam/audit/verify` (admin) → `{"valid", "errors"}`.

### 3. 2FA (TOTP)

- Dependencias nuevas: `pyotp>=2.9`, `cryptography>=42.0`.
- Columnas en `iam_users`: `totp_secret` (Text cifrado con Fernet),
  `totp_enabled` (bool) y `backup_codes` (Text cifrado).
- `SecretCipherPort` (Fernet, clave `iam.encryption_key`) y `TotpServicePort`
  (pyotp: `random_base32`, `provisioning_uri`, `verify` con `valid_window=1`,
  backup codes de 8 hex con `secrets.token_hex(4)`).
- Flujos:
  - `POST /auth/2fa/enable` → secreto + provisioning URI (QR) + 10 backup codes.
  - `POST /auth/2fa/verify` → valida el código TOTP y activa el 2FA.
  - `POST /auth/login` → si la cuenta tiene 2FA, responde
    `{"requires_2fa": true, "temp_token": ...}` (temp token JWT de corta vida).
  - `POST /auth/verify-2fa` → valida TOTP/backup code y emite los tokens.
  - `POST /auth/2fa/backup` → regenera backup codes (2FA ya activo).

### 4. API keys

- Tabla `iam_api_keys`: `id`, `user_id`, `name`, `key_hash` (SHA-256), `scopes`
  (jsonb), `last_used_at`, `created_at`, `expires_at`.
- Material `sk_live_` + 32 hex (solo se muestra una vez); se guarda el hash.
- AuthN: `X-API-Key` en `get_current_user` resuelve la key, carga el usuario y
  monta una `Identity` con `is_api_key=True` y `scopes`; la intersección de
  scopes se aplica en `AccessControlService.authorize` (si la key no tiene el
  scope → 403; key sin scopes → deniega todo).
- Endpoints: `GET/POST /iam/api-keys`, `DELETE /iam/api-keys/{id}`,
  `POST /iam/api-keys/{id}/regenerate` (todos admin vía `require_action`).

### Archivos

| Archivo | Cambio |
|---|---|
| `modules/iam/domain/permissions.py` | Catálogo, READ/WRITE/PANEL_ACTIONS y matriz `ROLE_PERMISSIONS` |
| `modules/iam/domain/repository.py` | `PermissionRepositoryPort` (listar/sembrar/por rol) |
| `modules/iam/domain/user.py` | `totp_secret`, `totp_enabled`, `backup_codes` |
| `modules/iam/domain/errors.py` | Errores 2FA/API keys/cipher |
| `modules/iam/application/access.py` | `authorize` con matriz de permisos + intersección de scopes |
| `modules/iam/application/audit_chain.py` | Cómputo/verificación de la cadena de hash |
| `modules/iam/application/security_use_cases.py` | Use cases 2FA y API keys |
| `modules/iam/application/ports.py` | `ApiKeyStorePort`, `SecretCipherPort`, `TotpServicePort`, `temp_token` en `TokenService` |
| `modules/iam/application/use_cases.py` | `LoginUseCase` emite challenge 2FA; `IamDeps` nuevos puertos |
| `modules/iam/application/facade.py` | Métodos 2FA/API keys/auditoría |
| `modules/iam/infrastructure/models.py` | Columnas 2FA + hash-chain + `iam_permissions`/`iam_role_permissions`/`iam_api_keys` |
| `modules/iam/infrastructure/iam_security.py` | `PostgresPermissionRepository`, `PostgresApiKeyStore`, `FernetSecretCipher`, `PyotpTotpService`, generación de material |
| `modules/iam/infrastructure/audit_store.py` | Hash-chain en `record` + `verify()` |
| `modules/iam/api/schemas.py` + `api/router.py` | Endpoints 2FA, API keys, auditoría |
| `bootstrap/container.py` / `config.py` | Wiring y settings `iam.encryption_key`/`iam.totp_issuer`/`iam.temp_token_ttl_seconds` |
| `bootstrap/security.py` | `get_current_user` con `X-API-Key` |
| `bootstrap/errors.py` | Mapping de errores 2FA/API keys |
| `infrastructure/db/alembic/versions/0012_iam_complete.py` | Migración completa (depende de 0011) |
| `kernel/ports/access.py` | `Identity.scopes` + `is_api_key` |

### Tests

- `tests/test_iam_permissions_matrix.py` (200): catálogo, partición
  READ/WRITE/PANEL y combinaciones rol×acción.
- `tests/test_iam_audit_chain.py` (8): hash dependiente de campos, encadenado,
  detección de manipulación de `hash`/`prev_hash`.
- `tests/test_iam_security_use_cases.py` (17): 2FA (enable/confirmar/login con
  challenge/backup codes) y API keys (crear/listar/revocar/rotar/resolver).
- `tests/test_iam_security_integration.py` (11): endpoints 2FA/API keys vía
  HTTP y auditoría.
- `tests/test_iam_postgres_integration.py` (+4 opt-in): catálogo sembrado,
  hash-chain en Postgres, API keys CRUD y roundtrip 2FA del usuario.

### Verificación

- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (385 archivos)
- `uv run pytest -q` ✅ **801 passed, 35 deselected** (antes 565/31): +236 tests
  (200 + 8 + 17 + 11 del módulo IAM).

## 24. Fase H — paso 19: módulo Settings avanzado (persistencia, endpoints, límites)

> **Fecha**: 2026-08-08
> **Origen**: hasta este paso, la configuración global era solo el placeholder
> ``EnvSettingsAdapter`` (variables de entorno + atributos pydantic) sin
> persistencia, sin endpoints de administración y sin límites configurables por
> servidor. Este paso completa el módulo Settings (Blueprint §3.13/§16.14,
> TDD §15.7).

### 1. Modelo de datos y catálogo

- Tabla ``settings``: ``key`` (PK), ``value`` (JSONB), ``category``
  (`storage`/`limits`/`defaults`/`system`), ``description``, ``updated_by``,
  ``updated_at``.
- Catálogo de 18 claves en `modules/settings/domain/defaults.py`
  (``SETTING_DEFINITIONS``, ``DEFAULT_VALUES``):
  - **storage**: `storage.base_path`, `storage.backup_path`, `storage.template_path`.
  - **limits**: `limits.max_servers`, `limits.max_backups_per_server`,
    `limits.max_world_size_mb`, `limits.default_cpu_cores`, `limits.default_ram_mb`,
    `limits.default_disk_gb`.
  - **defaults**: `defaults.image`, `defaults.tag`, `defaults.version`,
    `defaults.port_pool_start`, `defaults.port_pool_end`, `defaults.timezone`.
  - **system**: `system.maintenance_mode`, `system.log_level`,
    `system.audit_retention_days`.

### 2. Puerto, repositorios y resolución

- `SettingsRepositoryPort` añadido a `kernel/ports/settings.py`
  (get/set/set_many/delete/get_many/list_by_category/get_all/list_full).
- `PostgresSettingsRepository` (upsert por clave, ``set_many`` atómico) y
  ``InMemorySettingsRepository`` (para tests).
- Resolución de cada clave en ``SettingsService``: **DB (cache)** →
  **``EnvSettingsAdapter`` (fallback de entorno)** → **default del catálogo** →
  default del argumento. ``EnvSettingsAdapter`` sigue funcionando como fallback.

### 3. SettingsService

- Implementa ``SettingsPort`` (lectura síncrona) + escritura async
  (``set``/``set_many``/``reset``/``reload``), getters tipados
  (``get_int``/``get_float``/``get_bool``/``get_path``) y validación por tipo
  del catálogo (int/float/bool/str/path).
- Auditoría: cada cambio registra un ``AuditEntry`` con acción
  ``settings.update`` (reutiliza el audit tamper-evident del paso 18).
- ``reload()`` es tolerante a tabla ausente (migración sin aplicar): la cache
  queda vacía y la resolución cae al fallback env/defaults.

### 4. Endpoints REST (admin)

| Método | Ruta | Permiso | Efecto |
|---|---|---|---|
| GET | `/settings` | `settings.view` | Todos los settings |
| GET | `/settings/category/{category}` | `settings.view` | Por categoría |
| GET | `/settings/{key}` | `settings.view` | Un setting |
| PUT | `/settings/{key}` | `settings.update` | Actualizar (valida + audita) |
| PATCH | `/settings` | `settings.update` | Múltiples (atómico) |
| DELETE | `/settings/{key}` | `settings.update` | Reset a default |

### 5. Integración con otros módulos

- `RuntimeSpecFactory`: `defaults.image`/`defaults.tag`/`defaults.timezone`/
  `defaults.port_pool_start`/`defaults.port_pool_end`/`limits.default_ram_mb`/
  `limits.default_cpu_cores`, con fallback a las claves legacy (`server.*`).
- Configuration reader/facade y Template: `defaults.version` (fallback
  `server.default_version`).
- World import: `limits.max_world_size_mb` (fallback al antiguo
  `world_max_import_bytes`).
- Backup: `limits.max_backups_per_server` se aplica en `CreateBackupUseCase`.
- Container: `storage.backup_path`/`storage.template_path` configuran
  `LocalBackupStore` y `TemplateArchiveStore`; `reload()` en el lifespan.
- Se mantiene el campo legacy `world_max_import_bytes` en `Settings` pydantic
  (sin uso) por compatibilidad de config.

### Archivos

| Archivo | Cambio |
|---|---|
| `kernel/ports/settings.py` | +`SettingsRepositoryPort` |
| `modules/settings/domain/defaults.py` | Catálogo de 18 claves con categoría/tipo/descripción |
| `modules/settings/domain/errors.py` | `SettingNotFoundError`, `SettingValidationError`, `SettingCategoryError`, `MaintenanceModeError` |
| `modules/settings/application/service.py` | `SettingsService` (lectura + escritura + tipos + auditoría) |
| `modules/settings/infrastructure/models.py` | `SettingRow` |
| `modules/settings/infrastructure/postgres_repository.py` | `PostgresSettingsRepository` |
| `modules/settings/infrastructure/memory.py` | `InMemorySettingsRepository` |
| `modules/settings/api/schemas.py` + `api/router.py` | Endpoints REST |
| `modules/server/application/spec_factory.py` | Defaults nuevos con fallback legacy |
| `modules/configuration/*`, `modules/template/*` | `defaults.version` con fallback |
| `modules/world/api/router.py` | Límite desde `limits.max_world_size_mb` |
| `modules/backup/application/use_cases.py` | `limits.max_backups_per_server` en create |
| `bootstrap/container.py` | `settings_service` en Container, rutas configurables |
| `bootstrap/main.py` | Router + `reload()` en lifespan |
| `infrastructure/db/alembic/versions/0013_settings_table.py` | Tabla + siembra de defaults (depende de 0012) |

### Tests

- `tests/test_settings_service.py` (21): resolución DB→env→default, getters
  tipados, validación, auditoría, get_all/get_category, compatibilidad
  estructural.
- `tests/test_settings_integration.py` (12): endpoints HTTP (authN, GET/PUT/
  PATCH/DELETE, 403 viewer, validación 422), integración con `RuntimeSpecFactory`
  y rutas de storage configurables.
- `tests/test_settings_postgres_integration.py` (+2 opt-in): CRUD, set_many
  atómico, upsert.
- `tests/test_backup_use_cases.py` (+1): `limits.max_backups_per_server` se
  aplica al crear.
- `tests/test_api_integration.py`: límite de import 413 ahora vía
  `limits.max_world_size_mb`; `make_container` construye el `SettingsService`
  con repo en memoria + audit IAM.

### Verificación

- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (397 archivos)
- `uv run pytest -q` ✅ **835 passed, 37 deselected** (antes 801/35): +34 tests
  (21 + 12 + 1 del módulo Settings; +2 opt-in Postgres).

## 25. Extensión — endpoint de recursos de servidor (CPU/RAM)

> **Fecha**: 2026-08-08
> **Origen**: el paso 19 configura valores por defecto de CPU/RAM para servidores
> nuevos, pero no permitía modificar los ya creados. Esta extensión añade
> `PUT /servers/{id}/resources` para actualizar CPU/RAM de un servidor existente
> recreando el contenedor.

### Alcance

- `PUT /servers/{server_id}/resources` con body `{cpu_cores?, ram_mb?}` (ambos
  opcionales; si uno no se envía se mantiene el actual).
- Respuestas: `200` (actualizado), `422` (valores fuera de rango — la API valida
  `ge=1/le=64` CPU y `ge=512/le=65536` RAM en el schema), `403` (sin
  `server.update`), `404` (servidor inexistente), `409` (servidor en
  `starting`/`stopping`/`removed` → `SERVER.BUSY`).
- Si no hay cambios reales (mismos valores), responde `200` sin recrear.
- Recrea el contenedor: si corría, para → `materialize` con el nuevo spec →
  arranca (mismo mecanismo que `ChangeVersion`/`ApplyConfig`, `_recreate`).
- Publica `SERVER.RESOURCES_CHANGED` (payload `{old, new}`).
- Auditoría: IAM suscribe `server.resources_changed` con un
  `ResourceChangeAuditHandler` que registra la acción `server.resources.update`
  (resultado `success`, detalle `old`/`new`) en el audit tamper-evident del
  paso 18.

### Implementación

| Archivo | Cambio |
|---|---|
| `modules/server/application/commands.py` | `UpdateResourcesCommand` (server_id, cpu_cores?, ram_mb?, actor_id?) |
| `modules/server/domain/events.py` | `SERVER_RESOURCES_CHANGED` + `server_resources_changed(...)` |
| `modules/server/domain/server.py` | `Server.change_resources(cpu_cores, ram_mb)` (copia defensiva del spec, devuelve si cambió) |
| `modules/server/domain/errors.py` | `ServerResourcesValidationError` (`SERVER.RESOURCES_INVALID`) y `ServerBusyError` (`SERVER.BUSY`) |
| `modules/server/application/use_cases.py` | `UpdateServerResourcesUseCase` (validar estado y cotas, `change_resources`, `_recreate`, evento) |
| `modules/server/application/facade.py` | `update_resources(cmd)` |
| `modules/server/api/schemas.py` | `UpdateResourcesRequest` + `ServerResourcesResponse` |
| `modules/server/api/router.py` | `PUT /servers/{id}/resources` con `require_server_action("server.update")` |
| `modules/iam/domain/permissions.py` + `0012`/`0014` | Permiso `server.update` en el catálogo y siembra (BBDD ya migradas) |
| `modules/iam/application/handlers.py` + `facade.py` | `ResourceChangeAuditHandler` suscrito a `server.resources_changed` |

### Notas

- El topic derivado del evento es `server.resources_changed` (con guion bajo):
  `event.type.lower()` convierte `SERVER.RESOURCES_CHANGED` así. La suscripción
  de IAM usa ese topic exacto (hallazgo al integrar: el topic NO es
  `server.resources.changed`).
- `server.update` no estaba en el catálogo del paso 18; se añadió al catálogo y
  a la migración 0014 (las BBDD con la 0012 ya aplicada reciben el permiso).

### Tests

- `tests/test_server_use_cases.py` (TestUpdateServerResources, 9): actualiza CPU
  y RAM recreando el contenedor, no-op sin cambios, solo RAM, recrea y arranca si
  corría, CPU < 1 / RAM < 512 rechazadas, `starting`/`removed` → `SERVER.BUSY`,
  servidor inexistente.
- `tests/test_api_integration.py` (TestServerResourcesApi, 7): 200, 422 (CPU/RAM
  inválidas), 403 (viewer), 404, 401, y auditoría `server.resources.update`.

### Verificación

- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (398 archivos)
- `uv run pytest -q` ✅ **854 passed, 37 deselected** (antes 835/37): +16 tests
  (9 + 7 de la extensión de recursos).

## 26. Fix — límite de RAM no se aplicaba en contenedores Docker

> **Fecha**: 2026-08-08
> **Origen**: al verificar `PUT /servers/{id}/resources` con `docker inspect`, la
> CPU se aplicaba correctamente (`NanoCpus: 4000000000`), pero la RAM NO:
> `Memory: 0` en lugar de `8589934592` bytes (8192 MB).

### Causa raíz

En `DockerRuntimeAdapter.materialize`, el `mem_limit` se leía de la clave
`resources["memory"]`, pero el `RuntimeSpec` producido por `spec_factory` y por
el endpoint de recursos guarda la RAM en `resources["memory_mb"]` (int en MB).
Al no existir la clave `memory`, `mem_limit` quedaba en `None` y Docker creaba el
contenedor sin límite de memoria.

### Fix

Nuevo helper `_mem_limit(resources)` en `docker.py` que convierte
`memory_mb` (MB) a bytes (`MB * 1024 * 1024`) y lo pasa como `mem_limit`:

```python
def _mem_limit(resources: dict[str, Any]) -> str | int | None:
    memory_mb = resources.get("memory_mb")
    if memory_mb is not None:
        return int(memory_mb) * 1024 * 1024
    return resources.get("memory")
```

La clave legacy `resources["memory"]` se mantiene como fallback para no romper
consumidores previos (el test antiguo de `materialize` usaba `{"memory": "2g"}`).

### Verificación

- `tests/test_runtime.py` (+2): `memory_mb=8192` → `mem_limit == 8192 * 1024 * 1024`
  (y `nano_cpus` correcto); sin `memory_mb` → `mem_limit is None`. El test previo
  de `{"memory": "2g"}` sigue pasando (sin regresión).
- `docker inspect <container>` debe mostrar `"Memory": 8589934592` tras recrear
  un servidor con 8192 MB (verificación manual pendiente de entorno Docker real).

### Verificación automática

- `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅
- `uv run mypy --strict .` ✅ (398 archivos)
- `uv run pytest -q` ✅ **856 passed, 37 deselected** (antes 854/37): +2 tests
  del fix de RAM.

---

## 27. Infraestructura de producción — Dockerfiles backend/frontend + compose portable

> **Fecha**: 2026-08-09
> **Alcance**: estandarizar el despliegue del panel (backend + frontend + Postgres)
> con Docker, portable a cualquier máquina. Se separan las imágenes por aplicación
> (contrario a un único Dockerfile que corra ambas), se cierra la deuda de aplicar
> migraciones en producción y se externalizan credenciales/storage por entorno.
> No toca el contrato §4.1, el TDD ni las capas del backend.

### Decisión principal — una imagen por aplicación

- **Backend** = proceso vivo (uvicorn). **Frontend** = build estático servido por
  nginx. Compartir un solo Dockerfile/containizarlos juntos mezcla ciclos de vida
  y bases distintas; se mantienen **contenedores separados** orquestados por
  `docker-compose.prod.yml` en una red interna `bedrockpanel`.
- Solo `frontend` publica un puerto al host; `backend` y `postgres` permanecen en
  la red interna.

### Archivos creados/modificados

| Archivo | Contenido |
|---|---|
| `infra/docker/Dockerfile.backend` | Multi-stage (builder uv → runtime python:3.13-slim). Sin `--reload`; `uv:0.5.26` fijado en `ARG UV_VERSION` (independiente de `latest`); copia `pyproject`/`uv.lock`/`.python-version` y `alembic.ini`. |
| `infra/docker/entrypoint.backend.sh` | 1) espera Postgres (sondeo con psycopg, sin cliente instalado), 2) `alembic upgrade head`, 3) arranca uvicorn con `BEDROCK_PANEL_WEB_CONCURRENCY` o 2×NCPU (máx 8). |
| `infra/docker/Dockerfile.frontend` | Multi-stage (node:22 → build `pnpm install --frozen-lockfile` + `pnpm build` → nginx:1.27 sirviendo `dist/`). pnpm 9 fijado vía Corepack (no hay `packageManager` en `package.json`). |
| `infra/docker/nginx.conf` | Sirve el SPA en `/`, activos con cache inmutable, proxy `/api/`→`backend:8000` (REST + WS con `Upgrade`) y `/ws`→`backend:8000` (gateway WS de Notification). `client_max_body_size` acorde a import de mundos. |
| `docker-compose.prod.yml` | postgres (+healthcheck) + backend (depends_on sano, env `BEDROCK_PANEL_*`, mount `/var/run/docker.sock`, volumen de storage) + frontend. |
| `.env.prod.example` | Plantilla de entorno con credenciales/almacenamiento/claves requeridas. |
| `.dockerignore` | Excluye node_modules, `dist/`, venv, `.env*` y datos del contexto de build. |
| `docs/deployment.md` | Guía completa: arquitectura, preparación, build/up, uso diario, volúmenes, env vars y notas de seguridad. |

### Decisiones de integración con el código existente

| Punto | Decisión |
|---|---|
| `BEDROCK_PANEL_STORAGE_ROOT` | Ruta **absoluta del host**, montada en el backend **en la misma ruta**, y usada por docker-py como origen de los bind-mounts `{storage_root}/{server_id}:/data` (§20/§21). Mantenerla idéntica host/contenedor es crítico para worlds/backups/templates y bind-mounts. |
| Socket de Docker | Única vía de producción para que `DockerRuntimeAdapter` gestione los contenedores Minecraft en el host (`docker.sock`). |
| Migraciones | Se ejecutan en el entrypoint, antes de uvicorn; cierra la deuda de "alembic upgrade en arranque" (§11/§17). Alembic lee la URL vía `Settings` (misma fuente de verdad, §13). |
| Workers | `BEDROCK_PANEL_WEB_CONCURRENCY` o 2×NCPU; la persistencia es Postgres, los buffers/streams en memoria son por proceso. |

### Verificación

- `docker compose ... config` ✅ (con `.env.prod` poblado).
- `sh -n entrypoint.backend.sh` ✅ (sintaxis shell).
- Verificación de red/construcción de las imágenes queda pendiente de un host con
  acceso a los builds y al daemon Docker (mismo criterio que las integraciones
  opt-in del resto del proyecto).

### Pendiente / deuda

- Construcción real de las imágenes (`docker build`) y smoke-test end-to-end en
  un host con Docker (no se ejecuta aquí, por lo que los hits de red/ue son
  a validar en el destino).
- TLS/HTTPS externo (terminación en un reverse proxy a nivel de host o `frontend`
  con certificados), fuera de alcance de esta pila base.
- El `package.json` del frontend no declara `packageManager`; la versión de pnpm
  se fija explícitamente en `Dockerfile.frontend` (Corepack). Puede añadirse el
  campo para robustez futura.

---

## 28. Bootstrap de super_admin por entorno + guía de instalación multi-SO

**Fecha**: 2026-08-09

### Resumen

Sobre la infraestructura de producción (sección 27), se añade un **administrador
inicial mediante variables de entorno** (para entrar al panel sin crear usuarios por
comando) y una **guía de instalación intuitiva** para Windows, macOS y Ubuntu.

### Cambios

| Área | Detalle |
|---|---|
| `bootstrap/config.py` | Nuevos settings `bootstrap_admin_username`, `bootstrap_admin_password`, `bootstrap_admin_display_name` (env `BEDROCK_PANEL_BOOTSTRAP_ADMIN_*`). |
| `iam/application/facade.py` | Nuevo `ensure_bootstrap_admin(username, password, display_name)` idempotente: crea el usuario si falta y asegura el rol `super_admin` sin degradarlo. Maneja la race entre workers de uvicorn capturando `UniqueViolation` y re-resolviendo el usuario creado por el worker ganador (arranque limpio, sin trazas de error). |
| `bootstrap/main.py` | `_bootstrap_admin()` en el lifespan tras el `reload()` de settings; defensivo (try/except), no rompe el arranque. |
| `docker-compose.prod.yml` | Reenvío de las 3 variables `BEDROCK_PANEL_BOOTSTRAP_ADMIN_*` al backend. |
| `.env.prod.example` | Documentadas las variables de bootstrap con defaults (`admin` / placeholder / `Administrador`). |
| `docs/installation.md` | **Nuevo**: guía paso a paso para Windows/macOS/Linux (Docker, `.env.prod`, Fernet, arranque, login admin, uso diario, troubleshooting). Enlazada desde `README.md`. |
| `docs/deployment.md` | Tabla de variables ampliada con el bootstrap + sección "Administrador inicial". |
| Tests | `TestBootstrapAdmin` en `tests/test_iam_use_cases.py` (3 tests: creación con rol, idempotencia/no-degradación, cortocircuito en vacío). |

### Verificación

- `uv run pytest tests/test_iam_use_cases.py -q` → `16 passed`.
- `ruff check` / `ruff format --check` / `mypy --strict` ✅ en `facade.py`.
- Rebuild + `up -d` real: login `POST /api/v1/auth/login` → `200` con roles `["super_admin"]`; logs del backend sin ERROR ni traceback de bootstrap con múltiples workers.

### Pendiente / deuda

- Probar la guía `docs/installation.md` en un PC externo (Windows/macOS/Ubuntu) como
  criterio de aceptación de la portabilidad.

---

## 29. Ajustes de convivencia dev/prod: stack dev, cliente Docker, JWT y exposición de Postgres

**Fecha**: 2026-08-10

### Resumen

Perfectas la experiencia de **desarrollo** (coexistencia con producción) y cierro
errores detectados al correr el stack dev de forma manual: el backend dev no podía
conectar a Postgres, el cliente Docker rompía en el manejo de errores de permisos, y
se añadieron el secret JWT y la exposición de Postgres para herramientas externas.

### Cambios

| Área | Detalle |
|---|---|
| `docker-compose.dev.yml` | `BEDROCK_PANEL_DATABASE_URL` apuntando al servicio `postgres:5432` de la red dev (antes faltaba y usaba el default erróneo), `depends_on: postgres` y montaje `/var/run/docker.sock` para que el poller de reconcile alcance el daemon. |
| `infrastructure/runtime/client_factory.py` | Corregido `_has_permission_error`: la SDK de Docker usa `args` a veces como **string** no tupla, lo que hacía `node.args[1]` indexar un carácter y reventar con `AttributeError: 'str' object has no attribute 'args'`. Ahora solo se sigue si es tupla con 2º elemento `BaseException`. |
| `bootstrap/config.py` | Nuevo setting `iam_jwt_secret` (env `BEDROCK_PANEL_IAM_JWT_SECRET`) para firma HMAC HS256; sin él se usa el fallback de desarrollo (29 bytes) y PyJWT emite `InsecureKeyLengthWarning`. |
| `docker-compose.prod.yml` | Reenvío de `BEDROCK_PANEL_IAM_JWT_SECRET` y `ports` para Postgres (`${BEDROCK_PANEL_PG_PORT:-5432}:5432`) que permite conectar DBeaver/pgAdmin en `localhost:5432`. |
| `.env.prod.example` | Documentados `BEDROCK_PANEL_IAM_JWT_SECRET` y `BEDROCK_PANEL_PG_PORT`. |
| `docs/installation.md` | Sección Linux generalizada: ya no solo "Ubuntu", sino Ubuntu/Debian y derivadas (Linux Mint, Pop!_OS, Zorin) usando el instalador oficial que detecta la distro. Añadido paso de la clave JWT. |
| `docs/deployment.md` | Tabla de variables ampliada con `BEDROCK_PANEL_IAM_JWT_SECRET`. |
| Tests | `tests/test_client_factory.py`: `test_permission_detection_with_str_args_does_not_crash_and_finds_cause` (args string → detecta `PermissionError` en la cadena de causas) y `test_str_args_without_permission_is_retryable_and_does_not_crash`. |

### Cómo quedó la convivencia dev/prod

- **Dev**: `docker-compose.dev.yml` (backend `:8000` con `--reload`, Postgres host `5433`) + Vite local `:5173` (`pnpm dev`) con proxy `/api` → `localhost:8000`. Cambios en `src` se recargan en caliente.
- **Prod**: `docker-compose.prod.yml` (backend estático multi-worker **sin** `--reload`, nginx `:8080`, Postgres host `5432`).
- No comparten puertos ni volúmenes; evolución y despliegue se "sube" con `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`.

### Verificación

- `uv run pytest tests/test_client_factory.py -q` → `8 passed`; `tests/test_iam_use_cases.py` → `16 passed`.
- `ruff check` / `ruff format --check` / `mypy --strict` ✅ en `client_factory.py` y `config.py`.
- Stack dev real: DB conecta, WS `/api/v1/ws` y monitoring aceptados, adiós `AttributeError`, adiós `runtime.operation_failed` (con daemon alcanzable vía socket).
- Prod real: `BEDROCK_PANEL_IAM_JWT_SECRET` aplicado elimina `InsecureKeyLengthWarning`; Postgres expuesto y conectable (`psql` verificado); login `admin` `200` `super_admin`.

### Pendiente / deuda

- Redactar `docs/development.md` para formalizar el flujo dev/prod coexistente (hoy explicado en README y changelog).

## 30. Auditoría de sync WS — doble-inspect, métricas CPU/jugadores y dedup del poller

> **Fecha**: 2026-08-10
> **Origen**: auditoría de sincronización en tiempo real pedida por el usuario.
> Cuatro síntomas aparentemente separados que compartían dos causas de backend:
> (1) el doble poll del mismo contenedor por dos caminos independientes y
> (2) métricas que el backend nunca computaba (CPU hardcodeada a `None`, disco
> a `0`, jugadores a `0` porque el probe no parseaba el PONG RakNet).

### Hallazgo 0 — el frontend YA se conecta a ambos WS (no era un problema de suscripción)

`frontend-standards.md` §4 estaba **desactualizado**: decía que el WS por
servidor "quedó reemplazado por el gateway". En realidad ADR-002 mantiene el
WS de monitoring por servidor (`/servers/{id}/monitoring/ws`) y el frontend ya
lo usaba (`useServerMonitoring` → `useMonitoringStore`). Por eso RAM sí se
actualizaba: el pipeline WS funcionaba, pero el **backend** llenaba
`cpu=None`, `disk_mb=0` y `players=0`. El síntoma 3 no era de conexión sino de
datos.

### Alcance

- **Doble-inspect (síntoma 1)**: había DOS fuentes de la redundancia, ambas
  corregidas:
  1. **Doble poll**: en producción corren a la vez el `BackgroundPoller.poll_all`
     (cada `poll_interval`, lifespan) y, cuando hay un cliente viendo la card,
     el WS `monitoring_ws` ejecuta `poll_server` del mismo servidor → dos pasadas
     del mismo contenedor. **Solución**: `SnapshotHub` (cache con TTL =
     `poll_interval`) en la facade de monitoring. `MonitoringFacade.poll_server`
     y `poll_all` pasan por el hub: un snapshot reciente se reutiliza y solo hay
     **una pasada por servidor por ventana**, venga de quien venga (WS o fondo).
     Sin poller de fondo (tests, `monitoring_poller=None`) el hub está vacío y el
     WS pollea directo (fallback) — los tests de integración del WS no cambian.
  2. **Doble inspect dentro de una pasada**: `get_resources` hacía su propio
     `containers.get()` (GET /json) además del que ya hacía `get_state`→`status`
     en la misma pasada, y después el `stats`. Con dos pollers eso daba
     `inspect, inspect, stats, inspect, inspect, stats`; con el hub resuelto
     quedaba `inspect, inspect, stats`. **Solución**: `get_resources` ahora usa
     la API low-level `client.api.stats()` (GET /containers/{id}/stats) sin el
     `containers.get()` previo → **un inspect + un stats por pasada**.
- **CPU (síntoma 3)**: `docker.get_resources` devolvía `"cpu_percent": None`
  hardcodeado. Ahora `_compute_cpu_percent` calcula el delta entre `cpu_stats`
  y `precpu_stats` (fórmula estándar de Docker); sin `precpu` (primer sample)
  devuelve `0.0`.
- **Jugadores (síntoma 3)**: `RakNetStatusProbe` solo reportaba online/latencia.
  Ahora parsea el `ID_UNCONNECTED_PONG` (0x1c) de BDS y extrae
  `players_online`/`players_max` del campo `MCPE;...;players;max;...`. Si el
  payload no es un pong válido devuelve `(0, 0)` sin romper el probe.
- **Disco**: se mantiene `disk_mb=0.0` — Docker no expone el uso del bind
  mount de storage en `/stats`. Documentado como sin fuente (el stat card
  muestra "0 / X GB", honesto, no inventado).

### Archivos

| Archivo | Contenido |
|---|---|
| `modules/monitoring/application/snapshot_hub.py` | `SnapshotHub` + `poll_or_cached` (dedup por TTL) |
| `modules/monitoring/application/facade.py` | `poll_server`/`poll_all` cacheados por el hub |
| `modules/monitoring/application/polling.py` | Propiedad `server` pública (para listar en `poll_all` del hub) |
| `modules/monitoring/infrastructure/raknet_probe.py` | Parseo del PONG RakNet → players_online/max |
| `infrastructure/runtime/docker.py` | `_compute_cpu_percent` real + `get_resources` usa `api.stats` sin inspect previo |
| `tests/test_monitoring.py` | `test_poll_or_cached_*` + `test_facade_poll_server_y_poll_all_comparten_una_pasada` |
| `tests/test_runtime.py` | `test_get_resources_computes_cpu_percent_from_delta` + `FakeClient.api` |
| `tests/test_phase_d_config_monitoring.py` | `test_raknet_probe_parses_players_from_bedrock_pong` + `test_parse_pong_ignores_non_bedrock_payloads` |

### Verificación

- `uv run pytest` → `870 passed, 37 deselected` (6 tests nuevos + 1 de delta ≤0).
- `ruff check` / `ruff format` ✅; `mypy --strict` ✅ en los archivos tocados
  (quedan 2 errores preexistentes en `tests/test_client_factory.py` de un commit
  anterior, fuera del alcance de esta auditoría).
- La dedup se comprueba con `test_facade_poll_server_y_poll_all_comparten_una_pasada`
  (1 sola llamada al probe).
- **CPU en vivo**: con un servidor real arrancado, el WS de monitoring reportó
  `cpu_percent` reales por delta (`3.84`, `1.74`) — antes `None`/`0`.

### Corrección posterior — CPU: descartar muestra inválida (no clampear, no inventar)

> **Fecha**: 2026-08-10 (revisión del usuario). En producción se observó
> `cpu: 202%` — un delta inválido de `precpu_stats` (sin `system_cpu_usage`
> válido o contadores no monótonos) producía un % descabellado. La política
> acordada: **no clampear a 100 ni reportar `0.0` inventado** — si la muestra
> no es computable se descarta ese valor de CPU y la siguiente pasada (5 s)
> trae un delta real.

- `_compute_cpu_percent` ahora devuelve `float | None`: `None` cuando
  `precpu_stats` no trae `system_cpu_usage`/`total_usage` válido o cuando el
  delta de CPU o del sistema da ≤0. Antes devolvía `0.0` (inventaba un valor).
- `MetricSample.cpu` pasa a `float | None` y se propaga hasta el payload del WS
  (`"cpu": null` → el StatCard muestra "—" en lugar de un % falso). **No se
  descarta la vuelta entera**: un contenedor parado siempre trae `precpu`
  inválido, y descartar el snapshot completo congelaría jugadores/RAM/estado en
  el frontend (el server seguiría siendo observable offline).
- `docker.get_resources` documenta la semántica de `None`.

### Corrección posterior — entorno dev: `server.public_host=localhost` no alcanzaba el juego

> **Fecha**: 2026-08-10. Al repetir la prueba real del gateway se encontró que
> el servidor jamás llegaba a `running` (y por tanto no se emitían
> `SERVER.STARTED`/`PLAYER.JOINED`) en el entorno de desarrollo: el backend
> corre en el contenedor `bedrockpanel-dev` donde `localhost` es el propio
> contenedor, no el host. El probe RakNet (`RakNetStatusProbe`) sondea
> `view.connection.host` = `server.public_host`, que resolvía a `localhost`
> (verificado: desde el contenedor `localhost:19136 → False`, `172.18.0.1 → True`).

- `docker-compose.dev.yml` expone ahora `BEDROCK_PANEL_SERVER_PUBLIC_HOST`
  (default `localhost`, override con `${BEDROCK_PANEL_SERVER_PUBLIC_HOST}`),
  mismo patrón que `docker-compose.prod.yml`. Para desarrollo con backend en
  contenedor hay que apuntarlo a una dirección alcanzable (p. ej. el gateway de
  la red docker = IP del host).
- **Con esa corrección, la prueba real confirma**:
  - el gateway `/ws` capturó `SERVER.STARTING` y `SERVER.STARTED` cuando el
    servidor real llegó a `running` (~17 s);
  - `ConsoleStreamManager` arrancó el stream al `SERVER.STARTED` (log
    "Arrancando stream de {server_id}") — el fix de reconciliación
    (`ConsoleStreamReconciler.reconcile()` en el lifespan) está aplicado y
    cubierto por `tests/test_console_stream_reconcile.py`;
  - una línea de BDS en vivo (`There are 0/10 players online`) fluyó por el WS
    de console y al buffer, confirmando que el stream está attached y que
    `PlayerJoinDetector` recibirá `Player connected: ...` → `PLAYER.JOINED`
    (el detector no tiene bug de parseo; su regex y tests ya estaban bien).

### Pendiente / deuda

- Evaluar con el equipo de backend si conviene migrar Monitoring al gateway
  único `/ws` a largo plazo (hoy es desviación ADR-002 legítima). No se
  resuelve en esta auditoría por ser decisión de arquitectura.
- `PLAYER.JOINED` de punta a punta con un jugador real sigue pendiente de
  verificación manual en navegador (requiere que un cliente Bedrock se conecte);
  el pipeline (stream attached + detector + regex) ya está confirmado y probado.

---

### Corrección posterior — el probe RakNet usaba `server.public_host`, no una dirección alcanzable

> **Fecha**: 2026-08-10. El fix anterior (punto "Corrección posterior — entorno dev")
> aconsejaba apuntar `BEDROCK_PANEL_SERVER_PUBLIC_HOST` a una dirección alcanzable desde
> el backend, lo que **confluyó dos conceptos**: el host público que ven los clientes
> Bedrock (IP LAN, para que los jugadores se conecten desde fuera) y el destino del ping
> RakNet del probe, que corre **dentro** del contenedor del backend. Al fijar el env a la
> IP LAN `10.241.18.26`, el probe pasó a sondear una dirección inalcanzable desde el
> contenedor (timeout; el gateway Docker `172.18.0.1` sí es alcanzable), por lo que
> `mark_started` nunca se disparaba: el estado quedaba en `starting` indefinidamente y no
> se emitían `SERVER.STARTED` ni `PLAYER.JOINED` (diagnóstico vía `noti_event_log`: ningún
> `SERVER.STARTED` desde las 20:21:47 UTC pese a sesiones reales de juego).

**Causa raíz**: `StatusPoller.poll_server()` sondaba `view.connection.host` (`results.py:36`,
`connection_from_spec` → `server.public_host`). Un solo host servía a dos usos con
requisitos de alcance distintos.

**Solución (separación de responsabilidades)**:

- Nuevo setting `BEDROCK_PANEL_MONITORING_PROBE_HOST` (`monitoring.probe_host`,
  `bootstrap/config.py`), default `None`. `polling.py` resuelve el host del ping:
  `_probe_host(view)` devuelve `monitoring.probe_host` si está configurado, si no cae en
  `connection.host` (compatibilidad).
- `docker-compose.dev.yml` fija `BEDROCK_PANEL_MONITORING_PROBE_HOST=172.18.0.1` (gateway
  de la red Docker, alcanzable desde el contenedor). `BEDROCK_PANEL_SERVER_PUBLIC_HOST`
  queda únicamente para lo que los clientes ven (IP LAN p. ej. `10.241.18.26`).
- Tests: `test_monitoring.py` añade cobertura de `_probe_host` (usa el configurado cuando
  existe; cae al host público si no). Suite backend: **872 passed**.
- Verificación real end-to-end: `POST /servers/{id}/start` → estado `running` en ~8 s
  (antes: `starting` indefinido), evento `SERVER.STARTED` en `noti_event_log` (seq 329),
  el `ConsoleStreamManager` arranca el stream al recibirlo, y la conexión que ve la UI
  sigue siendo `10.241.18.26:19132` (host público intacto).

### Corrección posterior — spam DEBUG de urllib3/SDK Docker en logs del backend

> **Fecha**: 2026-08-11. Con `BEDROCK_PANEL_LOG_LEVEL=DEBUG` (dev), el SDK de
> Docker logueaba a DEBUG cada sondeo del poller (`GET /v1.55/containers/*/stats`
> y `/json` cada ~5 s por servidor vía `urllib3.connectionpool`, además de
> `docker.utils.config`), inundando el output sin aportar nada.

**Cambio**: `configure_logging()` (`app/kernel/logging.py`) fija a **WARNING** los
loggers de terceros `urllib3`, `docker`, `watchfiles`, `httpcore` y `httpx`,
dejando el DEBUG raíz solo para la app (`app.*`). Con `INFO`/`WARNING` (prod) el
comportamiento no cambia (ya estaban por debajo).

- Verificado en contenedor: tras el reload automático (`uvicorn --reload`) el
  patrón `DEBUG urllib3|docker` desapareció (0 líneas) mientras los logs INFO de
  la app (WS `[accepted]`, `stream_manager`) siguen saliendo.
- Suite backend: **872 passed**; `ruff` ✅.

## 31. Ajustes por mundo + mundo por defecto "Mi Mundo 1"

> **Fecha**: 2026-08-11. Pedido: al crear un mundo poder configurar semilla,
> modo de juego, dificultad y distancia de chunks; y que el primer mundo de un
> servidor nuevo se llame "Mi Mundo 1" en lugar del default "Bedrock level" de
> BDS.

### Alcance

- **Configuración por mundo** (`seed`, `gamemode`, `difficulty`,
  `view_distance`) en `CreateWorldCommand`/`UpdateWorldCommand` (renombrar +
  ajustar). Se guardan en la metadata (`world_metadata` gana 4 columnas) y, al
  **activar** el mundo, viajan en `WORLD.ACTIVATED` para que Server los
  inyecte como env al renderizar el spec: `LEVEL_SEED`, `GAMEMODE`,
  `DIFFICULTY`, `VIEW_DISTANCE`.
- **Mundo por defecto** "Mi Mundo 1": `ConfigurationFacade.desired_config()`
  sin perfil siembra `LEVEL_NAME` desde `defaults.level_name` (default
  "Mi Mundo 1", configurable por settings). Con perfil el default **no** pisa
  las properties del usuario.
- **UI**: el diálogo "Crear mundo" incluye semilla/modo/dificultad/chunks; el
  listado de mundos gana "Ajustar" (edición con renombrado + settings), que usa
  el `PATCH /servers/{id}/worlds/{name}` ya existente con permiso `world.update`.

### Mecánica del evento (decisión §22)

`WORLD.ACTIVATED` no lleva `config_rev`; se reaplica la config deseada sin
tocar la revisión de Configuration. El handler `WorldActivatedHandler` propaga:
`level_name` (directorio del mundo) y `environment` override con los ajustes
(seed/gamemode/difficulty/view_distance, `view_distance` → texto). El override
se fusiona sobre la env deseada con la mayor prioridad en `ApplyConfigUseCase`
(nuevo campo `environment` en `ApplyConfigCommand`).

### Migración

`0015_world_world_settings`: columnas en `world_metadata`, permiso
`world.update` (operator/admin/super_admin, mismo patrón que 0014) y setting
`defaults.level_name = "Mi Mundo 1"`.

### Verificación

- Suite backend: **887 passed**; `ruff` ✅; `mypy` ✅ (330 archivos).
- Frontend: `tsc -b` ✅, `eslint` ✅, `vitest` 68 passed.

### Corrección posterior — el sync trae los datos del mundo desde el disco

> **Fecha**: 2026-08-11. En una BBDD ya migrada los mundos existentes (creados
> por BDS o importados) tenían `seed`/`gamemode`/`difficulty`/`view_distance`
> en `NULL`: la metadata se creaba en el primer sync sin leer los ajustes.

**Cambio**: el sync ahora lee los ajustes del mundo del disco de forma
**best effort** y rellena la metadata cuando esta no los tiene (backfill; lo
configurado por el usuario **no** se pisa):

- `src/app/infrastructure/storage/level_reader.py` (nuevo): parser NBT
  little-endian (gzip o crudo) de `level.dat` → `seed` (prefiere
  `WorldGenSettings.seed`, respaldo `RandomSeed`), `gamemode` (`GameType`:
  0/1/2 → survival/creative/adventure), `difficulty` (`Difficulty`: 0–3).
  `view_distance` no vive en `level.dat` (es ajuste de servidor): se respalda
  con `view-distance` de `server.properties`. Nunca lanza (nivel corrupto →
  dict vacío).
- `ServerStoragePort.world_settings()` (nuevo método) + implementación en
  `LocalServerStorage`.
- `ScanWorldsUseCase.sync()` pasa los ajustes a `_new_world` (descubrimiento) y
  a `_refreshed_world` (backfill de campos `None`).
- UI: el listado de mundos muestra modo/dificultad/chunks/semilla cuando hay.

**Verificación**: suite backend **899 passed**; `ruff`/`mypy` ✅ (331 archivos);
frontend `tsc`/`eslint`/`vitest` 68 ✅.

### Corrección posterior 2 — formato real de `level.dat` de BDS 1.26.x + orden sync/worlds

> **Fecha**: 2026-08-11. En un servidor real el sync devolvía
> `seed`/`gamemode`/`difficulty` en `null` (solo `view_distance` salía del
> `server.properties`). El parser asumía gzip + NBT sin cabecera.

**Hallazgo**: BDS 1.26.43.1 escribe `level.dat` **sin gzip** y con una
**cabecera de 8 bytes** (`0a 00 00 00` + longitud LE del payload NBT). El
parser consumía la cabecera como si fuera NBT y terminaba con un compound raíz
vacío → `{}`.

**Cambios**:
- `level_reader.py`: `_strip_level_header()` detecta la cabecera moderna (solo
  cuando el marcador y la longitud declarada son coherentes) y aplica el
  mismo recorte al payload gzip descomprimido; sigue aceptando gzip clásico y
  crudo sin cabecera. Verificado contra el `level.dat` real (se extrae
  `seed=-299205636354301287`, `gamemode=survival`, `difficulty=easy`).
- Frontend `WorldsPage`: el orden pasa a ser **sync primero, worlds después**
  (antes era worlds → sync → worlds, 3 llamadas). La query de mundos queda
  gateada por un flag `synced` que se activa al terminar el sync inicial; el
  botón "Sincronizar" queda siempre activo (muestra spinner mientras corre).

**Verificación**: suite backend **901 passed**; `ruff`/`mypy` ✅; frontend
`tsc`/`eslint`/`vitest` 68 ✅.

### Corrección posterior 3 — sync dentro del query de mundos (StrictMode seguro)

> **Fecha**: 2026-08-11. El intento anterior (gate con `syncState` + ref
> `pendingFor` + `onSettled`) quedaba **atascado en "Sincronizando mundos…"**
> en desarrollo: tras el sync (201) el `GET /worlds` nunca se disparaba y el
> sync se repetía en bucle.

**Causa raíz (verificada por test con `StrictMode`)**: en desarrollo React
desmonta y remonta el componente con **estado nuevo**, así que el ref
`pendingFor` se resetea y, peor, la mutación iniciada en el primer montaje
queda **huérfana**: el `MutationObserver` pierde sus listeners al desmontar y
`MutationObserver.#notify()` descarta el `onSettled` (`hasListeners()` es
false). Como el ref-guard impedía al segundo montaje relanzar la mutación,
`setSyncState({done:true})` nunca corría → el gate nunca pasaba. En
producción (sin StrictMode) funcionaba; en dev (Vite) no.

**Cambio** (`hooks.ts` + `WorldsPage.tsx`): se elimina por completo el
`useEffect`, el gate y el hook `useSyncWorlds`. El sync vive **dentro del
`queryFn`** de `useWorlds`: primero `POST /worlds/sync` (que ya devuelve la
lista reconciliada, 201) y si falla, fallback a `GET /worlds` (metadata). Así:
- React Query **deduplica por `queryKey`**, de modo que aunque StrictMode
  monte dos veces el componente, el `queryFn` corre **una sola vez** (sync →
  lista, sin llamadas duplicadas ni bucles).
- El botón "Sincronizar" hace `invalidateQueries(worldKeys.all(serverId))` →
  refetch → re-sync; el spinner se ata a `isFetching`.
- La pantalla "Sincronizando mundos…" se muestra solo mientras `isLoading`
  (primera carga, sin datos); con datos se ve la lista con el botón activo.

**Verificación**: test de regresión nuevo
`apps/frontend/src/features/worlds/WorldsPage.test.tsx` con `StrictMode`
(sync una sola vez, fallback a metadata, botón re-sync) — **71 tests** ✅,
`tsc` ✅, `eslint` ✅. Backend sin cambios. En BBDD del servidor real:
`seed=-299205636354301287`, `gamemode=survival`, `difficulty=easy`,
`view_distance=32`.

### Corrección posterior 4 — ajustes que no se aplicaban al mundo (2026-08-11)

> **Origen**: probando "Ajustar mundo" en el servidor real, cambiar la semilla,
> el nombre (`level_name`) o el modo de juego no tenía efecto en el juego; solo
> la dificultad funcionaba. La propagación al contenedor **sí** ocurría
> (env + `server.properties` correctos); el problema era cómo BDS trata esos
> ajustes en **mundos existentes**.

**Diagnóstico** (verificado en el contenedor real):

1. **Modo de juego**: con `force-gamemode=false` (default), BDS usa el modo
   guardado en `level.dat` (`GameType`), ignorando `gamemode` de
   `server.properties` en mundos existentes.
2. **Semilla**: `level-seed` solo se usa al **generar** un mundo nuevo; BDS no
   regenera uno existente (cambiar la semilla no puede cambiar el mundo).
3. **Nombre**: el nombre en juego sale del tag `LevelName` de `level.dat`;
   `LEVEL_NAME`/`level-name` solo indica qué carpeta cargar y BDS reescribe
   `levelname.txt` desde el nivel, así que renombrar la carpeta no cambiaba el
   nombre mostrado.

**Cambios**:

- `handlers.py` `_world_environment`: si hay `gamemode` configurado, inyecta
  además `FORCE_GAMEMODE=true` (el itzg image lo mapea a
  `force-gamemode=true`) → BDS aplica el modo configurado aunque el mundo ya
  exista.
- `level_reader.py` nuevo `patch_level_name()`: reescribe el tag `LevelName`
  de `level.dat` preservando el resto (NBT secuencial: se rehace solo el
  tramo del string y la longitud de la cabecera; mantiene gzip/cabecera según
  viniera; nunca lanza). Puerto `ServerStoragePort.patch_level_name` +
  `LocalServerStorage.patch_level_name`.
- `UpdateWorldUseCase`: al renombrar, parchea el `LevelName` del `level.dat`
  y escribe `levelname.txt`; así el nombre en juego (y la metadata tras el
  sync) cambia de verdad.
- Frontend: hint en Crear/Ajustar mundo — la semilla solo se aplica al
  generar un mundo nuevo, no regenera uno existente.

**Verificación**:

- Backend: **909 passed**; `ruff` ✅; `mypy` ✅. Nuevos tests: `patch_level_name`
  (formato moderno/gzip/crudo, lossless, corrupto), `FORCE_GAMEMODE` en la
  propagación y rename que parchea `LevelName`.
- E2E en el servidor real (JWT firmado con el secreto de dev):
  - `PATCH gamemode=creative` → contenedor con `GAMEMODE=creative
    FORCE_GAMEMODE=true`, `server.properties` con `force-gamemode=true` y BDS
    arrancando en `Game mode: 1 Creative` (revertido a survival después).
  - Rename `village → village-test → village` (con servidor en marcha):
    `LevelName` de `level.dat` parcheado y BDS abriendo `worlds/village/db`.
  - La semilla en un mundo existente no cambia el mundo (inherente a BDS);
    el hint lo comunica.

### Pendiente / deuda

- No se soporta "limpiar" un ajuste a `None` desde `UpdateWorldCommand` (solo
  volver a escribirlo); el default del juego se obtiene enviando el ajuste
  vacío desde la UI no está soportado — los campos vacíos no se envían.

## 34. UI de Monitoring (Fase 6 — parte 1)

> **Fecha**: 2026-08-12. Sin cambios de backend: el WS de monitoring (ADR-002)
> ya estaba completo. Se añadió la página frontend de monitoreo con gráficos
> Recharts. Se verificó que **no existe** `GET /servers/{id}/metrics` (ni en el
> router ni en la facade) → el frontend usa solo el WS en vivo y filtra el
> histórico en memoria; discrepancias documentadas en `docs/change-log-frontend.md`
> (Fase 6 — Monitoring).

### Verificación

- Frontend: `tsc` ✅ · `eslint` ✅ · `vitest` **119 passed** (16 nuevos) ✅ ·
  `build` ✅.
- E2E contra el backend real: el WS `/servers/{id}/monitoring/ws?token=` emite
  `SERVER.STATE` scope `monitoring` con el payload de 8 campos, `ts` y `seq`
  crecientes cada ~5 s ✅.

## 35. Fixes de QA de Monitoring (dropdown + gráficos)

> **Fecha**: 2026-08-12. Solo frontend (sin cambios de backend): el dropdown de
> servidores perdía la subpágina al cambiar de servidor, y los gráficos usaban
> valores absolutos (RAM en MB) con curvas angulosas. Se documentan en
> `docs/change-log-frontend.md` (Fase 6 — Monitoring bis).

### Verificación

- Frontend: `tsc` ✅ · `eslint` ✅ · `vitest` **120 passed** (1 nuevo) ✅ ·
  `build` ✅.

## 36. CPU por núcleo + iconos en stat cards de Monitoring

> **Fecha**: 2026-08-12. Solo frontend. La CPU del WS superaba el 100% (185%)
> porque el backend reporta % por núcleo (fórmula Docker × `online_cpus`, 100%
> = un núcleo — comportamiento documentado en `test_runtime.py`). No se cambió
> el backend (el valor crudo es correcto); el frontend ahora normaliza contra
> `cpu_cores` del servidor y clampa a 100. Detalle en
> `docs/change-log-frontend.md` (Fase 6 — Monitoring ter).

### Verificación

- Frontend: `tsc` ✅ · `eslint` ✅ · `vitest` **125 passed** (5 nuevos) ✅ ·
  `build` ✅.

## 37. Overshoot de la curva + barra de CPU (QA Monitoring)

> **Fecha**: 2026-08-12. Solo frontend. (1) La curva `natural` bajaba de 0 en
> los picos de CPU → se cambió a `monotone` + `clipPath`. (2) La barra de la
> card de CPU se llenaba de más: `StatCard.progress` espera fracción 0..1 y se
> le pasaba el percent → se corrige a fracción. Detalle en
> `docs/change-log-frontend.md` (Fase 6 — Monitoring cuarta iteración).

### Verificación

- Frontend: `tsc` ✅ · `eslint` ✅ · `vitest` **125 passed** ✅ · `build` ✅.

## 33. UI de Backups (cierre de la Fase 4)

> **Fecha**: 2026-08-12. Sin cambios de backend: el módulo Backup (paso 13)
> ya estaba completo. Se añadió la UI frontend de Backups verificando el
> contrato real (router/schemas) y se documentan las diferencias con el
> borrador del plan en `docs/change-log-frontend.md` (Fase 4 — Parte 4).

### Verificación

- Frontend: `tsc` ✅ · `eslint` ✅ · `vitest` **103 passed** (10 nuevos) ✅ ·
  `build` ✅.
- E2E contra el backend real (JWT dev `super_admin`): crear backup (201,
  `state=completed`, checksum + entries) → detalle → descarga
  (`application/zstd`, `filename="{world}-{id}.tar.zst"`) → validate (200) →
  restore (200) → delete (204) → prune (`keep_last_n`) ✅.

## 32. Búsqueda parcial de jugadores + listado de bans (Player)

> **Fecha**: 2026-08-12. Pedido desde QA del front: (1) búsqueda de jugadores
> por **coincidencia parcial** ("Cra" debe encontrar "CrafterTec"), (2) una
> **lista de baneados** consultable para poder desbanear sin conocer el ban id.
> Se toca backend (search + listados) y front (sección de baneados + botón
> desbanear).

### Cambios backend

- `GET /servers/{id}/players/search?name=` ahora devuelve **`list[ResolvePlayerResponse]`**
  (antes un solo objeto o 404). Coincidencia parcial case-insensitive por
  `ilike('%term%')`, orden por `last_seen_at` desc, límite 10. La ruta se
  declara ANTES de `/servers/{id}/players/{xuid}` para que `bans` no colisione
  con el path param.
- Nuevo `GET /servers/{id}/players/bans` → `list[ServerBanResponse]`
  (`player.list`), orden `created_at` desc. Nuevo schema `ServerBanResponse`
  (antes el ban por servidor solo respondía 204).
- Nuevo `GET /players/bans/global` → `list[GlobalBanResponse]`
  (`player.ban.global`), orden `created_at` desc.
- Ports: `PlayerRepositoryPort.search_players(term, limit=10)`,
  `PlayerBanRepositoryPort.list_global_bans()` / `list_server_bans(server_id)`.
  Implementados en Postgres y memoria.
- Facade: `search_players`, `list_global_bans`, `list_server_bans`.

### Cambios frontend

- `searchPlayer` devuelve lista; resultados en filas con estado de ban.
- Sección "Jugadores baneados" (globales + del servidor combinados) con botón
  "Desbanear" + confirmación; visible a la mano sin depender del buscador.
- Un jugador baneado en el buscador muestra "Desbanear" en vez de Kick/Ban.
- Fix del cierre de `GlobalBanDialog`/`BanPlayerDialog` (la X y Cancelar no
  cerraban: el handler no propagaba `onOpenChange(next)` al padre).

### Verificación

- Backend: **909 passed**; `ruff` ✅; `mypy` ✅. Nuevos tests de search parcial
  y listados en `test_api_integration.py` (`TestPlayerApi`).
- Frontend: `tsc` ✅; `eslint` ✅; `vitest` **93 passed** (6 nuevos) ✅;
  `build` ✅.
- E2E backend real: `search?name=Cra` → `CrafterTec`; ban por servidor 204 →
  list → DELETE 204 → `[]`; ban global 201 → list → DELETE 204 → `[]`.
