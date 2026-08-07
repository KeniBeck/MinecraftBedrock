# BedrockPanel

Panel web moderno para administrar servidores Minecraft Bedrock sobre Docker.

Monorepo modular según el Technical Design Document v0.1:

- `apps/backend` — FastAPI (monolith modular) en Python 3.13.
- `apps/frontend` — SPA React + TypeScript + Vite (pendiente).
- `packages` — contratos compartidos frontend/backend (opcional).
- `docs` — TDD, Implementation Blueprint, ADR y análisis de la imagen.
- `infra` — Dockerfiles, compose y scripts.
- `deploy` — systemd y ejemplos VPS.
- `tests` — pruebas de integración/e2e (top-level).

## Backend (desarrollo)

```bash
cd apps/backend
uv sync
uv run uvicorn app.main:app --reload
```

La raíz responde `GET /` con `{name, version, status: "ok"}` y la documentación
interactiva vive en `/docs`. Documentación de referencia: `docs/technical-design.md`
y `docs/implementation-blueprint.md`.

### Comportamiento de arranque del servidor Bedrock

Cuando el volumen montado en `/data` ya contiene un binario local de Bedrock
(`bedrock_server-<version>` o `bedrock_server`), el runtime usa
`VERSION=EXISTING` en lugar de intentar descargarlo de nuevo. Esto evita que el
contenedor falle por problemas de descarga/SSL al arrancar con una instalación ya
presente.

### Exposición en nube, proxy o túnel

El servidor Bedrock sigue siendo funcional en un despliegue local o en la nube
siempre que el tráfico se exponga de forma compatible con el protocolo del juego:

- Bedrock usa UDP en los puertos `19132/19133` para gameplay y descubrimiento LAN.
- Si se usa un proxy o túnel, este debe conservar el tráfico UDP sin convertirlo
  en un flujo HTTP/TCP-only; un proxy web estándar no es suficiente para
  gameplay real.
- Para exposición pública, lo más robusto es un túnel o forwarding que soporte
  UDP, o bien un despliegue con IP pública y reenvío directo de puertos.
- El panel deja por defecto `ONLINE_MODE=false` y `ENABLE_LAN_VISIBILITY=true`
  para que el servidor funcione en modo local/privado y sea más fácil de
  conectar desde la red local.

Si el arranque o la carga del mundo se vuelve lenta, se puede aumentar el
recurso asignado al contenedor desde los settings del backend:
`server.resources.memory_mb` y `server.resources.cpus`. Los valores por defecto
actuales son `2048` MB y `2.0` CPUs.
