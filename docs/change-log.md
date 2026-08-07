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
