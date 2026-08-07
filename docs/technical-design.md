# Technical Design Document — Panel de Administración de Servidores Minecraft Bedrock

> **Título**: Technical Design Document (TDD)
> **Proyecto**: Panel web moderno para administrar servidores Minecraft Bedrock sobre Docker
> **Nombre de trabajo**: *BedrockPanel*
> **Estado**: Borrador v0.1 — Diseño arquitectónico
> **Fecha**: 2026-08-05
> **Audiencia**: Arquitectos, desarrolladores backend/frontend, DevOps, mantenedores
> **Referencias**: `docs/analisis-proyecto-base.md` (análisis completo de `itzg/docker-minecraft-bedrock-server`)

---

## Índice

1. [Documento de control](#1-documento-de-control)
2. [Visión general y filosofía](#2-visión-general-y-filosofía)
3. [Stack tecnológico](#3-stack-tecnológico)
4. [Arquitectura general](#4-arquitectura-general)
5. [Dominios del negocio](#5-dominios-del-negocio)
6. [Abstracción ServerRuntime y ServerStorage](#6-abstracción-serverruntime-y-serverstorage)
7. [Sistema de eventos](#7-sistema-de-eventos)
8. [Diseño de backups](#8-diseño-de-backups)
9. [World Management](#9-world-management)
10. [Administración: allowlist, operadores, config, packs y plantillas](#10-administración)
11. [Monitoreo](#11-monitoreo)
12. [API por dominios](#12-api-por-dominios)
13. [Canal WebSocket en tiempo real](#13-canal-websocket-en-tiempo-real)
14. [Seguridad](#14-seguridad)
15. [Base de datos: modelo conceptual](#15-base-de-datos-modelo-conceptual)
16. [Estructura del repositorio](#16-estructura-del-repositorio)
17. [Roadmap](#17-roadmap)
18. [Análisis crítico](#18-análisis-crítico)
19. [Glosario](#19-glosario)

---

## 1. Documento de control

### 1.1 Propósito

Definir la arquitectura técnica completa de un panel de administración de servidores
Minecraft Bedrock, similar en espíritu a Pterodactyl, pero **especializado
exclusivamente en Bedrock Edition** y construido sobre la imagen oficial
`itzg/minecraft-bedrock-server` como **motor (engine) no modificable**.

### 1.2 Decisiones que este documento NO toma

- Nombres finales de paquetes/modulos en el código.
- Librerías concretas más allá de las ya acordadas en el stack.
- Diseño visual del frontend.
- Contratos de API (se definen en un ADR/OpenAPI posterior).

### 1.3 Supuestos

- La imagen de BDS no se modifica ni se extiende; es el motor.
- El software BDS es descargado por la propia imagen en el arranque (ver doc de análisis).
- El estado del servidor vive en el volumen `/data`; el contenedor es efímero.
- El panel correrá en el mismo host que los servidores (al menos inicialmente).
- Producto Open Source multi-tenant desde el diseño (no desde el MVP).

---

## 2. Visión general y filosofía

### 2.1 Principios rectores

| Principio | Aplicación |
|---|---|
| **Clean Architecture** | Dependencias apuntan hacia dentro: Dominio no conoce Infraestructura ni la web. |
| **SOLID** | Responsabilidad única por módulo, inversión de dependencias vía puertos. |
| **DDD ligero** | *Bounded contexts* bien delimitados, agregados explícitos, lenguaje ubicuo. |
| **Vertical Slices** | Cada funcionalidad vertical (endpoint + use case + regla + persistencia) autocontenida dentro de su módulo. |
| **Dependency Injection** | Composición en el bootstrap; sin singletons ocultos ni dependencias globales. |
| **Event Driven** | Los módulos se comunican por eventos publicados en un bus; desacoplamiento por eventos. |
| **Modular Monolith** | Un solo proceso/despliegue, módulos separados por límites de dominio. Microservicios NO en el roadmap inmediato. |
| **Testability** | Puertos abstractos permiten probar dominios con dobles (fakes) sin Docker real. |

### 2.2 Decisiones arquitectónicas clave (ADRs resumidos)

1. **Monolito modular, no microservicios.** Coste operativo menor, transacciones ACID
   simples, y el patrón de límites de módulos permite extraer servicios después sin
   reescribir dominios. La extracción futura se facilita por los eventos y puertos.
2. **La imagen es un motor no modificado.** La integración se hace por **orquestación**
   (crear/recrear contenedores, `docker exec`, inspección) y por **acceso directo al
   volumen de datos** (`ServerStorage`), nunca parcheando la imagen ni sus scripts.
3. **Separación runtime / storage.** El *ciclo de vida* del proceso (Docker/Podman/nativo)
   y el *estado persistente* (volumen `/data`) son dos abstracciones independientes.
   Esta es la decisión que permite runtime-agnosticismo y backups correctos.
4. **Fuente de verdad de configuración = BBDD.** El panel guarda la config deseada y la
   traduce a variables de entorno al crear/recrear el contenedor. La imagen genera
   `server.properties` en el arranque; el panel nunca compite con ella.
5. **Consola por inyección de stdin.** `send-command` + `docker logs`, porque Bedrock
   no tiene RCON nativo (ver doc de análisis, §7).
6. **Backups consistentes con `save hold`/`save resume`** sobre el mundo, con snapshot
   del almacenamiento (no del contenedor).
7. **Estado en vivo vía ping RakNet UDP** implementado en el backend, no dependiendo
   del healthcheck de Docker.

---

## 3. Stack tecnológico

| Capa | Tecnología | Justificación |
|---|---|---|
| **Backend** | Python 3.13 + FastAPI | Tipado moderno (Pydantic v2), async, ecosistema maduro, websockets nativos. |
| **Validación** | Pydantic v2 | Schemas de entrada/salida y validación de dominio en una sola fuente. |
| **Persistencia** | SQLAlchemy 2 + Alembic | ORM + migraciones; Postgres como motor. |
| **Orquestación** | Docker SDK for Python (`docker`) | Puerto concreto del adaptador `ServerRuntime` (reemplazable). |
| **Planificación** | APScheduler | Tareas en proceso (backups, reinicios, limpiezas). |
| **Tiempo real** | WebSockets (FastAPI/Starlette) | Consola, logs, eventos. |
| **Caché/broker (opcional)** | Redis | Rate limiting distribuido, pub/sub para réplicas, tareas asíncronas. |
| **Frontend** | React + TypeScript + Vite + TailwindCSS + TanStack Query + Zustand | SPA moderna, fetch cacheado, estado ligero. |
| **Proxy** | Nginx o Traefik | TLS, cabeceras de seguridad, proxy de WebSocket. |
| **Infra** | Docker Compose, PostgreSQL, (Redis) | Despliegue reproducible en VPS y doméstico. |

> **Regla**: el backend es el único componente que habla con el runtime (socket Docker).
> El frontend jamás toca Docker, ni el volumen, ni la red interna.

---

## 4. Arquitectura general

### 4.1 Vista de capas

```
┌──────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                          │
│               React · TypeScript · TailwindCSS                │
└───────────────┬───────────────────────────────┬───────────────┘
                │ HTTPS (REST)                  │ WSS (eventos/consola/logs)
┌───────────────▼───────────────────────────────▼───────────────┐
│                        Presentación                           │
│         API Routers (FastAPI) · Websocket Gateway             │
│         Schemas Pydantic · AuthN/AuthZ de entrada              │
├───────────────────────────────────────────────────────────────┤
│                        Aplicación                             │
│   Use Cases por módulo · Orquestación · Transacciones         │
│   Commands / Queries · Validación de negocio                  │
├───────────────────────────────────────────────────────────────┤
│                        Dominio                                │
│   Agregados · Value Objects · Reglas de negocio               │
│   Puertos (repositorios, runtime, storage, eventos)           │
│   Eventos de dominio · Políticas de dominio                   │
├───────────────────────────────────────────────────────────────┤
│                       Infraestructura                          │
│   Adaptadores: ServerRuntime (Docker), ServerStorage (FS),    │
│   RakNet ping, parsers de logs, Postgres repos, Redis,        │
│   APScheduler, almacenamiento de backups (local/S3)           │
└───────────────────────┬───────────────────────────────────────┘
                        │ Docker SDK / socket Docker (aislado)
┌───────────────────────▼───────────────────────────────────────┐
│                 Docker Runtime                                 │
│   Contenedor itzg/minecraft-bedrock-server (motor)             │
│   Volumen /data (bind mount controlado por el panel)           │
│   → Minecraft Bedrock Dedicated Server                         │
└───────────────────────────────────────────────────────────────┘
```

### 4.2 Responsabilidades por capa

| Capa | Responsabilidades | No es responsable de |
|---|---|---|
| **Presentación** | Recibir/validar requests, autenticar/autorizar, serializar, gestionar WebSockets, mapear errores a HTTP | Reglas de negocio, persistencia, runtime |
| **Aplicación** | Orquestar use cases, transacciones, coordinar módulos, aplicar eventos, gestionar tareas | Lógica de negocio pura, detalles de infraestructura |
| **Dominio** | Entidades, invariantes, value objects, políticas, eventos de dominio, puertos | HTTP, DB, Docker, I/O |
| **Infraestructura** | Adaptadores concretos (Docker, filesystem, Postgres, Redis, raknet, S3) | Reglas de negocio |

### 4.3 Reglas de dependencia

**Permitidas**

- Presentación → Aplicación → Dominio (flujo descendente).
- Aplicación e Infraestructura pueden depender de Dominio.
- Presentación y Aplicación dependen de puertos (interfaces) del Dominio, NO de adaptadores.
- Cada módulo puede usar el *kernel compartido* (IDs, errores, bus de eventos, tipos de dominio).

**Prohibidas**

- Dominio → Aplicación / Presentación / Infraestructura.
- Aplicación → adaptadores concretos (solo vía puertos; la inyección ocurre en bootstrap).
- Dependencias entre módulos de forma directa: se comunican **solo por eventos o
  use cases expuestos de forma explícita** (facade del módulo), nunca importando
  el interior de otro módulo.
- Presentación → Infraestructura directa.
- Frontend → Docker / volumen / runtime.

### 4.4 Reglas de módulos (Monolito Modular)

- Cada módulo es un *bounded context* con su propia carpeta, esquema de DB propio
  (tablas con prefijo), sus propios eventos y su propia API.
- Un módulo puede **publicar** eventos y **suscibirse** a eventos de otros; no accede
  al estado interno de otros módulos.
- Composición por DI en el bootstrap: el conmutador de módulos se registra en un
  catálogo central.
- Los *vertical slices* viven dentro del módulo (API → use case → regla → adaptador).

---

## 5. Dominios del negocio

### 5.1 Catálogo de dominios (bounded contexts)

| # | Dominio | Responsabilidad central | Agregado raíz |
|---|---|---|---|
| 1 | **Identity & Access (IAM)** | Usuarios, roles, permisos, sesiones, auditoría | `User`, `Role` |
| 2 | **Server** | Instancias de servidor: ciclo de vida, imagen, versión, env, estado | `Server` |
| 3 | **World** | Mundos: importar/exportar/duplicar/activar/eliminar, metadatos | `World` |
| 4 | **Backup** | Backups, restauración, retención, validación, almacenamiento | `Backup` |
| 5 | **Player** | Jugadores: presencia, bans, historial, XUID | `Player` |
| 6 | **Permission** | Allowlist, operadores, niveles de permiso (en-juego) | `PermissionSet` |
| 7 | **Configuration** | server.properties, packs, variables, esquema de propiedades | `ConfigProfile` |
| 8 | **Console** | Envío de comandos, captura y parseo de salida | (síncrono) `ConsoleSession` |
| 9 | **Scheduler** | Tareas programadas (backups, reinicios, anuncios) | `TaskSchedule` |
| 10 | **Monitoring** | Estado, métricas, jugadores online, uptime, latencia | `ServerMetrics` |
| 11 | **Template** | Plantillas de servidor/mundo, reutilización | `Template` |
| 12 | **Notification** | Envío a frontend/WebSocket y webhooks (consumidor del bus) | — |
| 13 | **Settings** | Configuración global del panel y de almacenamiento | `Setting` |

### 5.2 Responsabilidades, límites y relaciones

#### IAM (Identity & Access)
- Responsabilidades: registro/login, contraseñas (argon2), JWT + refresh, roles,
  permisos, membresías por servidor, auditoría, API keys.
- Límite: no conoce servidores ni mundos; solo emite autorizaciones (¿puede el actor X
  ejecutar `restart` sobre el server Y?).
- Relaciones: todos los módulos consultan sus decisiones de autorización.

#### Server
- Responsabilidades: modelo de la instancia (imagen, tag, `VERSION`, env, puertos,
  recursos, rutas de volumen), operaciones de ciclo de vida (crear, iniciar, detener,
  reiniciar, eliminar, recrear), traducción config→env, aplicación de plantillas.
- Límite: NO ejecuta directamente; delega en el puerto `ServerRuntime`. NO lee ni
  escribe ficheros del mundo; delega en `ServerStorage`.
- Relaciones: raíz del árbol. Posee `World`, `Backup`, `Player`, `ConfigProfile`.
  Consume eventos `TASK_RUNNING` (reinicios), `BACKUP_RESTORE_COMPLETED` (arrancar).

#### World
- Responsabilidades: ciclo de vida de mundos (importar/exportar/duplicar/eliminar/
  activar), metadatos (semilla, versión, tamaño, última vez), validación de `level.dat`.
- Límite: conoce la carpeta `worlds/<level-name>` dentro del storage; no conoce Docker.
- Relaciones: pertenece a `Server`; los backups referencian mundos; al activar un mundo
  solicita un cambio de configuración al módulo `Server` (evento `WORLD_ACTIVATED`).

#### Backup
- Responsabilidades: crear/restaurar/borrar/prunear backups, retención, validación,
  checksum, compresión, abstracción de almacenamiento (local/S3), consistencia con
  `save hold/resume`.
- Límite: actúa sobre el storage (snapshot de ficheros) y la consola (comandos save);
  no sabe qué runtime está detrás.
- Relaciones: consume `TASK_RUNNING` (schedules), `SERVER_STOPPED` (backups en frío);
  publica `BACKUP_*`. Emite solicitudes a `Console` (`save hold`).

#### Player
- Responsabilidades: seguimiento de jugadores (XUID/gamertag), presencia online
  (fuente: ping + eventos de join/leave parseados), bans, historial de sesiones, XUID lookup cache.
- Límite: identifica jugadores por XUID (no por nombre, que cambia).
- Relaciones: reacciona a `PLAYER_JOINED`/`PLAYER_LEFT` (emitidos por `Console`);
  consultado por `Monitoring` para el contador online; `Permission` lo usa para resolver XUIDs.

#### Permission (en-juego)
- Responsabilidades: `allowlist.json`, `permissions.json`, niveles
  (visitor/member/operator), `default-player-permission-level`, resolución XUID↔gamertag.
- Límite: es la config de permisos del servidor, **distinta** del RBAC del panel (IAM).
- Relaciones: escribe ficheros en storage y/o emite comandos de consola (`op`,
  `allowlist add/reload`, `permission set`). Consume `PLAYER_JOINED` para auto-completar
  XUIDs.

#### Configuration
- Responsabilidades: esquema de `server.properties` (replica de `property-definitions.json`
  de la imagen), mapeo propiedad↔env, packs (behavior/resource), `variables.json`,
  validación de rangos y valores permitidos.
- Límite: solo administra la representación deseada; el `Server` aplica cambios.
- Relaciones: al cambiar, emite `CONFIG_CHANGED`; el `Server` responde recreando.

#### Console
- Responsabilidades: enviar comandos (stdin), capturar/difundir salida (stdout/stderr),
  parsear líneas relevantes (join/leave/backup/errores), buffer de logs en memoria.
- Límite: no interpreta negocio; solo emite líneas y comandos. El **parseo** es
  responsabilidad de una pipeline de eventos (pos-processadores).
- Relaciones: publica `CONSOLE_OUTPUT`, `PLAYER_JOINED`, `PLAYER_LEFT`, `WORLD_SAVED`.
  Consume solicitudes de `Backup` (`save hold`) y `Permission` (`op ...`).

#### Scheduler
- Responsabilidades: cron de tareas (backups, reinicios, comandos, limpieza), estados
  de tarea, reintentos, timezone, bloqueo de concurrencia.
- Límite: solo emite *órdenes*; no ejecuta la lógica de backups ni de reinicios.
- Relaciones: publica `TASK_STARTED`, `TASK_COMPLETED`, `TASK_FAILED`; los módulos
  `Backup`/`Server` se suscriben y ejecutan su dominio.

#### Monitoring
- Responsabilidades: estado (RakNet ping), métricas (CPU/RAM/disco/jugadores/latencia),
  uptime, healthcheck de runtime, muestras de series temporales, lectura de logs.
- Límite: solo observa; jamás modifica. Sus lecturas son de solo lectura.
- Relaciones: reacciona a `SERVER_STARTED`/`SERVER_STOPPED`; consume `PLAYER_*` para
  conciliar el contador; consulta `ServerRuntime` y `ServerStorage`.

#### Template
- Responsabilidades: captura/reproducción de config + mundo + packs como artefacto
  reutilizable; versionado; validación.
- Relaciones: usado por `Server` al crear instancias y por `World` al importar.

#### Notification
- Responsabilidades: gateway WebSocket, difusión de eventos al frontend, webhooks,
  persistencia de eventos de salida.
- Relaciones: consumidor del bus de eventos; no genera lógica de negocio.

#### Settings
- Responsabilidades: configuración global (defaults, ubicaciones de almacenamiento,
  límites del panel, timezone).
- Relaciones: consultado por todos los módulos vía un puerto de configuración.

### 5.3 Mapa de dependencias entre dominios (resumen)

```
IAM ──► (autoriza) ──► Server, World, Backup, Player, Console, Monitoring, Configuration
Server ──► World, Backup, Player, Configuration (pertenencia)
Console ──► (emite) ──► Player, Monitoring, Backup, World
Scheduler ──► Backup, Server, Console
Backup ──► Console (save hold/resume), Server (restore: stop/start)
Notification ◄── (consume todo el bus)
Template ──► Server, World
```

Regla de oro: **no hay ciclos de dependencia directa**; todo acoplamiento cruzado pasa
por el bus de eventos o por una *facade* explícita de use cases.

---

## 6. Abstracción ServerRuntime y ServerStorage

### 6.1 Motivación

La imagen se administra de tres formas distintas:

1. **Ciclo de vida y proceso** (crear, arrancar, logs, comandos, señales, healthcheck).
2. **Estado persistente** (el volumen `/data` y todo su contenido).
3. **Estado del juego** (ping RakNet, que es independiente del runtime).

Hoy 1 y 2 son Docker, pero en el futuro 1 puede ser Podman, systemd nativo o
Kubernetes, y 2 puede ser un bind mount, un volumen o un PVC. Por eso se separan.

### 6.2 ServerRuntime (abstracción del proceso)

**Concepto**: una capacidad que sabe *ejecutar y vigilar un proceso de servidor*
definido por un **RuntimeSpec** (imagen/tag, comando/entrypoint, variables de entorno,
puertos, volúmenes, recursos, etiquetas, red, usuario/UID/GID, healthcheck).

**Operaciones conceptuales del contrato**

- Materializar el runtime a partir de un spec (crear contenedor).
- Arrancar, detener (con espera de *graceful stop* y timeout), reiniciar.
- Eliminar el artefacto de runtime (con o sin borrado de datos).
- Consultar estado (running/stopped/starting/dying), estado de salud, exit code,
  recursos usados, uptime.
- Obtener logs (cola + streaming).
- Enviar entrada al stdin del proceso (comandos de consola).
- Esperar condiciones (puerto UDP respondiendo, proceso vivo, etc.).
- Señalar (SIGTERM/SIGKILL) y gestionar el apagado ordenado.

**Ports/adapters previstos**

| Runtime | Adaptador | Detalles a ocultar |
|---|---|---|
| Docker | `DockerRuntime` (Docker SDK) | Red, nombres de contenedor, bind mounts, labels, `docker exec` para `send-command` |
| Podman | `PodmanRuntime` | API compatible con Docker (socket) — adaptador casi igual |
| Nativo Linux | `NativeRuntime` | systemd/process supervisor, `popen`/pty, señales, `/proc` |
| Kubernetes | `K8sRuntime` | Pod/Deployment, PVC, `kubectl exec`, servicios |

**Normas de diseño**

- El dominio `Server` depende solo del **puerto** (concepto, no código): le ofrece
  `start`, `stop`, `restart`, `remove`, `getState`, `streamLogs`, `sendStdin`, `spec`.
- Los eventos del runtime (`CONTAINER_*`) se **normalizan** a eventos de dominio
  (`SERVER_STARTED`, `SERVER_STOPPED`, `SERVER_CRASHED`) dentro del adaptador, para que
  el resto del sistema no conozca Docker.
- El estado observable que el panel muestra (`server.status`) es **dominio**, derivado
  del runtime + almacenamiento + ping; el estado interno de Docker es un detalle.
- Los identificadores internos del runtime (container id/name) son atributos del
  agregado `Server`, no identidad.

### 6.3 ServerStorage (abstracción del estado persistente)

**Concepto**: una capacidad que representa el árbol `/data` del servidor como un
filesystem lógico independiente de dónde esté físicamente.

**Operaciones conceptuales**

- Conocer la ruta raíz del storage.
- Leer/escribir ficheros de configuración (`server.properties`, `allowlist.json`,
  `permissions.json`, `config/default/variables.json`).
- Enumerar/validar mundos y packs.
- Snapshot de un mundo o del storage completo (para backups).
- Restaurar un snapshot (reemplazar un mundo/archivo).
- Estadísticas de disco (uso/espacio).

**Adaptadores previstos**

| Storage | Adaptador | Cuándo |
|---|---|---|
| Local (bind mount) | `LocalStorage` | **Recomendado**: el backend tiene acceso directo a `/var/lib/panel/instances/<id>/`; backups y edición de ficheros sin entrar al contenedor |
| Volumen (via runtime) | `RuntimeStorage` (`docker cp`/`exec`) | Fallback cuando el panel no monta los directorios (entornos ajenos) |
| Cloud (futuro) | `S3Storage`, `CephFS` | Clúster/k8s |

**Normas de diseño**

- El backend necesita los bind mounts de los servidores **solo si usa `LocalStorage`**.
  Es la decisión recomendada para MVP: el panel gestiona las rutas de datos en el host.
- Nunca se lee/escribe el storage mientras el servidor está en operación **salvo**
  operaciones diseñadas para eso (backups con `save hold`, lectura de config).
- Las operaciones destructivas sobre storage exigen servidor detenido o bloqueo
  explícito (ver §8 y §9).

### 6.4 Cómo se desacopla el sistema de Docker

1. **El dominio no importa librerías de Docker**: solo puertos.
2. **Bootstrap registra adaptadores**: `ServerRuntime=DockerRuntime`,
   `ServerStorage=LocalStorage`. Cambiar de proveedor = cambiar el registro de DI.
3. **Eventos normalizados**: el bus nunca transporta conceptos de Docker.
4. **Spec de configuración**: el runtime se materializa desde `RuntimeSpec`
  (dato), no desde llamadas de bajo nivel repartidas por el código.
5. **Estrategia**: si un día se soporta Podman/nativo/k8s, se añade un adaptador nuevo;
  ningún módulo de dominio se modifica.

---

## 7. Sistema de eventos

### 7.1 Transporte y arquitectura del bus

- **Núcleo**: bus de eventos **en proceso** (in-process), síncrono para efectos
  transaccionales y asíncrono para consumidores pesados.
- **Durabilidad (opcional/etapa 2)**: patrón **Outbox** sobre Postgres — los eventos
  se persisten en la misma transacción que el cambio de dominio y se publican después.
- **Escalado multi-réplica**: Redis pub/sub para difundir eventos entre réplicas del
  backend (permite varios workers con un solo WebSocket gateway).
- **Orden**: orden parcial por entidad (por `server_id`) y orden total por secuencia
  global en la salida WebSocket.
- **Entrega**: al menos-una con deduplicación por ID de evento (idempotencia en consumidores).

### 7.2 Catálogo de eventos

Convención: `TEMA.CASO` (p. ej. `SERVER.STARTED`). Columna "consume": módulos.

#### Servidor / runtime

| Evento | Cuándo | Consumidores | Para qué |
|---|---|---|---|
| `SERVER.CREATED` | Instancia materializada en el panel (DB + spec) | Notification, Monitoring | UI, empezar a observar |
| `SERVER.CONFIG_CHANGED` | Se cambia config/env en BBDD | Server, Notification | Recrear contenedor |
| `SERVER.STARTING` | El runtime inicia | Monitoring, Notification | UI "starting", watchdog |
| `SERVER.STARTED` | Proceso BDS responde al ping | Monitoring, Player, Scheduler, Notification | iniciar métricas, uptime, marcar online |
| `SERVER.STOPPING` | Comienza apagado ordenado | Monitoring, Notification | aviso |
| `SERVER.STOPPED` | Proceso terminó limpiamente | Monitoring, Backup, Scheduler, Notification | detener métricas, permitir backups en frío |
| `SERVER.CRASHED` | El proceso muere sin stop ordenado | Monitoring, Scheduler, Notification, IAM (audit) | alertar, política de reinicio |
| `SERVER.REMOVED` | Instancia eliminada (datos opcionalmente conservados) | Backup, Notification | limpiar dependencias |
| `SERVER.VERSION_CHANGED` | `VERSION` distinta aplicada/descargada | World, Backup, Notification | registrar formato de mundo, sugerir backup |
| `UPDATE.AVAILABLE` | Existe versión más reciente que la actual | Notification, Server | avisar de actualización |

#### Jugador

| Evento | Cuándo | Consumidores | Para qué |
|---|---|---|---|
| `PLAYER.JOINED` | Línea de log parseada / cambio de contador | Player, Monitoring, Permission, Notification | contador, historial, XUID auto |
| `PLAYER.LEFT` | Línea de log parseada / timeout | Player, Monitoring, Notification | contador, playtime |
| `PLAYER.BANNED` | Comando ban aplicado | Player, Notification | estado del ban |
| `PLAYER.OPERATOR_CHANGED` | `op`/`deop` o fichero modificado | Player, Permission | consistencia permisos |

#### Mundo

| Evento | Cuándo | Consumidores | Para qué |
|---|---|---|---|
| `WORLD.CREATED` | Mundo generado/importado | Backup, Notification | sugerir backup inicial |
| `WORLD.IMPORTED` | Importación válida completada | Notification | UI |
| `WORLD.EXPORTED` | Exportación completada | Notification | registro |
| `WORLD.DUPLICATED` | Copia completada | Notification | UI |
| `WORLD.DELETED` | Mundo eliminado (soft) | Backup, Notification | retención de backups huérfanos |
| `WORLD.ACTIVATED` | Se cambia el mundo activo | Server, Configuration, Notification | recrear con nuevo level-name |

#### Backup

| Evento | Cuándo | Consumidores | Para qué |
|---|---|---|---|
| `BACKUP.STARTED` | Inicio real del snapshot | Notification | progreso en UI |
| `BACKUP.PROGRESS` | Actualización de progreso | Notification | barra de progreso |
| `BACKUP.COMPLETED` | Snapshot + checksum + metadatos OK | Notification, Player | UI, desbloquear operaciones |
| `BACKUP.FAILED` | Error en backup | Scheduler, Notification, IAM (audit) | alertar, reintentos |
| `BACKUP.RESTORE_STARTED` | Se inicia restauración | Server, Notification | detener servidor |
| `BACKUP.RESTORE_COMPLETED` | Mundo restaurado y verificado | Server, Notification | arrancar servidor |
| `BACKUP.RESTORE_FAILED` | Falla la restauración | Notification | alerta, rollback |
| `BACKUP.DELETED` | Backup borrado o pruned | Notification | UI |
| `BACKUP.VALIDATED` | Verificación de integridad OK | Notification | confianza en el backup |

#### Consola / configuración

| Evento | Cuándo | Consumidores | Para qué |
|---|---|---|---|
| `CONSOLE.COMMAND_SENT` | Comando enviado al stdin | Audit, Notification | trazabilidad |
| `CONSOLE.OUTPUT` | Línea de salida del servidor | parsers, Notification, Monitoring | logs en vivo, parseo |
| `CONFIG.CHANGED` | server.properties/packs modificado (deseado) | Server, Notification | aplicar (recrear) |
| `PACK.INSTALLED` / `PACK.REMOVED` | Pack añadido/quita del storage o activación | Configuration, Notification | UI |
| `WORLD.SAVED` | Línea de guardado de mundo detectada | Backup, Notification | calendario de backups, healthcheck |

#### Scheduler / tareas

| Evento | Cuándo | Consumidores | Para qué |
|---|---|---|---|
| `TASK.SCHEDULED` | Se crea/actualiza una programación | Notification | UI |
| `TASK.STARTED` | La tarea comienza | Backup, Server, Console, Notification | ejecutar dominio |
| `TASK.COMPLETED` | La tarea terminó OK | Notification | UI |
| `TASK.FAILED` | La tarea falló (agotó reintentos) | IAM (audit), Notification | alertar |
| `TASK.CANCELLED` | Tarea cancelada | Notification | UI |

#### IAM / sistema

| Evento | Cuándo | Consumidores | Para qué |
|---|---|---|---|
| `AUTH.LOGIN_SUCCESS` / `AUTH.LOGIN_FAILED` | Login | IAM (audit), Notification(opcional) | auditoría, bloqueo por intentos |
| `IAM.USER_CREATED` / `IAM.USER_ROLE_CHANGED` | Admin gestiona usuarios | IAM (audit), Notification | auditoría |
| `SYSTEM.HEALTH_DEGRADED` | Panel detecta problemas globales | Notification | alerta |

### 7.3 Quién consume y para qué (agregado)

- **Notification/WS**: prácticamente todos los eventos → difusión al frontend.
- **Monitoring**: eventos de ciclo de vida y de jugador.
- **Backup**: `WORLD.SAVED` (ventana de backup), `SERVER.STOPPED` (backup en frío),
  `TASK.STARTED` (backup programado).
- **Server**: `CONFIG.CHANGED`, `BACKUP.RESTORE_*`, `TASK.STARTED` (reinicio), `UPDATE.AVAILABLE`.
- **Player/Permission**: líneas de consola parseadas.
- **Scheduler**: escucha `BACKUP.FAILED`/`TASK.FAILED` para reintentos y próximos runs.

### 7.4 Reglas de idempotencia y consistencia

- Todo consumidor debe ser idempotente (mismo evento dos veces = mismo resultado).
- Los eventos que disparan operaciones largas (backup, recreate) se modelan como
  *órdenes* (`TASK.STARTED` con tipo de tarea) y su resultado real se reporta con
  eventos de resultado (`BACKUP.COMPLETED`).
- Los cambios de estado críticos se persisten en BBDD ANTES de publicar el evento
  (outbox), para que una caída del proceso no pierda el evento.

---

## 8. Diseño de backups

### 8.1 Modelo conceptual de un backup

Un backup es un **artefacto versionado + registro en BBDD**, no un simple zip:

- **Contenido**: snapshot del mundo activo (o mundo específico) y, opcionalmente, de la
  configuración del servidor (server.properties, allowlist, permissions, variables,
  packs de usuario).
- **Tipos de backup**: `world` (solo mundo), `full` (mundo + config + packs de usuario),
  `config` (solo config).
- **Kinds de origen**: `manual`, `scheduled`, `pre-upgrade`, `pre-restore`, `auto-mvp`.

### 8.2 Flujo de creación (backup consistente en caliente)

1. Verificar estado: si el servidor está online → método **en caliente**; si está
   detenido → método **en frío** (snapshot directo, más simple y seguro).
2. **En caliente**:
   - Enviar `save hold` (vía Console).
   - Esperar confirmación (`save query` o ventana de espera con timeout).
   - Snapshot del directorio del mundo (streaming, comprimido).
   - **Siempre** `save resume` (incluso en error) — red de seguridad.
   - Si el `save hold` no confirma en el timeout: decidir política (abortar y marcar
     como "inconsistent skip", o continuar marcando el backup como `degraded`).
3. **En frío**: snapshot directo sin comandos.
4. Calcular **checksum SHA-256** durante la compresión (streaming hash).
5. Registrar metadatos: mundo, versión del juego en ese momento, tamaño, nº de entradas,
   duración, checksum, tipo, origen, referencia de almacenamiento.

### 8.3 Compresión, formato y nomenclatura

- **Formato**: tar + **zstd** (buena ratio, velocidad alta, multithread). Alternativa
  `brotli` para máxima ratio en mundos grandes.
- **Nomenclatura**: fichero opaco + metadatos en BBDD.
  `bk_<server_uuid8>_<backup_uuid>_<kind>.zst`. La trazabilidad humana vive en la BBDD,
  no en el nombre del fichero (evita colisiones y permite renombrar).
- **Manifiesto**: bloque de metadatos al inicio del archivo (JSON) para que el backup
  sea autodescriptible si se extrae fuera del panel.

### 8.4 Retención

- **Políticas por servidor** combinables:
  - *Keep last N* (siempre los N más recientes).
  - *Tiers temporales* (diarios de los últimos 7, semanales de las últimas 4, mensuales
    de los últimos 6).
  - *Por antigüedad* (borrar > X días).
- **Prune**: job programado (Scheduler) que marca backups obsoletos, los borra del
  almacenamiento y registra `BACKUP.DELETED`.
- **Protección**: backups con flag `protected` no se prunen (p. ej. pre-upgrade).

### 8.5 Validación e integridad

- **Post-creación**: recomputar checksum (o validar durante el streaming) y, opcionalmente,
  listar entradas del archivo para confirmar que el nivel contiene `level.dat` y `db/`.
- **Pre-restauración**: verificar checksum y leer el manifiesto antes de tocar el mundo.
- **Backups corruptos**: se marcan `corrupt`, no se prunen automáticamente, y se notifica.

### 8.6 Restauración (flujo atómico y con rollback)

1. `BACKUP.RESTORE_STARTED` → detener el servidor (en caliente con `stop`, esperar
   `SERVER.STOPPED`).
2. Verificar integridad del backup.
3. **Snapshot de seguridad** del mundo actual (backup `pre-restore`, retención corta,
   con `protected`), para poder deshacer.
4. Reemplazar `worlds/<level>/` desde una **copia de trabajo temporal** (staging),
   no directamente sobre el destino (evita mundos a medias si falla el streaming).
5. Verificar `level.dat` del destino.
6. Publicar `BACKUP.RESTORE_COMPLETED` → arrancar el servidor.
7. En fallo: restaurar el `pre-restore` y dejar el servidor detenido con estado claro.

### 8.7 Almacenamiento

- **Abstracción de storage**: `BackupStore` port con adaptadores:
  - `LocalStore` (disco del host) — MVP.
  - `S3Store`/MinIO — etapa 2 (multibyte, retención de objetos, versionado).
  - `SFTPStore`/`NFSStore` — futuro.
- **Cifrado** (opcional, etapa 2): cifrado transparente por backup (AES-256-GCM con
  clave gestionada por el panel) para backups off-site.
- **Límites**: cuota por servidor, alertas cuando el storage supera umbrales.

### 8.8 Buenas prácticas y riesgos

| Buena práctica | Riesgo que mitiga |
|---|---|
| `save hold/resume` siempre con timeout + resume forzado | Mundo "held" / corrupción |
| Snapshot desde copia de trabajo | Restauración a medias |
| Checksum + manifiesto | Corrupción silenciosa |
| Backup pre-upgrade protegido | Upgrade que rompe formato de mundo |
| Restauración con rollback (`pre-restore`) | Restauración fallida |
| No tocar el mundo mientras se snapshot en caliente | Corrupción por escritura concurrente |
| Política de retención explícita | Crecimiento ilimitado de disco |
| Probar restauraciones periódicamente (restore drill) | Backups que no sirven |
| Registro de la versión de juego en el backup | Incompatibilidad de formato de mundo |

---

## 9. World Management

### 9.1 Conceptos

- Un **mundo** = carpeta `worlds/<level-name>/` en el storage (LevelDB en `db/`,
  `level.dat`, `levelname.txt`, `world_*_packs.json`).
- Un servidor puede contener **muchos mundos**, pero **solo uno activo**: el que
  referencia `level-name` en `server.properties`.
- El mundo es la unidad de **backup, exportación e importación**.

### 9.2 Operaciones

| Operación | Requisito | Flujo conceptual |
|---|---|---|
| **Importar** | Archive `.mcworld`/`.zip`/`.mctemplate` o carpeta | Validar (level.dat presente y NBT válido), sanitizar nombre, descomprimir a `worlds/<nombre>/`, registrar metadatos, quedar inactivo (activación manual) |
| **Exportar** | Servidor online o detenido | Snapshot del mundo (en caliente con `save hold` si aplica) → `.mcworld` (zip) para descarga |
| **Duplicar** | Servidor detenido (recomendado) | Copiar árbol del mundo (LevelDB) con nuevo nombre + metadatos |
| **Eliminar** | Servidor detenido o mundo inactivo | **Soft delete** (papelera con TTL) → purge real |
| **Activar** | Servidor detenido (cambio de level-name) | Cambiar config → `Server` recrea/reinicia con el nuevo `LEVEL_NAME` |
| **Desactivar** | — | No existe como tal: siempre hay un mundo activo; "desactivar" = activar otro |
| **Listar/metadata** | — | Metadatos en BBDD (etiqueta, notas, origen, tamaño, semilla, versión, última vez, estado) |

### 9.3 Metadata y validación

- **Metadata en BBDD** (clave `server_id + folder_name`): independiente del contenido,
  sobrevive a renames y permite buscar/ordenar.
- **Validación de import**: `level.dat` (NBT válido, contiene `LevelName`), carpeta `db`
  no vacía, nombre sin `/\n\r\t\f?*\\<>|":`, sin path traversal, sin colisión con un
  mundo existente, tamaño razonable.
- **Sanitización de zip**: protección **zip-slip** (rutas absolutas y `..`) en todos los
  descomprimidos (también aplica a packs).

### 9.4 Multi-mundo: experiencia

- El panel permite "biblioteca de mundos" por servidor: importar varios, ver stats,
  elegir cuál está activo. El cambio de mundo activo implica downtime (recreate) y se
  avisa.

---

## 10. Administración

### 10.1 Allowlist

- **Estado deseado en BBDD** → se materializa en `allowlist.json` (vía storage) y se
  puede aplicar en vivo con comandos de consola (`allowlist add/remove/reload`) para
  cambios inmediatos.
- **Resolución XUID↔gamertag**: consulta a la API MCProfile (o a las líneas del log de
  `PLAYER.JOINED`) con **caché local** (tabla del dominio Player) para no depender de la
  API en cada arranque.
- `allowlist.json` debe contener `name` + `xuid` (la imagen no resuelve nombres a mano).

### 10.2 Operadores (ops)

- Doble vía, consistente con la imagen: fichero `permissions.json`
  (`[{"permission":"operator","xuid":...}]`) y/o comandos en vivo `op`/`deop`.
- El panel sincroniza ambas: si edita el fichero, reinicia o usa `permission set`.

### 10.3 Permissions (en-juego)

- Niveles: `visitor` / `member` / `operator`.
- Fichero `permissions.json` gestionado por el dominio Permission; `permission set`
  para cambios en vivo.
- `default-player-permission-level` gestionado como propiedad de config.

### 10.4 server.properties

- **Esquema de propiedades** en el dominio Configuration: réplica estructurada del
  `property-definitions.json` de la imagen (env, valores permitidos, mappings, rangos).
- El panel **solo escribe env vars en la creación/recreación** del contenedor; nunca
  edita `server.properties` en caliente cuando la env var está activa (la imagen lo
  sobreescribiría en el arranque).
- Al cambiar: validar contra el esquema → persistir → `SERVER.CONFIG_CHANGED` →
  recrear contenedor → `set-property` aplica en el arranque.
- Propiedades nuevas de BDS sin env en la imagen (p. ej. `transport`) se exponen como
  "propiedades avanzadas" con edición directa del fichero y reinicio.

### 10.5 Behavior / Resource packs

- **Catálogo de packs** por servidor (UUID del manifest, nombre, versión, tipo, activo,
  tamaño, fecha).
- Instalación: subir `.mcpack`/`.mcaddon`/`.zip` → validar `manifest.json` → extraer a
  `behavior_packs/<uuid>/` o `resource_packs/<uuid>/` (zip-slip protegido) → registrar
  activación en `worlds/<mundo>/world_behavior_packs.json` /
  `world_resource_packs.json` (pack_id + version) → reiniciar.
- **Activación por mundo**: un pack puede estar instalado pero solo activo en ciertos
  mundos; el panel edita los `world_*_packs.json` correspondientes.
- `TEXTUREPACK_REQUIRED` gestionado como propiedad.
- Los packs vanilla de Mojang se **ocultan de la UI de gestión** (la imagen los
  regenera en el upgrade; tocarlos es peligroso).

### 10.6 World templates

- Una plantilla = artefacto reutilizable (config + mundo opcional + packs opcionales)
  con versión, tags y descripción.
- **Crear plantilla**: desde un servidor existente (snapshot limpio de config + mundo)
  o desde un artefacto subido (`.mctemplate`/`.mcworld` + preset de config).
- **Aplicar plantilla**: en la creación de un servidor (wizard) o como importación de
  mundo+packs a un servidor existente.
- El catálogo de plantillas es global (dominio Template) y puede versionarse.

---

## 11. Monitoreo

### 11.1 Fuentes y métricas

| Métrica | Fuente | Detalles |
|---|---|---|
| Estado del servidor | Dominio Server (derivado de runtime + ping) | starting/running/stopping/stopped/crashed |
| Jugadores online / máx | **Ping RakNet UDP** (backend) | Independiente de Docker; fuente primaria de estado |
| MOTD / versión / protocolo | Ping RakNet | Latencia = tiempo de respuesta del ping |
| Latencia | Ping RakNet | RTT en ms |
| Uptime | `SERVER.STARTED` → ahora | Marca de tiempo del evento |
| CPU % | Runtime stats (docker stats / cgroup) | Muestreo cada N segundos |
| RAM | Runtime stats | Uso/reserva |
| Disco | Storage (stat de la ruta del volumen) | Uso del directorio de datos |
| Healthcheck Docker | Runtime inspect | estado + último cambio |
| Logs | Streaming de logs del runtime | buffer en memoria + retención opcional en DB |
| TPS | **No expuesto por BDS nativamente** | Ver nota |

### 11.2 Nota honesta sobre TPS

- BDS **no expone TPS** (a diferencia de Java). El panel debe presentar un **indicador
  estimado de salud de ticks** basado en heurísticas (retraso de respuestas del ping,
  gaps de timestamps en logs, tiempo de `save hold`) y **etiquetarlo claramente como
  estimación**, no como TPS real. No se debe inventar un número de TPS que el motor no da.

### 11.3 Muestreo y almacenamiento

- **Estado y métricas en vivo**: consulta bajo demanda + suscripción WebSocket
  (push cada intervalo configurado, p. ej. 5 s).
- **Series temporales**: tabla de muestras en Postgres con retención configurable
  (MvP) o Prometheus (etapa 2). Cada muestra: server_id, timestamp, cpu, ram, players,
  latency, status.
- **Reconciliación de jugadores**: el contador del ping + eventos `PLAYER.JOINED/LEFT`
  se reconcilian para detectar caídas del parseo.

### 11.4 Logs

- **En vivo**: stream del runtime → buffer en memoria (ring) → WebSocket.
- **Persistencia**: retención configurable en DB (búsqueda, filtros por nivel/tiempo,
  descarga) o exportación a Loki (etapa 2).
- **Parseo**: pipeline de post-procesamiento que extrae eventos de negocio (join, leave,
  backup, errores) de las líneas crudas.

### 11.5 Alertas (base)

- Reglas simples configurables: servidor caído X min, disco > Y %, backup fallido,
  crash detectado. Destino: UI + webhooks (futuro).

---

## 12. API por dominios

> Diseño por módulos. Los contratos exactos (verbos/paths) se definirán en el OpenAPI.

| Módulo API | Responsabilidades |
|---|---|
| **Auth** | Login, refresh, logout, tokens, cambio de contraseña, 2FA |
| **Users** | CRUD de usuarios, estado, reset de contraseña |
| **Roles & Permissions** | CRUD de roles, catálogo de permisos, asignación |
| **Servers** | CRUD de instancias, ciclo de vida, imagen/versión, plantilla de creación, estado |
| **Server Config** | Lectura/validación/escritura de la config deseada (env/properties) |
| **Worlds** | CRUD de mundos, importar/exportar/duplicar/activar, metadata |
| **Backups** | CRUD de backups, crear (manual), restaurar, políticas de retención, validar |
| **Backup Schedules** | CRUD de programaciones (cron) |
| **Players** | Listado, detalle, búsqueda por XUID/gamertag, bans, historial |
| **Permissions (in-game)** | allowlist, ops, niveles, default-player-permission-level |
| **Packs** | Catálogo de behavior/resource packs, instalación, activación por mundo |
| **Console** | Enviar comando, estado de la sesión de consola |
| **Logs** | Consulta de logs históricos, filtros, descarga |
| **Monitoring** | Estado en vivo, métricas, series temporales, uptime |
| **Templates** | CRUD de plantillas de servidor/mundo, importar/exportar |
| **Tasks** | Listado de tareas, estado, cancelación |
| **Settings** | Configuración global, ubicaciones de almacenamiento |
| **Audit** | Consulta de logs de auditoría (solo admins) |
| **Events/WS** | Handshake WebSocket y control de suscripciones |

---

## 13. Canal WebSocket en tiempo real

### 13.1 Diseño

- **Un único endpoint** `/ws` con autenticación (token de corta duración en el
  handshake). Todas las réplicas del backend publican al mismo broker (Redis pub/sub)
  para que cualquier worker entregue al cliente.
- **Modelo de suscripción**:
  - Canal global: notificaciones, estado de la flota.
  - Canal por servidor: logs, consola, estado, métricas, jugadores, backups.
  - Canal por usuario: eventos de IAM propios.
- **Autorización por canal**: al suscribirse a un servidor, se verifica la membresía
  (IAM) de forma explícita y en cada re-suscripción.

### 13.2 Envolvente de mensaje

`{event, server_id?, scope, payload, ts, seq}` con orden parcial por canal y seq global
para detectar huecos y soportar *resume* (el cliente reenvía su último seq tras
reconectar).

### 13.3 Eventos automáticos hacia el frontend

| Categoría | Eventos push automáticos |
|---|---|
| Ciclo de vida | `SERVER.STARTING/STARTED/STOPPING/STOPPED/CRASHED/REMOVED` |
| Estado | snapshots periódicos de estado/métricas (5 s) |
| Consola/logs | líneas de `CONSOLE.OUTPUT` (con backpressure y coalescing) |
| Jugadores | `PLAYER.JOINED/LEFT`, contador reconciliado |
| Backups | `BACKUP.STARTED/PROGRESS/COMPLETED/FAILED/RESTORE_*` |
| Config | `CONFIG.CHANGED`, `PACK.INSTALLED/REMOVED`, `WORLD.ACTIVATED` |
| Tareas | `TASK.STARTED/COMPLETED/FAILED/CANCELLED` |
| Actualizaciones | `UPDATE.AVAILABLE`, `SERVER.VERSION_CHANGED` |
| Sistema | `AUTH.LOGIN_FAILED` (aviso al propio usuario), health del panel |

### 13.4 Control de flujo y robustez

- Cola por cliente con límite; política de descarte (drop-oldest) para logs, nunca para
  eventos de estado críticos.
- Heartbeat (ping/pong), reconnection con `seq` resume.
- Límite de rate: nº de mensajes/segundo por cliente; suscripciones por conexión.
- CORS y verificación de origen en el handshake WebSocket.

---

## 14. Seguridad

### 14.1 Autenticación

- **JWT** de corta vida (access) + **refresh token** rotativo (tabla de sesiones,
  revocable). Hasheo de passwords con **argon2id**.
- **2FA opcional** (TOTP) para cuentas con roles administrativos.
- Sesión ligada a IP/User-Agent con heurística de riesgo (opcional).
- Toda operación sensible revalida el token.

### 14.2 Autorización

- **RBAC global** + **ACL por servidor**:
  - **Super Admin**: gestión global, usuarios, roles, nodos.
  - **Admin**: gestión de cualquier servidor, templates, settings.
  - **Operador**: operaciones sobre servidores asignados (start/stop/restart, consola,
    backups, mundos, config, jugadores).
  - **Invitado / viewer**: solo lectura (estado, logs, jugadores) sobre servidores
    asignados.
- **Matriz de permisos** por acción (códigos tipo `server.console.write`,
  `backup.restore`, `world.delete`); los roles asignan permisos; las membresías
  asignan roles por servidor.
- Las decisiones de autorización se centralizan en IAM (punto único) y se aplican en
  Presentación (checks HTTP) y en el WebSocket (por canal).

### 14.3 CSRF

- La SPA usa **tokens Bearer en cabecera `Authorization`** (no cookies) → **CSRF no
  aplica** en la arquitectura recomendada. Si alguna ruta usara cookies, se exige
  `SameSite=Strict/Lax` + token CSRF. Se documenta explícitamente para evitar regresiones.

### 14.4 Rate limiting

- Por IP y por usuario (token bucket, respaldo Redis): login, registro, reset de
  contraseña, consola, backup; límites globales en la API.
- Lockout por intentos de login fallidos + CAPTCHA (etapa 2).

### 14.5 Auditoría

- Log de auditoría **append-only** con encadenado de hash (tamper-evidence),
  registrando actor, acción, recurso, resultado, IP, user-agent, timestamp.
- Eventos de IAM y operaciones destructivas SIEMPRE auditados.

### 14.6 Hardening operativo

- El **socket Docker solo lo usa el backend** (nunca el frontend); idealmente un
  docker daemon/socket dedicado con alcance restringido o un proxy que solo permita
  operaciones sobre los contenedores del panel.
- Contenedores BDS **no root**: UID/GID controlados por el panel (mismo dueño del
  volumen) — la imagen ya lo soporta vía `UID`/`GID`/`--match /data`.
- **Aislamiento de red**: backend ↔ contenedores en red interna; puertos UDP solo
  expuestos a jugadores; API solo detrás de TLS (Traefik/Nginx).
- **Uploads seguros**: validación de tipo/ tamaño, sanitización de nombres, protección
  zip-slip, escaneo opcional.
- **Secretos**: nunca en BBDD en claro (claves de cifrado de backups, passwords de
  runtime); variable de entorno/secrets manager.
- **XSS**: la salida de consola se renderiza escapada; los comandos de consola van por
  **stdin** (no a shell), por lo que no hay inyección de shell — validar igualmente
  longitud y caracteres de control.
- **Headers de seguridad**: CSP, HSTS, X-Content-Type-Options, frame-ancestors, CORS
  con allowlist estricta.

---

## 15. Base de datos: modelo conceptual

> Diseño conceptual (entidades y relaciones). El esquema físico (SQL) se define en la
> fase de implementación. Tablas prefijadas por módulo para respetar los bounded contexts.

### 15.1 Dominio IAM

| Entidad | Campos clave | Relaciones |
|---|---|---|
| `User` | id, email/username, password_hash, display_name, status, totp_secret, created_at, last_login_at | N:M con `Role` (vía `UserRole`); 1:N `ServerMembership`; 1:N `AuditLog`; 1:N `Session`; 1:N `ApiKey` |
| `Role` | id, name, description, is_system | N:M `User`; N:M `Permission` (vía `RolePermission`) |
| `Permission` | id, code, description | N:M `Role` |
| `Session` (refresh tokens) | id, user_id, token_hash, expires_at, revoked_at, ip, ua | N:1 `User` |
| `ApiKey` | id, user_id, token_hash, scopes, last_used_at, expires_at | N:1 `User` |
| `AuditLog` | id, actor_id, actor_type, action, resource_type, resource_id, result, detail(jsonb), ip, ua, created_at, prev_hash | N:1 `User` (actor) |

### 15.2 Dominio Server

| Entidad | Campos clave | Relaciones |
|---|---|---|
| `Server` | id, uuid, name, slug, status, image, image_tag, version, runtime_spec(jsonb), storage_path, udp_port_v4, udp_port_v6, ssh_enabled, created_by, created_at, deleted_at | 1:N `World`; 1:N `Backup`; 1:N `Player`; 1:N `ServerMembership`; 1:N `ConfigProfile`; 1:N `Task` |
| `ServerMembership` | server_id, user_id, role | N:1 `Server`; N:1 `User` |
| `ConfigProfile` | server_id, properties(jsonb, "config deseada"), active | N:1 `Server` |

### 15.3 Dominio World

| Entidad | Campos clave | Relaciones |
|---|---|---|
| `World` | id, server_id, folder_name, level_name, active(bool), seed, game_version, size_bytes, metadata(jsonb), imported_from, deleted_at(soft) | N:1 `Server`; 1:N `Backup` |

### 15.4 Dominio Backup

| Entidad | Campos clave | Relaciones |
|---|---|---|
| `Backup` | id, server_id, world_id?, name, kind(manual/scheduled/…), type(world/full/config), status, storage_ref, storage_location_id, size_bytes, checksum_sha256, compression, entries_count, duration_ms, protected(bool), metadata(jsonb), started_at, completed_at | N:1 `Server`; N:1 `World`; N:1 `StorageLocation` |
| `BackupSchedule` | id, server_id, name, cron, timezone, enabled, type, retention(jsonb), last_run_at, next_run_at | N:1 `Server`; 1:N `Backup` |
| `StorageLocation` | id, name, type(local/s3/…), config(jsonb, cifrado) | 1:N `Backup` |

### 15.5 Dominio Player

| Entidad | Campos clave | Relaciones |
|---|---|---|
| `Player` | id, server_id, xuid, gamertag, first_seen_at, last_seen_at, online, playtime_seconds, last_ip, banned, ban_reason, ban_expires_at, metadata(jsonb) | N:1 `Server`; 1:N `PlaySession` |
| `PlaySession` | id, player_id, joined_at, left_at, duration_ms | N:1 `Player` |

### 15.6 Dominio Configuration

| Entidad | Campos clave | Relaciones |
|---|---|---|
| `Pack` | id, server_id, type(behavior/resource), uuid, name, version, path, active, manifest(jsonb), installed_at | N:1 `Server`; N:M `World` (activación) |

### 15.7 Dominio Template / Scheduler / Settings

| Entidad | Campos clave | Relaciones |
|---|---|---|
| `Template` | id, name, kind(server/world), description, artifact_ref, version, tags(jsonb), created_at | — |
| `Task` | id, server_id?, type, status, run_at, payload(jsonb), result(jsonb), attempts, error, created_by, created_at | N:1 `Server` |
| `TaskSchedule` | id, name, type, cron, timezone, enabled, server_id?, payload(jsonb), last_run_at, next_run_at | N:1 `Server` |
| `Setting` | id, key, value(jsonb) | — |

### 15.8 Infraestructura técnica

| Entidad | Descripción |
|---|---|
| `EventOutbox` | Eventos pendientes de publicar (patrón outbox); consumidos y eliminados |
| `EventLog` | Registro inmutable de eventos publicados (trazabilidad, resume WS) |
| `MetricSample` | series temporales (server_id, ts, cpu, ram, disk, players, latency, status) |
| `LogEntry` | logs persistentes (server_id, ts, level, source, line) — retención configurable |

### 15.9 Reglas de consistencia

- Eliminación de un `Server` → soft delete; dependencias (World/Backup/Player) quedan
  marcadas como huérfanas y se purgan según política (los backups conservados se
  desvinculan lógicamente).
- `World.active` es único por servidor (constraint parcial): solo un mundo activo.
- Cambios de config se versionan (auditoría); `ConfigProfile` guarda el deseado y el
  aplicado para detectar "pending changes".
- Las claves foráneas entre módulos se usan solo a nivel de identidad (id); el acceso
  al estado interno de otro módulo está prohibido (regla de módulos).

---

## 16. Estructura del repositorio

> Monorepo. Los módulos se añaden por carpeta sin tocar los existentes.

```
minecraft-bedrock-panel/
├── apps/
│   ├── backend/                       # FastAPI (modular monolith)
│   │   └── src/
│   │       ├── bootstrap/             # Composición de DI, arranque, config, asgi
│   │       ├── kernel/                # Shared kernel: IDs, errores, bus, eventos, logging
│   │       ├── modules/
│   │       │   ├── iam/               # auth, users, roles, audit
│   │       │   ├── server/            # instancias, ciclo de vida
│   │       │   ├── world/
│   │       │   ├── backup/
│   │       │   ├── player/
│   │       │   ├── permission/
│   │       │   ├── configuration/     # server.properties, packs
│   │       │   ├── console/
│   │       │   ├── scheduler/
│   │       │   ├── monitoring/
│   │       │   ├── template/
│   │       │   ├── notification/      # WS gateway
│   │       │   └── settings/
│   │       │       └── (estructura interna por módulo)
│   │       │           ├── api/       # routers + schemas (vertical slice)
│   │       │           ├── application/  # use cases
│   │       │           ├── domain/       # entidades, value objects, puertos, eventos
│   │       │           └── infrastructure/ # adaptadores
│   │       ├── infrastructure/        # adaptadores compartidos
│   │       │   ├── runtime/           # docker.py (ServerRuntime), podman/native/k8s (futuro)
│   │       │   ├── storage/           # local.py (ServerStorage), runtime_storage.py
│   │       │   ├── status/            # raknet ping client
│   │       │   ├── backups/           # tar+zstd, s3, cifrado
│   │       │   ├── parsers/           # log parse pipeline
│   │       │   └── db/                # SQLAlchemy models + Alembic migrations
│   │       └── (pyproject.toml, settings, etc.)
│   └── frontend/                      # React + Vite + Tailwind
│       └── src/
│           ├── app/                   # layout, routing, providers
│           ├── features/              # feature slices (servers, worlds, backups, console…)
│           ├── shared/                # UI kit, hooks, utils
│           ├── api/                   # client REST (TanStack Query)
│           ├── ws/                    # cliente websocket + resume
│           └── store/                 # Zustand
├── packages/                          # (opcional) contratos compartidos frontend/backend (schemas)
├── docs/                              # TDD, ADRs, análisis de la imagen, guías
├── infra/
│   ├── docker/                        # Dockerfiles (backend, frontend build)
│   ├── compose/                       # compose.yml (prod, dev), nginx/traefik
│   └── scripts/
├── deploy/                            # systemd, ejemplo VPS
├── tests/                             # (o tests/ dentro de cada módulo) unit + integración
├── .github/workflows/                 # CI: lint, test, build, docker
└── README.md, LICENSE, etc.
```

Reglas de la estructura:

- Cada módulo de backend es **autocontenido** (API + casos de uso + dominio + adaptador
  propio). Los adaptadores de infraestructura compartida (runtime, storage, raknet)
  se importan por inyección, nunca directamente desde el dominio.
- Los tests siguen a su módulo (unit) o viven en `tests/` para integración e2e.
- El frontend es *feature-first*: cada feature mapea a un dominio del backend.

---

## 17. Roadmap

### Fase 0 — Fundación
- Monorepo, CI, Dockerfiles, compose dev/prod, Postgres, Alembic baseline.
- Kernel compartido (bus de eventos, errores, configuración).
- Autenticación básica + esqueleto de módulos.

### Fase 1 — MVP
- **Server**: crear/arrancar/detener/reiniciar/eliminar instancias; puertos; estado.
- **Console**: enviar comandos (`send-command`), stream de logs.
- **Monitoring básico**: ping RakNet, estado, jugadores online, uptime, métricas CPU/RAM/disco.
- **Backups manuales**: snapshot con `save hold/resume`, compresión zstd, checksum,
  restauración con rollback.
- **Config básica**: server.properties via env (recreate).
- **WebSocket**: estado + logs + consola en tiempo real.

### Fase 1.1 — Mundos y jugadores
- World management completo (import/export/duplicar/activar/eliminar, metadata).
- Player: historial, playtime, búsqueda XUID, bans.
- Allowlist y operadores (en vivo + fichero).

### Fase 1.2 — Usuarios, roles y permisos
- IAM completo: roles, permisos por acción, membresías por servidor, auditoría.
- Rate limiting, 2FA, API keys.

### Fase 1.3 — Configuración avanzada, packs y plantillas
- server.properties schema-driven completo (incluidas propiedades nuevas de BDS).
- Packs behavior/resource (instalar, activar por mundo).
- Plantillas de servidor y mundo, clonación.

### Fase 1.4 — Automatización
- Backups programados + retención + prune.
- Tareas programadas (reinicios, anuncios, comandos).
- Alertas + webhooks.

### Fase 2 — Escalado y robustez
- Outbox durable, Redis pub/sub, múltiples réplicas del backend.
- Almacenamiento de backups S3/MinIO + cifrado.
- Métricas con Prometheus/Grafana (o TS en DB), retención avanzada.
- Redis como cache/rate-limit distribuido.

### Fase 3 — Multi-nodo y cluster
- `ServerRuntime` multi-proveedor (Podman, nativo).
- Nodos remotos (agent ligero o acceso al runtime remoto) → multi-host.
- Alta disponibilidad (Redis + réplicas), migración de servidores entre nodos.
- API pública + marketplace de packs.

### Fase 4 — Ecosistema
- Migración a microservicios **solo si** la evidencia lo justifica (seguir monolith
  modular es la decisión por defecto).
- Multi-idioma, plugin system, auditoría avanzada.

---

## 18. Análisis crítico

### 18.1 Fortalezas

- **Límites de dominio claros**: cada contexto es testeable aislado; el monolito
  modular permite refactorizar sin microservicios.
- **Runtime-agnosticismo real**: separación runtime/storage hace trivial añadir Podman
  o nativo, y protege el dominio de la "fricción Docker".
- **Event-driven**: permite escalar a multi-réplica y añadir consumidores (webhooks,
  notificaciones) sin tocar emisores.
- **No se modifica la imagen**: todo el diseño aprovecha capacidades existentes
  (`send-command`, env vars, `save hold/resume`, `MC_PACK`, ping RakNet).
- **Decisiones honestas** (RCON inexistente, TPS estimado) evitan prometer lo que el
  motor no puede dar.
- **Seguridad por diseño**: separación socket Docker, RBAC+ACL, auditoría con
  tamper-evidence, uploads sanitizados.

### 18.2 Debilidades

- **Recrear contenedor para cada cambio de config** genera downtime y una superficie
  de estados intermedios que el panel debe modelar con cuidado (cola de operaciones).
- **Acceso directo al filesystem (LocalStorage)** vincula el backend al host: el
  backend debe correr con permisos sobre `/var/lib/panel/instances/*` y, si el backend
  vive en otro nodo, se pierde (mitigado en Fase 3 con agentes/almacenamiento remoto).
- **Inyección de comandos por stdin sin shell**: segura pero frágil ante procesos que
  dejan de leer stdin; el panel necesita detectar "consola no disponible".
- **Parseo de logs de BDS** es frágil: el formato cambia entre versiones; el parseo
  debe ser tolerante y no bloquear el pipeline.
- **Monolito en Python + APScheduler en proceso**: el scheduler no sobrevive a caídas
  del proceso sin el patrón outbox/job store persistente (previsto en Fase 2).
- **El websocket en una sola réplica** requiere broker (Redis) en cuanto se escale.

### 18.3 Riesgos técnicos

- **Corrupción de mundo** por operaciones concurrentes (backup en caliente + restore
  simultáneo). Mitigación: bloqueos por servidor (mutex de operaciones) en el dominio
  Server.
- **Upgrade de versión de BDS con `LATEST`** puede cambiar formato de mundo; el panel
  debe defender backups pre-upgrade y ofrecer pinning.
- **Fuga de memoria de BDS**: reinicios programados necesarios; downtime asumido y
  comunicado.
- **Dependencias externas** (MCProfile, APIs de versión): cachear y degradar con gracia.
- **Seguridad del socket Docker**: es el mayor riesgo; mitigación con daemon dedicado
  y auditoría.
- **Rendimiento del ping UDP en hosts con muchos servidores**: el poller debe
  escalonarse y usar conexiones no bloqueantes.

### 18.4 Complejidad

- Complejidad **necesaria**: bounded contexts, outbox, bus de eventos, retención.
- Complejidad **a evitar en MVP**: multi-nodo, cifrado de backups, Prometheus, API keys.
  El roadmap las pospone con criterio.
- La complejidad del **estado del servidor** (deseado vs aplicado vs real) es la más
  alta del sistema; se recomienda una máquina de estados explícita documentada y con
  tests exhaustivos.

### 18.5 Escalabilidad

- Horizontal: réplicas del backend + Redis (Fase 2). El estado vive en Postgres y el
  volumen, no en el proceso → replica-friendly.
- Vertical: el monolito FastAPI async maneja muchos servidores; el cuello es el
  poller de ping y el streaming de logs → separar por tareas asíncronas.
- Multi-host: requiere Fase 3 (agentes/nodos). El diseño de eventos y runtime ya lo
  contempla.

### 18.6 Mantenibilidad

- Alta gracias a: capas estrictas, módulos autocontenidos, DI centralizada, esquemas
  por módulo, docs (TDD + ADRs).
- Riesgo: que los módulos "filtren" dependencias entre sí; mitigado por reglas de
  arquitectura revisadas en CI (import-lint, dependency-cruiser equivalente para Python).

### 18.7 Mejoras futuras

- Plugin system (hooks sobre eventos).
- Agente ligero en los nodos para runtime remoto (como wings de Pterodactyl).
- Marketplace de packs/plantillas.
- Estadísticas históricas avanzadas (sesiones, picos, economía del mundo).
- API pública con API keys y scopes.
- Cifrado de backups y doble factor a nivel de restore.
- Dashboard global multi-servidor con agregación.

---

## 19. Glosario

| Término | Definición |
|---|---|
| **BDS** | Bedrock Dedicated Server, software de servidor oficial de Mojang |
| **Bounded context** | Límite de modelado DDD; contexto donde un término tiene significado único |
| **Modular monolith** | Aplicación desplegada como un solo proceso con módulos con límites estrictos |
| **Puerto / adaptador** | Interfaz (puerto) en dominio y su implementación (adaptador) en infraestructura |
| **Outbox** | Patrón: eventos persistidos en la misma transacción del cambio y publicados después |
| **ServerRuntime** | Abstracción del ciclo de vida/proceso del servidor (Docker, Podman, nativo, k8s) |
| **ServerStorage** | Abstracción del estado persistente (volumen `/data`) |
| **RuntimeSpec** | Descripción declarativa de cómo materializar un servidor en un runtime |
| **RakNet** | Protocolo de transporte de red de Bedrock; el ping no conectado da estado |
| **XUID** | Identificador numérico de cuenta Xbox (16+ dígitos) |
| **save hold/resume** | Comandos BDS que pausan/reanudan el guardado del mundo (para backups) |
| **RBAC** | Control de acceso basado en roles |
| **ACL** | Lista de control de acceso (aquí: membresías por servidor) |

---

*Este documento es la referencia oficial de arquitectura. Cualquier cambio sustancial
requiere un ADR y actualización de este TDD. Pendiente de instrucciones antes de generar
código.*
