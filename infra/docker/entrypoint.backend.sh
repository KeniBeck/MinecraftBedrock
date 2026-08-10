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
CONCURRENCY="${BEDROCK_PANEL_WEB_CONCURRENCY:-}"
if [ -z "$CONCURRENCY" ]; then
    # 2 workers por CPU, entre 1 y 8.
    CPUS=$(nproc)
    CONCURRENCY=$((CPUS * 2))
    [ "$CONCURRENCY" -lt 1 ] && CONCURRENCY=1
    [ "$CONCURRENCY" -gt 8 ] && CONCURRENCY=8
fi

echo "[entrypoint] Arrancando uvicorn con $CONCURRENCY worker(s)..."
exec ./.venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers="$CONCURRENCY"