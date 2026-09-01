#!/usr/bin/env sh
# Entrypoint del backend BedrockPanel en producción.
#
# 1. Espera a que Postgres acepte conexiones (sondeo con psycopg, ya instalado
#    en el venv; no se instala un cliente de Postgres aparte).
# 2. Aplica las migraciones Alembic (`alembic upgrade head`).
# 3. Arranca uvicorn con los workers derivados de CPU (respetando
#    `BEDROCK_PANEL_WEB_CONCURRENCY` si está fijado).
#
# Se ejecuta dentro de `apps/backend` con el venv instalado.

set -e

DAEMON_URL="${BEDROCK_PANEL_DATABASE_URL:-postgresql+psycopg://panel:panel@postgres:5432/panel}"

# ---- pgres_ready: sondea la conexión a Postgres con psycopg ----------------- #
pgres_ready() {
    ./.venv/bin/python - "$DAEMON_URL" <<'PY' 2>/dev/null
import importlib, sys
url = sys.argv[1]
# psycopg no entiende el sufijo SQLAlchemy "+psycopg".
url = url.replace("+psycopg", "", 1) if "+psycopg" in url else url
psycopg = importlib.import_module("psycopg")
try:
    with psycopg.connect(url) as conn:
        conn.execute("select 1")
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
    return $?
}

# ---- 1. Espera por Postgres ------------------------------------------------ #
# Postgres NO se instala como cliente; se usa psycopg (ya en el venv de la app)
# para sondear la conexión a través de la misma URL de SQLAlchemy.
echo "[entrypoint] Esperando por Postgres..."
tries=0
until pgres_ready; do
    tries=$((tries + 1))
    if [ "$tries" -ge 30 ]; then
        echo "[entrypoint] Postgres no aceptó conexiones tras 30 intentos. Abortando."
        exit 1
    fi
    echo "[entrypoint] Postgres aún no está listo (intento $tries/30)..."
    sleep 2
done

# ---- 2. Migraciones Alembic ------------------------------------------------ #
echo "[entrypoint] Aplicando migraciones Alembic..."
./.venv/bin/alembic upgrade head

# ---- 3. Uvicorn ------------------------------------------------------------- #
# IMPORTANTE — Tiempo real y workers:
#   El panel es un sistema de tiempo real STATEFUL en proceso: el bus de eventos
#   (InProcessEventBus), el registro de conexiones WebSocket (ConnectionManager),
#   los streams de consola y los pollers viven en la memoria de UN solo proceso.
#   Con `--workers>1` cada worker es un proceso independiente: la conexión WS del
#   navegador cae en un worker y las difusiones/eventos ocurren en otro, por lo
#   que consola en vivo, notificaciones, sync de mundos y el scheduler dejan de
#   funcionar (además el reloj del scheduler se duplicaría N veces).
#
#   Dev corre 1 worker (`--reload`); en producción el default es TAMBIÉN 1 worker.
#   `BEDROCK_PANEL_WEB_CONCURRENCY` sigue existiendo SOLO como override para casos
#   avanzados; >1 requiere externalizar el bus (p. ej. Redis pub/sub) — ver
#   docs/troubleshooting-tiempo-real-produccion.md.
CONCURRENCY="${BEDROCK_PANEL_WEB_CONCURRENCY:-1}"
if [ "$CONCURRENCY" -ne 1 ] 2>/dev/null; then
    echo "[entrypoint] ADVERTENCIA: BEDROCK_PANEL_WEB_CONCURRENCY=$CONCURRENCY (>1)."
    echo "[entrypoint] Con varios workers el estado en memoria (WebSockets, consola,"
    echo "[entrypoint] notificaciones, scheduler) NO es compartido y el tiempo real se rompe."
    echo "[entrypoint] Vea docs/troubleshooting-tiempo-real-produccion.md."
fi

echo "[entrypoint] Arrancando uvicorn con $CONCURRENCY worker(s)..."
exec ./.venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers="$CONCURRENCY"