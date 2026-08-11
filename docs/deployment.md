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

```bash
# detener (mantiene datos)
docker compose -f docker-compose.prod.yml stop

# re-arrancar
docker compose -f docker-compose.prod.yml start

# parar y borrar contenedores y red (NO borra el volumen de Postgres)
docker compose -f docker-compose.prod.yml down

# parar y borrar TAMBIÉN el volumen de datos de Postgres (¡destructivo!)
docker compose -f docker-compose.prod.yml down -v
```

### Reconstruir tras cambios de código

```bash
docker compose -f docker-compose.prod.yml up -d --build
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
| `BEDROCK_PANEL_WEB_CONCURRENCY` | 2×NCPU (máx 8) | Workers de uvicorn |
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
- **Workers**: FastAPI inicia 1 worker con `uvicorn` en dev; en prod el entrypoint
  usa NCPU. Si el estado en memoria (streams, buffers WS) entre procesos no es
  un requisito, los workers son seguros porque la persistencia es Postgres.
- Para un despliegue más aislado puede fijarse `network_mode` o exponer solo el
  puerto del frontend y mantener el backend interno (ya es el caso por defecto:
  solo `frontend` publica puerto al host).