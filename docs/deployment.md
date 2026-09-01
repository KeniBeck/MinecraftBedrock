# Despliegue en producción — BedrockPanel (Docker)

Guía para llevar la pila **backend + frontend + Postgres** a cualquier máquina
con Docker de forma reproducible y estandarizada. Complementa a
`docker-compose.dev.yml` (solo backend + Postgres de desarrollo).

Responde a estas decisiones:

- **Un Dockerfile por aplicación** (no uno que corra ambas): el backend es un
  proceso vivo (uvicorn) y el frontend un build estático que sirve nginx. Los
  contenedores se orquestan con `docker-compose.prod.yml` y comparten una red
  interna `bedrockpanel`.
- **Postgres portable**: credenciales por entorno (`.env.prod`), volumen nombrado
  y healthcheck + `depends_on` para que el backend espere a la DB antes de migrar.

---

## 1. Arquitectura

```
        PUERTO HOST 8080 (u otro)
        ┌─────────────────────────────┐
        │         frontend            │  nginx:80 (imagen)
        │  sirve el SPA estático      │
        │  proxy /api  → backend:8000 │
        │  proxy /ws   → backend:8000 │
        └──────────┬──────────────────┘
                   │ red interna "bedrockpanel"
        ┌──────────▼──────────────────┐   ┌─────────────────────┐
        │         backend             │──▶│     postgres        │
        │  FastAPI (uvicorn:8000)     │   │  Postgres 16 (:5432)│
        │  Alembic upgrade en arranque│   │  volumen nombrado   │
        └───┬──────────────┬──────────┘   └─────────────────────┘
            │ /var/run/docker.sock        (healthcheck + depends_on)
            │ (gestiona contenedores Minecraft en el HOST)
            ▼
        Contenedores Bedrock via docker-py: {container_prefix}-{server_id}
        with bind-mount {BEDROCK_PANEL_STORAGE_ROOT}/{server_id}:/data
```

Puntos de integración importantes con el código existente:

| Contrato | Dónde | Cómo lo cubre la imagen |
|---|---|---|
| `Settings` lee env `BEDROCK_PANEL_*` | `bootstrap/config.py` | Variables inyectadas en el compose |
| URL de DB (Alembic = app) | `bootstrap/config.py`, `alembic/env.py` | `BEDROCK_PANEL_DATABASE_URL` |
| Migraciones al arranque | `alembic upgrade head` | Entrypoint (`entrypoint.backend.sh`) |
| API + WS bajo `Settings.api_prefix` (`/api/v1`) y `GET /ws` | `bootstrap/main.py` | nginx proxy `/api/` y `/ws` |
| Runtime multi-servidor Docker | `infrastructure/runtime/docker.py` | mount `/var/run/docker.sock` |
| Storage (worlds/backups/templates) | `LocalServerStorage`, `RuntimeSpecFactory` | volumen en la misma ruta host y contenedor |
| WebSocket global / por servidor | `notification`, `console`, `monitoring` | nginx con `Upgrade`+`Connection` |

---

## 2. Requisitos previos

- **Docker Engine** con la API del daemon accesible desde el contenedor
  (Linux: el socket `unix:///var/run/docker.sock` se monta; en macOS/Windows usa
  Docker Desktop y comparte el socket).
- Acceso a internet para descargar imágenes base (`python:3.13-slim`,
  `node:22-alpine`, `nginx:1.27-alpine`, `postgres:16`, `ghcr.io/astral-sh/uv`).
- `cryptography` instalable en la máquina que genere la clave Fernet (o generar
  la clave en cualquier Python con la dependencia).

---

## 3. Preparación

### 3.1. Archivo de entorno

Copia el ejemplo y rellena los valores:

```bash
cp .env.prod.example .env.prod
# edita: POSTGRES_PASSWORD, BEDROCK_PANEL_SERVER_PUBLIC_HOST,
#        BEDROCK_PANEL_STORAGE_ROOT, BEDROCK_PANEL_IAM_ENCRYPTION_KEY
```

Genera la clave Fernet de IAM (necesaria para 2FA / backup codes):

```bash
# desde apps/backend (donde ya está cryptography)
cd apps/backend && uv run python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> `BEDROCK_PANEL_STORAGE_ROOT` debe ser una **ruta absoluta del host**. Es la
> misma que se monta dentro del contenedor del backend y la que usa docker-py
> como origen de los bind-mounts `{storage_root}/{server_id}:/data` de cada
> contenedor Minecraft. Mantenerla idéntica en host y contenedor es **crítico**
> para que worlds/backups/templates y los bind-mounts apunten al mismo sitio.

---

## 4. Construir y levantar

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

- El backend arranca cuando Postgres esté sano (healthcheck) y aplica
  `alembic upgrade head` automáticamente (entrypoint).
- El frontend (nginx) queda escuchando en `http://<host>:{BEDROCK_PANEL_HTTP_PORT}`
  (default `8080`).

Ver el estado:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Logs:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f backend
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f frontend
```

---

## 5. Uso diario

### Administrador inicial (bootstrap)

Si en `.env.prod` defines `BEDROCK_PANEL_BOOTSTRAP_ADMIN_USERNAME` y
`BEDROCK_PANEL_BOOTSTRAP_ADMIN_PASSWORD`, el backend crea (solo la primera vez, de forma
**idempotente**) un usuario con rol `super_admin`. Con él puedes entrar al panel sin
crear usuarios por comando. La creación es segura frente a los múltiples workers de
uvicorn: si dos procesos intentan crear el mismo username a la vez, uno gana y el otro
re-resuelve el usuario existente sin romper el arranque ni dejar trazas de error.

### Detener / arrancar / borrar

> Todos los comandos de producción llevan `--env-file .env.prod` (igual que en la
> sección 4): el compose usa variables **obligatorias** (`POSTGRES_PASSWORD`,
> `BEDROCK_PANEL_IAM_ENCRYPTION_KEY`...). Sin el flag, `stop`/`start`/`down`
> fallan al interpolar esas variables. Ojo al orden: `--env-file` va antes de `-f`.

```bash
# detener (mantiene datos)
docker compose --env-file .env.prod -f docker-compose.prod.yml stop

# re-arrancar
docker compose --env-file .env.prod -f docker-compose.prod.yml start

# parar y borrar contenedores y red (NO borra el volumen de Postgres)
docker compose --env-file .env.prod -f docker-compose.prod.yml down

# parar y borrar TAMBIÉN el volumen de datos de Postgres (¡destructivo!)
docker compose --env-file .env.prod -f docker-compose.prod.yml down -v
```

### Reconstruir tras cambios de código

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

---

## 6. Rutas y volúmenes

| Recurso | Ubicación |
|---|---|
| DB (Postgres) | volumen nombrado `bedrockpanel-pgdata-prod` (`/var/lib/postgresql/data`) |
| Datos del panel (worlds, backups, templates) y bind-mounts Minecraft | `BEDROCK_PANEL_STORAGE_ROOT` en el host |
| Socket de Docker | `- /var/run/docker.sock:/var/run/docker.sock` (solo backend) |

Para backup manual del panel: conserva el volumen de Postgres Y el directorio
`BEDROCK_PANEL_STORAGE_ROOT` del host.

---

## 7. Variables de entorno clave

| Variable | Default | Descripción |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `bedrockpanel` / *(requerido)* / `bedrockpanel` | Credenciales de Postgres |
| `BEDROCK_PANEL_SERVER_PUBLIC_HOST` | `localhost` | IP/LAN/DNS para que conecten los jugadores |
| `BEDROCK_PANEL_MONITORING_PROBE_HOST` | *(usa public_host)* | Dirección con la que el backend verifica el juego (sondeo RakNet). En Docker: gateway de la red (p. ej. `172.18.0.1`) |
| `BEDROCK_PANEL_STORAGE_ROOT` | `/var/lib/bedrockpanel/instances` | Ruta host del storage (MUST match inside container) |
| `BEDROCK_PANEL_IAM_ENCRYPTION_KEY` | *(requerido)* | Clave Fernet de IAM (secrets 2FA/backup codes) |
| `BEDROCK_PANEL_IAM_JWT_SECRET` | *(fallback dev)* | Clave HMAC de firma de JWT (HS256); recomendable ≥32 bytes |
| `BEDROCK_PANEL_WEB_CONCURRENCY` | 1 | Workers de uvicorn. **Default 1 obligatorio**: el panel es stateful en proceso (WebSockets, consola, notificaciones, scheduler). Ver nota de workers abajo |
| `BEDROCK_PANEL_LOG_LEVEL` | `INFO` | Nivel de log del backend |
| `BEDROCK_PANEL_HTTP_PORT` | `8080` | Puerto host del frontend |
| `BEDROCK_PANEL_BOOTSTRAP_ADMIN_USERNAME` | `admin` | Usuario super_admin inicial (solo se crea la 1ª vez) |
| `BEDROCK_PANEL_BOOTSTRAP_ADMIN_PASSWORD` | *(requerido si username definido)* | Contraseña del bootstrapped admin |
| `BEDROCK_PANEL_BOOTSTRAP_ADMIN_DISPLAY_NAME` | `Administrador` | Nombre visible del admin inicial |

---

## 8. Notas de seguridad y operación

- **No uses secretos por defecto en producción**: `POSTGRES_PASSWORD` y
  `BEDROCK_PANEL_IAM_ENCRYPTION_KEY` son obligatorios en el compose (`:?`).
- El backend necesita el **socket de Docker del host** porque gestiona los
  contenedores Minecraft (runtime multi-servidor, §20). No se requiere dentro de
  la red del panel; es un requisito de administración de contenedores.
- **Exposición en nube**: Bedrock usa UDP `19132/19133`. Un proxy HTTP no basta
  para gameplay (ver `README.md`); el frontend sirve el panel (TCP), los
  puertos UDP del juego se exponen a nivel de red/host según corresponda.
- **Workers**: el panel es un sistema de tiempo real **stateful en proceso**: el
  bus de eventos (`InProcessEventBus`), el registro de conexiones WebSocket
  (`ConnectionManager`), los streams de consola y los pollers de monitoreo y
  scheduler viven en la memoria de **un solo proceso**. Por eso el default de
  `BEDROCK_PANEL_WEB_CONCURRENCY` es **1** (igual que dev). Con `--workers>1`
  cada worker es un proceso aislado: la conexión WS del navegador cae en un
  worker y los eventos se emiten en otro, rompiendo consola en vivo,
  notificaciones, sync de mundos y duplicando las tareas del scheduler. Para
  escalar a varios workers primero hay que externalizar el bus (Redis pub/sub) —
  ver `docs/troubleshooting-tiempo-real-produccion.md`.
- Para un despliegue más aislado puede fijarse `network_mode` o exponer solo el
  puerto del frontend y mantener el backend interno (ya es el caso por defecto:
  solo `frontend` publica puerto al host).

---

## 9. Errores comunes y recuperación

### 9.1 `dependency failed to start: container bedrockpanel-postgres has no healthcheck configured`

**Síntoma**: `docker compose --env-file .env.prod -f docker-compose.prod.yml start`
(o `up`) falla con ese mensaje, aunque `docker ps` muestra el postgres corriendo.

**Causa**: el contenedor `bedrockpanel-postgres` que hay en el host fue creado por
`docker-compose.dev.yml`, no por el de producción. Ambos stacks usaban el **mismo
nombre de contenedor** (`bedrockpanel-postgres`) y el **mismo proyecto** (el del
directorio). El `start`/`up` de prod reutiliza el contenedor existente; como el de
dev **no define healthcheck**, la dependencia `postgres: condition: service_healthy`
del backend no puede evaluarse y el arranque se aborta.

**Se distingue así**: el postgres creado por dev publica `5433:5432` y no tiene
healthcheck; el de prod publica `5432:5432` (default) y sí lo tiene:

```bash
docker inspect bedrockpanel-postgres \
  --format 'config={{index .Config.Labels "com.docker.compose.project.config_files"}} healthcheck={{if .Config.Healthcheck}}yes{{else}}NO{{end}}'
```

**Recuperación** (quita solo el contenedor conflictivo y recrea la pila; los
volúmenes de datos se conservan):

```bash
# 1. Elimina el postgres huérfano de dev (los datos dev viven en el volumen
#    `bedrockpanel-pgdata` y no se tocan).
docker rm -f bedrockpanel-postgres

# 2. Recrea la pila de producción completa.
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 3. Verifica que el nuevo postgres tiene healthcheck y que el backend usa 1 worker.
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs backend | grep -i worker
```

**Prevención (ya aplicada)**: `docker-compose.dev.yml` ahora usa un proyecto propio
(`name: bedrockpanel-dev`) y nombres de contenedor propios
(`bedrockpanel-postgres-dev`, `bedrockpanel-dev-panel`), de modo que dev y prod
pueden coexistir sin colisión de nombres ni de healthcheck. Dev y prod usan
volúmenes de Postgres distintos (`bedrockpanel-pgdata` vs `bedrockpanel-pgdata-prod`).

### 9.2 `Found orphan containers (minecraft-bedrock) for this project`

Es informativo, no un error: el contenedor del servidor Minecraft
(`docker-compose.yml` base, proyecto por defecto del directorio) comparte proyecto
con la pila del panel. No se borra nada. Si se quiere silenciar, usar
`--remove-orphans` con cuidado (eliminaría el contenedor Minecraft; sus datos viven
en el bind-mount `./data` y se recrea con `docker compose up -d`).