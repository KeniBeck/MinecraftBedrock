# Troubleshooting: tiempo real roto en producción (WebSockets, consola, notificaciones)

Guía de diagnóstico y solución para el problema clásico de despliegue: en
desarrollo (backend en contenedor + frontend con `pnpm dev`) las vistas en
tiempo real funcionan, pero en producción (todo en contenedores) **no llegan
eventos en vivo**: consola, notificaciones de jugadores, sync de mundos y
eventos de creación/edición.

## 1. Síntomas

- La consola en vivo de un servidor no muestra líneas nuevas.
- No llegan notificaciones en tiempo real (jugadores entran/salen, backups, etc.).
- La creación/edición de mundos no se refleja en vivo (se ve tras recargar).
- Todo lo anterior **funciona en dev** con el frontend en `pnpm dev`.

> Nótese que **no** es un problema de puertos ni de nginx: el proxy de WebSocket
> (`/api/` y `/ws` con `Upgrade`/`Connection`) está correcto en
> `infra/docker/nginx.conf`, y el cliente usa el mismo origen
> (`window.location.host` → `/api/v1/ws?token=`), que en producción es nginx.

## 2. Causa raíz

El panel es un sistema de tiempo real **stateful en proceso**: el estado vive en
la memoria de **un solo proceso Python** (un worker de uvicorn).

| Subsistema en memoria | Archivo |
|---|---|
| Bus de eventos (`InProcessEventBus`) | `apps/backend/src/app/infrastructure/events/bus.py` |
| Registro de conexiones WebSocket (`ConnectionManager`) | `apps/backend/src/app/modules/notification/application/connection_manager.py` |
| Gestor de streams de consola | `apps/backend/src/app/modules/console/infrastructure/stream_manager.py` |
| Poller de monitoreo | `apps/backend/src/app/modules/monitoring/infrastructure/poller.py` |
| Poller del scheduler | `apps/backend/src/app/modules/scheduler/infrastructure/poller.py` |

### Por qué dev funciona y prod no

- **Dev** (`docker-compose.dev.yml`): `uvicorn ... --reload` → **1 worker**.
  Un solo proceso contiene el bus, las conexiones WS y los streams; el tiempo
  real es coherente.
- **Prod** (`infra/docker/entrypoint.backend.sh`): lanzaba uvicorn con
  `--workers=N` (2×CPU, máx 8). Cada worker es un **proceso independiente** con
  su **propia copia** de bus, connection manager y pollers.

### Qué rompe N workers

El socket compartido de uvicorn reparte las conexiones (REST y WS) entre los
workers al azar:

1. **WebSockets huérfanos**: el navegador conecta al worker A (`ConnectionManager`
   lo registra allí); los eventos los publica el worker B. `broadcast_to_channels`
   del worker B no conoce la conexión de A → **el mensaje nunca llega**.
2. **Consola en vivo**: el stream del contenedor Minecraft se lee en un worker,
   pero la conexión WS que la muestra está en otro.
3. **Notificaciones / sync de mundos**: los `DomainEvent` se propagan solo
   dentro del worker que los publicó (`InProcessEventBus` es local al proceso).
4. **Scheduler duplicado**: el `SchedulerPoller` corre en cada worker → las
   tareas programadas (backups, comandos) se ejecutarían **N veces**.
5. **Monitoreo duplicado**: el `BackgroundPoller` también corre en cada worker
   (redundante, menos grave que el scheduler).

## 3. Solución aplicada

Alinear la topología a la arquitectura: **un solo worker de uvicorn** en
producción (idéntico a dev).

### Cambios

- `infra/docker/entrypoint.backend.sh`
  - Default de `BEDROCK_PANEL_WEB_CONCURRENCY` = `1` (antes 2×CPU máx 8).
  - Si alguien fuerza un valor >1, el entrypoint imprime una advertencia clara.
- `docker-compose.prod.yml`
  - `BEDROCK_PANEL_WEB_CONCURRENCY: ${BEDROCK_PANEL_WEB_CONCURRENCY:-1}` (default
    explícito) y comentario de advertencia en el encabezado.
- `.env.prod.example` y `.env.prod`
  - Comentario actualizado: default 1 worker, no subirlo sin externalizar el bus.
- `docs/deployment.md`
  - Nota de workers corregida (la anterior asumía que el estado en memoria no era
    un requisito, lo cual es falso para WebSockets) y tabla de variables.

### Verificación

```bash
# 1. Reconstruye y levanta
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 2. Confirma que el backend arranca con 1 worker
docker compose --env-file .env.prod -f docker-compose.prod.yml logs backend | grep -i "worker"

# 3. Abre el panel (http://<host>:${BEDROCK_PANEL_HTTP_PORT}) y comprueba:
#    - Consola en vivo de un servidor en ejecución.
#    - Notificaciones al iniciar/parar un servidor o al entrar un jugador.
#    - Sync de mundos (crear/editar/importar) sin recargar la página.

# 4. (Opcional) Health del WS desde el contenedor del frontend:
docker exec bedrockpanel-frontend wget -qO- --header='Connection: Upgrade' \
  --header='Upgrade: websocket' http://backend:8000/api/v1/ws 2>&1 | head -c 200
```

## 4. ¿Puedo usar varios workers igualmente?

Sí, pero **solo tras externalizar el estado en proceso**. El plan profesional
para escalar horizontalmente es:

1. **Bus de eventos distribuido**: sustituir `InProcessEventBus` por un bus
   pub/sub con Redis (`redis.asyncio`). Cada worker publica en Redis y se
   suscribe a una difusión para re-publicar localmente en su propio
   `ConnectionManager` (patrón estándar de WebSockets escalables).
2. **Líder único para los pollers**: con varios workers, `SchedulerPoller` y
   `BackgroundPoller` se duplicarían. Hay que elegir un líder (p. ej. lock
   distribuido en Redis, `SET NX EX`) para que el reloj del scheduler corra una
   sola vez.
3. **Añadir `redis` como servicio** en `docker-compose.prod.yml` y la variable
   `BEDROCK_PANEL_REDIS_URL` en `bootstrap/config.py`.

Hasta que exista eso, mantener `BEDROCK_PANEL_WEB_CONCURRENCY=1`. El panel es un
proceso async: un solo worker de uvicorn puede sostener miles de conexiones WS
concurrentes; el escalado en un host único es vertical (CPU/RAM del contenedor).

## 5. Referencia de archivos

| Archivo | Cambio |
|---|---|
| `infra/docker/entrypoint.backend.sh` | Default 1 worker + advertencia si >1 |
| `docker-compose.prod.yml` | Default explícito `:-1` + comentario |
| `.env.prod.example` / `.env.prod` | Comentario de workers actualizado |
| `docs/deployment.md` | Nota de workers y tabla de variables corregidas |
