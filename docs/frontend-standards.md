# Frontend Standards — BedrockPanel

> Guía de referencia para el agente que implementa `frontend/`. Sustituye al
> borrador anterior en los puntos donde ese borrador asumía cosas que la API
> real no hace — ver "Correcciones vs. el borrador" al final.

## 1. Stack tecnológico

| Capa | Elección | Motivo |
|---|---|---|
| Framework | React 18 + TypeScript (strict) | Consistente con el resto del stack tipado del backend |
| Build | Vite | Ya configurado en `frontend/` |
| Estilos | Tailwind CSS + shadcn/ui | Componentes accesibles, tema oscuro/claro nativo |
| Estado servidor | TanStack Query | Cache, reintentos, invalidación — no `useEffect` a mano para fetch |
| Estado UI | Zustand | Tema, sidebar colapsado, fondo activo — nunca datos de servidor |
| HTTP | Axios + interceptor | Adjunta `Authorization`, maneja 401 (refresh o logout) |
| Router | React Router v6 | Rutas protegidas por rol/permiso |
| Gráficos | Recharts | CPU/RAM/jugadores en Monitoring |
| Tests | Vitest + Testing Library | Componentes y hooks clave, no todo |

## 2. Autenticación — flujo real (no genérico)

`POST /api/v1/auth/login` con `{username, password}` devuelve **una de dos
formas**, hay que manejar ambas:

- `{access_token, refresh_token, ...}` — login directo, cuenta sin 2FA.
- `{requires_2fa: true, temp_token: "..."}` — la cuenta tiene TOTP activo.
  El frontend muestra un segundo paso (input de 6 dígitos o backup code) y
  llama `POST /api/v1/auth/verify-2fa` con `{temp_token, code}`, que ahí sí
  devuelve los tokens reales.

Flujo de habilitar 2FA (pantalla de Settings, no de login):
`POST /auth/2fa/enable` → devuelve secreto + `provisioning_uri` (renderizar
como QR) + 10 backup codes (mostrar UNA vez, con aviso de guardarlos) →
`POST /auth/2fa/verify` con el código que el usuario escribe desde su app
TOTP para confirmar y activar. `POST /auth/2fa/backup` regenera backup codes
si ya está activo.

JWT vía header `Authorization: Bearer <access_token>`. El interceptor de
Axios debe:
- Adjuntar el header en cada request.
- Ante `401`, intentar refresh una vez; si falla, logout + redirect a
  `/login`.
- Ante `403`, **no** redirigir a login — es un problema de permisos, no de
  sesión. Mostrar el mensaje de error del backend (`detail.message`) tal
  cual, no un genérico "no autorizado".

No hay endpoint de "logout" con estado server-side más allá de invalidar el
refresh token — confirma esto en el router de IAM antes de asumir un botón
de logout que solo borre el token local.

## 3. Modelo de permisos — no es un simple switch de roles

Hay **dos sistemas de roles distintos**, no los mezcles:

- **RBAC del panel** (IAM): `viewer < operator < admin < super_admin`.
  `admin`/`super_admin` pasan cualquier chequeo automáticamente. `viewer`
  solo lee. `operator` lee + escribe sobre servidores. Acciones de ámbito
  panel (gestión de usuarios, API keys, auditoría) solo las hace
  `admin`/`super_admin`.
- **Membresía por servidor**: un usuario puede tener un rol distinto por
  cada servidor al que tiene acceso (`server:{id}` en el modelo de
  autorización). Un `viewer` global puede ser `operator` de un server
  puntual.

El backend devuelve **65 códigos de permiso** granulares (`server.view`,
`server.update`, `player.ban.global`, etc. — ver
`modules/iam/domain/permissions.py` si necesitas el catálogo completo). El
frontend no debe hardcodear "si es admin, muestra el botón" — debe ocultar/
deshabilitar acciones según lo que el backend efectivamente autorizó,
idealmente consultando qué puede hacer el usuario en ese server (o
simplemente intentando la acción y mostrando el 403 con su mensaje si no
puede — más simple, aceptable para MVP, pero dejar la puerta abierta a un
endpoint de "mis permisos por server" si existe).

Si el usuario entra con una API key (`X-API-Key`, no aplica a sesiones de
navegador normales), no es un caso que el frontend web necesite manejar.

## 4. WebSocket — gateway único + WS de Monitoring por servidor (ADR-002)

**Hay DOS endpoints WS reales hoy** (verificado contra el código, change-log
§30 — este documento quedó desactualizado cuando se escribió solo el gateway):

1. **`GET /api/v1/ws`** — el gateway único de eventos de dominio
   (`modules/notification/api/router.py`). Sirve los eventos de NEGOCIO de
   todos los dominios (servidor, consola, mundo, backup, tarea, IAM, sistema)
   con protocolo de canales (`global`, `server:{id}`, `user:{id}`). Es la
   fuente del estado en vivo del dominio (SERVER.STARTED → estado del server,
   CONSOLE.OUTPUT → consola, PLAYER.JOINED → jugadores…).
2. **`GET /api/v1/servers/{id}/monitoring/ws`** — WS de métricas POR SERVIDOR
   (`modules/monitoring/api/router.py`, ADR-002, desviación aceptada). Emite
   snapshots de CPU/RAM/disco/jugadores cada `poll_interval` (~5 s) en un
   envelope de transporte `SERVER.STATE` con `scope="monitoring"`. **NO es un
   evento de negocio**: no se publica en el bus ni llega al gateway `/ws`.

**Regla práctica**: los eventos de *negocio* (cambios de estado, consola,
jugadores, backups) vienen del **gateway `/ws`**. Las *métricas* (CPU/RAM/
disco) vienen del **WS de monitoring por servidor**. Si una página necesita
ambos (ej. la card de detalle), conecta los dos — no asumas que el gateway
trae métricas ni que el WS de monitoring trae eventos de negocio.

**Conexión (gateway)**: `ws://<host>/api/v1/ws?token=<access_token>` (o header
`Authorization` si el cliente WS del navegador lo soporta — en la práctica,
usa el query param, es más simple en browsers). Cierra con código `4401` si
el token no autentica.

**Protocolo, mensajes que el cliente envía** (JSON):
- `{"action": "subscribe", "channels": ["server:{id}", "global"]}`
- `{"action": "unsubscribe", "channels": [...]}`
- `{"action": "resume", "last_seq": <int>, "channels": [...]}` — para
  recuperar eventos perdidos tras una reconexión.
- `{"action": "pong"}` — respuesta a heartbeat, si el server lo pide.

Un JSON malformado cierra la conexión con `4408`. Una acción desconocida
responde `{"error": "NOTI.UNKNOWN_ACTION"}` sin cerrar. Una suscripción a un
canal inválido o sin permiso responde `{"error":
"NOTI.INVALID_SUBSCRIPTION"}`. Un `resume` que pide demasiado backlog
responde `{"error": "NOTI.RESUME_TOO_LARGE"}` — en ese caso, el cliente debe
simplemente re-suscribirse sin `last_seq` (perder el historial es aceptable,
no reintentar el resume con el mismo `last_seq`).

**Canales (gateway)**: `global` (abierto a cualquier sesión autenticada),
`server:{id}` (requiere `server.view` en ese servidor — si no tiene acceso, la
suscripción se rechaza, no falla la conexión entera), `user:{id}` (solo tu
propio id).

**Eventos que llegan del servidor** (envelope, campos observados en el
código): algo con `event_type`/`scope`/`server_id`/`payload`/`seq`/`ts` —
confirma el nombre exacto de cada campo mirando
`modules/notification/application/event_dispatcher.py::serialize_envelope`
antes de tipar la interfaz TypeScript; no lo inventes desde este documento.
El enrutado a canal ya lo hace el backend (si el evento trae `server_id` va
a `server:{id}`; eventos IAM/AUTH van a `user:{actor_id}`; el resto a
`global`) — el frontend no decide el canal, solo se suscribe a los que le
interesan según qué página está viendo.

**Cliente WS recomendado** (hook `useWebSocket`/store dedicado):
- Un único socket compartido a nivel de app (no uno por componente).
- Al montar cualquier página que necesite eventos de un server puntual,
  suscribirse a `server:{id}`; al desmontar, `unsubscribe` (no dejar
  canales colgados innecesariamente — hay rate limiting y buffers
  limitados del lado del servidor).
- Reconexión con backoff; al reconectar, guardar el último `seq` visto por
  canal y mandar `resume` antes de operar normal.
- La consola en vivo (Console page) se alimenta de este mismo WS filtrando
  eventos `CONSOLE.OUTPUT` del canal `server:{id}` — no hay endpoint HTTP
  de polling para logs en vivo, es 100% WS.
- **Métricas**: el hook `useServerMonitoring` abre UN socket por servidor a
  `/servers/{id}/monitoring/ws` (este sí es un socket por recurso, es el
  diseño del ADR-002) y escribe en `useMonitoringStore`. Los componentes leen
  del store; no abren su propio socket de métricas.
- El contrato completo de "qué store lee cada tipo de dato" está en **§14**.

## 5. Estructura de carpetas (feature-first)

```
frontend/src/
  app/                  # router, providers, layout raíz
  features/
    auth/                # login, 2FA, verify-2fa
    servers/             # dashboard, lista, detalle, start/stop/restart
    worlds/
    backups/
    players/             # lista, ban global/server, kick, sesiones
    console/             # terminal en vivo + envío de comandos
    scheduler/
    monitoring/          # gráficos CPU/RAM/jugadores
    templates/           # capturar/aplicar
    permission/           # allowlist, operadores (in-game, NO confundir con IAM)
    iam/                  # usuarios, roles, API keys, auditoría (solo admin+)
    settings/             # tema, fondo, cambio de contraseña, 2FA propio
  components/ui/          # shadcn, genéricos sin lógica de negocio
  lib/
    api/                  # cliente axios + funciones por dominio
    ws/                   # WebSocketClient, store de canales/seq
    auth/                 # interceptor, guards de ruta
  stores/                 # zustand: tema, sidebar, ws-connection
```

Cada carpeta de `features/` mapea 1:1 con un dominio/bounded context real
del backend (ver `docs/technical-design.md` §5.1) — así el frontend no
inventa agrupaciones propias que luego hay que reconciliar con la API.

## 6. Sidebar — ítems reales, confirmados contra el mockup

Orden y naming exactos (ver mockup en §9.1): **Dashboard · Servidor ·
Consola · Jugadores · Mundos · Backups · Programador · Monitoreo ·
Plantillas · Permisos · Configuración · Logs**.

- **"Servidor"** (singular) es la página de detalle/gestión del servidor
  activo — la lista/selector de servidores vive en la pastilla del header
  (§9.1), no como página propia del sidebar.
- **"Permisos" en el sidebar es SOLO in-game** (allowlist, op, niveles
  visitor/member/operator) — confirmado con el usuario. El RBAC del panel
  (usuarios, roles, API keys, auditoría — módulo IAM) **no va en el
  sidebar**, va colgado del ícono de perfil/engranaje del header (menú
  desplegable "Admin Administrador" o el ícono ⚙ junto a la campana — ver
  §9.1). Ocúltalo del todo (ni el ícono del header) si el usuario no es
  `admin`/`super_admin`.
- **"Logs"** es una página aparte de la Consola — probablemente el
  histórico/buscador de logs pasados vs. la Consola que es el stream en
  vivo + envío de comandos. Confirma el alcance exacto contra qué endpoint
  de Monitoring/Console lo respalda antes de construirla; si no hay un
  endpoint claro de "logs históricos" distinto del buffer de Console, dilo
  en el resumen de la fase en vez de inventar uno.
- **"Configuración"** aquí es `server.properties` del servidor activo
  (módulo Configuration), no ajustes del panel — esos van en el header
  también (ver arriba).

## 7. Endpoints reales confirmados en esta sesión (usar estos, no adivinar)

Prefijo base: `/api/v1`. Algunos ya probados en vivo durante el desarrollo
del backend:

- `POST /auth/login`, `POST /auth/verify-2fa`, `POST /auth/2fa/enable`,
  `POST /auth/2fa/verify`, `POST /auth/2fa/backup`.
- `GET/POST /servers`, `POST /servers/{id}/start`, `/stop`.
- `GET /servers/{id}/worlds`.
- `POST /servers/{id}/templates/capture` `{name}`, `GET /templates`,
  `GET /templates/{id}`, `POST /servers/{id}/templates/{id}/apply`
  `{world_name?}` (409 `TEMPLATE.EXISTS` si el mundo destino ya existe —
  mostrar ese mensaje, no un error genérico), `DELETE /templates/{id}`.
- `GET /servers/{id}/players/online`, `POST /servers/{id}/players/{player_id}/ban`
  `{reason?, expires_at?}`, `DELETE .../ban`, `POST .../kick`,
  `POST /players/bans/global`, `DELETE /players/bans/global/{ban_id}`.
- `PUT /servers/{id}/permissions/allowlist-enabled` `{enabled}`.
- `GET /ws` (ver §4).

Para el resto de endpoints (Backup, Scheduler, Monitoring, Configuration,
IAM completo), **lee el router real de cada módulo** en
`apps/backend/src/app/modules/{modulo}/api/router.py` antes de asumir la
forma — este documento no pretende listar los ~13 módulos completos, solo
orienta dónde mirar y qué ya se confirmó en producción real.

## 8. Manejo de errores — formato uniforme

Todo error del backend llega con esta forma (confirmado repetidas veces
hoy):

```json
{
  "detail": {
    "code": "ALGO.ESPECIFICO",
    "message": "Mensaje legible para mostrar tal cual",
    "context": { }
  }
}
```

El interceptor de Axios/una utilidad `getApiError(err)` debe extraer
`detail.message` para mostrar en toasts/formularios, y `detail.code` para
lógica condicional puntual (ej. `TEMPLATE.EXISTS` → ofrecer elegir otro
nombre en vez de solo mostrar el error). Nunca mostrar el JSON crudo ni un
"Error interno" genérico si `detail.message` existe.

## 9. Diseño visual — basado en el mockup aprobado

El usuario proveyó un mockup del Dashboard que **es la referencia visual
vinculante** para todo el frontend, no solo para esa página. Replica su
lenguaje visual (glassmorphism oscuro, iconografía pixel-art de Minecraft,
badges tipo píldora, cards con borde sutil brillante) en TODAS las páginas,
no únicamente en Dashboard.

### 9.1 Estructura del mockup (qué es cada cosa)

- **Header**: pastilla "Servidor: Survival • En línea" a la izquierda —
  **es un selector desplegable** para cambiar entre servidores (confirmado
  con el usuario; el backend ya soporta multi-servidor real desde el fix de
  esta sesión). Al lado, pastilla "3/10 jugadores" (contador en vivo, vía
  WS). A la derecha: campana de notificaciones con badge numérico (eventos
  del WS sin leer — probablemente canal `global`/`user:{id}`), ícono de
  engranaje (⚙, acceso a IAM/ajustes del panel si es admin — ver §6), y
  el menú de perfil ("Admin / Administrador" con avatar y chevron,
  desplegable con logout).
- **Sidebar**: colapsable (flecha `<` junto al logo), ítems con ícono +
  texto, ítem activo con fondo verde sólido y esquinas redondeadas (no solo
  un subrayado). Logo "BEDROCK PANEL" en tipografía pixel/bloque estilo
  Minecraft, con íconos de espada/pico. Pie del sidebar: versión (`v0.1.0`)
  + link "Open Source", sobre el fondo decorativo (cueva con cristales
  morados — ver §9.2, es uno de los fondos dinámicos, no algo fijo).
- **Panel central**: card grande de servidor (miniatura del mundo, nombre,
  badge de estado, metadata en pastillas — versión/mundo/dirección/tiempo
  activo — y los 4 botones de acción grandes con color semántico: verde
  Iniciar, gris-azulado Reiniciar, rojo Detener, ámbar Crear backup). Debajo,
  fila de 6 "stat cards" (Jugadores/CPU/RAM/Disco/TPS/Chunks) con ícono
  pixel-art, valor grande, y barra de progreso donde aplica. Debajo, gráfico
  de área (Recharts) de uso de recursos con selector de rango (15m/1h/24h/7d)
  y toggle de series (CPU/RAM/Jugadores). Consola en tiempo real embebida al
  fondo del panel central (mismo componente que usa la página "Consola"
  completa — reutilízalo, no lo dupliques).
- **Columna derecha**: card "Estado del servidor" (checklist con ícono de
  check verde: Docker, Red, Disco, Memoria, Sistema), "Jugadores en línea"
  (avatar, nombre, rol/badge tipo corona para admin, latencia con ícono de
  señal — con link "Ver todos" a la página Jugadores), "Eventos recientes"
  (feed con ícono por tipo de evento + tiempo relativo — esto es
  literalmente el feed de eventos del WS renderizado, no una lista estática),
  y "Acciones rápidas" (grid 2x3 de botones a atajos de otras páginas).

### 9.2 Fondos dinámicos — confirmado con el usuario

El fondo (la imagen morada/cueva que se ve tras el sidebar en el mockup) es
**uno de varios fondos seleccionables que se aplican a TODA la app**, no
solo un detalle decorativo del sidebar — y cambia también la paleta de
acento, no solo la imagen.

- Zustand store `useThemeStore`: `theme: 'dark' | 'light'` (default
  `'dark'`), `backgroundId: string` (referencia a un fondo predefinido del
  catálogo, no una URL arbitraria salvo que se agregue upload explícito
  después).
- El fondo se ve a través/detrás de las superficies de glassmorphism
  (sidebar, cards) — es decir, sidebar y cards usan
  `backdrop-blur` + fondo semitransparente (`bg-slate-900/60` o similar),
  NO opaco — así el fondo se percibe en los bordes/vacíos como en el
  mockup.
- Transición crossfade entre fondos: dos capas `<div>` con `background-image`
  y `opacity` animada, precargando la siguiente imagen antes del fade — no
  recargues la imagen visible.
- Paleta de acento por fondo: mapa fijo `backgroundId → tokens de acento`
  (no extracción de color en vivo — complejidad innecesaria para el MVP).
  El fondo del mockup (cueva morada) usa acento verde para success/activo
  (`Iniciar`, ítem de sidebar activo, checks de estado) — ese es el default;
  cada fondo del catálogo trae su propia combinación coherente predefinida
  por quien diseñe los fondos, no calculada.

**Tipos de fondo (implementación real, `BackgroundDef.type`)**: el catálogo
distingue `'gradient' | 'image'`. La **implementación por defecto usa
gradientes radiales/lineales** (radial-gradient + linear-gradient con
transparencias `rgba`), ya que estos generan bordes suaves e iluminaciones
que se difuminan naturalmente detrás del `backdrop-blur` de las superficies,
manteniendo la lectura limpia de la UI. El campo `css` de cada entrada es un
string de `background` CSS; para los gradientes es la cadena completa de
capas.

**Nota técnica sobre imágenes reales**: si se implementan imágenes reales,
estas deben ser tratadas como "fuentes de luz difusa" mediante un **desenfoque
estratégico** en el componente `Background` para evitar que los detalles nítidos
rompan la ilusión de profundidad del glassmorphism: se recomienda
`filter: blur(12px)` (12–16px) con un `scale(1.05)` para ocultar los bordes del
desenfoque, y **una viñeta radial encima de la imagen** — `radial-gradient(circle,
transparent 40%, rgba(9,10,20,0.85) 100%)` — que oscurece los bordes de forma
estratégica sin ocultar el centro del paisaje. Un desenfoque excesivo
(`blur(80px)`) deja ver solo una mancha abstracta de color; uno insuficiente hace
que la imagen enfocada se vea como un póster pegado al fondo y atraviese el
cristal de las superficies. El crossfade entre gradientes e imágenes es el mismo
(remount por `key` con fade-in CSS); la imagen se precarga igual que los
gradientes.

- Catálogo actual (default `cave`):
  - `cave` (gradiente) — acento `emerald` (el del mockup).
  - `end` (gradiente) — acento `sky`.
  - `nether` (gradiente) — acento `orange`.
  - `world` (imagen, `url("/backgrounds/mundo-mn.webp") center/cover`) —
    acento `cyan`. Se renderiza con `filter: blur(12px)` + `scale(1.05)` +
    viñeta radial (transparente 40% → `rgba(9,10,20,0.85)` 100%).

### 9.3 Tokens visuales observados en el mockup (usar como base real)

- Fondo base de superficies: azul-violeta muy oscuro con transparencia
  (`slate-900`/`indigo-950` con opacidad ~60-80%), bordes sutiles
  luminosos (`border-white/10` con un leve glow en hover/activo).
- Radios grandes (`rounded-xl`/`rounded-2xl`) en todas las cards, nunca
  esquinas vivas.
- Verde (`emerald-400/500`) para success/online/activo/iniciar.
- Rojo (`red-500/600`) para detener/destructivo.
- Ámbar (`amber-500/600`) para backup/acciones "especiales" (no
  destructivas pero tampoco rutinarias).
- Azul (`blue-400/500`) como acento neutro secundario (RAM, reiniciar).
- Violeta (`violet-600`) para acciones de **creación** (nueva variante `create`
  en `button.tsx`, añadida tras el mockup — no estaba en la paleta original).
- **Capa `pixel`**: el `Button` expone `pixel` y `pixelTexture`. `pixel` activa
  el bloque saliente de Minecraft (bevel duro de dos tonos SIN blur, radio 0,
  hover = wash, press = el bloque se hunde, disabled = aplanado/desaturado) vía
  `.pixel-btn` en `pixel-theme.css`. `pixelTexture` (default `true`) añade ruido
  Stone-esco 8×8 con blend overlay sobre el color de la variante. Botones de
  acción de un server (Iniciar/Detener/Reiniciar/Backup) y el "Crear servidor"
  usan `pixel`.
- Iconografía: estilo pixel-art/voxel de Minecraft para íconos de dominio
  (bloques, picos, cofres) — íconos de UI genéricos (campana, engranaje,
  chevron, plus de "crear") en un set normal tipo `lucide-react`, no forces
  pixel-art en TODO, sería ilegible en tamaños chicos.
- Tipografía: un font pixel/bloque solo para el logo/headers grandes
  ("BEDROCK PANEL", títulos de card tipo "Survival Server") — el resto
  (metadata, tablas, botones) usa una sans-serif normal y legible. No
  satures todo el texto con la fuente pixel, el mockup no lo hace (mira
  "Jugadores en línea", "Steve", "Administrador" — todo sans-serif normal).

## 10. Convenciones de código

- Sin `any` — si un tipo de respuesta del backend no está claro, genera el
  tipo TS a mano leyendo el `schemas.py`/`response_model` real del endpoint,
  no lo inventes de memoria.
- Un hook de TanStack Query por endpoint (`useServers`, `useServer(id)`,
  `useStartServer()` como mutation), no un hook gigante por página.
- Componentes de `features/` no importan directamente `axios` — siempre a
  través de `lib/api/{dominio}.ts`.
- Tests: prioriza hooks de datos (mockeando la API) y componentes con lógica
  real (formularios, WS reconnect) sobre componentes puramente visuales.

## 11. Secuencia de implementación sugerida

1. Auth (login + 2FA) + interceptor + guards de ruta.
2. Layout (Sidebar + Header) + store de tema/fondo.
3. WebSocket client compartido (antes de construir páginas que lo
   necesiten, para no improvisarlo a mitad de Console).
4. Servidores (lista + detalle + start/stop).
5. Consola en vivo (ya con el WS listo del paso 3).
6. Mundos, Backups, Jugadores, Plantillas.
7. Scheduler, Monitoring, Permisos (in-game), Configuration.
8. IAM (usuarios/roles/API keys/auditoría) — solo visible para admin+.
9. Ajustes del panel (tema, fondo, 2FA propio, cambio de contraseña).

Documentar cada paso completado en `docs/change-log-frontend.md`, mismo
formato que usa `docs/change-log.md` del backend (fecha, alcance, decisiones,
archivos, verificación).

## 12. Correcciones vs. el borrador original

Por si el agente venía con el prompt anterior en mente, estas son las
diferencias deliberadas respecto a ese borrador:

- El WS **no** es un canal simple por servidor — es un gateway único con
  protocolo de suscripción/resume/canales. Constrúyelo así desde el inicio,
  no lo simplifiques y lo migres después.
- El login puede requerir un segundo paso (2FA) — el formulario de login no
  es un solo submit, es potencialmente de dos pasos.
- Los roles no son un enum plano global — hay rol global + rol por
  membresía de servidor. No hardcodear "si rol === admin".
- "Permisos" en el sidebar del borrador original es ambiguo — sepáralo en
  IAM (panel) y Permission (in-game).
- El formato de error es `{detail: {code, message, context}}`, no lo que
  asumiera el borrador anterior.
- El diseño visual **no es libre** — el mockup de §9 es vinculante para
  todas las páginas, no solo Dashboard. La pastilla de servidor en el
  header es un selector real (multi-servidor), no una etiqueta.

## 13. Sincronización en tiempo real (patrón obligatorio)

> Base establecida por la auditoría de sync WS (change-log §30). Todo lo que
> venga (Fase 3 Consola, Fase 5 Jugadores, Fase 6 Monitoring/Scheduler) debe
> seguir este patrón, no improvisar uno nuevo por fase.

### 13.1 Qué endpoints WS existen hoy (verificado contra el código)

| Endpoint | Fuente | Qué trae |
|---|---|---|
| `GET /api/v1/ws` | `modules/notification/api/router.py` | Eventos de **negocio** con protocolo de canales (`global`, `server:{id}`, `user:{id}`): `SERVER.*`, `CONSOLE.OUTPUT`, `PLAYER.JOINED/LEFT`, `BACKUP.*`, `TASK.*`, `IAM/AUTH.*`. Envelope: `{event, server_id, scope, payload, ts, seq}`. |
| `GET /api/v1/servers/{id}/monitoring/ws` | `modules/monitoring/api/router.py` (ADR-002) | Métricas por servidor: snapshot `SERVER.STATE` (`scope="monitoring"`) cada ~5 s con `{state, status, latency_ms, players, players_max, cpu, ram_mb, disk_mb}`. **No es evento de negocio** — no llega al gateway. |

Regla: **negocio → gateway `/ws`; métricas → WS de monitoring por servidor.**
No asumas que el gateway trae métricas, ni que el WS de monitoring trae
eventos de negocio. Conecta ambos solo en las páginas que necesiten los dos
(ej. la card de detalle usa `useServerMonitoring` + `useServerStateSync`).

### 13.2 Un evento WS actualiza N cachés de TanStack Query

El caso real que motivó esto: `SERVER.STARTED` debe actualizar a la vez el
**detalle** `['server', id]` (lo lee la card) y la **lista** `['servers']`
(la lee el selector del header). Si solo se toca una cache, el header queda
con el estado viejo (bug de la auditoría).

Patrón obligatorio — un solo handler actualiza **todas** las cachés que
guarden el mismo recurso:

```ts
function applyState(queryClient, serverId, state) {
  queryClient.setQueryData(['server', serverId], (cur) => cur ? { ...cur, state } : cur)
  queryClient.setQueryData(['servers'], (list) =>
    list?.map((s) => s.id === serverId ? { ...s, state } : s),
  )
}
```

- Las claves (`serverKeys.all`, `serverKeys.detail`) viven en
  `lib/api/servers.ts` (no en el hook) para evitar import circular y que
  cualquier consumidor las reutilice.
- Si aparece un tercer consumidor del mismo recurso, **agrégale su cache al
  mismo handler** (o normaliza en una cache por-id con selectores), no crees
  un segundo `setQueryData` por consumidor.
- Los cambios de estado NO invalidan ni refetchean; se aplican optimistamente
  desde el evento (el WS es la fuente de verdad para `state`).

### 13.3 Qué genera notificación vs. qué es silencio

La campana (`useNotifications` + `useNotificationsStore`) filtra los eventos
que son *notificación visible*; el resto de envelopes del gateway solo
actualiza datos (no badge, no dropdown):

| Tipo | ¿Notificación? |
|---|---|
| `SERVER.STARTED`, `SERVER.STOPPED`, `SERVER.CRASHED` | Sí |
| `PLAYER.JOINED`, `PLAYER.LEFT` | Sí |
| `BACKUP.COMPLETED`, `BACKUP.FAILED`, `TASK.FAILED` | Sí |
| `SERVER.STATE` (monitoring), `CONSOLE.OUTPUT`, métricas | **No** — ruido, filtrar siempre |

- El filtro vive en el hook `useNotifications` (`NOTIFICATION_EVENTS`), no en
  el store — el store solo persiste lo que recibe.
- Suscripciones de la campana: `global` + `user:{id}` + `server:{id}` de los
  **servidores visibles** (vía `useServers`). `useServerStateSync` (detalle)
  se suma; el cliente WS del gateway es un singleton y mergea canales.
- **"Leído" es estado local (zustand)**: no hay endpoint REST de
  notificaciones en el backend (verificado). No se persiste server-side.
  Si algún día existe un endpoint de "mark read", migrarlo ahí.
- El store deduplica por `seq` (un `resume` re-emite eventos ya vistos) y
  mantiene un tope (`MAX_ITEMS`).

## 14. Contrato de consumo WS — exactamente dos stores

> Base: auditoría puntual de la pasada de verificación (change-log backend §30 /
> ADR-013 Rejected). El frontend tiene **dos dueños de socket** y **dos stores
> de lectura**; ningún otro código abre conexiones ni lee el payload del WS.

### 14.1 Quién abre sockets (dueños, verificados contra el código)

| Dueño (nombre real) | Endpoint | Escritura |
|---|---|---|
| `useWebSocketStore` (`stores/ws.ts`) — **singleton** `WebSocketClient` (`lib/ws/WebSocketClient.ts`) | gateway `/api/v1/ws` | Eventos de negocio → `useNotificationsStore` + cachés TanStack (`useServerStateSync`) |
| `useServerMonitoring` (`hooks/useServerMonitoring.ts`) — refcount: **un** socket por servidor activo | `/api/v1/servers/{id}/monitoring/ws` | Telemetría → `useMonitoringStore` |

### 14.2 Tabla de consumo (regla obligatoria)

**Ningún componente nuevo abre socket propio ni lee el payload del WS
directamente.** Todo dato en vivo se lee de **exactamente una** de estas dos
stores, según la tabla:

| Dato en vivo | Store (nombre real) | Fuente |
|---|---|---|
| Cambio de estado / evento de negocio (`SERVER.*`, `CONSOLE.OUTPUT`, `PLAYER.*`, `BACKUP.*`, `TASK.*`, `IAM/AUTH.*`) | `useNotificationsStore` (`stores/notifications.ts`) | gateway `/ws` vía `useWebSocketStore` |
| Telemetría numérica continua (CPU, RAM, disco, jugadores, `latency_ms`) | `useMonitoringStore` (`stores/monitoring.ts`) | `useServerMonitoring` |

Los cambios de **estado de servidor** (para cards/selectores) se leen de las
cachés de TanStack Query, que `useServerStateSync` actualiza desde el gateway —
**no** del payload del WS directo (patrón §13.2).

### 14.3 Reglas derivadas

- Un componente que necesite ambos tipos de dato consume **las dos stores** (ej.
  `Header`, `StatCards`); nunca abre un segundo socket de métricas.
- La capa que sí crea sockets es solo la de infraestructura listada en §14.1; un
  endpoint nuevo con socket propio **debe** integrarse a una de las dos stores
  (o justificar una tercera por ADR), no proliferar sockets por página.
- Auditoría puntual (2026-08-10): verificado que ningún componente abre
  `new WebSocket(...)` fuera de `useServerMonitoring` y del singleton del
  gateway — los 2 bugs históricos de este patrón (dropdown de estado, badge de
  jugadores) se corrigieron apuntando al store correcto, no creando otro socket.
