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

## 4. WebSocket — un único gateway, con protocolo de canales

**No hay un WS por página.** Hay un único endpoint `GET /api/v1/ws` que
sirve TODOS los eventos en tiempo real de TODOS los dominios (servidor,
consola, mundo, backup, tarea, IAM, sistema). El WS por-servidor que
pudiera existir en versiones tempranas del backend quedó reemplazado por
este — no lo repliques.

**Conexión**: `ws://<host>/api/v1/ws?token=<access_token>` (o header
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

**Canales**: `global` (abierto a cualquier sesión autenticada), `server:{id}`
(requiere `server.view` en ese servidor — si no tiene acceso, la suscripción
se rechaza, no falla la conexión entera), `user:{id}` (solo tu propio id).

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
- Iconografía: estilo pixel-art/voxel de Minecraft para íconos de dominio
  (bloques, picos, cofres) — íconos de UI genéricos (campana, engranaje,
  chevron) en un set normal tipo `lucide-react`, no forces pixel-art en
  TODO, sería ilegible en tamaños chicos.
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
