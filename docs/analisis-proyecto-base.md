# Análisis técnico del proyecto base: `itzg/docker-minecraft-bedrock-server`

> Documento de análisis y arquitectura para el desarrollo de un panel web moderno de
> administración de servidores Minecraft Bedrock sobre Docker.
>
> Fecha: 2026-08-05 · Objetivo de este documento: entender completamente la imagen
> oficial antes de escribir cualquier línea de código.

---

## Índice

1. [Resumen del proyecto](#1-resumen-del-proyecto)
2. [Arquitectura interna de la imagen](#2-arquitectura-interna-de-la-imagen)
3. [Componentes de Docker](#3-componentes-de-docker)
4. [Flujo de ejecución](#4-flujo-de-ejecución)
5. [Variables de entorno (catálogo completo)](#5-variables-de-entorno-catálogo-completo)
6. [Administración de un servidor](#6-administración-de-un-servidor)
7. [Comunicación: protocolo, RCON y consola](#7-comunicación-protocolo-rcon-y-consola)
8. [Limitaciones de la imagen](#8-limitaciones-de-la-imagen)
9. [Riesgos](#9-riesgos)
10. [Oportunidades](#10-oportunidades)
11. [Posibles extensiones](#11-posibles-extensiones)
12. [Recomendaciones para el panel profesional](#12-recomendaciones-para-el-panel-profesional)

---

## 1. Resumen del proyecto

`itzg/docker-minecraft-bedrock-server` es la imagen Docker de referencia (MIT,
~1.8k stars, 263 commits, mantenida por *itzg*) para ejecutar el **Bedrock
Dedicated Server (BDS)** de Mojang en un contenedor.

Características esenciales que condicionan todo lo demás:

- **El software BDS NO está empaquetado en la imagen.** Se descarga de los
  servidores de Mojang **en cada arranque** si `VERSION=LATEST` (valor por defecto).
  Por eso las *releases* de la imagen son independientes de las *releases* de Mojang.
- El software BDS oficial es **solo x86_64**. En arquitecturas `arm64` la imagen usa
  **box64** (emulación binaria por traducción de syscalls), más lenta que nativa.
- Todo el estado se guarda en el volumen `/data`. El contenedor es **efímero**:
  el dato es el volumen, no el contenedor. Esto es lo que hace viable construir un
  panel encima: el contenedor se puede recrear cuantas veces se quiera.
- La imagen es una **familia de binarios Go propios** que la envuelven:
  `entrypoint-demoter` (PID 1, graceful shutdown + democión de UID/GID),
  `mc-server-runner` (wrapper del proceso y consola remota),
  `mc-monitor` (healthcheck y métricas) y `set-property` (mapeo env → server.properties).

Tags de imagen: `latest`, `stable` y releases semánticas (`2026.4.1`).
Disponible en Docker Hub y GHCR.

---

## 2. Arquitectura interna de la imagen

### 2.1 Cadena de procesos

```
PID 1  /opt/demoter-entry.sh  (bash, wrapper trivial)
   └─ exec entrypoint-demoter  (Go, PID 1, se ejecuta como root al inicio)
        │   --match /data            → deduce UID/GID del propietario del volumen
        │   --stdin-on-term stop     → en SIGTERM escribe "stop" en el stdin del servidor
        │   --stdin-on-term-announce + --stdin-on-term-delay (opcional, STOP_SERVER_ANNOUNCE_DELAY)
        │
        └─ exec /opt/bedrock-entry.sh  (bash, ya con UID/GID demotidos)
             │   (descarga/actualiza BDS, escribe permissions/allowlist/variables,
             │    genera server.properties vía set-property, LD_PRELOAD bds-ipv6fix)
             │
             └─ exec mc-server-runner  (Go)
                  │   [--remote-console]  → servidor SSH en :2222 (si ENABLE_SSH)
                  │
                  └─ bedrock_server-<VERSION>
                       (en arm64: mc-server-runner box64 ./bedrock_server-<VERSION>)
```

Puntos clave de esta cadena:

- **`entrypoint-demoter`** resuelve el problema clásico de volúmenes montados: el
  contenedor arranca como root, mira quién es dueño de `/data` y "degrada" (demote)
  el proceso hijo a ese usuario/grupo. Alternativamente se fuerza con `UID`/`GID`.
  Si ya se ejecuta como no-root, no degrada.
- **`--match /data`** es lo que hace que el proceso del servidor corra con los
  permisos del volumen. Es la razón por la que un bind mount con propietario
  incorrecto produce fallos al arrancar.
- **SIGTERM**: `entrypoint-demoter` intercepta y escribe `stop` en el stdin del
  proceso BDS (cierre limpio con guardado del mundo). `mc-server-runner` también
  tiene lógica de `stop`, pero demoter "gana" por estar en PID 1.
- **Doble arranque en arm64**: `mc-server-runner` lanza `box64` como wrapper del
  binario real, por eso `send-command` detecta el proceso por `/proc/*/exe`.

### 2.2 Descarga y detección de versiones

El arranque resuelve la URL de descarga en este orden:

| Modo (`VERSION`) | Fuente de la URL de descarga |
|---|---|
| `LATEST` (default) | API `https://net.web.minecraft-services.net/api/v1.0/download/links` filtrando `downloadType == serverBedrockLinux`; fallback a `PROCESSED_DOWNLOAD_LINKS_URL` (JSON de `kittizz/bedrock-server-downloads` en GitHub) |
| `PREVIEW` | Misma API con `downloadType == serverBedrockPreviewLinux` |
| `1.2.3.4` (versión concreta) | Se obtiene la URL base y se reemplaza el número de versión dentro de la URL (`replaceVersionInUrl`) |
| `EXISTING` | No descarga: usa `bedrock_server-{version}` o `bedrock_server` ya presentes en `/data` |
| `DIRECT_DOWNLOAD_URL` | Override total: se descarga exactamente esa URL |

- La versión concreta se **extrae del nombre del zip** (`bedrock-server-(.*).zip`).
- `PREVIEW=true` fuerza el tratamiento como preview para versiones concretas.
- `DOWNLOAD_LINKS_URL` y `DOWNLOAD_SECONDARY_LINKS_URL` permiten sobreescribir la API
  (útil si Minecraft cambia el endpoint). `USE_MINECRAFT_SERVICES=false` salta la API
  y usa directamente el JSON procesado de GitHub.

### 2.3 Actualizaciones

**El upgrade ocurre en el arranque.** Con `VERSION=LATEST`, cada reinicio del
contenedor comprueba si hay una versión más nueva y, si la hay, la descarga.

Proceso de instalación/upgrade (dentro de `/data`):

1. Descarga el zip a `$DOWNLOAD_DIR` (por defecto `/data/.downloads`).
2. Borra solo lo que *debe* regenerarse: `bedrock_server`, `bedrock_server-*`,
   `*.so`, `release-notes.txt`, `bedrock_server_how_to.html`,
   `valid_known_packs.json`, `premium_cache`.
3. Hace **backup de paquetes/definiciones** en `backup-pre-<NUEVA_VERSION>/`:
   - `behavior_packs`, `resource_packs`, `definitions`, `minecraftpe`, `structures`,
     `treatments`, `world_templates` se copian/mueven ahí.
   - Dentro del backup **se eliminan los packs de Mojang** (`chemistry`, `vanilla`,
     `editor`, `experimental`) para que el zip instale los nuevos.
   - Los **packs de usuario se conservan** (se copian al backup y `unzip -n` no
     los sobrescribe en el árbol activo).
4. `unzip -q -n` (no sobrescribe) del zip nuevo.
5. `chmod +x` y **renombra el binario** a `bedrock_server-<VERSION>`, permitiendo que
   convivan varios binarios en `/data`.
6. Poda backups viejos: conserva `PACKAGE_BACKUP_KEEP` (default `2`).

Implicaciones para el panel:

- **Actualizar = cambiar `VERSION` y recrear el contenedor** (o simplemente reiniciar
  si ya está en `LATEST`).
- Los directorios `backup-pre-<version>` son la red de seguridad que crea la propia
  imagen, pero solo cubren packs/definiciones, **no el mundo**.

### 2.4 Healthcheck

```
HEALTHCHECK --start-period=1m CMD /usr/local/bin/mc-monitor status-bedrock --host 127.0.0.1 --port $SERVER_PORT
```

- Usa el **ping no conectado de RakNet** (protocolo de estado de Bedrock) por **UDP**
  sobre el puerto de juego del contenedor.
- `$SERVER_PORT` se resuelve desde el entorno del contenedor, así que si cambias el
  puerto, el healthcheck lo sigue (siempre que se use la variable y no se edite
  `server.properties` a mano).
- `--start-period=1m` da margen para la descarga inicial (que puede tardar).

### 2.5 Carpetas y archivos en `/data`

Layout real de un BDS 1.26.x (verificado contra la instancia local):

| Ruta | Naturaleza | Observaciones |
|---|---|---|
| `bedrock_server-<version>` | Binario oficial | Se reemplaza en cada upgrade |
| `*.so`, `libMinecraft.Server.Lib.a` | Librerías de Mojang | Se reemplazan en cada upgrade |
| `server.properties` | **Config de usuario (persistente)** | Se reescribe al arrancar desde las env vars |
| `allowlist.json` | **Persistente** | `[{"name":..., "xuid":...}]` |
| `permissions.json` | **Persistente** | `[{"permission":..., "xuid":...}]` |
| `worlds/<level-name>/` | **Mundo (persistente)** | `level.dat`, `level.dat_old`, `levelname.txt`, `db/` (LevelDB), `world_behavior_packs.json`, `world_resource_packs.json` |
| `behavior_packs/`, `resource_packs/` | Packs de usuario + vanilla | Los packs vanilla (`vanilla`, `chemistry`, `editor`, `experimental`, `vanilla_cube`) se regeneran |
| `definitions/`, `minecraftpe/`, `structures/`, `treatments/`, `world_templates/` | Datos de Mojang | Se regeneran desde el zip en cada upgrade (lo anterior se mueve a `backup-pre-*`) |
| `config/default/variables.json` | Variables de script (persistente) | Generado por `VARIABLES` |
| `config/default/permissions.json` | Permisos de scripts (persistente) | Distinto de `permissions.json` raíz |
| `backup-pre-<version>/` | Backups de packs previos a upgrade | Prune según `PACKAGE_BACKUP_KEEP` |
| `premium_cache/` | Caché | Se elimina en cada upgrade |
| `Dedicated_Server.txt`, `packet-statistics.txt`, `packetlimitconfig.json`, `profanity_filter.wlist`, `release-notes.txt`, `bedrock_server_how_to.html`, `valid_known_packs.json`, `data/`, `development_*_packs/` | Archivos del software BDS | Se regeneran/reemplazan en upgrade |
| `.downloads/`, `.tmp/` | Temporales de descarga | Carpeta HOME del proceso |
| `.hostKey.pem` | Clave host SSH (persistente) | Solo si `ENABLE_SSH`; debe persistir |
| `.remote-console.env`, `.remote-console.yaml` | Credenciales de consola remota | Solo si `ENABLE_SSH` |

### 2.6 Archivos que NUNCA deben modificarse

- `bedrock_server-*`, `*.so`, `libMinecraft.Server.Lib.a` — se borran y regeneran en
  el upgrade; modificarlos rompe el servidor o provoca parches incoherentes.
- Packs de Mojang dentro de `behavior_packs/` y `resource_packs/` (`vanilla*`,
  `chemistry`, `editor`, `experimental`) — la imagen los elimina en el upgrade.
- `definitions/`, `minecraftpe/`, `structures/`, `treatments/`, `world_templates/`,
  `premium_cache`, `valid_known_packs.json`, `release-notes.txt`,
  `bedrock_server_how_to.html` — se regeneran desde el zip.
- Ficheros de la capa de imagen: `/opt/*.sh`, `/opt/demoter-entry.sh`,
  `/usr/local/bin/*`, `/etc/bds-property-definitions.json`.

---

## 3. Componentes de Docker

### 3.1 Dockerfile (resumen)

| Fase/elemento | Qué hace |
|---|---|
| `FROM debian` | Base mínima; paquetes instalados: `curl`, `openssl`, `unzip`, `jq` |
| `TARGETOS/TARGETARCH/TARGETVARIANT` | Build multiarquitectura (amd64 nativo, arm64 con box64) |
| `easy-add` | Instalador oficial de binarios de itzg |
| `entrypoint-demoter` 0.5.1 | PID 1: graceful shutdown, democión de usuario |
| `set-property` 0.1.6 | Aplica env vars a `server.properties` usando `property-definitions.json` |
| `mc-monitor` 0.17.0 | Healthcheck y métricas/estado |
| `mc-server-runner` 1.15.1 | Wrapper del proceso + consola remota SSH/WebSocket |
| `bds-ipv6fix.so` | Shim que parchea BDS para dual-stack en el mismo puerto |
| `COPY *.sh /opt/`, `COPY bin/* /usr/local/bin/` | Entrypoints y `send-command` |
| `COPY property-definitions.json` | Catálogo env → propiedad de server.properties |
| `ENV VERSION=LATEST SERVER_PORT=19132 SERVER_PORT_V6=19133 ENABLE_BDS_V6BIND_FIX=false` | Defaults |
| `HEALTHCHECK ... mc-monitor status-bedrock` | Estado real del juego |
| `EXPOSE 19132/udp 19133/udp` | Puertos de juego |
| `VOLUME /data` · `WORKDIR /data` | Persistencia y cwd del proceso |

### 3.2 Entrypoints

- **`/opt/demoter-entry.sh`** (ENTRYPOINT): construye los argumentos de
  `entrypoint-demoter`. Por defecto `--match /data --debug --stdin-on-term stop`.
  Si `STOP_SERVER_ANNOUNCE_DELAY` es un número positivo, añade
  `--stdin-on-term-announce` y `--stdin-on-term-delay`.
- **`/opt/bedrock-entry.sh`**: lógica real de arranque (ver [Flujo](#4-flujo-de-ejecución)).
- **`/usr/local/bin/send-command`**: escribe comandos al stdin del proceso BDS vía
  `/proc/<pid>/fd/0`. Usado con `docker exec <contenedor> send-command <cmd>`.

### 3.3 Variables de entorno del contenedor

Aplicadas por `docker run -e` / compose `environment`. Solo tienen efecto **en la
creación** del contenedor (el entrypoint las lee una vez al arrancar).

### 3.4 Volúmenes

- **Único volumen: `/data`.** Ahí vive BDS completo + config + mundos + backups.
- Se recomienda bind mount (para que el panel acceda a los ficheros) o named volume
  (recomendado en producción, requiere `chown` previo si se quiere no-root).
- Si el contenedor corre con un usuario específico, el volumen debe pertenecer a ese
  usuario (`UID`/`GID` o propietario de `/data`).

### 3.5 Redes y puertos

| Puerto | Protocolo | Uso |
|---|---|---|
| 19132 | UDP | Juego IPv4 (`SERVER_PORT`) |
| 19133 | UDP | Juego IPv6 (`SERVER_PORT_V6`) |
| 2222 | TCP | Consola remota SSH (`ENABLE_SSH=true`, usando `RCON_PASSWORD`) |
| 80 | TCP/WS | Consola websocket de `mc-server-runner` (**no activada por defecto**) |

- La imagen **no define ninguna red**; usa la red bridge por defecto o la que el
  panel asigne. La comunicación con `mc-monitor`/healthcheck es `127.0.0.1` intra-contenedor.
- `enable-lan-visibility=true` (default) hace que BDS **también** escuche en los
  puertos por defecto (19132/19133) para descubrimiento LAN, **aunque cambies los
  puertos**. Es una fuente clásica de conflictos en multi-instancia.

### 3.6 Healthcheck

`mc-monitor status-bedrock` (ver §2.4). Estados: `starting` durante descarga
(`--start-period=1m`), luego `healthy`/`unhealthy` según responda el ping UDP.

---

## 4. Flujo de ejecución

Secuencia completa del arranque de un contenedor:

1. **demoter-entry.sh** evalúa `STOP_SERVER_ANNOUNCE_DELAY` y construye los flags de
   `entrypoint-demoter`, luego `exec` a este.
2. **entrypoint-demoter** (root): determina UID/GID desde `UID`/`GID` o del
   propietario de `/data` (`--match /data`) y ejecuta `bedrock-entry.sh` con ese usuario.
3. **bedrock-entry.sh**:
   a. Configura `HOME=/data`, `TMPDIR=/data/.tmp`, `LD_LIBRARY_PATH=.`.
   b. Imprime `Image info` (`/etc/image.properties`).
   c. Valida `EULA=TRUE` (si no, **aborta**).
   d. Si `DIRECT_DOWNLOAD_URL`, la usa; si no, resuelve URL según `VERSION`
      (API Minecraft Services → fallback JSON GitHub → `replaceVersionInUrl`).
   e. Determina `SERVER=bedrock_server-<version>`; si no existe el binario,
      descarga, limpia binarios/docs, hace `backup-pre-<version>` de packs, `unzip -n`,
      `chmod`, renombra y poda backups viejos.
   f. Si `MC_PACK`: descomprime/imprime packs (behavior/resource) y/o mundo en
      `worlds/<LEVEL_NAME>`, con `FORCE_WORLD_COPY`/`FORCE_PACK_COPY`.
   g. Si `OPS`/`MEMBERS`/`VISITORS`: resuelve XUIDs (gamertag → mcprofile.io) y
      escribe `permissions.json`.
   h. Si `ALLOW_LIST_USERS`/`WHITE_LIST_USERS`: escribe `allowlist.json` y fuerza
      `ALLOW_LIST=true`.
   i. Si `VARIABLES`: escribe `config/default/variables.json`.
   j. Elimina la línea `white-list=` de `server.properties` y ejecuta
      `set-property --file server.properties --bulk /etc/bds-property-definitions.json`
      para aplicar **todas** las env vars de propiedades.
   k. Si `ENABLE_BDS_V6BIND_FIX=true` y existe el `.so`: `LD_PRELOAD=bds-ipv6fix.so`.
   l. Si `ENABLE_SSH=true`: genera/usa `RCON_PASSWORD`, escribe
      `.remote-console.env/.yaml`, añade `--remote-console` a mc-server-runner.
   m. `exec mc-server-runner [--remote-console] box64 ./bedrock_server-<version>`
      (en arm64) o `./bedrock_server-<version>`.
4. **mc-server-runner**: arranca el proceso BDS, forwardea stdin, y difunde
   stdout/stderr a las sesiones remotas (SSH si está habilitado).
5. **BDS**: genera el mundo (si no existe), escucha UDP 19132/19133, y el
   **healthcheck** lo da por sano.
6. **SIGTERM** → `entrypoint-demoter` escribe `stop` (con anuncio opcional) → BDS
   guarda y cierra limpio → contenedor termina con código 0.

---

## 5. Variables de entorno (catálogo completo)

### 5.1 Variables específicas del contenedor

| Variable | Tipo | Default | Descripción | Cuándo usarla |
|---|---|---|---|---|
| `EULA` | string | — (obligatoria) | `TRUE` para aceptar el EULA de Minecraft | Siempre, obligatoria |
| `VERSION` | string | `LATEST` | Versión de BDS. `LATEST`, `PREVIEW`, `EXISTING` o versión concreta | Para fijar/pinear versiones o auto-upgrade |
| `PREVIEW` | bool | `false` | Marca como preview una versión concreta | Con `VERSION=<preview>` |
| `UID` | int | propietario de `/data` | UID del proceso del servidor | Cuando el volumen es de otro usuario |
| `GID` | int | propietario de `/data` | GID del proceso del servidor | Igual |
| `TZ` | string | — | Zona horaria de logs (ej. `America/New_York`) | Para logs correctos |
| `PACKAGE_BACKUP_KEEP` | int | `2` | Nº de `backup-pre-*` a conservar | Para controlar disco |
| `DIRECT_DOWNLOAD_URL` | URL | — | URL directa del zip `bedrock-server-VERSION.zip` | CI/CD o si la API falla |
| `DOWNLOAD_PROGRESS` | bool | `false` | Barra de progreso en la descarga | Depuración/observabilidad |
| `ENABLE_SSH` | bool | `false` | Consola remota SSH en :2222 (genera `RCON_PASSWORD`) | Para acceso remoto a consola |
| `ENABLE_BDS_V6BIND_FIX` | bool | `false` | Permite el mismo puerto IPv4+IPv6 con `bds-ipv6fix` | Dual-stack con un solo puerto |
| `MC_PACK` | path | — | Importa al arranque un `.mcpack`/`.mcworld`/`.mcaddon`/zip o directorio (packs y/o mundo) | Importar mundos/packs en creación |
| `FORCE_WORLD_COPY` | bool | `false` | Con `MC_PACK`, reemplaza el mundo en cada arranque | Desplegados repetibles |
| `FORCE_PACK_COPY` | bool | `false` | Con `MC_PACK`, reemplaza packs del mismo nombre en cada arranque | Desplegados repetibles |
| `STOP_SERVER_ANNOUNCE_DELAY` | int (s) | — (off) | Anuncio de apagado y espera antes de `stop` en SIGTERM | Avisar a jugadores antes de parar |
| `STOP_SERVER_ANNOUNCE` | string | `say Server shutting down in %delay% seconds` | Línea de anuncio (token `%delay%`) | Personalizar aviso |
| `OPS` | string | — | Operadores (XUID o gamertag, separados por coma/salto de línea) | Gestión de operadores |
| `MEMBERS` | string | — | Miembros (`permission=member`) | Gestión de permisos |
| `VISITORS` | string | — | Visitantes (`permission=visitor`) | Gestión de permisos |
| `ALLOW_LIST_USERS` | string | — | Entradas allowlist `name:xuid` | Allowlist al crear/actualizar |
| `WHITE_LIST_USERS` | string | — | Alias obsoleto de `ALLOW_LIST_USERS` | Compatibilidad |
| `RESOLVE_XUID_API_URL` | URL | `https://mcprofile.io/api/v1/bedrock/gamertag` | API para resolver gamertag → XUID | Entornos offline/alternativos |
| `RCON_PASSWORD` | string | *aleatoria (ver nota)* | Contraseña SSH/websocket de consola remota | Fijar credencial de consola |
| `VARIABLES` | string/JSON | — | Variables de script → `config/default/variables.json` | Servidores con addons script |

> **Nota (pendiente de verificación)**: el default de `RCON_PASSWORD` figura arriba como
> *aleatoria*, pero el riesgo 9 (§9) indica que `mc-server-runner` usa *"minecraft"* si no
> se define. Contradicción detectada en la revisión de documentos; el valor real debe
> confirmarse contra la imagen/README antes de implementar. En la instancia local SSH no
> está habilitado (no hay `.remote-console.*`), así que no es verificable desde `/data`.

### 5.2 Variables internas (con default dentro de `bedrock-entry.sh`)

| Variable | Default | Función |
|---|---|---|
| `DOWNLOAD_DIR` | `$PWD/.downloads` | Carpeta temporal de descargas |
| `USE_MINECRAFT_SERVICES` | `true` | Usar la API de Minecraft Services para el lookup |
| `DOWNLOAD_LINKS_URL` | `https://net.web.minecraft-services.net/api/v1.0/download/links` | API primaria |
| `DOWNLOAD_SECONDARY_LINKS_URL` | idem | API secundaria |
| `PROCESSED_DOWNLOAD_LINKS_URL` | `https://raw.githubusercontent.com/kittizz/bedrock-server-downloads/.../bedrock-server-downloads.json` | Fallback de links |
| `USE_BOX64` | `true` | Emular BDS con box64 en arm64 |
| `DEBUG_CURL` | `false` | Verbose en curl |
| `DEBUG` | — | `TRUE` activa `set -x` y logs de entorno |
| `LEVEL_NAME` | `Bedrock level` | También es propiedad de servidor (ver 5.4) |

### 5.3 Variables de permisos y allowlist en runtime

- Los gamertags se resuelven a XUID **en el arranque** vía API externa. Si el
  servicio falla, el valor original se deja como está.
- `permissions.json` solo se escribe si alguna de `OPS/MEMBERS/VISITORS` está definida.
- `allowlist.json` solo se escribe si `ALLOW_LIST_USERS`/`WHITE_LIST_USERS` están
  definidas; en ese caso se fuerza `ALLOW_LIST=true` en `server.properties`.

### 5.4 Variables de propiedades de servidor

Cada variable genera la propiedad equivalente en `server.properties` mediante
`set-property`. Valores `allowed` = validación de la imagen; `mappings` = alias
aceptados (p. ej. `GAMEMODE=0` → `survival`).

| Variable | Propiedad | Tipo/Valores permitidos | Descripción |
|---|---|---|---|
| `SERVER_NAME` | `server-name` | string (sin `;`) | Nombre visible en el servidor |
| `GAMEMODE` | `gamemode` | `survival`,`creative`,`adventure` (+0/1/2) | Modo de juego de jugadores nuevos |
| `FORCE_GAMEMODE` | `force-gamemode` | bool | Obligar modo de juego sobre el guardado |
| `DIFFICULTY` | `difficulty` | `peaceful`,`easy`,`normal`,`hard` (+0-3) | Dificultad |
| `ALLOW_CHEATS` | `allow-cheats` | bool | Habilitar comandos |
| `MAX_PLAYERS` | `max-players` | int > 0 | Jugadores máximos |
| `ONLINE_MODE` | `online-mode` | bool | Requiere autenticación Xbox Live |
| `WHITE_LIST` | `white-list` | bool | **Obsoleto** → usar `ALLOW_LIST` |
| `ALLOW_LIST` | `allow-list` | bool | Exigir allowlist.json |
| `SERVER_PORT` | `server-port` | int 1-65535 | Puerto UDP IPv4 |
| `SERVER_PORT_V6` | `server-portv6` | int 1-65535 | Puerto UDP IPv6 |
| `ENABLE_LAN_VISIBILITY` | `enable-lan-visibility` | bool | Descubrimiento LAN (bind de puertos por defecto) |
| `VIEW_DISTANCE` | `view-distance` | int ≥ 5 | Distancia de chunks |
| `TICK_DISTANCE` | `tick-distance` | int 4-12 | Chunks tickeados |
| `PLAYER_IDLE_TIMEOUT` | `player-idle-timeout` | int ≥ 0 | Minutos de inactividad para expulsar (0=∞) |
| `MAX_THREADS` | `max-threads` | int | Hilos (0 = todos) |
| `LEVEL_NAME` | `level-name` | string | Nombre de carpeta del mundo en `worlds/` |
| `LEVEL_SEED` | `level-seed` | string | Semilla |
| `LEVEL_TYPE` | `level-type` | `DEFAULT`,`FLAT`,`LEGACY` | Tipo de mundo |
| `DEFAULT_PLAYER_PERMISSION_LEVEL` | `default-player-permission-level` | `visitor`,`member`,`operator` | Permiso de nuevos jugadores |
| `TEXTUREPACK_REQUIRED` | `texturepack-required` | bool | Forzar descarga de texture packs |
| `CONTENT_LOG_FILE_ENABLED` | `content-log-file-enabled` | bool | Log de contenido a fichero |
| `CONTENT_LOG_LEVEL` | `content-log-level` | `verbose`,`info`,`warning`,`error` | Nivel de log de contenido |
| `CONTENT_LOG_CONSOLE_OUTPUT_ENABLED` | `content-log-console-output-enabled` | bool | Log de contenido a stdout |
| `COMPRESSION_THRESHOLD` | `compression-threshold` | int 0-65535 | Umbral de compresión de red |
| `COMPRESSION_ALGORITHM` | `compression-algorithm` | `zlib`,`snappy` | Algoritmo de compresión |
| `SERVER_AUTHORITATIVE_MOVEMENT` | `server-authoritative-movement` | `server-auth`,`client-auth`,`server-auth-with-rewind` (true/false mapeado) | Movimiento autoritativo |
| `PLAYER_POSITION_ACCEPTANCE_THRESHOLD` | `player-position-acceptance-threshold` | float | Tolerancia de posición |
| `PLAYER_MOVEMENT_SCORE_THRESHOLD` | `player-movement-score-threshold` | float | Umbral score de movimiento |
| `PLAYER_MOVEMENT_ACTION_DIRECTION_THRESHOLD` | `player-movement-action-direction-threshold` | float 0-1 | Tolerancia dirección de ataque |
| `PLAYER_MOVEMENT_DISTANCE_THRESHOLD` | `player-movement-distance-threshold` | float | Umbral de distancia |
| `PLAYER_MOVEMENT_DURATION_THRESHOLD_IN_MS` | `player-movement-duration-threshold-in-ms` | int | Umbral de duración |
| `CORRECT_PLAYER_MOVEMENT` | `correct-player-movement` | bool | Correcciones de movimiento |
| `SERVER_AUTHORITATIVE_BLOCK_BREAKING` | `server-authoritative-block-breaking` | bool | Rotura de bloques autoritativa |
| `SERVER_AUTHORITATIVE_BLOCK_BREAKING_PICK_RANGE_SCALAR` | `server-authoritative-block-breaking-pick-range-scalar` | float | Alcance de rotura |
| `CHAT_RESTRICTION` | `chat-restriction` | `None`,`Dropped`,`Disabled` | Restricción de chat |
| `DISABLE_PLAYER_INTERACTION` | `disable-player-interaction` | bool | Ignorar interacción entre jugadores |
| `CLIENT_SIDE_CHUNK_GENERATION_ENABLED` | `client-side-chunk-generation-enabled` | bool | Generación de chunks en cliente |
| `BLOCK_NETWORK_IDS_ARE_HASHES` | `block-network-ids-are-hashes` | bool | IDs de bloques con hash |
| `DISABLE_PERSONA` | `disable-persona` | bool | Uso interno |
| `DISABLE_CUSTOM_SKINS` | `disable-custom-skins` | bool | Deshabilitar skins personalizadas |
| `SERVER_BUILD_RADIUS_RATIO` | `server-build-radius-ratio` | `Disabled` o 0.0-1.0 | Radio de construcción servidor |
| `ALLOW_OUTBOUND_SCRIPT_DEBUGGING` | `allow-outbound-script-debugging` | bool | Debugger de scripts saliente |
| `ALLOW_INBOUND_SCRIPT_DEBUGGING` | `allow-inbound-script-debugging` | bool | Debugger de scripts entrante |
| `FORCE_INBOUND_DEBUG_PORT` | `force-inbound-debug-port` | int | Puerto del debugger |
| `SCRIPT_DEBUGGER_AUTO_ATTACH` | `script-debugger-auto-attach` | `disabled`,`connect`,`listen` | Auto-adjuntar debugger |
| `SCRIPT_DEBUGGER_AUTO_ATTACH_CONNECT_ADDRESS` | `script-debugger-auto-attach-connect-address` | string | Dirección `host:port` del debugger |
| `SCRIPT_WATCHDOG_ENABLE` | `script-watchdog-enable` | bool | Watchdog de scripts |
| `SCRIPT_WATCHDOG_ENABLE_EXCEPTION_HANDLING` | `script-watchdog-enable-exception-handling` | bool | Manejo de excepciones del watchdog |
| `SCRIPT_WATCHDOG_ENABLE_SHUTDOWN` | `script-watchdog-enable-shutdown` | bool | Apagado ante excepción no controlada |
| `SCRIPT_WATCHDOG_HANG_EXCEPTION` | `script-watchdog-hang-exception` | bool | Excepción en hang |
| `SCRIPT_WATCHDOG_HANG_THRESHOLD` | `script-watchdog-hang-threshold` | int ms | Umbral de hang (default 10000) |
| `SCRIPT_WATCHDOG_SPIKE_THRESHOLD` | `script-watchdog-spike-threshold` | int | Umbral de spike |
| `SCRIPT_WATCHDOG_SLOW_THRESHOLD` | `script-watchdog-slow-threshold` | int | Umbral de scripts lentos |
| `SCRIPT_WATCHDOG_MEMORY_WARNING` | `script-watchdog-memory-warning` | int MB | Aviso de memoria (default 100) |
| `SCRIPT_WATCHDOG_MEMORY_LIMIT` | `script-watchdog-memory-limit` | int MB | Límite de memoria (default 250) |
| `OP_PERMISSION_LEVEL` | `op-permission-level` | int | Nivel de permiso de ops |
| `EMIT_SERVER_TELEMETRY` | `emit-server-telemetry` | bool | Telemetría |
| `MSA_GAMERTAGS_ONLY` | `msa-gamertags-only` | bool | Solo gamertags MSA |
| `ITEM_TRANSACTION_LOGGING_ENABLED` | `item-transaction-logging-enabled` | bool | Log de transacciones de ítems |

> Nota: en BDS 1.26.x `server.properties` también trae `transport=raknet`,
> `server-authoritative-movement-strict`, `server-authoritative-dismount-strict`,
> `server-authoritative-entity-interactions-strict` y otras propiedades *nuevas que
> todavía no tienen variable de entorno* en la imagen. Para esas, el panel deberá
> editar el fichero directamente (o esperar a que la imagen las incorpore).

---

## 6. Administración de un servidor

### 6.1 Mundos

- **Crear**: `LEVEL_NAME=<nombre>` en la creación; BDS genera `worlds/<nombre>/` con
  `level.dat`, `db/` (LevelDB) y `levelname.txt`.
- **Cambiar de mundo activo**: cambiar `LEVEL_NAME` (env) y **recrear** el contenedor,
  o editar `level-name` en `server.properties` y **reiniciar**. Cada mundo es una
  carpeta independiente; se pueden mantener varios y alternar.
- **Importar un mundo**: subir un `.mcworld` (zip con `level.dat` en la raíz) y
  descomprimirlo en `worlds/<nombre>/` (requiere reinicio), o usar `MC_PACK` +
  `FORCE_WORLD_COPY` en la creación.
- **Borrar/duplicar/renombrar**: operaciones de sistema de ficheros sobre `worlds/`
  (recomendado con el contenedor parado). El nombre visible lo da `levelname.txt`.
- El mundo usa **LevelDB** (carpeta `db`); no es compatible con mundos Java.

### 6.2 Backups

BDS no trae backup integrado. La técnica segura es el **freno de guardado**:

1. `docker exec <ctr> send-command "save hold"` → pausa el guardado del mundo.
2. Esperar confirmación (`save query` devuelve éxito cuando está totalmente pausado;
   en la práctica un pequeño `sleep` es la vía habitual).
3. **Snapshot** de `worlds/<level-name>/` (tar/zstd) sin riesgo de corrupción.
4. `docker exec <ctr> send-command "save resume"` → reanuda el guardado.

Consideraciones:

- Usar `save hold` + `save resume` **siempre con timeout y `save resume` forzado**
  como red de seguridad (si el proceso muere con el mundo "held", el guardado queda
  inconsistentemente pausado).
- Para restauración: **parar el contenedor**, reemplazar `worlds/<level>/`,
  **arrancar de nuevo**.
- La comunidad mantiene soluciones como `kaiede/minecraft-bedrock-backup` que
  implementan exactamente este flujo en un sidecar.

### 6.3 Restauraciones

Parar → reemplazar carpetas del mundo (o de packs/config) desde el backup →
arrancar. Cualquier cambio de ficheros en `server.properties`/`allowlist.json`/
`permissions.json` **solo se aplica en el arranque**.

### 6.4 Operadores / permisos / allowlist

Dos vías, ambas válidas según el caso:

| Vía | Mecanismo | Cuándo se aplica | Uso |
|---|---|---|---|
| **Ficheros** | Escribir `permissions.json` / `allowlist.json` | Al reiniciar | Cambios masivos, XUIDs conocidos |
| **Consola** | `op <name>`, `deop`, `permission set <player> <level>`, `allowlist add/remove/reload` | Inmediato | Cambios puntuales en vivo |

- Formato `permissions.json`: `[{"permission":"operator"|"member"|"visitor","xuid":"..."}]`.
- Formato `allowlist.json`: `[{"ignoresPlayerLimit":false,"name":"...","xuid":"..."}]`.
- Los gamertags necesitan resolución a XUID (API mcprofile.io en la imagen; el panel
  debería hacer lo mismo y cachear).

### 6.5 server.properties

- **Estrategia recomendada para el panel**: el estado de configuración vive en la BBDD
  del panel; al arrancar se traduce a env vars y la imagen genera `server.properties`
  con `set-property`. **Cualquier cambio exige recrear el contenedor** (las env vars
  se fijan en creación; `server.properties` solo se lee al arrancar).
- Alternativa puntual: editar el fichero directamente en el volumen + reiniciar.
  **Precaución**: si la env var correspondiente está definida, en el siguiente arranque
  la imagen la sobrescribe.
- También se puede ejecutar `set-property` a demanda:
  `docker exec <ctr> set-property --file server.properties --bulk ...` (pero el valor
  se aplica igualmente al reiniciar).

### 6.6 Packs (addons, behavior/resource)

1. **Vía ficheros (estándar, funciona con la imagen sin tocar)**: descomprimir el
   `.mcaddon`/`.mcpack` en `behavior_packs/<uuid>/` o `resource_packs/<uuid>/` y
   registrar el pack en `worlds/<mundo>/world_behavior_packs.json` /
   `world_resource_packs.json` con su `pack_id` (uuid del manifest) y `version`.
   Requiere reinicio.
2. **Vía `MC_PACK`** en la creación: la imagen descomprime e instala packs, mundo y
   genera los `world_*_packs.json` automáticamente (incluye detección de `.mcaddon`).
3. `TEXTUREPACK_REQUIRED=true` fuerza la descarga del resource pack en los clientes.
4. Los packs de Mojang (`vanilla*`, `chemistry`, `editor`, `experimental`) **no se
   tocan**: la imagen los regenera en cada upgrade.

### 6.7 Plantillas

- Una **plantilla** es un snapshot de `/data` (config + mundo opcional + packs) listo
  para copiarse como base de una nueva instancia.
- La imagen no tiene un sistema de plantillas; el panel debe implementarlo copiando
  árboles de directorios y ajustando `server.properties`/env (puerto, nivel).
- Alternativa ligera: `MC_PACK` con un `.mctemplate`/`.mcworld` + config por env.

### 6.8 Upgrades

- **Con `VERSION=LATEST`**: reiniciar el contenedor = auto-upgrade (siempre comprueba).
- **Pinear**: `VERSION=<concreta>` y cambiarla manualmente (recrear contenedor).
- Antes de upgradear: **backup del mundo** (el upgrade de la imagen no lo toca, pero
  el formato de mundo de Mojang puede cambiar entre versiones).
- Los `backup-pre-<version>` de la imagen cubren packs/definiciones, no el mundo.

---

## 7. Comunicación: protocolo, RCON y consola

### 7.1 RCON — punto crítico

**El BDS de Mojang NO implementa el protocolo Source RCON.** No existe
`enable-rcon`/`rcon.port`/`rcon.password` en `server.properties` de Bedrock; esas
opciones pertenecen a Java Edition. Cualquier panel que prometa "RCON" para Bedrock
lo implementa realmente **por otra vía**.

En esta imagen, `RCON_PASSWORD` existe únicamente como credencial para la **consola
remota SSH/WebSocket** que monta `mc-server-runner` (por alinearse con la convención
de Java). Implicación directa: **el panel no puede usar librerías de RCON estándar**
contra un BDS vanilla.

### 7.2 Protocolo Bedrock (juego)

- **RakNet sobre UDP.** Sin TCP para el juego.
- Puertos: `19132/udp` IPv4 y `19133/udp` IPv6 por defecto.
- Clientes: consolas, móviles y Windows requieren ese puerto UDP abierto.
- Descubrimiento LAN (`enable-lan-visibility`) responde en los puertos por defecto.
- `ENABLE_BDS_V6BIND_FIX=true` + mismo puerto para ambas familias (Bedrock no
  implementa Happy Eyeballs; sin el fix un cliente IPv6 a 19132 se cuelga).

### 7.3 Consultas de estado (status query)

- BDS responde al **ping no conectado de RakNet** (paquete 0x01) por UDP en el puerto
  de juego, con MOTD, versión de protocolo, versión del juego, jugadores online/máximo
  y gamertag de la sesión.
- Es lo que usa `mc-monitor status-bedrock` (healthcheck) y lo que el panel debería
  implementar en el backend (hay librerías Go/Node listas) para mostrar estado en vivo.
- El **protocolo GameSpy4 Query** (port 19132) está **obsoleto** para Bedrock.

### 7.4 Consola

Mecanismos disponibles con la imagen sin modificar:

| Mecanismo | Entrada | Salida | Notas |
|---|---|---|---|
| `docker exec <ctr> send-command "<cmd>"` | Sí (stdin vía `/proc/<pid>/fd/0`) | Solo en `docker logs` | Simple, un comando a la vez |
| `docker attach` (con `-it`) | Sí | Sí | Requiere stdin_open/tty |
| SSH :2222 (`ENABLE_SSH=true`) | Sí | Sí (streaming) | Password = `RCON_PASSWORD`; bidireccional real |
| WebSocket :80 `/console` | Sí | Sí (+ `logHistory`) | **No activado por defecto** en esta imagen (existe en `mc-server-runner`) |

Para un panel, la vía robusta sin tocar la imagen es: **`send-command` para enviar +
`docker logs` para recibir**. La alternativa interactiva es `ENABLE_SSH` + un cliente
SSH en el backend (el panel fija `RCON_PASSWORD` al crear el contenedor).

---

## 8. Limitaciones de la imagen

1. **Sin RCON nativo.** La consola es por inyección de stdin; "RCON" real no existe
   para BDS vanilla.
2. **`server.properties` solo se lee al arrancar.** Todos los cambios de configuración
   requieren reiniciar (y los cambios vía env requieren recrear el contenedor).
3. **Auto-upgrade implícito.** Con `VERSION=LATEST`, cada reinicio puede cambiar la
   versión del juego sin avisar.
4. **Software oficial x86_64.** En `arm64` se emula con box64: rendimiento reducido
   y compatibilidad limitada (la imagen avisa si no hay fix de IPv6 para esa arch).
5. **Sin plugins ni mods estilo Java.** Solo behavior/resource packs; sin Forge/Fabric.
6. **`enable-lan-visibility` provoca binds en 19132/19133 aunque cambies los puertos**,
   lo que rompe multi-instancia en un mismo host si no se desactiva.
7. **Resolución externa de gamertags** (mcprofile.io) en el arranque para
   `OPS/MEMBERS/VISITORS`; sin red/API, los gamertags no se resuelven.
8. **Dependencias externas de descarga** (API Minecraft Services + JSON de GitHub);
   si ambas fallan, el arranque aborta (mitigación: `DIRECT_DOWNLOAD_URL`).
9. **El healthcheck depende de UDP mapeado** y del ping RakNet; no refleja la salud
   de la CPU o del mundo, solo que responde a pings.
10. **`save hold` es frágil** para backups: si el proceso muere durante el freno,
    hay que forzar `save resume` o el guardado queda pausado.
11. **No hay gestión de múltiples instancias**: puertos, volúmenes y redes son
    responsabilidad de la capa superior (el panel).
12. **BDS tiene fugas de memoria conocidas**; se recomienda reinicio programado
    (downtime implícito).
13. **Cambios de formato de mundo de Mojang** entre versiones: un mundo puede no ser
    compatible hacia atrás; el upgrade no lo advierte.

Operaciones que **requieren reinicio**: cualquier cambio de `server.properties`,
permisos/allowlist por fichero, packs, cambio de mundo activo.
Operaciones que **requieren recrear el contenedor**: cualquier cambio de env vars
(versión, puertos, EULA, etc.) — el dato persiste porque está en el volumen.

---

## 9. Riesgos

1. **Exposición del socket de Docker.** El backend necesitará el socket Docker
   (o un SDK remoto). Es equivalente a root del host. Mitigación: socket aislado,
   API del panel con auth fuerte, nunca exponer el socket a Internet, revisar la
   estrategia de Pterodactyl (daemon aislado + gRPC autenticado).
2. **Recrear contenedor = ventana de downtime.** El panel debe serializar operaciones
   (cambio de env → stop → recreate → start) y exponer estados intermedios.
3. **Perder el mundo.** Toda operación destructiva (borrar mundo, restore, upgrade)
   debe pedir confirmación y hacer backup previo.
4. **Upgrade inesperado de versión** al usar `LATEST`; cambios de formato de mundo.
5. **Escritura concurrente a la consola.** `send-command` y sesiones SSH compiten por
   el stdin; el backend debe serializar.
6. **Permisos del volumen.** Si el panel crea el bind mount con otro UID/GID, el
   proceso BDS falla al arrancar o no puede escribir.
7. **Conflicto de puertos** entre instancias (incluido el bind de
   `enable-lan-visibility`); el panel necesita un asignador de puertos.
8. **Ataques por puerto UDP expuesto** (kick de jugadores, flooding). Rate limiting
   y firewall a nivel de infraestructura.
9. **`RCON_PASSWORD` por defecto "minecraft"** en `mc-server-runner` si no se define:
   el panel debe generar y fijar siempre la password si habilita SSH.
10. **APIs externas** (versiones, XUID): dependencia de disponibilidad de terceros.

---

## 10. Oportunidades

1. **El contenedor es efímero, el dato es el volumen**: se puede recrear, clonar,
   versionar y mover instancias con relativa facilidad — ideal para un panel.
2. **Estado real vía ping RakNet**: el panel puede mostrar online/players/version
   sin ningún agente dentro del contenedor.
3. **`mc-monitor` exporta a Prometheus/OpenTelemetry**: métricas de jugadores y
   latencia ya resueltas; solo falta montarlo como sidecar.
4. **`send-command` + `docker logs`**: consola funcional sin modificar la imagen.
5. **`ENABLE_SSH` + `mc-server-runner`**: consola bidireccional ya integrada en la
   imagen para la versión avanzada.
6. **`MC_PACK` + `FORCE_*_COPY`**: importación declarativa de mundos/packs en la
   creación — perfecto para plantillas y restauraciones reproducibles.
7. **`STOP_SERVER_ANNOUNCE_DELAY`**: apagados con aviso a jugadores desde el panel.
8. **Comunidad activa y soluciones de referencia** (backup sidecar, webhooks,
   bridges) que validan el enfoque.
9. **BDS tiene comandos de gestión en vivo** (`op`, `allowlist add/reload`,
   `permission set`, `changesetting`, `save hold/resume`) que permiten muchas
   operaciones sin reiniciar.
10. **Modelo de plantillas/eggs**: el patrón "instancia = config (env/BBDD) +
    volumen + imagen" es directamente reproducible (similar a los eggs de Pterodactyl).

---

## 11. Posibles extensiones

- Multi-instancia con asignador de puertos y aislamiento por red/compose.
- Clonación de servidores (duplicar volumen + cambiar env).
- Plantillas ("eggs"): presets de config + mundo + packs.
- Programación de reinicios (mitigación de fugas de memoria).
- Backups a S3/minio con retención y cifrado.
- Historial de versiones con rollback (guardar versión anterior).
- Estadísticas: Prometheus + Grafana embebido, o métricas propias (ping + docker stats).
- Logs: streaming con búsqueda, niveles y persistencia (vector/loki).
- Webhooks / bots de Discord/Telegram (estado, jugadores, eventos).
- API pública de estado para el server list.
- Sandboxing: limitar recursos por contenedor (cpu/mem), redes restringidas.
- Market de addons/packs con instalación 1-click.

---

## 12. Recomendaciones para el panel profesional

> **Nota editorial (2026-08-05)**: el stack propuesto en esta sección (Node.js/NestJS o Go)
> es anterior a la decisión definitiva del TDD. El stack final acordado es **Python 3.13 +
> FastAPI** (backend) y **React + TypeScript + Vite + TailwindCSS** (frontend); ver
> `docs/technical-design.md` §3.

### 12.1 Arquitectura propuesta

```
Browser (SPA: React/Vue)
   │  HTTPS + WebSocket
   ▼
Frontend
   │  REST + WebSocket (console, logs, eventos)
   ▼
Backend API (Node.js/NestJS o Go)
   ├── Módulo Docker (dockerode / Docker SDK)  → crea/arranca/recrea contenedores
   ├── Módulo Filesystem                         → acceso directo a /data (bind mounts)
   │        (mundos, backups, config files, packs, plantillas)
   ├── Módulo Status (cliente RakNet ping UDP)  → online/players/version en vivo
   ├── Módulo Console (send-command + docker logs / SSH opcional)
   ├── Módulo Métricas (sidecar mc-monitor → Prometheus)
   ├── Base de datos (Postgres)                  → usuarios, roles, instancias, config
   └── Storage de backups (local, S3/minio)
   │
   ▼
Docker SDK / socket Docker (aislado)
   ▼
Contenedor itzg/minecraft-bedrock-server  (motor, SIN modificar)
   ▼
Minecraft Bedrock Server (BDS)
```

### 12.2 Decisiones clave

1. **Fuente de verdad de configuración = BBDD del panel**, traducida a env vars en la
   creación del contenedor. Un cambio de config = **recrear** (nunca editar
   `server.properties` en caliente si la env var está activa).
2. **Separación de volúmenes**: el panel debe controlar el **bind mount host**
   (`/var/lib/panel/instances/<id>/:/data`) para poder hacer backups, restaurar y
   editar ficheros directamente con el contenedor parado.
3. **Consola por defecto**: `docker exec send-command` (enviar) + `docker logs`
   (recibir) con serialización por instancia. Fase 2: `ENABLE_SSH=true` +
   `RCON_PASSWORD` generada por el panel para consola bidireccional.
4. **Backups**: `save hold` → snapshot del `worlds/<level-name>/` → `save resume`,
   con timeout y `save resume` forzado de seguridad; metadatos en BBDD.
5. **Status en vivo**: implementar el ping RakNet en el backend (UDP) en lugar de
   depender del healthcheck. El healthcheck de Docker se usa para el estado
   `starting/healthy/unhealthy`.
6. **Versiones**: el panel consulta las mismas fuentes que la imagen (API Minecraft
   Services / JSON de GitHub) y ofrece `LATEST`, `PREVIEW`, `EXISTING` o versiones
   concretas. Antes de cada upgrade, backup del mundo.
7. **Multi-instancia**: pool de puertos gestionado por el panel + `ENABLE_LAN_VISIBILITY`
   apagado en instancias multi para evitar conflictos.
8. **Permisos del volumen**: asegurar UID/GID consistente (el panel fija `UID`/`GID`
   o `chown` del bind mount al crear la instancia).
9. **Seguridad**: el socket Docker solo es accesible por el backend (daemon aislado);
   el backend expone una API con JWT + roles; separar el frontend del socket por completo.
10. **Modelo de instancia**: "instancia = {config_env, image_tag, port_mapping,
    volume_path, estado}". Al ser todo reproducible desde config + volumen, el panel
    puede ofrecer clonado y plantillas como primitivas de primer nivel.

### 12.3 Stack sugerido (sin decidir aún, a validar)

- **Backend**: Node.js/NestJS o Go — con SDK de Docker maduro y fácil streaming de
  logs/websocket.
- **Frontend**: React + Tailwind, WebSocket para consola y logs.
- **BBDD**: Postgres (usuarios, roles, instancias, backups, auditoría).
- **Métricas**: sidecar `mc-monitor` + Prometheus (o implementación propia del ping).
- **Backups**: librería `tar`/`zstd` en el backend + almacenamiento pluggable.

---

*Fin del documento. Pendiente de instrucciones antes de generar cualquier línea de
código.*
