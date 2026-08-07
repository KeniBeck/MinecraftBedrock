# Implementation Blueprint v1.0 — Panel de Administración de Servidores Minecraft Bedrock

> **Título**: Implementation Blueprint v1.0
> **Proyecto**: *BedrockPanel* — panel web para servidores Minecraft Bedrock sobre Docker
> **Estado**: Aprobado como contrato técnico de implementación
> **Fecha**: 2026-08-05
> **Documento fuente**: `docs/technical-design.md` (TDD v0.1) — **todas sus decisiones son definitivas e inmutables**
> **Documentos relacionados**: `docs/analisis-proyecto-base.md`
> **Propósito**: especificar *cómo* implementar el sistema de forma que respete al 100% el TDD. Es el contrato que seguirán los agentes de código. No redefine arquitectura: la traduce a especificaciones.

---

## Índice

1. [Dependencias entre módulos](#1-dependencias-entre-módulos)
2. [Orden de implementación](#2-orden-de-implementación)
3. [Responsabilidades por módulo](#3-responsabilidades-por-módulo)
4. [Contratos internos](#4-contratos-internos)
5. [Flujo de datos](#5-flujo-de-datos)
6. [Ciclo de vida del servidor](#6-ciclo-de-vida-del-servidor)
7. [Ciclo de vida de un mundo](#7-ciclo-de-vida-de-un-mundo)
8. [Ciclo de vida de un backup](#8-ciclo-de-vida-de-un-backup)
9. [Catálogo de eventos](#9-catálogo-de-eventos)
10. [Convenciones](#10-convenciones)
11. [Manejo de errores](#11-manejo-de-errores)
12. [Política de logging](#12-política-de-logging)
13. [Observabilidad](#13-observabilidad)
14. [Estrategia de testing](#14-estrategia-de-testing)
15. [Extensibilidad](#15-extensibilidad)
16. [Checklist de implementación por módulo](#16-checklist-de-implementación-por-módulo)

---

## 1. Dependencias entre módulos

### 1.1 Principios de dependencia (herencia del TDD §4.3)

- Flujo descendente: Presentación → Aplicación → Dominio.
- Aplicación e Infraestructura pueden depender de Dominio.
- Presentación y Aplicación dependen de **puertos**, nunca de adaptadores.
- Dominio **jamás** depende de Aplicación, Presentación o Infraestructura.
- La comunicación entre módulos se hace **solo por eventos o por facades de use cases**;
  nunca importando el interior de otro módulo.

### 1.2 Puertos técnicos compartidos (kernel)

Para evitar dependencias cruzadas y permitir que varios dominios consuman capacidades
técnicas, los siguientes **puertos técnicos** viven en el **kernel compartido**
(no en el dominio de un módulo concreto):

| Puerto técnico | Propósito | Implementado por | Consumido por |
|---|---|---|---|
| `ServerRuntimePort` | Ciclo de vida/proceso del servidor | `infrastructure/runtime/*` (Docker, futuro Podman/nativo/k8s) | Dominios **Server** y **Console** |
| `ServerStoragePort` | Árbol `/data` del servidor | `infrastructure/storage/*` (local, runtime-storage) | Dominios **Server**, **World**, **Configuration**, **Permission** |
| `BackupStorePort` | Almacenamiento de artefactos de backup | `infrastructure/backups/*` (local, futuro S3) | Dominio **Backup** |
| `StatusProbePort` | Ping RakNet (estado del juego) | `infrastructure/status/*` | Dominio **Monitoring** |
| `AccessControlPort` | Decisiones de autorización | Módulo **IAM** (infraestructura) | Presentación de **todos** los módulos |
| `SettingsPort` | Lectura de configuración global | Módulo **Settings** (infraestructura) | Todos los módulos |
| `EventBusPort` | Publicación/suscripción de eventos | `infrastructure/events/*` (bus + outbox + redis) | Todos los módulos |
| `TimeProviderPort` | Reloj inyectable | `infrastructure/common/*` | Dominios con tiempo (Scheduler, Backup, Monitoring) |
| `IdGeneratorPort` | Generación de IDs (UUID v7) | `infrastructure/common/*` | Todos los módulos |

**Regla**: un dominio puede depender de puertos técnicos del kernel, pero el kernel
**no conoce** los dominios.

### 1.3 Matriz de dependencias entre módulos

Leyenda: `D` = dependencia permitida (facade de use cases), `P` = depende de un puerto
técnico del kernel, `E` = solo se comunica por eventos, `—` = prohibido/imposible.

| Módulo | Puede depender de | Nunca de |
|---|---|---|
| **IAM** | Settings (P), kernel | Cualquier módulo de negocio (Server, World, Backup, Player, Console, …) |
| **Server** | Settings (P), Runtime (P), Storage (P); Template (D, creación), Configuration (D, lectura de config deseada; aplicar config por evento `CONFIG.CHANGED`) | World/Backup/Player/Permission/Console/Monitoring internos (solo E) |
| **World** | Settings (P), Storage (P); Console (D, export con `save hold`); Server (E, `WORLD.ACTIVATED` → recrear), Configuration (E, `WORLD.ACTIVATED` → level-name) | Backup/Player internos (solo E) |
| **Backup** | Settings (P), Storage (P), BackupStore (P); **Console (D, save hold/resume)**, **Server (D, stop/start)** | World/Player internos (solo E) |
| **Player** | Settings (P); Console (D, ban/unban/kick) | Server internos (solo E); Permission (solo E: `PLAYER.OPERATOR_CHANGED`) |
| **Permission** | Settings (P), Storage (P); Console (D, op/allowlist), Player (D, XUID) | Server/World internos (solo E) |
| **Configuration** | Settings (P), Storage (P); — (aplicar por evento `CONFIG.CHANGED`, consumido por Server) | World/Backup internos (solo E) |
| **Console** | Settings (P), Runtime (P); Server (D, identidad y estado del proceso) | Cualquier dominio de negocio (no interpreta) |
| **Scheduler** | Settings (P); Server (D), Backup (D), Console (D) como *destinos de tareas* | Todos (solo E para el resto) |
| **Monitoring** | Settings (P), Runtime (P), Storage (P), StatusProbe (P) | Console/Player internos (solo E) |
| **Template** | Settings (P), Storage (P) | Server/World internos (solo E; Server lo consume vía facade) |
| **Notification** | Settings (P), EventBus (P), kernel | Todos los demás (consumidor terminal) |
| **Settings** | kernel | Todo |

### 1.4 Dependencias prohibidas (lista explícita)

1. **World, Backup, Player, Permission, Configuration, Monitoring**: prohibido importar
   el dominio o la infraestructura de **Server** (solo facades públicas).
2. **Backup**: prohibido llamar al runtime directamente (usa Console + Server facades).
3. **Console**: prohibido parsear/interpretar negocio (solo emite líneas y comandos).
4. **IAM**: prohibido conocer servidores, mundos, backups o jugadores.
5. **Ningún módulo** puede importar el *infrastructure* de otro módulo.
6. **Ningún módulo** puede usar Docker SDK, `os`, filesystem o Postgres directamente
   fuera de sus adaptadores de infraestructura o del kernel.
7. **Frontend**: prohibido tocar Docker, volumen, red interna o la BBDD.
8. **Notification**: nadie depende de Notification (terminal); el WebSocket consume el bus.

### 1.5 Dependencias que deben invertirse

| Acoplamiento natural | Se invierte a | Mecanismo |
|---|---|---|
| Módulos quieren saber "¿puede este usuario X hacer Y en el servidor Z?" | Módulos definen `AccessControlPort`; **IAM** lo implementa | DI en bootstrap |
| Módulos quieren leer defaults globales | Módulos definen `SettingsPort`; **Settings** lo implementa | DI en bootstrap |
| Server/Console quieren ejecutar contenedores | Dominios definen `ServerRuntimePort`; adaptador Docker lo implementa | DI en bootstrap |
| Backup quiere "detener/arrancar servidor" | Backup llama a la **facade pública** de use cases de Server | Facade (no import directo) |
| Scheduler quiere "ejecutar backup" | Scheduler envía `TASK.STARTED`; Backup reacciona y ejecuta su dominio | Evento |
| Monitoreo quiere saber cuándo cambió el estado | Monitoring escucha eventos del bus | Evento |

---

## 2. Orden de implementación

Orden lógico de construcción (no sprints). Cada paso desbloquea el siguiente.

### Fase A — Base técnica (kernel + infraestructura compartida)

1. **Kernel compartido**: config, logging, errores base, IDs, bus de eventos,
   `TimeProvider`, `IdGenerator`.
2. **Capa de persistencia**: Postgres + SQLAlchemy + Alembic con migraciones por módulo
   (prefijo de tabla), patrón de repositorios.
3. **Módulo Settings**: settings port + tabla `Setting` + defaults globales.
4. **Adaptadores de runtime y storage en versión mínima**:
   `ServerRuntimePort` → Docker; `ServerStoragePort` → LocalStorage. Son el suelo de
   todo lo demás.
5. **Infraestructura de eventos**: bus en proceso + outbox sobre Postgres (y cableado a
   Redis como opcional, respetando TDD §7.1).

> **Por qué primero**: toda dependencia del sistema cuelga de kernel, DB, puertos y bus.
> Sin esto, ningún módulo puede ser construido respetando capas.

### Fase B — Servidor y consola (la espina dorsal)

6. **Módulo Server (núcleo)**: entidad `Server`, `RuntimeSpec`, estados, puertos,
   use cases de ciclo de vida (crear/iniciar/detener/reiniciar/eliminar/recrear).
7. **Módulo Console**: envio de comandos (stdin), streaming de logs, buffer en memoria.

> **Por qué**: Server es el agregado raíz del dominio y Console es el primer consumidor
> real del runtime; juntos validan el contratos runtime/storage más temprano.

### Fase C — Presentación protegida

8. **Módulo IAM (mínimo viable)**: `User`, login, JWT + refresh, `AccessControlPort`
   con roles base (super_admin, admin, operator, viewer) y membresía por servidor.

> **Por qué**: toda la API debe estar detrás de autenticación/autorización desde el
> primer endpoint; se evita reescribir rutas después.

### Fase D — Observación y configuración

9. **Módulo Monitoring (básico)**: `StatusProbePort` → cliente RakNet, estado en vivo,
   muestras en `MetricSample`, reconciliación de jugadores.
10. **Módulo Configuration (básico)**: esquema de propiedades (espejo de
    `property-definitions.json`), mapeo propiedad→env, validación.

> **Por qué**: monitoring valida el ping (crítico para "online"), y configuration es
> prerequisito de World (level-name) y de Backup (aplicar cambios sin romper estado).

### Fase E — Datos del jugador y mundos

11. **Módulo Player**: eventos join/leave, sesiones, playtime, cache XUID.
12. **Módulo World**: operaciones sobre `worlds/*`, validación de `level.dat`,
    metadata, import/export/duplicar/activar/eliminar.

> **Por qué**: Player alimenta al contador y al histórico; World es la unidad de
> backup/exportación, y Backup depende de ambos conceptos.

### Fase F — Persistencia de datos (backups y permisos)

13. **Módulo Backup**: snapshot + `save hold/resume`, compresión, checksum, retención,
    restauración con rollback, `BackupStorePort` local.
14. **Módulo Permission**: allowlist, ops, `permissions.json`, niveles, resolución XUID.

> **Por qué**: Backup es el valor central del producto y necesita a Console, Server,
> World y Storage maduros. Permission cierra la administración en-juego.

### Fase G — Automatización y reutilización

15. **Módulo Scheduler**: tareas programadas, cron, reintentos, bloqueo de concurrencia.
16. **Módulo Template**: captura/reproducción de config + mundo + packs.

> **Por qué**: Scheduler orquesta backups/reinicios ya existentes; Template reutiliza
> Server + World + Configuration.

### Fase H — Cierre y robustez

17. **Módulo Notification / WebSocket gateway**: difusión de eventos al frontend,
    canales, resume por seq.
18. **IAM completo**: roles/permisos por acción, auditoría tamper-evident, 2FA, API keys.
19. **Settings avanzado**: ubicaciones de almacenamiento, límites, defaults por tenant.

> **Por qué**: Notification necesita el catálogo de eventos maduro; IAM completo y
> auditoría cierran la parte de seguridad; Settings avanzado acaba la configurabilidad.

### Frontend

Se construye en paralelo por **feature** alineada con cada módulo backend (features
`servers`, `console`, `monitoring`, `worlds`, `backups`, `players`, `permissions`,
`config`, `scheduler`, `templates`, `iam`). La capa `ws` y `store` se asientan cuando
exista el gateway (Fase H), pero pueden desarrollarse contra un stub de eventos.

---

## 3. Responsabilidades por módulo

Convención de columnas: **Entradas** = qué recibe; **Salidas** = qué produce;
**Eventos publicados/consumidos** según el catálogo de la sección 9;
**Dependencias permitidas** según §1.3.

### 3.1 IAM (Identity & Access)

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Identidad, autenticación, autorización (RBAC + ACL por servidor), sesiones, auditoría |
| Entradas | Credenciales, tokens, usuarios, roles, decisiones de autorización |
| Salidas | Tokens, identidad autenticada, decisiones de autorización, registros de auditoría |
| Eventos publicados | `AUTH.LOGIN_SUCCESS`, `AUTH.LOGIN_FAILED`, `IAM.USER_CREATED`, `IAM.USER_ROLE_CHANGED` |
| Eventos consumidos | `SERVER.CRASHED`, `TASK.FAILED`, `BACKUP.FAILED` (para auditoría de incidentes) |
| Dependencias permitidas | kernel, SettingsPort, EventBusPort, TimeProviderPort, IdGeneratorPort |
| Implementa | `AccessControlPort` |

### 3.2 Server

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Instancias de servidor: identidad, `RuntimeSpec`, ciclo de vida, versión, traducción config→env |
| Entradas | Órdenes de creación/arranque/parada/reinicio/eliminación/recreación; cambios de config; tareas |
| Salidas | Instancias persistidas, especificaciones materializadas en runtime, estados normalizados |
| Eventos publicados | `SERVER.CREATED`, `SERVER.CONFIG_CHANGED`, `SERVER.STARTING`, `SERVER.STARTED`, `SERVER.STOPPING`, `SERVER.STOPPED`, `SERVER.CRASHED`, `SERVER.REMOVED`, `SERVER.VERSION_CHANGED` |
| Eventos consumidos | `CONFIG.CHANGED`, `SERVER.CONFIG_CHANGED` (auto-recreate), `BACKUP.RESTORE_STARTED/COMPLETED`, `TASK.STARTED` (reinicios), `WORLD.ACTIVATED` |
| Dependencias permitidas | kernel, SettingsPort, ServerRuntimePort, ServerStoragePort, Template facade, Configuration facade (solo lectura de config deseada; aplicar config se recibe por evento `CONFIG.CHANGED`) |
| Expone | Facade pública de use cases (lifecycle, applyConfig, changeVersion) |

### 3.3 World

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Ciclo de vida de mundos y su metadata |
| Entradas | Archivos `.mcworld`/`.zip`/`.mctemplate`, órdenes de activar/duplicar/eliminar |
| Salidas | Mundos validados en storage, metadata persistida, artefactos exportados |
| Eventos publicados | `WORLD.CREATED`, `WORLD.IMPORTED`, `WORLD.EXPORTED`, `WORLD.DUPLICATED`, `WORLD.DELETED`, `WORLD.ACTIVATED` |
| Eventos consumidos | `SERVER.VERSION_CHANGED` (registrar formato de mundo) |
| Dependencias permitidas | kernel, SettingsPort, ServerStoragePort, Console facade (export: `save hold`); activar/level-name se comunican por evento `WORLD.ACTIVATED` |

### 3.4 Backup

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Creación/restauración/retención/validación de backups y su almacenamiento |
| Entradas | Órdenes de backup (manual, programada, pre-upgrade, pre-restore), políticas, backups a restaurar |
| Salidas | Artefactos en `BackupStore`, registros `Backup`, restauraciones verificadas |
| Eventos publicados | `BACKUP.STARTED`, `BACKUP.PROGRESS`, `BACKUP.COMPLETED`, `BACKUP.FAILED`, `BACKUP.RESTORE_STARTED`, `BACKUP.RESTORE_COMPLETED`, `BACKUP.RESTORE_FAILED`, `BACKUP.DELETED`, `BACKUP.VALIDATED` |
| Eventos consumidos | `TASK.STARTED` (backup programado), `SERVER.STOPPED` (backup en frío), `WORLD.SAVED` (ventana), `WORLD.DELETED` (huérfanos) |
| Dependencias permitidas | kernel, SettingsPort, ServerStoragePort, BackupStorePort, Console facade, Server facade |
| Expone | Facade pública (createBackup, restoreBackup, prune, validate) |

### 3.5 Player

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Presencia, historial, playtime, bans y resolución XUID |
| Entradas | Eventos de join/leave, órdenes de ban |
| Salidas | Registros `Player`/`PlaySession`, XUID resueltos y cacheados |
| Eventos publicados | `PLAYER.BANNED` |
| Eventos consumidos | `PLAYER.JOINED`, `PLAYER.LEFT`, `PLAYER.OPERATOR_CHANGED` (consistencia), `SERVER.STARTED` (limpiar presencia) |
| Dependencias permitidas | kernel, SettingsPort, Console facade (ban/unban/kick) |
| Expone | Facade pública (resolveXuid, findPlayer) |

### 3.6 Permission

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Allowlist, operadores y niveles de permiso en-juego (fichero + comandos) |
| Entradas | Entidades `allowlist.json`/`permissions.json`, órdenes op/deop/allowlist |
| Salidas | Ficheros actualizados en storage, comandos enviados vía Console |
| Eventos publicados | `PLAYER.OPERATOR_CHANGED` |
| Eventos consumidos | `PLAYER.JOINED` (autocompletar XUID) |
| Dependencias permitidas | kernel, SettingsPort, ServerStoragePort, Console facade, Player facade |

### 3.7 Configuration

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Esquema de `server.properties`, mapeo propiedad→env, packs y `variables.json` |
| Entradas | Configuración deseada, packs subidos, cambios de propiedad |
| Salidas | Config deseada persistida y validada, catálogo de packs |
| Eventos publicados | `CONFIG.CHANGED`, `PACK.INSTALLED`, `PACK.REMOVED` |
| Eventos consumidos | `WORLD.ACTIVATED` (cambio de level-name) |
| Dependencias permitidas | kernel, SettingsPort, ServerStoragePort (aplicación de cambios vía evento `CONFIG.CHANGED`; no depende de Server) |
| Expone | Facade pública (applyProperties, installPack, removePack) |

### 3.8 Console

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Enviar comandos al stdin y difundir la salida sin interpretar negocio |
| Entradas | Comandos (con prioridad), suscripciones de salida |
| Salidas | Líneas de stdout/stderr, buffer de logs, acuses de envío |
| Eventos publicados | `CONSOLE.COMMAND_SENT`, `CONSOLE.OUTPUT`, `WORLD.SAVED` (detección declarativa de guardado) |
| Eventos consumidos | `TASK.STARTED` (comandos programados) |
| Dependencias permitidas | kernel, SettingsPort, ServerRuntimePort, Server facade (identidad/estado) |
| Notas | El parseo de líneas lo ejecutan consumidores (parsers declarativos en `infrastructure/parsers`); Console no decide semántica |

### 3.9 Scheduler

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Programación, ejecución y reintentos de tareas |
| Entradas | Programaciones (cron), eventos de fallo |
| Salidas | Tareas ejecutadas/reintentadas, estados de tarea |
| Eventos publicados | `TASK.SCHEDULED`, `TASK.STARTED`, `TASK.COMPLETED`, `TASK.FAILED`, `TASK.CANCELLED` |
| Eventos consumidos | `BACKUP.FAILED`, `TASK.FAILED` (reintentos), `SERVER.CRASHED` (política de reinicio) |
| Dependencias permitidas | kernel, SettingsPort, TimeProviderPort, facades Server/Backup/Console (como ejecutores) |

### 3.10 Monitoring

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Estado, métricas, muestras temporales y latencia; solo observa |
| Entradas | Pings RakNet, stats del runtime, stats de storage, eventos de ciclo de vida |
| Salidas | Muestras en `MetricSample`, estado en vivo, series temporales |
| Eventos publicados | `UPDATE.AVAILABLE`, `SYSTEM.HEALTH_DEGRADED` |
| Eventos consumidos | `SERVER.STARTING/STARTED/STOPPED/CRASHED`, `PLAYER.JOINED/LEFT` |
| Dependencias permitidas | kernel, SettingsPort, ServerRuntimePort, ServerStoragePort, StatusProbePort |

### 3.11 Template

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Captura/reproducción de config + mundo + packs como plantillas versionadas |
| Entradas | Servidores fuente, archivos `.mctemplate`/`.mcworld`, presets de config |
| Salidas | Plantillas persistidas, artefactos exportados |
| Eventos publicados | — (excepción documentada: operaciones de plantilla son síncronas request/response; el resultado se devuelve por HTTP y se audita. Notification no difunde resultados de plantilla; si en el futuro se requieren, se añadirá un evento `TEMPLATE.*` vía ADR) |
| Eventos consumidos | — |
| Dependencias permitidas | kernel, SettingsPort, ServerStoragePort |

### 3.12 Notification

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Difusión de eventos al frontend (WebSocket), persistencia del stream de salida |
| Entradas | Eventos del bus, conexiones WebSocket autenticadas |
| Salidas | Mensajes WS con `{event, server_id?, scope, payload, ts, seq}` |
| Eventos publicados | — (terminal) |
| Eventos consumidos | Todos los eventos con alcance frontend |
| Dependencias permitidas | kernel, SettingsPort, EventBusPort |

### 3.13 Settings

| Aspecto | Especificación |
|---|---|
| Responsabilidad única | Configuración global (defaults, almacenamiento, límites, timezone) |
| Entradas | Cambios de ajustes (solo admin) |
| Salidas | Lectura de ajustes (port), notificación de cambio |
| Eventos publicados | — (Settings no publica eventos de dominio; los cambios se auditan vía IAM) |
| Eventos consumidos | — |
| Dependencias permitidas | kernel |
| Implementa | `SettingsPort` |

---

## 4. Contratos internos

Contratos **funcionales** (no interfaces en código). Cada contrato define un conjunto de
operaciones y garantías semánticas.

### 4.1 Contrato `ServerRuntimePort` (dominios Server/Console ↔ adaptadores runtime)

**Semántica**: representa un proceso de servidor definido por un `RuntimeSpec`.

`RuntimeSpec` contiene (datos): imagen y tag, `VERSION`, variables de entorno,
mapeo de puertos, volúmenes/montajes, recursos (CPU/RAM), red, usuario/UID/GID,
etiquetas, healthcheck, `stdin_open`/`tty`.

**Operaciones**:

| Operación | Garantía funcional |
|---|---|
| `materialize(spec)` | Crea el artefacto de runtime (contenedor) sin arrancarlo. Devuelve identificador interno. |
| `start(id)` | Arranca el proceso. No espera a que el juego responda (eso lo hace Monitoring). |
| `stop(id, grace)` | Envía señal de parada ordenada (la imagen gestiona `stop` vía entrypoint-demoter). Espera salida dentro de `grace`; si no, fuerza. |
| `restart(id, grace)` | Parada ordenada + arranque. |
| `remove(id, deleteData)` | Elimina el artefacto. `deleteData=false` conserva el storage. |
| `getState(id)` | Estado normalizado: `running/stopped/starting/stopping/dying/created/absent`. |
| `getHealth(id)` | Estado de salud del runtime + último cambio de estado. |
| `getResources(id)` | CPU/RAM actuales. |
| `getExitCode(id)` | Código de salida del último proceso. |
| `streamLogs(id)` | Secuencia de líneas stdout/stderr (cola + streaming). |
| `sendStdin(id, data)` | Escribe en el stdin del proceso (ordenado, con bloqueo por instancia). |
| `waitFor(condition)` | Esperar condición (p. ej. puerto respondiendo, proceso vivo). |
| `signal(id, sig)` | Señal explícita (SIGTERM/SIGKILL) para casos gestionados. |

**Garantías**: las operaciones son idempotentes para paradas/remociones; errores de bajo
nivel se normalizan (sección 11); los eventos del runtime se traducen a eventos de
dominio antes de entrar al bus (`CONTAINER_*` → `SERVER_*`).

> **Nota — dos niveles de estado (revisión de arquitectura, hallazgo M1)**: `getState` expone
> el **`RuntimeState`** (nivel infraestructura, refleja el artefacto/proceso):
> `running/stopped/starting/stopping/dying/created/absent`. El dominio **Server** mantiene su
> propio **`ServerState`** (§16.3): `created/starting/running/stopping/stopped/crashed/removed`.
> El mapeo ocurre en el adaptador + dominio Server, **antes** de publicar al bus (TDD §6.2):
>
> | `RuntimeState` | `ServerState` |
> |---|---|
> | `created` | `created` |
> | `starting` | `starting` |
> | `running` | `running` |
> | `stopping`, `dying` | `stopping` |
> | `stopped` | `stopped` |
> | `absent` | `removed` |
> | — | `crashed` (derivado: salida sin `stop` ordenado; evento de runtime `die`) |
>
> El dominio jamás ve `RuntimeState` en crudo; los consumidores solo reciben `ServerState`.

### 4.2 Contrato `ServerStoragePort` (dominios Server/World/Configuration/Permission ↔ adaptadores storage)

**Semántica**: representa el árbol `/data` de un servidor.

| Operación | Garantía funcional |
|---|---|
| `path()` | Ruta raíz lógica del storage. |
| `exists(rel)`, `read(rel)`, `write(rel, bytes)`, `remove(rel)` | Acceso de ficheros con validación de ruta (no se sale de la raíz). |
| `listWorlds()` | Enumera `worlds/*` con tamaño y estructura mínima. |
| `worldSnapshot(worldName)` | Abre un stream de lectura del árbol de un mundo. |
| `writeSnapshot(rel, stream)` | Escribe un árbol/archivo desde stream (para restauración). |
| `diskStats()` | Uso/espacio del directorio de datos. |
| `lock(scope)` / `unlock(scope)` | Exclusión mutua por operación (backup, restore) — prevención de corrupción. |

**Garantías**: las rutas siempre son relativas y validadas (no path traversal); los
snapshots son streams (no cargan todo en memoria); las operaciones destructivas exigen
lock o servidor detenido.

### 4.3 Contrato `BackupStorePort` (Backup ↔ adaptadores de almacenamiento)

| Operación | Garantía funcional |
|---|---|
| `put(ref, stream)` | Almacena el artefacto bajo referencia estable. |
| `get(ref)` | Abre stream de lectura. |
| `delete(ref)` | Elimina el artefacto. |
| `exists(ref)` | Comprueba presencia. |
| `list(location)` | Lista artefactos (para prune). |
| `verify(ref, expectedChecksum)` | Recalcula checksum del artefacto. |

**Garantías**: `ref` es opaco para el dominio (BBDD guarda la referencia); el adaptador
resuelve dónde (disco local, S3 futuro); `put`/`get` son streams.

### 4.4 Contrato `StatusProbePort` (Monitoring ↔ ping RakNet)

| Operación | Garantía funcional |
|---|---|
| `probe(host, port, timeout)` | Devuelve `online, motd, version, protocol_version, players_online, players_max, latency_ms` o `offline`. |

**Garantías**: nunca bloquea el hilo principal (timeout estricto, no bloqueante); los
resultados no son cached (el cache es responsabilidad de Monitoring).

### 4.5 Contrato `AccessControlPort` (toda Presentación ↔ IAM)

| Operación | Garantía funcional |
|---|---|
| `authenticate(credentials)` | Devuelve identidad + tokens o rechaza. |
| `authorize(identity, action, resource)` | Decisión booleana + motivo, evaluando roles globales y membresías por servidor. |
| `subject(identity)` | Resuelve el actor para auditoría. |

**Garantías**: las decisiones se toman en un solo punto; ningún módulo implementa su
propia comprobación; todas las decisiones se auditan si la acción es sensible.

### 4.6 Contrato `EventBusPort` (todos ↔ bus)

| Operación | Garantía funcional |
|---|---|
| `publish(event)` | Persiste (outbox) y difunde; entrega al-menos-una con deduplicación por `event_id`. |
| `subscribe(topic, handler)` | Registra consumidor idempotente. |
| `consume()` | Procesa el outbox (publicación durable) y los eventos pendientes. |

**Garantías**: orden parcial por entidad (`server_id`) y secuencia global en la salida;
los eventos publicados dentro de una transacción se escriben en el outbox en la misma
transacción.

### 4.7 Contrato API ↔ Application

- La capa API traduce **requests HTTP/WS validados** (Pydantic) en **comandos de
  aplicación** y devuelve **resultados de aplicación** serializados.
- La API **no contiene reglas de negocio**: solo authn/authz de entrada, validación de
  forma, serialización y mapeo de errores.
- Las transacciones se abren en Application, nunca en la API.
- Los DTOs de salida no exponen detalles internos del dominio (solo el contrato público).

### 4.8 Contrato Application ↔ Domain

- Application invoca **servicios de dominio / métodos de agregado** y coordina puertos.
- El dominio **no sabe que existe una API**: levanta errores de dominio tipados.
- Los eventos de dominio se recogen tras una operación y se publican por el bus
  (a través del outbox), dentro del mismo borde transaccional.
- Application traduce comandos externos a invariantes de dominio y viceversa.

### 4.9 Contrato Infrastructure ↔ Runtime (Docker)

- El adaptador Docker implementa `ServerRuntimePort` **íntegramente**.
- Traduce los errores del SDK Docker a los tipos de infraestructura normalizados
  (sección 11): imagen no encontrada, puerto en uso, OOM, contenedor inexistente, etc.
- Traduce eventos del runtime (die, start, health) a eventos de dominio.
- **Es el único lugar del sistema que importa la librería Docker.**
- Para comandos de consola usa el mecanismo `send-command` de la imagen vía
  `docker exec`, con bloqueo por instancia.

### 4.10 Contratos que NO existen (aclaración contra acoplamientos implícitos)

- **"Runtime ↔ World"** NO existe como contrato: World usa `ServerStoragePort` y la
  facade de Server para activar/crear mundos.
- **"Runtime ↔ Backup"** NO existe como contrato: Backup usa `ServerStoragePort`
  (snapshot), `Console` facade (`save hold/resume`) y `Server` facade (stop/start).
  La comunicación con el runtime es siempre indirecta, preservando la abstracción.

---

## 5. Flujo de datos

### 5.1 Flujo de mando (Frontend → Minecraft)

```
Browser (SPA)
  │  HTTPS  (JSON, validado por Pydantic)
  ▼
API (router del módulo)
  │  AuthN (token) → AuthZ (AccessControlPort: ¿actor puede acción sobre recurso?)
  │  Validación de forma → construye Command
  ▼
Application (use case del módulo)
  │  Abre transacción · invoca servicios de dominio · recoge eventos
  ▼
Domain (agregado/políticas)
  │  Valida invariantes · muta estado · emite eventos de dominio → outbox
  ▼
Port (ServerRuntimePort / ServerStoragePort / facades)
  │
  ▼
Infrastructure (adaptador: Docker SDK / LocalStorage / console exec)
  │
  ▼
Docker Runtime → contenedor itzg/minecraft-bedrock-server
  │  env → set-property → server.properties (arranque)
  │  stdin → bedrock_server (comandos de consola)
  ▼
Minecraft Bedrock Server
```

### 5.2 Flujo de retorno (Minecraft → Frontend)

```
Minecraft Bedrock Server
  │  stdout/stderr (logs, respuestas de comandos, eventos del juego)
  ▼
Docker Runtime (docker logs / attach)
  ▼
Adaptador runtime (streaming, normaliza)  →  Console
  │  buffer en memoria + emisión CONSOLE.OUTPUT
  ▼
Parser pipeline (infrastructure/parsers, declarativo)
  │  detecta join/leave/guardado/errores
  ▼
Eventos de dominio (PLAYER.JOINED, WORLD.SAVED, …) → EventBus (outbox)
  ▼
Consumidores (Player, Monitoring, Backup, Permission, …)
  ▼
Notification (WebSocket gateway) → {event, server_id?, scope, payload, ts, seq}
  ▼
Browser (WSS)
```

### 5.3 Flujo de estado (ping RakNet, independiente del runtime)

```
Monitoring (poller escalonado) → StatusProbePort → RakNet UDP 19132
   → online/motd/version/players/latency
   → MetricSample (Postgres) + snapshot por WS (5 s)
```

### 5.4 Flujo de configuración (BBDD → server.properties)

```
Configuration (config deseada en ConfigProfile)  →  validación contra esquema
  → SERVER.CONFIG_CHANGED / CONFIG.CHANGED
  → Server: render RuntimeSpec (env = mapeo propiedades→env) 
  → recrear contenedor (parar → materialize con nuevo env → arrancar)
  → imagen: set-property --bulk → server.properties (solo en arranque)
```

### 5.5 Reglas transversales del flujo

- Todo request HTTP lleva `request_id`; todo evento lleva `event_id`; el id se propaga a
  logs e infraestructura (correlación, §12/§13).
- Las operaciones destructivas son **transaccionales**: persistir estado → publicar
  evento → efecto observable.
- Nunca hay escritura directa al runtime desde el frontend ni desde un módulo que no sea
  el propietario del puerto.

---

## 6. Ciclo de vida del servidor

### 6.1 Creación

| Paso | Módulo | Acción |
|---|---|---|
| 1 | Settings | Lee defaults (imagen, tag, timezone, storage default, pool de puertos) |
| 2 | IAM | Verifica permiso `server.create`; registra al creador como admin del servidor (membresía) |
| 3 | Template (opcional) | Aplica plantilla (config + mundo + packs) si se indicó |
| 4 | Configuration | Prepara la config deseada (properties → env) |
| 5 | Server | Asigna puertos (pool), genera `RuntimeSpec` (env, UID/GID, storage path, recursos), persiste `Server` |
| 6 | Infrastructure | `ServerRuntimePort.materialize(spec)` (crea contenedor, NO arranca) |
| 7 | Server | Persiste estado `created`; publica `SERVER.CREATED` |
| 8 | Notification | UI actualiza |

> **Nota — multi-instancia (revisión de arquitectura, hallazgo B7)**: al generar el `RuntimeSpec`,
> el panel fija `ENABLE_LAN_VISIBILITY=false` salvo que el servidor sea el único del host o se
> gestionen explícitamente los puertos por defecto. Sin esto, BDS hace bind a 19132/19133
> (descubrimiento LAN) aunque los puertos se cambien, provocando conflictos (análisis §3.5 y §9).

### 6.2 Inicio

| Paso | Módulo | Acción |
|---|---|---|
| 1 | IAM | `server.start` sobre el servidor |
| 2 | Server | `ServerRuntimePort.start(id)`; estado → `starting`; publica `SERVER.STARTING` |
| 3 | Infrastructure | Arranca contenedor; la imagen descarga/valida BDS y arranca el juego |
| 4 | Monitoring | `StatusProbePort` sondea hasta online (con timeout) |
| 5 | Server | Estado → `running`; publica `SERVER.STARTED` |
| 6 | Consumidores | Monitoring inicia métricas/uptime; Player limpia presencia; Scheduler agenda |

### 6.3 Parada

| Paso | Módulo | Acción |
|---|---|---|
| 1 | IAM | `server.stop` |
| 2 | Server | `ServerRuntimePort.stop(id, grace)`; estado → `stopping`; publica `SERVER.STOPPING` (y `STOP_SERVER_ANNOUNCE_DELAY` si está configurado) |
| 3 | Infrastructure | Señal SIGTERM → entrypoint-demoter escribe `stop` en stdin → BDS guarda y cierra |
| 4 | Server | Espera salida; estado → `stopped`; publica `SERVER.STOPPED` |
| 5 | Consumidores | Monitoring detiene métricas; Backup habilita backups en frío |

### 6.4 Reinicio

`stop` (pasos 6.3) → `start` (pasos 6.2), serializados como una **operación única** con
estado `restarting` durante todo el proceso. Un segundo reinicio durante el primero se
rechaza (bloqueo por servidor, §4.9/§11).

### 6.5 Actualización de versión

| Paso | Módulo | Acción |
|---|---|---|
| 0 | Monitoring | Detecta `UPDATE.AVAILABLE` (consulta fuentes de versiones) y notifica |
| 1 | User | Selecciona versión nueva (o mantiene `LATEST`) |
| 2 | Backup | Backup `pre-upgrade` (protegido de retención) |
| 3 | Server | `SERVER.VERSION_CHANGED`; `RuntimeSpec.VERSION` = nueva |
| 4 | Server | Recrea contenedor (parar → materialize con nuevo env → arrancar) |
| 5 | Infrastructure | La imagen descarga e instala la nueva versión en el arranque |
| 6 | Consumidores | World registra versión de formato; Backup nota; Notification avisa |

### 6.6 Eliminación

| Paso | Módulo | Acción |
|---|---|---|
| 1 | IAM | `server.delete` (confirmación explícita) |
| 2 | Server | Si está corriendo: stop ordenado (6.3) |
| 3 | Backup | Decide retención de backups (conservar como huérfanos o purgar según política) |
| 4 | Server | Soft delete en BBDD; `ServerRuntimePort.remove(id, deleteData?)` |
| 5 | Server | Publica `SERVER.REMOVED` |
| 6 | Consumidores | Backup/Notification limpian dependencias lógicas |

---

## 7. Ciclo de vida de un mundo

### 7.1 Importar

| Paso | Módulo | Acción |
|---|---|---|
| 1 | API | Recibe archive `.mcworld`/`.zip`/`.mctemplate` (validación de tamaño/tipo) |
| 2 | World | Valida contenido: `level.dat` NBT válido, `db/` presente, **protección zip-slip**, sanitización de nombre |
| 3 | World | Extrae a `worlds/<nombre-sanitizado>/` vía `ServerStoragePort` |
| 4 | World | Persiste metadata (semilla, versión, tamaño, origen); estado `inactive` |
| 5 | World | Publica `WORLD.IMPORTED` |

### 7.2 Activar

| Paso | Módulo | Acción |
|---|---|---|
| 1 | World | Marca nuevo mundo `active` y el anterior `inactive` (constraint único por servidor) |
| 2 | Configuration | Cambia `level-name` en la config deseada |
| 3 | Server | Aplica cambio (recrear contenedor, §6.5 sin cambio de versión) |
| 4 | World | Publica `WORLD.ACTIVATED` |

### 7.3 Guardar

- BDS guarda automáticamente (autosave) y ante `save hold`/`save resume`.
- Console detecta la línea de guardado y publica `WORLD.SAVED` (sin interpretar nada más).
- Backup usa `WORLD.SAVED` como señal de ventana segura; Monitoring lo usa para salud.

### 7.4 Respaldar

Ver §8 (Backup). Para un mundo concreto: Backup acota el snapshot a
`worlds/<nombre>/` y registra `world_id` en el `Backup`.

### 7.5 Restaurar

Ver §8. La restauración siempre termina con verificación de `level.dat` y arranque
controlado; si falla, rollback al snapshot `pre-restore`.

### 7.6 Exportar

| Paso | Módulo | Acción |
|---|---|---|
| 1 | World | Si el servidor está online: `save hold` (vía Console facade) → snapshot → `save resume` (siempre) |
| 2 | World | Stream del mundo → empaquetado `.mcworld` (zip) vía `ServerStoragePort` |
| 3 | World | Publica `WORLD.EXPORTED`; el archivo se sirve como descarga |

### 7.7 Eliminar

| Paso | Módulo | Acción |
|---|---|---|
| 1 | IAM | `world.delete` (confirmación) |
| 2 | Server | Si el mundo es el activo: se **impide** eliminar (o se exige activar otro antes) |
| 3 | World | Soft delete (papelera con TTL) → purge real tras expirar |
| 4 | World | Publica `WORLD.DELETED` (Backup marca huérfanos) |

---

## 8. Ciclo de vida de un backup

### 8.1 Creación

| Paso | Módulo | Acción |
|---|---|---|
| 1 | Trigger | Manual (API), programado (`TASK.STARTED` → Backup), `pre-upgrade`, `pre-restore` |
| 2 | Backup | Verifica precondiciones: estado del servidor, storage disponible, sin operación en curso (lock) |
| 3 | Backup | Inserta `Backup` en estado `running` (outbox: eventos de creación) |
| 4 | Backup | **En caliente**: `save hold` (Console) → espera confirmación (timeout) → `save resume` **siempre** (finally). **En frío**: salta este paso |
| 5 | Backup | Snapshot vía `ServerStoragePort` (stream) → compresión (tar+zstd) |
| 6 | Backup | SHA-256 calculado durante el streaming |
| 7 | Backup | `BackupStorePort.put(ref, stream)` |
| 8 | Backup | Actualiza registro (tamaño, checksum, entradas, duración, storage_ref, estado `completed`) |
| 9 | Backup | Publica `BACKUP.COMPLETED` |

### 8.2 Validación

- **Post-creación**: `BACKUP.VALIDATED` si el checksum coincide y el manifiesto lista
  `level.dat` + `db/`. Si falla: estado `corrupt`, no se prune automáticamente, se notifica.
- **Pre-restauración**: verificar checksum + leer manifiesto **antes** de tocar el mundo.

### 8.3 Checksum

- SHA-256 **calculado durante el streaming** (no una segunda pasada).
- Almacenado en el registro y en el manifiesto del archivo.

### 8.4 Compresión

- `tar` + `zstd` (multithread). El manifiesto (JSON de metadatos) va **al inicio** del
  archivo para que el backup sea autodescriptible fuera del panel.

### 8.5 Almacenamiento

- `BackupStorePort` (local en MVP, S3 en Fase 2). `storage_ref` opaco en BBDD.
- Cuota por servidor con alerta (`SYSTEM.HEALTH_DEGRADED` si se supera umbral).

### 8.6 Restauración

| Paso | Módulo | Acción |
|---|---|---|
| 1 | IAM | `backup.restore` (confirmación) |
| 2 | Backup | Publica `BACKUP.RESTORE_STARTED` |
| 3 | Server | Detiene el servidor (facade) y espera `SERVER.STOPPED` |
| 4 | Backup | Verifica integridad (checksum + manifiesto) |
| 5 | Backup | Snapshot `pre-restore` del mundo actual (protegido) |
| 6 | Backup | Extrae a **directorio de staging** (no sobre el destino) |
| 7 | Backup | Verifica `level.dat` del staging → **swap** atómico sobre `worlds/<nombre>/` |
| 8 | Backup | Publica `BACKUP.RESTORE_COMPLETED` |
| 9 | Server | Arranca el servidor |
| 10 | Fallo | Rollback al `pre-restore`, servidor queda detenido y estado claro; `BACKUP.RESTORE_FAILED` |

### 8.7 Limpieza (retención/prune)

1. Scheduler lanza tarea de prune periódica (o tras cada `BACKUP.COMPLETED`).
2. Backup evalúa políticas: keep-last-N, tiers temporales (diario/semanal/mensual),
   antigüedad; respeta `protected` (pre-upgrade/pre-restore).
3. Marca obsoletos → `BackupStorePort.delete(ref)` → estado `deleted` → `BACKUP.DELETED`.

---

## 9. Catálogo de eventos

> Catálogo canónico (idéntico al TDD §7.2). Publica = módulo que emite; Consume =
> módulos consumidores; Objetivo = efecto deseado.

### 9.1 Servidor / runtime

| Evento | Publica | Consume | Cuándo | Objetivo |
|---|---|---|---|---|
| `SERVER.CREATED` | Server | Notification, Monitoring | Instancia persistida y materializada | UI, empezar a observar |
| `SERVER.CONFIG_CHANGED` | Server | Server, Notification | Config/env cambiada en BBDD | Recrear contenedor |
| `SERVER.STARTING` | Server | Monitoring, Notification | Runtime arranca | UI "starting", watchdog |
| `SERVER.STARTED` | Server | Monitoring, Player, Scheduler, Notification | El ping responde | métricas, uptime, online |
| `SERVER.STOPPING` | Server | Monitoring, Notification | Comienza apagado ordenado | aviso |
| `SERVER.STOPPED` | Server | Monitoring, Backup, Scheduler, Notification | Proceso terminó limpio | detener métricas, backup en frío |
| `SERVER.CRASHED` | Server | Monitoring, Scheduler, Notification, IAM | Muere sin stop ordenado | alertar, política de reinicio, auditoría |
| `SERVER.REMOVED` | Server | Backup, Notification | Instancia eliminada | limpiar dependencias |
| `SERVER.VERSION_CHANGED` | Server | World, Backup, Notification | Versión aplicada | formato de mundo, sugerir backup |
| `UPDATE.AVAILABLE` | Monitoring | Server, Notification | Hay versión más reciente | avisar actualización |

### 9.2 Jugador

| Evento | Publica | Consume | Cuándo | Objetivo |
|---|---|---|---|---|
| `PLAYER.JOINED` | Console (parser) | Player, Monitoring, Permission, Notification | Línea de join parseada | contador, historial, XUID auto |
| `PLAYER.LEFT` | Console (parser) | Player, Monitoring, Notification | Línea de leave/timed out | contador, playtime |
| `PLAYER.BANNED` | Player | Player, Notification | Ban aplicado | estado del ban |
| `PLAYER.OPERATOR_CHANGED` | Permission | Player, Permission | op/deop o fichero modificado | consistencia permisos |

### 9.3 Mundo

| Evento | Publica | Consume | Cuándo | Objetivo |
|---|---|---|---|---|
| `WORLD.CREATED` | World | Backup, Notification | Mundo generado/importado | sugerir backup inicial |
| `WORLD.IMPORTED` | World | Notification | Importación válida | UI |
| `WORLD.EXPORTED` | World | Notification | Exportación completada | registro |
| `WORLD.DUPLICATED` | World | Notification | Copia completada | UI |
| `WORLD.DELETED` | World | Backup, Notification | Soft delete | retención huérfanos |
| `WORLD.ACTIVATED` | World | Server, Configuration, Notification | Cambio de mundo activo | recrear con level-name |

### 9.4 Backup

| Evento | Publica | Consume | Cuándo | Objetivo |
|---|---|---|---|---|
| `BACKUP.STARTED` | Backup | Notification | Inicio real del snapshot | progreso UI |
| `BACKUP.PROGRESS` | Backup | Notification | Actualización de progreso | barra de progreso |
| `BACKUP.COMPLETED` | Backup | Notification, Player | Snapshot + checksum OK | UI, desbloquear |
| `BACKUP.FAILED` | Backup | Scheduler, Notification, IAM | Error en backup | alertar, reintento, auditoría |
| `BACKUP.RESTORE_STARTED` | Backup | Server, Notification | Inicio restauración | detener servidor |
| `BACKUP.RESTORE_COMPLETED` | Backup | Server, Notification | Mundo restaurado y verificado | arrancar servidor |
| `BACKUP.RESTORE_FAILED` | Backup | Notification | Falla restauración | alerta, rollback |
| `BACKUP.DELETED` | Backup | Notification | Borrado o prune | UI |
| `BACKUP.VALIDATED` | Backup | Notification | Integridad OK | confianza |

### 9.5 Consola / configuración

| Evento | Publica | Consume | Cuándo | Objetivo |
|---|---|---|---|---|
| `CONSOLE.COMMAND_SENT` | Console | IAM (audit), Notification | Comando enviado al stdin | trazabilidad |
| `CONSOLE.OUTPUT` | Console | parsers, Notification, Monitoring | Línea de salida | logs en vivo, parseo |
| `CONFIG.CHANGED` | Configuration | Server, Notification | Config/packs modificado (deseado) | aplicar (recrear) |
| `PACK.INSTALLED` | Configuration | Configuration, Notification | Pack instalado/activado | UI |
| `PACK.REMOVED` | Configuration | Configuration, Notification | Pack eliminado | UI |
| `WORLD.SAVED` | Console (parser) | Backup, Notification | Línea de guardado detectada | calendario backups, salud |

> **Nota — dos eventos de cambio de configuración (no son redundantes)**:
> - `CONFIG.CHANGED` (publica **Configuration**): cambió la *config deseada* (properties/packs)
>   en BBDD. Server lo consume para re-renderizar el `RuntimeSpec` (mapeo propiedades→env) y recrear.
> - `SERVER.CONFIG_CHANGED` (publica **Server**): cambió el propio `RuntimeSpec` (env, versión,
>   puertos, imagen, recursos). Lo consume el propio Server (auto-recreate) y Notification (UI).
> En la práctica `CONFIG.CHANGED` es el desencadenante normal; `SERVER.CONFIG_CHANGED` se usa
> para cambios que no pasan por Configuration (versión, puertos, recursos).

### 9.6 Scheduler / tareas

| Evento | Publica | Consume | Cuándo | Objetivo |
|---|---|---|---|---|
| `TASK.SCHEDULED` | Scheduler | Notification | Programación creada/actualizada | UI |
| `TASK.STARTED` | Scheduler | Backup, Server, Console, Notification | La tarea comienza | ejecutar dominio |
| `TASK.COMPLETED` | Scheduler | Notification | Tarea OK | UI |
| `TASK.FAILED` | Scheduler | Scheduler (reintentos), IAM (audit), Notification | Tarea falló (sin reintentos) | alertar, reintentar |
| `TASK.CANCELLED` | Scheduler | Notification | Tarea cancelada | UI |

### 9.7 IAM / sistema

| Evento | Publica | Consume | Cuándo | Objetivo |
|---|---|---|---|---|
| `AUTH.LOGIN_SUCCESS` | IAM | IAM (audit), Notification (opcional) | Login OK | auditoría |
| `AUTH.LOGIN_FAILED` | IAM | IAM (audit), Notification | Login fallido | bloqueo por intentos |
| `IAM.USER_CREATED` | IAM | IAM (audit), Notification | Admin crea usuario | auditoría |
| `IAM.USER_ROLE_CHANGED` | IAM | IAM (audit), Notification | Cambio de rol/membresía | auditoría |
| `SYSTEM.HEALTH_DEGRADED` | Monitoring | Notification | Problema global (disco, cuota) | alerta |

### 9.8 Reglas de publicación

- Todo evento lleva `event_id`, `type`, `occurred_at`, `server_id?`, `actor_id?`, `payload`,
  `schema_version`.
- Los eventos que ordenan trabajo se nombran en pasado (hecho) salvo las **órdenes**
  (`TASK.STARTED`) que activan dominios; el resultado se reporta con eventos de resultado.
- Idempotencia obligatoria (§TDD 7.4): consumidor seguro ante reentrega.

---

## 10. Convenciones

### 10.1 Nombres de módulos

- Singular, minúscula, idénticos al TDD: `iam`, `server`, `world`, `backup`, `player`,
  `permission`, `configuration`, `console`, `scheduler`, `monitoring`, `template`,
  `notification`, `settings`.
- Paquete de un módulo: `modules.<nombre>`. Capa: `modules.<nombre>.api|application|
  domain|infrastructure`.

### 10.2 Nombres de servicios / use cases

- Patrón verbo+sustantivo y sufijo `UseCase`: `StartServerUseCase`, `CreateBackupUseCase`.
- Facades públicas de módulo: `<Modulo>Facade` (p. ej. `ServerFacade`, `ConsoleFacade`),
  expuestas solo en la capa application del módulo.

### 10.3 Nombres de eventos

- Formato `CONTEXTO.ACCION` en UPPER_SNAKE_CASE, contexto = nombre del módulo (sección 9).
- Tema de suscripción derivado: el contexto (p. ej. suscripción a `server.*`).

### 10.4 Nombres de DTO / comandos / resultados

- Comandos de aplicación: `<Verbo><Sustantivo>Command` (`RestoreBackupCommand`).
- Resultados: `<Verbo><Sustantivo>Result` (`RestoreBackupResult`).
- Schemas API: `<X>Request` / `<X>Response` (forma HTTP) sobre los anteriores.
- DTOs de eventos: `<Contexto><Accion>Event`.

### 10.5 Nombres de modelos/entidades

- Singular, PascalCase, idénticos a las tablas del TDD §15 (`User`, `Server`, `World`,
  `Backup`, `Player`, `Pack`, `Task`, `Template`, `AuditLog`, …).
- Tablas con prefijo de módulo: `iam_`, `server_`, `world_`, `backup_`, `player_`,
  `perm_`, `cfg_`, `console_`, `task_`, `mon_`, `tpl_`, `audit_`, `setting_`.

### 10.6 Excepciones

- Jerarquía única: raíz `AppError`; ramas `DomainError`, `InfrastructureError`,
  `HttpError`. Cada rama con subtipos (sección 11). Sufijo `Error`.
- Códigos de error: `MODULO.NOMBRE` en UPPER_SNAKE_CASE (`BACKUP.NOT_FOUND`).

### 10.7 Nombres de ficheros y carpetas

- Backend: `modules/<nombre>/<capa>/<uso>.py` (p. ej.
  `modules/backup/domain/backup.py`, `modules/backup/application/create_backup.py`).
- Migraciones: `db/alembic/versions/` con sufijo `<modulo>`.
- Frontend: `src/features/<feature>/` por feature alineada al módulo.
- Test: espejo de la ruta con sufijo `_test.py` (backend) / `*.test.ts(x)` (frontend).

### 10.8 Organización de carpetas

La establecida en el TDD §16 (monorepo `apps/backend`, `apps/frontend`, `packages`,
`docs`, `infra`, `deploy`, `tests`, `.github`). No se introducen carpetas nuevas fuera
de ese árbol sin ADR.

### 10.9 Otras convenciones

- Git: Conventional Commits; PR con descripción vinculada a este blueprint y checklist §16.
- Versionado semántico del producto y `schema_version` en los eventos.
- Config vía env con defaults tipados (kernel config); nada hardcodeado de entorno.
- Las reglas de arquitectura (imports prohibidos) se verifican en CI (import-lint).

---

## 11. Manejo de errores

### 11.1 Taxonomía única

| Clase | Subtipos | Origen | Contiene detalles internos |
|---|---|---|---|
| `DomainError` | `ValidationError`, `InvalidStateError`, `BusinessRuleViolation`, `NotFoundError`, `ConcurrencyConflictError` | Dominio | No |
| `InfrastructureError` | `StorageError`, `PersistenceError`, `RuntimeAdapterError`, `StatusProbeError`, `BackupStoreError` | Adaptadores | No (solo mensaje normalizado + código) |
| `DockerError` (subclase de RuntimeAdapterError) | `ImageNotFoundError`, `PortInUseError`, `ContainerNotFoundError`, `OomKilledError`, `PullFailedError`, `ExecFailedError`, `TimeoutError` | Adaptador Docker | No |
| `ConsoleError` | `ConsoleBusyError`, `ConsoleUnavailableError`, `ServerOfflineError`, `CommandRejectedError`, `StdinWriteError` | Console/adaptador | No |
| `HttpError` | mapeo de las anteriores + `401/403/404/409/422/500` | Presentación | No |
| `UnexpectedError` | catch-all | Cualquier capa | Solo en logs (correlation_id), nunca en respuesta |

### 11.2 Estrategia por capa

- **Dominio**: lanza `DomainError` con `code`, mensaje estable y contexto (server_id).
  No referencia librerías ni runtime.
- **Aplicación**: captura errores de dominio/infra, los traduce según política de
  reintento (idempotencia) y propaga.
- **Infraestructura**: los errores de SDK/sistema se **normalizan** en subtipos
  `InfrastructureError` dentro del adaptador; nunca se propagan excepciones crudas de
  librerías hacia arriba. Los adaptadores marcan `retryable` en errores transitorios.
- **Docker**: el adaptador clasifica (imagen/puerto/OOM/timeout/exec). `OomKilledError`
  además dispara evento `SERVER.CRASHED` con motivo.
- **RCON/consola**: como Bedrock no tiene RCON nativo, los errores de consola son de
  "stdin no disponible" (proceso caído, busy, servidor offline). Se serializan por
  servidor (cola) para evitar escrituras concurrentes.
- **HTTP**: envoltura única con `code`, `message`, `request_id`, `details` (RFC 7807
  Problem Details). 500 genérico ante `UnexpectedError`; los detalles completos solo en logs.
- **Inesperados**: log con stack + correlation_id; respuesta 500 estándar; el evento de
  auditoría captura el hecho si es relevante.

### 11.3 Reglas

- Ninguna excepción de dominio/infra se serializa tal cual al cliente (siempre traducida).
- Errores retryables: reintentos con backoff + jitter (máx. N); operaciones con
  idempotency key.
- Los conflictos de concurrencia (dos operaciones sobre el mismo servidor) son
  `ConcurrencyConflictError` → 409 con recurso y motivo.
- Toda operación destructiva falla **sin efecto parcial**: o completa o revierte.

---

## 12. Política de logging

### 12.1 Qué se registra

- Ciclo de vida de servidor/mundo/backup (transiciones de estado con IDs).
- Comandos de consola **sanitizados** (sin argumentos sensibles).
- Errores normalizados con contexto (`server_id`, `task_id`, `request_id`).
- Operaciones de infraestructura a nivel DEBUG (llamadas a runtime, storage).
- Decisiones de autorización denegadas (motivo + actor).
- Auditoría de acciones sensibles (ver §13).

### 12.2 Qué NUNCA se registra

- Passwords, hashes de passwords, tokens (access/refresh), secretos, `RCON_PASSWORD`,
  claves de cifrado, API keys.
- Contenido íntegro de comandos que puedan contener secretos.
- Datos personales innecesarios: IPs de jugadores se registran **enmascaradas**
  (último octeto) salvo necesidad justificada y auditable.
- Cabeceras HTTP completas (Authorization/Set-Cookie).

### 12.3 Niveles

| Nivel | Uso |
|---|---|
| DEBUG | Detalle de infraestructura, payloads de eventos, operaciones de runtime |
| INFO | Transiciones de estado, operaciones completadas, login exitoso |
| WARN | Degradaciones (backup corrupto, disco alto, reintentos, ping lento) |
| ERROR | Errores operativos (backup fallido, crash, restore fallido, auth fallido) |
| CRITICAL | Fallos del proceso/panel que requieren intervención inmediata |

### 12.4 Formato

- **JSON estructurado**, una línea por entrada.
- Campos: `ts`, `level`, `logger`, `msg`, `module`, `request_id`, `correlation_id`,
  `server_id`, `user_id`, `task_id`, `event`, `duration_ms`, `code`, `stack?`.

### 12.5 Contexto y correlación

- `request_id` por request HTTP; `connection_id` por WebSocket; `task_id` por tarea
  programada; `server_id`/`user_id` siempre que apliquen.
- El `correlation_id` se propaga a llamadas de infraestructura y a los logs del adaptador,
  y se incluye en las respuestas de error HTTP (trazabilidad para el usuario).

---

## 13. Observabilidad

### 13.1 Health checks

- **Liveness**: el proceso responde (endpoint de liveness).
- **Readiness**: DB, Redis (si activo), conectividad con el runtime y el bus.
- **Por servidor**: health del runtime + ping RakNet (estado del juego), expuesto en el
  estado de `Server` y en Monitoring.

### 13.2 Métricas

- Almacenadas en `MetricSample` (Postgres) por defecto — decisión del TDD §11.3.
  Prometheus es opción futura, **no se añade ahora** (respetar TDD).
- Muestras: CPU, RAM, disco, jugadores online/max, latencia, estado, por servidor y por
  intervalo configurable (default 5 s).
- Métricas del propio panel: latencia de operaciones de runtime, duración de backups,
  eventos publicados/consumidos, tasa de errores (desde logs).

### 13.3 Eventos

- `EventLog`: registro inmutable de eventos publicados (trazabilidad y resume WS).
- `EventOutbox`: cola durable de publicación (patrón outbox).

### 13.4 Auditoría

- `AuditLog` append-only con **encadenado de hash** (tamper-evidence): cada registro
  contiene `prev_hash`; alterar uno rompe la cadena.
- Registra: actor, acción (`server.start`, `backup.restore`, `world.delete`, …), recurso,
  resultado, IP, user-agent, timestamp, `correlation_id`.
- Las acciones destructivas y los cambios de IAM **siempre** se auditan.

### 13.5 Tracing

- Correlación por `request_id`/`connection_id`/`task_id` (punto 12.5).
- No se añade OpenTelemetry/distributed tracing en esta fase (fuera del TDD); la
  estructura de correlación ya lo habilita como extensión futura sin cambios (§15).

---

## 14. Estrategia de testing

### 14.1 Pirámide

| Nivel | Contenido | Dónde corre |
|---|---|---|
| **Unit** | Lógica de dominio (invariantes, validaciones, máquinas de estado), use cases con puertos *fake* | CI (rápido) |
| **Integration** | Repositorios contra Postgres real (test DB), bus real, adaptadores contra **Docker real** | CI (tagged `integration`) |
| **Contract** | Suite única por puerto técnico ejecutada contra cada adaptador (garantiza intercambiabilidad runtime/storage/store) | CI `integration` |
| **e2e** | Crear contenedor real, ejecutar ciclo completo con imagen real de BDS | CI **manual/opt-in** (descarga de BDS es pesada) |

### 14.2 Qué debe probarse por módulo

| Módulo | Foco de pruebas |
|---|---|
| Server | Máquina de estados, render de RuntimeSpec desde config, errores de ciclo de vida |
| Console | Orden/colas de comandos, buffer, serialización, detección de "console unavailable" |
| Monitoring | Probe RakNet (contra fake + real), reconciliación de contadores, persistencia de muestras |
| Backup | Flujo completo `save hold/resume` (real si es posible), checksum, retención, restore con rollback |
| World | Validación de `level.dat`, zip-slip, sanitización de nombres, activación |
| IAM | Tokens, expiración, RBAC+ACL matrix, auditoría (cadena de hash) |
| Scheduler | Cron (reloj inyectable), reintentos, bloqueo de concurrencia |
| Parsers | Detección de join/leave/guardado/errores con corpus de logs reales de BDS |

### 14.3 Qué NUNCA debe mockearse

- Los **puertos técnicos** cuando se prueban adaptadores: el adaptador Docker se prueba
  contra Docker real (integration), no con un mock del SDK.
- SQLAlchemy/Postgres: usar test DB real, no mocks del ORM.
- El **bus de eventos**: probar el bus real (in-process + outbox), no stubs.
- El **reloj** en Scheduler: se inyecta un `TimeProviderPort` fake (esto es un fake del
  puerto, permitido), no se mockea el tiempo global.
- El parseo de logs: con corpus reales, no con líneas inventadas en el test.
- El `StatusProbePort` en unit de dominio puede ser un fake (puerto); en integration se
  prueba contra un servidor RakNet real o un fake de protocolo dedicado.

### 14.4 Reglas

- Un use case se prueba aislado con **fakes que implementan el puerto** (permitidos),
  no con mocks que verifiquen llamadas de librerías.
- Cada PR debe pasar: lint + import-lint (reglas de arquitectura) + unit + integration.
- Fixtures por módulo; mundos de prueba pequeños generados para validación.

---

## 15. Extensibilidad

### 15.1 Añadir Podman

- Nuevo adaptador en `infrastructure/runtime/podman.py` implementando `ServerRuntimePort`
  (API compatible con Docker). Registro por DI. Cero cambios de dominio.

### 15.2 Añadir Kubernetes

- Adaptador `infrastructure/runtime/k8s.py` + `ServerStoragePort` sobre PVC.
- `RuntimeSpec` se traduce a Pod/Deployment/Service/PVC.
- Implica el modelo de nodos (Fase 3 del TDD); el dominio Server no cambia.

### 15.3 Múltiples servidores / multi-nodo

- Ya es primer nivel: `server_id` en todos los registros, pool de puertos, membresías.
- Multi-host: agente ligero o runtime remoto detrás de `ServerRuntimePort`
  (patrón wings de Pterodactyl); storage remoto vía `ServerStoragePort`.

### 15.4 Plugins

- Extension points = **eventos**: los plugins se registran como consumidores del bus.
- Catálogo de extension points documentado; los plugins nunca modifican dominios.

### 15.5 Almacenamiento remoto

- Nuevo adaptador `BackupStorePort` (S3/MinIO/SFTP/NFS). `StorageLocation` ya modela la
  configuración en BBDD.

### 15.6 Proveedores cloud

- Combinación de adaptadores existentes: runtime (gestionado o contenedor) + storage
  (S3/EFS) + backups (S3). Sin cambios de dominio.

### 15.7 Reglas que garantizan extensibilidad

- **Nada de librerías concretas en dominio** (solo puertos).
- **Adaptadores finos**: todo detalle de proveedor vive en infraestructura.
- **Eventos como contrato público**: añadir consumidores nunca toca emisores.
- **Registro por DI**: los nuevos adaptadores se registran en bootstrap, no se editan
  dominios.
- **OpenTelemetry/tracing** (futuro): ya soportado por la estructura de correlación;
  solo se añade el exportador.

---

## 16. Checklist de implementación por módulo

Criterio de aceptación técnico: **un PR que no supere el checklist de su módulo se
rechaza**. Checklist transversal aplica a todos.

### 16.1 Checklist transversal (todos los módulos)

- [ ] No importa el `infrastructure` de otro módulo ni de ningún otro módulo en dominio.
- [ ] No usa Docker SDK / `os` / filesystem / DB fuera de sus adaptadores.
- [ ] Depende de puertos del kernel (Runtime/Storage/Store/Probe/AccessControl/Settings/Bus).
- [ ] Eventos publicados únicamente vía `EventBusPort` (outbox); sin publicación directa.
- [ ] Nombres conforme a la sección 10; excepciones en jerarquía `AppError`.
- [ ] Errores normalizados; nada de librerías crudas hacia la API.
- [ ] Logging estructurado con correlación; sin secretos/PII.
- [ ] Schemas Pydantic en `api`; sin lógica de negocio en la API.
- [ ] Migraciones con prefijo de módulo; sin cambios no versionados.
- [ ] Tests unit + integration (cuando aplique) pasando; import-lint limpio.
- [ ] Auditoría de acciones sensibles registrada.

### 16.2 IAM

- [ ] Solo IAM implementa `AccessControlPort`; ninguna otra comprobación de authz.
- [ ] Passwords argon2id; tokens con expiración corta + refresh revocable.
- [ ] Matriz RBAC+ACL probada (tabla de casos: rol × acción × membresía).
- [ ] Auditoría encadenada con `prev_hash`; verificación de integridad en test.
- [ ] Rate limiting en login (por IP y usuario).
- [ ] `AUTH.*` e `IAM.*` publicados y consumidos correctamente.

### 16.3 Server

- [ ] Estado del servidor = máquina de estados explícita (created/starting/running/
      stopping/stopped/crashed/removed) con transiciones validadas.
- [ ] `RuntimeSpec` se renderiza desde config deseada; env = mapeo de Configuration.
- [ ] No conoce Docker: usa `ServerRuntimePort` (inyectado).
- [ ] Asignación de puertos desde pool con detección de conflicto.
- [ ] Recrear = parar → materialize → arrancar, serializado con lock por servidor.
- [ ] Eventos `SERVER.*` publicados en cada transición.

### 16.4 World

- [ ] Validación de import (level.dat NBT, db/, zip-slip, sanitización) probada.
- [ ] Un solo mundo activo por servidor (constraint) — activar desactiva el anterior.
- [ ] Eliminar el mundo activo bloqueado (o exigir activar otro).
- [ ] Operaciones de fichero vía `ServerStoragePort`; nunca rutas absolutas del host.
- [ ] `WORLD.*` publicados en cada operación.

### 16.5 Backup

- [ ] `save hold` → snapshot → `save resume` **siempre** (finally), con timeout.
- [ ] Checksum SHA-256 en streaming y manifiesto al inicio del archivo.
- [ ] Restauración con staging + swap atómico + snapshot `pre-restore` + rollback.
- [ ] Retención respeta `protected`; prune correcto; backups corruptos no se borran solos.
- [ ] Usa `BackupStorePort` y facades de Console/Server; **nunca** el runtime directo.
- [ ] Backup en frío cuando el servidor está detenido.

### 16.6 Player

- [ ] Presencia reconciliada (ping + eventos), detección de huecos.
- [ ] Playtime por sesión; XUID cacheado; gamertag nunca como identidad única.
- [ ] IPs enmascaradas en logs/persistencia salvo política explícita.

### 16.7 Permission

- [ ] Ficheros `allowlist.json`/`permissions.json` escritos vía storage con formato
      correcto (xuid + name).
- [ ] Cambios en vivo vía Console con reintentos y estado de resultado.
- [ ] Resolución XUID cacheada (Player facade); sin llamadas síncronas en hot path.

### 16.8 Configuration

- [ ] Esquema de propiedades es espejo de `property-definitions.json` (misma fuente de
      verdad: valores permitidos, mappings).
- [ ] Validación antes de persistir; cambios → `CONFIG.CHANGED`; aplicación vía Server.
- [ ] Packs: zip-slip protegido, manifest validado, `world_*_packs.json` correcto.

### 16.9 Console

- [ ] Cola por servidor (sin escrituras concurrentes a stdin); `send-command` vía runtime.
- [ ] Buffer de logs en memoria con límite; streaming idempotente.
- [ ] `CONSOLE.OUTPUT` publicado sin interpretar negocio (los parsers son externos).

### 16.10 Scheduler

- [ ] Reloj inyectable (`TimeProviderPort`); cron evaluado con timezone del servidor.
- [ ] Reintentos con backoff y deduplicación; bloqueo de concurrencia (una ejecución por
      tarea a la vez).
- [ ] `TASK.*` publicados correctamente; órdenes a dominios vía facades.

### 16.11 Monitoring

- [ ] Solo lectura (jamás modifica runtime/storage).
- [ ] Probe con timeout estricto y poller escalonado (sin ráfagas).
- [ ] Muestras en `MetricSample`; reconciliación de jugadores; `UPDATE.AVAILABLE`/
      `SYSTEM.HEALTH_DEGRADED` correctamente publicados.

### 16.12 Template

- [ ] Captura y reproducción completas (config + mundo + packs) verificadas por prueba e2e.
- [ ] Versionado y validación de plantillas.

### 16.13 Notification

- [ ] Mensaje WS `{event, server_id?, scope, payload, ts, seq}` con resume por seq.
- [ ] Autorización por canal (membresía) verificada en cada suscripción.
- [ ] Backpressure y rate limits por cliente; nunca bloquea el bus.
- [ ] Heartbeat/reconnect.

### 16.14 Settings

- [ ] `SettingsPort` implementado; defaults documentados; cambios con auditoría.
- [ ] Ningún módulo lee config global fuera del port.

---

## Apéndice A — Fuentes de verdad

| Pregunta | Fuente |
|---|---|
| Arquitectura y decisiones | `docs/technical-design.md` (TDD) |
| Comportamiento de la imagen | `docs/analisis-proyecto-base.md` |
| Contratos entre módulos | Este documento, §1 y §4 |
| Catálogo de eventos | Este documento, §9 (canónico con TDD §7.2) |
| Nombres y convenciones | Este documento, §10 |
| Criterio de aceptación | Este documento, §16 |

*Este documento es el contrato técnico de implementación. Los agentes de código deben
seguirlo literalmente; cualquier desviación requiere ADR y actualización del TDD y de
este blueprint.*
