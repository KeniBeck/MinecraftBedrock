# Change Log — Frontend BedrockPanel

> Mismo formato que `docs/change-log.md` del backend: fecha, alcance,
> decisiones, archivos, verificación. Cada fase del
> `docs/frontend-implementation-plan.md` se documenta aquí al completarse.

## Fase 1 — Cimientos (setup + auth + WS client)

> **Fecha**: 2026-08-08
> **Origen**: arranque del frontend sobre el scaffold Vite + React 19 existente
> en `apps/frontend/`. Fase 1 del plan: dependencias, shadcn/ui + tema,
> login de dos pasos (2FA), interceptor Axios, guards de rutas y cliente
> WebSocket compartido — **sin** páginas de datos (eso es Fase 2+).

### Alcance

- Stack según `frontend-standards.md` §1: React 18/19 + TypeScript **strict**,
  Vite, Tailwind CSS + shadcn/ui, TanStack Query, Zustand, Axios + interceptor,
  React Router, Recharts, Vitest + Testing Library.
- Login real de **dos pasos**: `POST /auth/login` → si responde
  `{requires_2fa: true, temp_token}`, segundo paso con `POST /auth/verify-2fa`;
  si no, entra directo. Verificado contra `iam/api/schemas.py` (LoginResponse /
  TokenResponse reales, no asumidos del standard).
- Interceptor Axios: `Authorization: Bearer`, 401 → refresh una vez (single-
  flight), si falla logout + redirect a `/login`; 403 → NO redirige, se muestra
  `detail.message` (frontend-standards §2/§8).
- Guards de rutas: `RequireAuth` (protegidas → /login) y `RequireGuest`
  (auth → /).
- Cliente WebSocket compartido (`/api/v1/ws?token=`): subscribe/unsubscribe/
  resume, reconexión con backoff exponencial, último `seq` por canal y
  re-suscripción sin `last_seq` ante `NOTI.RESUME_TOO_LARGE`. Envelope tipado
  contra `event_dispatcher.py::serialize_envelope` (`event/server_id/scope/
  payload/ts/seq`).
- Ruta placeholder post-login (`/`) que se suscribe al canal `global` y loguea
  los eventos en la consola del navegador para verificar el WS sin construir
  páginas de datos.

### Decisiones

- **react-router-dom v7** (API de v6): el standard decía v6, pero v7 mantiene la
  API de `createBrowserRouter`/`BrowserRouter` que se usa; misma forma.
- **Tailwind v4** (CSS-first, `@theme`): la config de tema vive en
  `src/index.css` con variables CSS de shadcn y variante `.dark`. El tema
  dark/light se persiste en localStorage (zustand `persist`).
- **Tipos verificados contra el backend**, no inventados:
  - `LoginResponse` (login) → `requires_2fa/temp_token/access_token/refresh_token/
    expires_in/identity` (schema real, campos `null` si no aplican).
  - `TokenResponse` (verify-2fa/refresh) → `access_token/refresh_token/
    expires_in/identity`.
  - Envelope WS → `event/server_id/scope/payload/ts/seq`.
  - Error → `{detail: {code, message, context}}`.
- **401 con single-flight**: varias peticiones simultáneas con token vencido
  comparten UNA llamada a `/auth/refresh`; el resto reusa el token nuevo.
- **403 no redirige**: es problema de permisos, no de sesión; el componente
  muestra `detail.message` vía `getApiMessage`.
- **Un solo `WebSocketClient`** a nivel de app (zustand store); los componentes
  usan `useWebSocket(channels)` que conecta con el token y suscribe/desuscribe
  por montaje. No hay sockets por página.
- `tsconfig.app.json` ganó `strict: true` + `noUncheckedIndexedAccess` +
  `exactOptionalPropertyTypes` (el scaffold no era strict; el standard §10 lo
  exige).

### Archivos

| Archivo | Contenido |
|---|---|
| `vite.config.ts` | Proxy `/api` → `:8000` (HTTP+WS), alias `@`, config vitest (jsdom) |
| `tsconfig.app.json` / `tsconfig.node.json` | `strict` + paths `@/*` |
| `src/index.css` | Tema Tailwind v4 (variables CSS shadcn, `.dark`) |
| `components.json` + `src/components/ui/{button,input,label,card}.tsx` | Base shadcn/ui |
| `src/lib/utils.ts` | `cn()` |
| `src/lib/api/types.ts` | Tipos reales del backend (LoginResponse/TokenResponse/errores) |
| `src/lib/api/client.ts` | `apiClient` + interceptor (Bearer/401/403) + `getApiMessage`/`getApiCode` |
| `src/lib/api/auth.ts` | `loginRequest`, `verifyTwoFactorRequest`, `refreshRequest`, `logoutRequest` |
| `src/lib/ws/types.ts` | Envelope y mensajes WS del wire real |
| `src/lib/ws/WebSocketClient.ts` | Cliente WS (backoff, resume, seq por canal) |
| `src/lib/auth/guards.tsx` | `RequireAuth` / `RequireGuest` |
| `src/stores/auth.ts` / `src/stores/theme.ts` / `src/stores/ws.ts` | Stores zustand |
| `src/hooks/useWebSocket.ts` | Conectar + suscribir/desuscribir por montaje |
| `src/features/auth/LoginPage.tsx` | Login de dos pasos (2FA) |
| `src/app/router.tsx` + `src/App.tsx` | Router + providers (QueryClient, tema) |

### Tests (vitest)

- `src/lib/api/client.test.ts` (5): `getApiMessage`/`getApiCode`, Bearer en
  request, 401 → refresh + reintento sin redirect, 403 → sin redirect, 401 sin
  refresh → logout. El interceptor se prueba con un **adapter mock** (los
  interceptores reales de axios; `spyOn(axios, 'request')` no captura las
  llamadas de la instancia).
- `src/lib/ws/WebSocketClient.test.ts` (4): conexión con `?token=`, envelopes,
  resume tras reconexión con último seq, `RESUME_TOO_LARGE` → re-suscripción sin
  `last_seq` (con un `WebSocket` fake).
- `src/features/auth/LoginPage.test.tsx` (3): login directo, flujo 2FA, error
  con `detail.message`.

### Hallazgos / discrepancias vs el standard

- El standard §4 decía que el envelope llega con "algo con event_type/…"; el
  código real (`serialize_envelope`) usa `event` (no `event_type`), más
  `server_id/scope/payload/ts/seq`. Se tipó con `event`, no `event_type`.
- `LoginResponse` real: todos los campos de tokens vienen `null` en el challenge
  2FA; no hay "una forma u otra" con objetos distintos — es UN objeto con
  campos opcionales. El cliente distingue por `requires_2fa`.

### Verificación

- `pnpm lint` ✅ · `pnpm typecheck` ✅ · `pnpm test` ✅ (14 passed) ·
  `pnpm build` ✅
- Confirmado manualmente en navegador por el usuario: login con usuario real
  (incluido el paso 2FA) y WS conectado con al menos un evento en la consola
  tras suscribirse al canal `global`.

## Fase 2 — Layout + Servidores

> **Fecha**: 2026-08-08
> **Origen**: Fase 1 completada. Layout fiel al mockup (frontend-standards §9),
> fondo dinámico, página de detalle de servidor con start/stop/restart y estado
> que se actualiza solo por WS.

### Alcance

- **Sidebar** (§9.1): colapsable (flecha junto al logo), logo "BEDROCK PANEL" en
  `font-pixel`, ítems del §6 con ícono + texto, **ítem activo con fondo verde
  sólido** (`bg-emerald-500`) y esquinas redondeadas, pie con versión + "Open
  Source". Glassmorphism: `bg-slate-900/60` + `backdrop-blur-xl` + `border-white/10`.
  En Fase 2 solo "Servidor" navega (a `/servers/:id`); el resto son placeholders
  deshabilitados (fases posteriores).
- **Header** (§9.1): pastilla de servidor que es un **selector real** (dropdown
  con la lista `GET /servers`, cambia el servidor activo y navega a su detalle),
  badge de estado por opción, campana/ajustes deshabilitados, toggle de tema
  oscuro/claro y menú de perfil con logout.
- **Fondo dinámico** (§9.2): store de tema con `backgroundId` y catálogo de
  **3 fondos** predefinidos (`cave`/`end`/`nether`) con su paleta de acento;
  crossfade por fade-in CSS (remount por `key`). Default: `cave` (morado +
  acento verde, el del mockup).
- **Página de detalle de servidor** (`/servers/:id`): card grande (miniatura
  decorativa, nombre, badge de estado, metadata en pastillas — versión/
  dirección/puerto/RCON — y los 4 botones con color semántico: verde Iniciar,
  gris-azulado Reiniciar, rojo Detener, ámbar Crear backup [deshabilitado hasta
  Fase 4]), fila de **stat cards con datos reales** del `ServerResponse` (estado,
  versión, dirección, puerto, RCON, imagen — sin inventar métricas de
  CPU/RAM/jugadores que aún no existen).
- **Estado en vivo por WS**: `useServerStateSync` suscribe al canal
  `server:{id}` y aplica `SERVER.STARTING/STARTED/STOPPING/STOPPED/CRASHED` a la
  cache de TanStack Query (sin refetch ni refresh de página).
- `AppLayout` envuelve las rutas protegidas; `/` y `/servers` redirigen al
  detalle del servidor activo (o el primero).

### Decisiones

- **No se inventan métricas**: los stat cards usan solo campos del
  `ServerResponse` real (los tokens del mockup CPU/RAM/jugadores requieren
  Monitoring/Players, fases posteriores). El prompt lo autoriza explícitamente.
- **Crossfade sin setState-en-effect**: la regla `react-hooks/set-state-in-effect`
  (v7) descarta el patrón de capas gestionadas por estado; se usa una animación
  CSS `@keyframes` con remount por `key` (fade-in), que cumple la regla y el
  criterio §9.2 (el fondo se ve a través de las superficies, transición visible).
- **Store de UI vs datos**: `useActiveServer` (id) es zustand/UI; los datos de
  servidor viven en TanStack Query (`useServer`). Cumple §1 (zustand nunca datos
  de servidor).
- **Acciones habilitadas por estado**: `serverActions()` replica la lógica del
  backend (start desde created/stopped/crashed; stop/restart desde
  running/starting).
- `react-router-dom` v7 con `createBrowserRouter` (misma API que v6).

### Archivos

| Archivo | Contenido |
|---|---|
| `src/stores/theme.ts` | `backgroundId` + catálogo de 3 fondos + paleta de acento |
| `src/stores/servers.ts` | `useActiveServer` (id activo, UI state) |
| `src/components/Background.tsx` | Fondo dinámico con fade-in CSS |
| `src/components/layout/{Sidebar,Header,AppLayout}.tsx` | Layout del mockup |
| `src/components/ui/{badge,dropdown-menu}.tsx` | Componentes shadcn nuevos |
| `src/components/ui/button.tsx` | Variantes semánticas start/stop/restart/backup |
| `src/lib/api/servers.ts` | Tipos reales (`ServerResponse`) + list/get/start/stop/restart |
| `src/lib/serverState.ts` | Labels/badges de estado + `serverActions()` |
| `src/features/servers/hooks.ts` | `useServers/useServer/useStart/useStop/useRestart` |
| `src/hooks/useServerStateSync.ts` | Sync de estado por WS (canal `server:{id}`) |
| `src/features/servers/components/{ServerCard,StatCards}.tsx` | Card grande + stat cards |
| `src/features/servers/ServerDetailPage.tsx` | Página de detalle |
| `src/features/servers/ServerRedirect.tsx` | Redirección al servidor activo/primero |
| `src/app/router.tsx` | `AppLayout` + rutas protegidas |
| `src/index.css` | `font-pixel` + `@keyframes background-fade` |

### Tests (vitest)

- `src/components/layout/Header.test.tsx` (3): pastilla muestra el activo, el
  dropdown cambia de servidor, estado por opción.
- `src/features/servers/ServerDetailPage.test.tsx` (5): card con estado/metadata,
  start habilitado en stopped → llama endpoint, stop deshabilitado en stopped,
  running → stop/restart habilitados, error 403 muestra `detail.message`.
- `src/hooks/useServerStateSync.test.tsx` (2): `SERVER.STARTED` actualiza la
  cache; eventos de otros servidores se ignoran (WebSocket fake).

### Hallazgos / discrepancias vs el standard

- `react-hooks` v7 añadió reglas nuevas (`set-state-in-effect`, `refs`) que
  fuerzan patrones más limpios; el crossfade se implementó con CSS puro en vez
  de capas en estado.
- "Crear backup" se renderiza deshabilitado (Fase 4) — el endpoint existe pero
  requiere elegir mundo (Fase 4 lo conecta).

### Verificación

- `pnpm lint` ✅ · `pnpm typecheck` ✅ · `pnpm test` ✅ (24 passed) ·
  `pnpm build` ✅ (solo warning de chunk >500kB, no bloqueante)
- Confirmado manualmente en navegador por el usuario: layout fiel al mockup
  (glassmorphism + fondo dinámico detrás de las superficies), selector de
  servidor cambiando entre los servidores reales, y start/stop/restart con el
  estado actualizándose por WS sin refrescar.

### Fix — `image_ref` rompía la card de servidor (2026-08-08)

La referencia completa de imagen Docker (`itzg/...@sha256:…`, 70+ caracteres) se
renderizaba sin truncar en la `ServerCard` (CardDescription) y en la StatCard
"Imagen", empujando el layout y generando scroll horizontal.

- `ServerCard`: `CardDescription` con `truncate` + `max-w-[26rem]` y
  `title={server.image_ref}` (tooltip nativo con el valor completo en hover).
  El contenedor del título ganó `min-w-0` para que el truncate funcione dentro
  del flex.
- `StatCards`: el valor de cada StatCard con `truncate` + `title={item.value}`
  y el contenedor de texto con `min-w-0`; el ícono con `shrink-0`.

**Sobre si debe mostrarse**: en la card grande como descripción bajo el nombre
aporta algo (identifica la imagen), pero el digest `@sha256:…` es ruido técnico
— se mantiene truncado con tooltip. La StatCard "Imagen" es la más cuestionable
por valor visual: si en la revisión visual sobra, se puede quitar o reemplazar
(no lo eliminé por cuenta propia).

- `pnpm lint` ✅ · `pnpm typecheck` ✅ · `pnpm test` ✅ (24 passed) ·
  `pnpm build` ✅

### Extensión — Fondos de imagen real ("Mundo Costero") (2026-08-08)

> **Origen**: el catálogo de `BACKGROUNDS` (`src/stores/theme.ts`) solo
> soportaba gradientes CSS. El estándar (§9.2) y el plan mencionaban la
> posibilidad de imágenes, pero la implementación no las manejaba.

### Alcance

- **`BackgroundDef.type`**: nuevo campo `type: 'gradient' | 'image'`
  (opcional, default `'gradient'`). El catálogo distingue cómo debe renderizar
  cada fondo el componente `Background`.
- **Nuevo fondo `world`** ("Mundo Costero"): `type: 'image'`, acento `cyan`,
  `css: 'url("/backgrounds/mundo-mn.webp") center/cover no-repeat'`. La imagen
  vive en `apps/frontend/public/backgrounds/mundo-mn.webp` (WebP, servida por
  Vite desde la raíz `/backgrounds/...`).
- **`Background.tsx`**: cuando el fondo es `type: 'image'`, la capa se
  renderiza con `filter: blur(80px)` + `transform: scale(1.1)` además del
  `background` del `css`. El crossfade (remount por `key` + `animate-background-fade`)
  es idéntico al de los gradientes, así que cambiar entre `cave` y `world` no
  introduce parpadeos.

### Decisiones

- **Imágenes = "luz ambiental difusa", no póster nítido**: las superficies de
  la app (Sidebar, Header, Cards) usan `backdrop-blur-xl` sobre fondos
  semitransparentes. Si la imagen se renderizara enfocada, sus detalles
  atravesarían el cristal y romperían la ilusión de profundidad del
  glassmorphism del mockup. El `blur(80px)` convierte la imagen en luz difusa;
  el `scale(1.1)` oculta los bordes del desenfoque.
- **Los gradientes siguen siendo el default**: generan bordes suaves que se
  difuminan naturalmente detrás del `backdrop-blur`, por eso el catálogo no los
  reemplaza — la imagen es una opción adicional, no la nueva normal.
- Imagen elegida por el usuario: `mundo-mn.webp` (más ligera que la otra
  opción `continente-oscuro.png`, 39 KB vs 3.5 MB).

### Archivos

| Archivo | Contenido |
|---|---|
| `src/stores/theme.ts` | `BackgroundType`, campo `type` en `BackgroundDef`, fondo `world` |
| `src/components/Background.tsx` | Render de imágenes con `blur(80px)` + `scale(1.1)` |
| `public/backgrounds/mundo-mn.webp` | Imagen del fondo "Mundo Costero" |
| `docs/frontend-standards.md` | §9.2 ampliado con tipos de fondo y nota técnica de blur |
| `docs/change-log-frontend.md` | Esta entrada |

### Verificación

- `pnpm lint` ✅ · `pnpm typecheck` ✅ · `pnpm test` ✅ (24 passed) ·
  `pnpm build` ✅
- Confirmado manualmente en navegador por el usuario: el fondo `world` aparece
  en el selector y el crossfade entre `cave` (gradiente) y `world` (imagen
  difusa) se ve suave y estético.

### Fix — "Desenfoque estratégico" del fondo de imagen (2026-08-08)

> **Origen**: tras la prueba manual, el fondo `world` con `blur(80px)` +
> `scale(1.1)` se veía como una mancha abstracta de color — el desenfoque era
> excesivo y destruía la imagen. El usuario pidió que el desenfoque fuera
> "estratégico": ver la silueta del paisaje en el centro, con los bordes
> integrados al tema oscuro del panel.

### Alcance

- **`Background.tsx`**:
  - Filtro reducido de `blur(80px)` → `blur(12px)` y `scale(1.1)` → `scale(1.05)`.
  - **Nueva capa de viñeta radial** encima de la imagen (solo `type: 'image'`):
    `radial-gradient(circle at 50% 50%, transparent 40%, rgba(9,10,20,0.85) 100%)`.
    Oscurece los bordes de forma estratégica sin ocultar el centro del paisaje.

### Decisiones

- **Desenfoque estratégico, no extremo**: `blur(12px)` mantiene la coherencia
  con el glassmorphism (los detalles nítidos no atraviesan el cristal de las
  superficies) pero deja ver la forma del paisaje (océano/tierra) en el centro.
- **La viñeta radial es la clave del acabado**: el gradiente transparente →
  `rgba(9,10,20,0.85)` funde los bordes con el tema oscuro del panel de forma
  gradual, evitando el corte duro de un simple `bg-black/30`.

### Archivos

| Archivo | Contenido |
|---|---|
| `src/components/Background.tsx` | `blur(12px)` + `scale(1.05)` + viñeta radial para imágenes |
| `docs/frontend-standards.md` | §9.2 nota técnica actualizada (blur 12px + viñeta radial) |
| `docs/change-log-frontend.md` | Esta entrada |

### Verificación

- `pnpm lint` ✅ · `pnpm typecheck` ✅ · `pnpm test` ✅ (24 passed) ·
  `pnpm build` ✅
- Confirmado manualmente en navegador por el usuario: seleccionar "Mundo
  Costero" muestra el paisaje en el centro mientras los bordes se fusionan con
  el tema oscuro.

### Header — refactor a bloques flotantes (glassmorphism) (2026-08-08)

> **Origen**: el `Header` era una barra sólida (`pixel-panel` con borde).
> `frontend-standards.md §9.1` exige bloques individuales "islas" flotando
> sobre el fondo dinámico. Refactor completo del header, descartando la
> barra previa.

### Alcance

- **Contenedor (**`Header`**)** pasa de barra a `flex-row` sin fondo propio:
  `sticky top-0 z-20 flex flex-row items-center gap-3 px-4 py-3`. El
  `AppLayout` ya no aporta ninguna superficie de barra al header.
- **4 bloques independientes**, cada uno un div propio con la superficie
  `glass` del mockup (§9.1/§9.2):
  `bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-xl px-4 py-2.5 flex items-center shrink-0`, separados por `gap-3`.
  - **1 · Izq**: logo "BEDROCK PANEL" (pixel-title) + icón sword + flecha de
    colapso del sidebar.
  - **2 · Centro-izq**: selector de servidor real (dropdown) con icono de
    espada, "Servidor: {nombre}" y estado en línea con punto verde.
  - **3 · Centro-der**: contador de jugadores (avatar verde + "X / 10
    jugadores").
  - **4 · Derecha**: campana con badge de pendientes, engranaje y menú de
    perfil con avatar y chevron.
- **Estado de colapso del sidebar elevado** a `AppLayout` (era local a
  `Sidebar` con `useState`); ahora `Sidebar` y el bloque 1 del header
  comparten `collapsed`/`onToggleCollapsed` vía props.
- Contador de jugadores y badge de la campana como placeholders (0) hasta
  cablearlos a eventos del WS.

### Archivos

| Archivo | Contenido |
|---|---|
| `src/components/layout/Header.tsx` | Refactor a 4 bloques flotantes sin barra |
| `src/components/layout/AppLayout.tsx` | Eleva estado de colapso y limpia el contenedor |
| `src/components/layout/Sidebar.tsx` | Recibe `collapsed`/`onToggleCollapsed` por props (colaboración mínima) |
| `docs/change-log-frontend.md` | Esta entrada |

### Verificación

- `pnpm lint` ✅ · `pnpm typecheck` ✅ · `pnpm build` ✅
- Confirmado manualmente en navegador por el usuario: el header se ve como
  bloques "isla" flotantes sobre el fondo, no como una barra (la flecha de
  colapso del header se eliminó en la entrada posterior de iconos; el control
  vive en el Sidebar).

> **Nota**: para que el flecha de colapso del bloque 1 controlara el sidebar
> fue necesario elevar el estado de colapso (que residía en `Sidebar`) a
> `AppLayout` y pasarlo por props — `Sidebar.tsx` se tocó solo para recibir
> esas props; la decisión del mockup no cambió.

### Header — Reemplazo de iconos del header por imágenes reales y eliminación del botón de colapso del sidebar (2026-08-08)

> **Origen**: revisión visual del header en bloques. Los iconos lucide
> (espada gris y cabeza de Steve con degradado) no transmitían el lenguaje
> "ítem de Minecraft"; el botón de colapso del sidebar duplicaba al que ya
> vive en el propio `Sidebar`.

### Alcance

- **Se elimina el botón de colapso** del header (bloque 1): desaparece el
  `<button>` con `<ChevronLeft />` que quedaba a la izquierda del selector de
  servidor. El header ahora arranca directamente con el selector. El control de
  colapso sigue disponible en el `Sidebar` (donde vive el logo "BEDROCK
  PANEL"). Las props `collapsed`/`onToggleCollapsed` se mantienen en la firma
  (renombradas `_collapsed`/`_onToggleCollapsed`) para no romper el contrato con
  `AppLayout`.
- **Selector de servidor**: el icono de espada gris (lucide `Sword`) se
  reemplaza por `<img src="/icons/Diamond_Sword_JE3_BE3.webp">` con clases
  `w-4 h-4 object-contain shrink-0` (ícono real de Minecraft).
- **Contador de jugadores**: el span con degradado (cabeza de Steve) se
  reemplaza por `<img src="/icons/dressing_room_skins.png">` con las mismas
  clases (ícono real de Minecraft).

### Archivos

| Archivo | Contenido |
|---|---|
| `src/components/layout/Header.tsx` | Elimina botón de colapso, reemplaza iconos por `<img>` reales |
| `docs/change-log-frontend.md` | Esta entrada |

### Verificación

- `pnpm lint` ✅ · `pnpm typecheck` ✅
- Confirmado manualmente en navegador por el usuario: el botón `<` ya no
  aparece en el header y ambas imágenes (`Diamond_Sword_JE3_BE3.webp` y
  `dressing_room_skins.png`) se renderizan en sus bloques.

### Extensión — Capa "pixel" reutilizable en <Button> + "Crear servidor" (2026-08-10)

> **Origen**: la tarea pedía un bloque de botón "pixel" reutilizable (el mockup
> §9.3 lo mostraba como un bloque saliente de Minecraft) y un modal "Crear
> servidor" real en el header. Todo verificado contra el backend: `server.create`
> es `PANEL_ACTION` (solo admin/super_admin), `CreateServerRequest =
> {name 1..128, version?, template_id?}` y el puerto lo asigna el pool (no va en
> el form).

### Decisiones

- **Capa pixel en el `Button` existente** (no librería nueva): la variante y la
  mecánica viven en `button.tsx` (cva) con dos slot extras:
  - `pixel`: activa `pixel-btn` (bevel duro de dos tonos SIN blur, border-radius
    0). Estados en CSS: hover = wash blanco + brightness, active = el bloque se
    *hunde* (invierte el bisel + `translateY(2px)`), disabled = desaturado
    oscuro y aplanado.
  - `pixelTexture` (default `true`): añade un overlay de ruido 8×8 Stone-esco
    con `blend-mode: overlay` para que la textura funcione sobre **cualquier**
    color de variante sin re-pintar una paleta por variante.
  - Uso: `<Button variant="start" pixel>` — el `<Button>` base no cambia su
    contrato, así que los botones no-pixel del resto del app siguen intactos.
  - Se **elimina** el uso manual de la clase `pixel-btn` que había en
    `ServerCard.tsx` (el bisel quedaba incompleto y ya lo provee la variante).
- **Nueva variante `create`** (violeta `bg-violet-600`) en `button.tsx` para
  acciones de creación. No estaba en la paleta §9.3 (que solo cubría
  emerald/red/amber/blue); se extiende el estándar.
- **Helper `useCan(action)`** en `lib/auth/useCan.ts`: a falta de endpoint de
  "mis permisos" (§3/§12 del estándar), centraliza el mapeo `permiso panel →
  roles mínimos` (`server.create` → admin/super_admin) y lo usa el header para
  **ocultar** (no deshabilitar) el botón. Autorización real siempre la aplica el
  backend (403 si no puede). Reutilizable para futuros botones de panel (§6).
- **Modal "Crear servidor"** (`CreateServerDialog.tsx`): wrapper shadcn
  `dialog.tsx` nuevo sobre `@radix-ui/react-dialog` (ya instalado) + formulario
  de estado local (patrón LoginPage, NO react-hook-form/zod — primera vez que se
  usa Dialog; se documenta la elección por consistencia con el resto del app).
- **Mapeo de errores**: `SERVER.ALREADY_EXISTS` (verificado en
  `modules/server/domain/errors.py`) se muestra como error de campo *Nombre*;
  el resto usa `getApiMessage`/`getApiCode`.
- **Íconos**: se mantiene `lucide-react` (`Plus`) para el botón — el estándar
  §9.3 reserva pixel-art solo para íconos de dominio; una acción de UI puntual
  como "crear" es un ícono de UI normal.
- **Cache**: `useCreateServer` (nueva mutation) invalida `serverKeys.all` en
  éxito; el resto de la lista del header se refresca por TanStack Query.

### Archivos

| Archivo | Contenido |
|---|---|
| `src/components/ui/button.tsx` | Variante `create`, slots `pixel`/`pixelTexture` |
| `src/styles/pixel-theme.css` | `.pixel-btn` completo (estados) + `.pixel-btn-texture` |
| `src/features/servers/components/ServerCard.tsx` | `pixel` en los 4 botones de acción |
| `src/components/ui/dialog.tsx` | Wrapper shadcn de `@radix-ui/react-dialog` |
| `src/lib/auth/useCan.ts` | Helper/paquete rol→permiso panel |
| `src/features/servers/components/CreateServerDialog.tsx` | Modal "Crear servidor" |
| `src/features/servers/hooks.ts` | `useCreateServer` (invalida lista) |
| `src/components/layout/Header.tsx` | Botón (oculto sin permiso) + modal |
| `docs/frontend-standards.md` | Variante `create` + capa `pixel` en §9.3 |
| `docs/change-log-frontend.md` | Esta entrada |

### Verificación

- `pnpm vitest run`: 24/24 ✅ (6 archivos)
- `pnpm build`: typecheck + build OK (solo warning de chunk > 500 kB, no bloquea)
- Confirmado manualmente en navegador por el usuario: bisel/press y textura
  del botón pixel en cada variante, el modal "Crear servidor" crea un servidor
  real, y el botón es visible solo para admin/super_admin.

### Extensión — Campana de notificaciones + sincronización de lista (auditoría WS, 2026-08-10)

> **Origen**: auditoría de sincronización en tiempo real (§30 del changelog
> backend). El backend arregló las causas de datos (CPU real, jugadores
> parseados, dedup del doble-inspect). Del lado frontend quedaron dos síntomas
> a corregir aquí: la campana no existía (era un botón muerto) y el header no
> sincronizaba el estado del servidor. Causa real del header: `useServerStateSync`
> solo actualizaba la cache del **detalle**, no la de la **lista**.

### Decisiones

- **`useServerStateSync` actualiza las DOS cachés** (`['server', id]` detalle +
  `['servers']` lista que lee el selector del header) desde el mismo handler de
  WS. Patrón §13.2 del estándar: un evento → N cachés, sin duplicar lógica. Se
  extrae `applyState`.
- **`serverKeys` se mueve a `lib/api/servers.ts`** para romper el import
  circular entre `features/servers/hooks.ts` y `hooks/useServerStateSync.ts`;
  `hooks.ts` lo re-exporta para no romper consumidores.
- **Campana real** (`NotificationsBell` + `useNotifications` +
  `useNotificationsStore`):
  - Filtro de eventos: solo `SERVER.STARTED/STOPPED/CRASHED`,
    `PLAYER.JOINED/LEFT`, `BACKUP.COMPLETED/FAILED`, `TASK.FAILED`. El ruido
    (`SERVER.STATE` de monitoring, `CONSOLE.OUTPUT`) se filtra en el hook
    (lista `NOTIFICATION_EVENTS`), no en el store.
  - Suscripciones: `global` + `user:{id}` + `server:{id}` de los servidores
    visibles (vía `useServers`), memoizadas para no re-suscribir por render.
  - "Leído" es estado local zustand (no hay endpoint REST de notificaciones en
    el backend — verificado). Marcar leído al abrir el dropdown.
  - Store deduplica por `seq` (los `resume` re-emiten eventos ya vistos) y
    limita a `MAX_ITEMS`.
  - Dropdown lista evento + tiempo relativo, con ícono de estado (verde =
    ok, rojo = fallo/crash).
- **Síntoma 3 (stats)**: no se tocó el frontend — `StatCards` ya leía
  `useMonitoringStore` (RAM funcionaba). El fix fue 100% backend (CPU real,
  jugadores). Disco sigue 0/«sin fuente» documentado.

### Archivos

| Archivo | Contenido |
|---|---|
| `src/hooks/useServerStateSync.ts` | Actualiza detalle + lista (`applyState`) |
| `src/lib/api/servers.ts` | `serverKeys` movido aquí (rompe circular) |
| `src/features/servers/hooks.ts` | Re-exporta `serverKeys` |
| `src/stores/notifications.ts` | Store zustand (items, dedup por seq, markAllRead) |
| `src/hooks/useNotifications.ts` | Suscripciones + filtro de eventos de notificación |
| `src/components/layout/NotificationsBell.tsx` | Badge + dropdown + mark-leído |
| `src/components/layout/Header.tsx` | Usa `NotificationsBell` (quita botón muerto) |
| `src/components/layout/NotificationsBell.test.tsx` | Badge, sin badge, mark-leído al abrir, dedup seq, orden |
| `src/features/servers/ServerDetailPage.test.tsx`, `src/components/layout/Header.test.tsx` | Mocks actualizados con `serverKeys` |
| `docs/frontend-standards.md` | §4 corregido (dos WS) + §13 nuevo (patrón de sync) |
| `docs/change-log-frontend.md` | Esta entrada |

### Verificación

- `pnpm vitest run`: 29/29 ✅ (7 archivos)
- `pnpm build`: typecheck + build OK (solo warning de chunk > 500 kB)
- `pnpm lint`: ✅
- Confirmado manualmente en navegador por el usuario: iniciar/parar un servidor
  real cambia el header a "En línea"/"Detenido" sin refrescar y la campana
  muestra la notificación; el stat de Jugadores y CPU se mueven en vivo.
  (Conectar un jugador real queda pendiente de prueba con un cliente Bedrock —
  criterio de la Fase 5.)

### Fix — Badge de jugadores del header (fuente en vivo del WS de monitoring, 2026-08-10)

> **Origen**: pasada de verificación con el servidor real `prubea-panel`
> (change-log backend §30). El contador "X / N jugadores" del header era un
> placeholder hardcodeado (`onlinePlayers = 0`) mientras el StatCard
> "Jugadores" ya leía en vivo de `useMonitoringStore`. Mismo root cause que el
> dropdown de estado: el header no apuntaba a la fuente en vivo.

### Decisiones

- **El header lee de la misma fuente que el StatCard**: `currentSnapshot(snapshots,
  activeServerId)` de `useMonitoringStore` (WS de monitoring del servidor
  activo). No usa REST inicial ni query aparte. `players_max` con el mismo
  fallback que StatCards (`Math.max(snap.players_max, 10)`).
- **WS de monitoring del servidor activo conectado a nivel de layout**:
  `AppLayout` llama `useServerMonitoring(activeServerId ?? undefined)`, así el
  badge tiene datos en vivo en cualquier página (no solo en el detalle).
- **`useServerMonitoring` ahora es idempotente por servidor** (refcount
  compartido en un registry de módulo): AppLayout y ServerDetailPage comparten
  UN socket para el mismo servidor (frontend-standards §4 — "los componentes
  leen del store, no abren su propio socket"). El snapshot se limpia solo
  cuando el ÚLTIMO suscriptor se desmonta.
- **`currentSnapshot` ampliado a `string | null | undefined`** (el id activo
  puede ser `null`); `serverId ?? ''` → EMPTY.

### Archivos

| Archivo | Contenido |
|---|---|
| `src/components/layout/Header.tsx` | Badge lee `useMonitoringStore` del servidor activo |
| `src/components/layout/AppLayout.tsx` | `useServerMonitoring(activeServerId)` global |
| `src/hooks/useServerMonitoring.ts` | Refactor a socket compartido por servidor (refcount) |
| `src/stores/monitoring.ts` | `currentSnapshot` acepta `null`/`undefined` |
| `src/components/layout/Header.test.tsx` | +1 test: badge muestra jugadores en vivo del WS |

### Verificación

- `pnpm vitest run`: 30/30 ✅ (7 archivos)
- `pnpm lint` ✅ · `pnpm typecheck` ✅
- Confirmado manualmente en navegador por el usuario: con el servidor real
  corriendo, el badge del header refleja el mismo contador que el StatCard
  "Jugadores" sin refrescar (jugadores en vivo desde el WS de monitoring).

### Cierre ADR-013 + contrato de consumo WS (§14) + auditoría de sockets (2026-08-10)

> **Origen**: revisión posterior a la pasada (change-log backend §30). No dejar
> la migración Monitoring→gateway en Proposed indefinido; formalizar quién
> consume qué en el frontend; y auditar que no queden sockets directos sueltos.

### Decisiones

- **ADR-013 cerrado como Rejected** (docs/adr.md): los dos WS son modelos de
  consistencia distintos — event log de negocio con `resume` por `seq` (gateway
  `/ws`) vs. telemetría de último valor descartable (WS de monitoring por
  servidor). No hay problema de escala real (2 sockets por pestaña, independiente
  de la cantidad de servidores: el de monitoring sigue solo al activo, refcount
  compartido). El riesgo de tocar el transporte recién estabilizado no se
  justifica sin un problema medible. Se escribe un **trigger de revisión
  futuro** explícito (límite de conexiones, latencia comprobada, costo de
  mantenimiento real) — el tema no se reabre de forma especulativa.
- **`frontend-standards.md` §14 nuevo — contrato de consumo WS**: exactamente
  dos stores de lectura con nombre real del código: `useNotificationsStore`
  (`stores/notifications.ts`) para cambio de estado/evento de negocio vía
  gateway (`useWebSocketStore`, `stores/ws.ts`); `useMonitoringStore`
  (`stores/monitoring.ts`) para telemetría numérica continua (CPU/RAM/disco/
  jugadores). Ningún componente abre socket propio; los dueños de socket son
  solo `useWebSocketStore` (singleton) y `useServerMonitoring` (refcount).
- **Auditoría puntual de sockets** (no se asumió que estaba bien): `grep` de
  `new WebSocket(`/`EventSource` en `apps/frontend/src`. Resultado: solo
  aparecen en `lib/ws/WebSocketClient.ts` (cliente del gateway, creado por
  `stores/ws.ts`) y `hooks/useServerMonitoring.ts` (telemetría) — **ningún
  componente abre socket directo** fuera de esos dos dueños.

### Archivos

| Archivo | Contenido |
|---|---|
| `docs/adr.md` | ADR-013 → Rejected + trigger de revisión futuro |
| `docs/frontend-standards.md` | §4 cross-ref + §14 (dueños de socket, tabla de consumo, reglas) |
| `docs/change-log-frontend.md` | Esta entrada |

### Verificación

- Auditoría: `grep -n "new WebSocket\\|EventSource" apps/frontend/src` → solo
  2 dueños de socket en producción (gateway singleton + telemetría). Sin
  cambios de código en esta entrada (docs + verificación).

### Extensión — Actualizar recursos de servidor (CPU/RAM) (2026-08-10)

> **Origen**: cierre de la Fase 2 del plan. Quedaba la acción de escritura
> sobre recursos sin UI; el backend ya la expone (`PUT /servers/{id}/resources`)
> con `UpdateServerResourcesUseCase` y el detalle ya devuelve `resources`.

### Decisiones

- **Contrato verificado contra el código real del backend** (no copiado del
  prompt): `api/schemas.py` → `UpdateResourcesRequest` con `cpu_cores` opcional
  (float 1..64) y `ram_mb` opcional (int 512..65536); respuesta 200
  `ServerResponse` (sin `resources`); `ServerDetailResponse` sí expone
  `resources` actuales → el modal precarga los valores del detalle.
  `domain/errors.py`: `SERVER.RESOURCES_INVALID` (422) y `SERVER.BUSY` (409).
  El use case recrea el contenedor solo si algo cambió y publica
  `SERVER.RESOURCES_CHANGED`; el ciclo de recreación emite `SERVER.STARTING`
  → el sync WS existente (`useServerStateSync`) ya lo refleja, **sin** sumar
  `RESOURCES_CHANGED` a `STATE_EVENTS`.
- **Permiso**: `server.update` es WRITE_ACTION (ámbito server, no PANEL_ACTION
  como `server.create`) → la tienen operator/admin/super_admin. Se extiende
  `PANEL_MIN_ROLES['server.update'] = ['operator', 'admin', 'super_admin']` en
  `lib/auth/useCan.ts`; sin permiso el botón se oculta (el backend además
  responde 403, que se maneja sin romper la UI).
- **UI**: modal reutilizando `dialog.tsx` con el patrón de `CreateServerDialog`
  (estado local + `getApiMessage`/`getApiCode`, sin react-hook-form). Botón en
  la columna de acciones de la card del detalle (junto a Iniciar/Reiniciar/
  Detener/Crear backup), no en la card pequeña del header. Validación client-side
  de rangos (CPU 1..64, RAM 512..65536) y envío solo de los campos cambiados;
  aviso explícito de reinicio si el servidor está en línea. `409 SERVER.BUSY`
  muestra `detail.message` del backend tal cual.
- **Cache**: `useUpdateResources` escribe el `ServerResponse` en el detalle y
  además invalida detalle y lista (la respuesta no trae `resources`, hay que
  re-fetchear los valores nuevos).

### Archivos

| Archivo | Contenido |
|---|---|
| `src/lib/api/servers.ts` | `UpdateServerResourcesRequest` + `updateServerResources` |
| `src/lib/auth/useCan.ts` | `server.update` en `PANEL_MIN_ROLES` |
| `src/features/servers/hooks.ts` | `useUpdateResources` (setQueryData + invalidación) |
| `src/features/servers/components/UpdateResourcesDialog.tsx` | Modal (nuevo) |
| `src/features/servers/components/ServerCard.tsx` | Botón integrado en la columna de acciones |
| `src/features/servers/components/UpdateResourcesDialog.test.tsx` | Tests del modal (nuevo) |
| `src/features/servers/hooks.test.tsx` | Tests del hook (nuevo) |
| `docs/frontend-implementation-plan.md` | Fase 2 cerrada (extensión implementada) |

### Verificación

- Tests vitest: **44 passed (9 files)** — incluye el hook (éxito escribe cache e
  invalida detalle+lista, 422/403 no invalidan) y el modal (oculto sin permiso,
  precarga de valores, validación de rangos, aviso de reinicio solo en línea,
  `409` muestra `detail.message`, `422` de FastAPI muestra fallback, 403 no
  rompe la UI).
- `pnpm typecheck` ✅ · `pnpm lint` ✅ · `pnpm build` ✅ (warning de chunk
  >500 kB conocido, no bloqueante).

### Fase 3 — Consola en vivo (2026-08-10)

> **Origen**: alcance del plan (`frontend-implementation-plan.md` §Fase 3).
> El contrato se verificó contra el backend real y corrigió varios supuestos del
> borrador inicial.

### Decisiones

- **El streaming NO usa el gateway**: la consola tiene un WS dedicado por
  servidor `/servers/{id}/console/ws?token=&after_seq=` (ADR-002, `console/api/
  router.py::console_ws`), igual que el de monitoring. El gateway no reenvía
  `CONSOLE.*` (verificado: ninguna referencia en `modules/notification`). Se
  replica el patrón de `useServerMonitoring` (registry con refcount por
  servidor + reconexión con backoff), NO el `useWebSocketStore.subscribe` del
  borrador (esa API no existe en `stores/ws.ts`).
- **Histórico sin polling HTTP**: `after_seq=-1` reproduce todo el buffer del
  backend (`ConsoleLog.since()` es exclusivo y los seq empiezan en 0); al
  reconectar o volver a la página se reanuda desde `lastSeq` guardado en el
  store (sin duplicar líneas). El `GET .../console/buffer` no se usa en la UI.
- **Envelope `CONSOLE.OUTPUT`**: `{event, server_id, scope: 'console',
  payload: {line}, ts, seq}` — se amplió `WsEnvelope.scope` para incluir
  `'console'`. `payload.line` es la línea cruda.
- **Envío de comandos**: `POST /servers/{id}/console/commands` devuelve **202**
  con `CommandAckResponse = {server_id, command, priority, seq, at}` (no un 200
  `{status}` como asumía el borrador). Body `{command: 1..512}` (priority
  default `normal`). Permiso real: **`server.console.write`** (WRITE_ACTION →
  operator+) para enviar y `server.console.read` (viewer+) para ver — se mapea
  `server.console.write` en `PANEL_MIN_ROLES`; sin permiso se oculta el input
  (el backend además responde 403). Errores `CONSOLE.*` (`SERVER_OFFLINE`,
  `COMMAND_REJECTED`, …) con `getApiMessage` inline, **sin toasts** (sonner no
  está instalado).
- **Aviso offline**: si el servidor no está `running`, banner ámbar + input y
  botón deshabilitados (el backend además responde `CONSOLE.SERVER_OFFLINE`).
- **Sidebar**: el ítem "Consola" estaba `disabled: true`; se cableó a
  `/servers/:serverId/console` usando el servidor activo (campo `sub` por ítem)
  y el activo ahora se calcula por match exacto del pathname.
- **Store**: `useConsoleStore` con buffer por servidor (límite 1000, igual que
  el anillo del backend) + `lastSeq` por servidor para resume idempotente. El
  buffer NO se limpia al desmontar (el scrollback persiste en la sesión).

### Archivos

| Archivo | Contenido |
|---|---|
| `src/stores/console.ts` | Store de líneas + `lastSeq` (nuevo) |
| `src/lib/api/console.ts` | `sendConsoleCommand` + tipos (202) (nuevo) |
| `src/features/console/hooks.ts` | `useConsole` (WS dedicado) + `toConsoleLine` + `useSendCommand` (nuevo) |
| `src/features/console/components/ConsoleTerminal.tsx` | Terminal (nuevo) |
| `src/features/console/ConsolePage.tsx` | Página `/servers/:serverId/console` (nuevo) |
| `src/app/router.tsx` | Ruta de la consola |
| `src/components/layout/Sidebar.tsx` | ítem "Consola" cableado + activo por pathname |
| `src/lib/auth/useCan.ts` | `server.console.write` |
| `src/lib/ws/types.ts` | `scope` incluye `'console'` |
| Tests | `stores/console.test.ts`, `features/console/hooks.test.tsx`, `ConsoleTerminal.test.tsx`, `ConsolePage.test.tsx`, `Sidebar.test.tsx` |
| `docs/frontend-implementation-plan.md` | Fase 3 implementada, verificación manual pendiente |

### Verificación

- Tests vitest: **65 passed (14 files)** — store (anillo 1000, lastSeq, clear),
  `toConsoleLine` (filtro evento/servidor/línea vacía), envío (202), terminal
  (líneas, vacío, banner offline, input oculto sin permiso, envío, error
  `CONSOLE.SERVER_OFFLINE`), página (carga/spinner/error), sidebar (links
  Consola/Servidor + activo).
- `pnpm typecheck` ✅ · `pnpm lint` ✅ · `pnpm build` ✅ (warning de chunk
  conocido).
- **Verificación manual (2026-08-10) ✅ confirmada por el usuario en
  navegador**: logs reales en vivo en la UI y comando enviado reflejado en
  `docker logs`. Además confirmado el comportamiento de la terminal: al enviar
  un comando el input se vacía y el foco permanece en el campo, y el scroll
  baja automáticamente para mostrar la respuesta. **Fase 3 cerrada.**

### Fix — Botón "Crear servidor" solo en la página de detalle (2026-08-10)

> **Origen**: revisión tras la Fase 3. El botón "Crear servidor" del header se
> mostraba en cualquier ruta protegida (también en la consola), cuando la acción
> pertenece al detalle del servidor.

### Decisiones

- El `Header` ahora renderiza `<CreateServerDialog/>` solo cuando
  `useMatch('/servers/:serverId')` matchea la ruta exacta del detalle. `useMatch`
  NO matchea rutas con segmentos extra, así que en `/servers/:id/console` (o
  cualquier página futura de la Fase 4) el botón no aparece. La visibilidad por
  permiso (`server.create`) sigue dentro del dialog, sin cambios.
- Tests del header cubren ambos casos (visible en `/servers/s1`, oculto en
  `/servers/s1/console` y en la raíz), sembrando `identity.roles: ['admin']` en
  `useAuthStore` (sin mockear `useCan`).

### Archivos

| Archivo | Contenido |
|---|---|
| `src/components/layout/Header.tsx` | `useMatch` + render condicional del dialog |
| `src/components/layout/Header.test.tsx` | Tests del botón por ruta |

### Verificación

- Tests vitest: **67 passed (14 files)** · `pnpm typecheck` ✅ · `pnpm lint` ✅ ·
  `pnpm build` ✅.

### Nota — IP mostrada (`172.18.0.1:19136`)

- No es un bug del frontend: `connection.host` viene solo de
  `server.public_host` (`modules/server/application/results.py:36`,
  `connection_from_spec`), es decir de la env
  `BEDROCK_PANEL_SERVER_PUBLIC_HOST` (default `localhost`). El compose de dev
  ya la reenvía (`docker-compose.dev.yml`: `${BEDROCK_PANEL_SERVER_PUBLIC_HOST:-localhost}`).

### Mejora — Consola: foco persistente tras enviar y estilo terminal (2026-08-10)

### Decisiones

- **Foco tras envío**: al enviar un comando el input se vacía y el foco vuelve
  al campo. El `ref` se adjunta al `<Input>` con `ref={inputRef}` (faltaba), y
  `focus()` se llama desde un `useEffect` en lugar de síncronamente: durante el
  envío el input está `disabled` (por `isPending`), así que enfocar en ese
  instante es un no-op. El effect se keyea con `[command, sendCommand.isPending]`
  y un flag `focusOnEnable` garantiza que solo se enfoca tras el commit donde el
  input ya no está deshabilitado (los commits de `isPending→false` y `command→''`
  pueden llegar en cualquier orden).
- **Estilo terminal**: fondo `bg-black`, texto verde claro (`text-green-400`),
  fuente `font-mono` (`text-sm`), input con `bg-black/50`, borde `border-white/10`
  y placeholder gris. El auto-scroll se mantiene (se pausa si el usuario sube).

### Archivos

| Archivo | Contenido |
|---|---|
| `src/features/console/components/ConsoleTerminal.tsx` | `ref` del input, `useEffect` de foco, estilo terminal |
| `src/features/console/components/ConsoleTerminal.test.tsx` | Aserción `toHaveFocus()` en el envío exitoso |

### Verificación

- Tests vitest: **67 passed (14 files)** · `pnpm typecheck` ✅ · `pnpm lint` ✅ ·
  `pnpm build` ✅.
- Para acceder desde un celular/otro dispositivo: exportar la IP local del host
  antes de levantar el contenedor, p. ej.
  `BEDROCK_PANEL_SERVER_PUBLIC_HOST=192.168.1.10 docker compose -f docker-compose.dev.yml up -d`
  (o fijarla en `.env`). El contenedor se recrea al cambiar la env. No se
  implementó ningún parche en el frontend: no resolvería el acceso desde otros
  dispositivos.

---

## Fase 4 — Limpieza de ruido en dev (WS y Button)

> **Fecha**: 2026-08-10/11. Tres problemas de ruido de desarrollo detectados al
> verificar la consola y las notificaciones tras jugar: warnings de React por el
> atributo `pixel`, errores "WebSocket is closed before the connection is
> established" al cerrar sockets aún en `CONNECTING`, y (en el backend) spam
> DEBUG del SDK de Docker. Este cambio cubre la parte de frontend; el log del
> backend se trata en `docs/change-log.md`.

### Alcance

- **Button (`components/ui/button.tsx`)**: el componente no desestructuraba las
  props de variante `pixel` / `pixelTexture` y las reenviaba al DOM como
  atributos booleanos → warning de React "Received `true` for a non-boolean
  attribute `pixel`". Ahora se desestructuran y se pasan a `buttonVariants()`
  (se dejaron de emitir al `<button>`).
- **Cierre de WebSockets en `CONNECTING`** (ruido de dev por el doble montaje de
  React StrictMode): `WebSocketClient.close()`, `useServerMonitoring.closeSocket`
  y `useConsole.closeSocket` ya no llaman `socket.close()` mientras el socket está
  en `CONNECTING` (el navegador loguea "WebSocket is closed before the
  connection is established"); el cierre se difiere al `onopen`. En sockets
  `OPEN` el comportamiento es idéntico al anterior.
- Los errores `ECONNRESET` del proxy WS de Vite no son un bug: aparecen cuando el
  backend se reinicia (`uvicorn --reload` al editar archivos o al recrear el
  contenedor) y las conexiones en vuelo se caen. Los tres clientes WS reconectan
  con backoff automáticamente (verificado: el backend vuelve a emitir `[accepted]`
  para el gateway, monitoring y console tras cada reinicio).

### Archivos

| Archivo | Cambio |
|---|---|
| `src/components/ui/button.tsx` | Desestructura `pixel`/`pixelTexture` y las pasa a `buttonVariants` |
| `src/lib/ws/WebSocketClient.ts` | `close()` difiere el cierre en `CONNECTING` |
| `src/hooks/useServerMonitoring.ts` | `closeSocket` difiere el cierre en `CONNECTING` |
| `src/features/console/hooks.ts` | `closeSocket` difiere el cierre en `CONNECTING` |
| `src/lib/ws/WebSocketClient.test.ts` | Test del cierre diferido en `CONNECTING` |

### Verificación

- Tests vitest: **68 passed (14 files)** · `pnpm typecheck` ✅ · `pnpm lint` ✅ ·
  `pnpm build` ✅.

---

## Fase 4 — Parte 1: Módulo World (Mundos)

> **Fecha**: 2026-08-10/11. Implementación del módulo World en el frontend:
> listar, crear, importar (multipart), sincronizar, exportar, duplicar, activar y
> eliminar mundos. Contrato verificado contra
> `apps/backend/src/app/modules/world/api/router.py` y `schemas.py` (no asumido).

### Alcance

- **`lib/api/worlds.ts`**: tipos (`World`, `CreateWorldRequest`,
  `DuplicateWorldRequest`) y clientes de API. Correcciones sobre el borrador:
  - `GET/POST /worlds/sync` devuelven **array** (`list[WorldResponse]`), no
    `{worlds: []}` → `listWorlds`/`syncWorlds` devuelven `World[]`.
  - `DuplicateWorldRequest` usa el campo **`target`** (schemas.py), no `name`.
  - El import NO fija `Content-Type` a mano: `apiClient` trae
    `application/json` por defecto y el navegador debe generar el
    `multipart/form-data; boundary=…` para que FastAPI parseee el body.
  - `worldKeys` viven en el módulo de API (evita import circular, patrón de
    `servers.ts`).
- **`features/worlds/hooks.ts`**: `useWorlds` (el `queryFn` hace sync primero —
  `POST /worlds/sync` devuelve la lista reconciliada — con fallback a
  `GET /worlds`; `refetchOnWindowFocus: false`), `useCreateWorld`,
  `useImportWorld`, `useExportWorld`, `useDuplicateWorld`, `useActivateWorld`,
  `useDeleteWorld`. Todas invalidan `worldKeys.all(serverId)` al escribir.
- **Componentes**: `WorldList` (lista + badge Activo + menú exportar/duplicar/
  eliminar), `CreateWorldDialog` e `ImportWorldDialog` (errores inline con
  `getApiMessage`, sin toasts — sonner no está instalado).
- **`WorldsPage`**: usa `useParams<{ serverId }>` (la ruta real usa `:serverId`,
  no `:id`); estados de carga/error inline; export dispara la descarga del blob
  como `.mcworld`.
- **`lib/utils.ts`**: nuevo helper `formatBytes`.
- **Ruta y navegación**: `{ path: '/servers/:serverId/worlds', element:
  <WorldsPage /> }` en `router.tsx`; ítem "Mundos" del Sidebar habilitado con
  `sub: 'worlds'`.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/lib/api/worlds.ts` | Nuevo — tipos y clientes de API World |
| `src/features/worlds/hooks.ts` | Nuevo — hooks de TanStack Query |
| `src/features/worlds/WorldsPage.tsx` | Nuevo — página de mundos |
| `src/features/worlds/components/WorldList.tsx` | Nuevo — lista de mundos |
| `src/features/worlds/components/CreateWorldDialog.tsx` | Nuevo — crear mundo |
| `src/features/worlds/components/ImportWorldDialog.tsx` | Nuevo — importar `.mcworld` |
| `src/lib/utils.ts` | `formatBytes` añadido |
| `src/app/router.tsx` | Ruta `/servers/:serverId/worlds` |
| `src/components/layout/Sidebar.tsx` | ítem Mundos habilitado |

### Verificación

- `pnpm typecheck` ✅ · `pnpm lint` ✅ · `pnpm test` (71 passed) ✅ ·
  `pnpm build` ✅.
- Smoke test contra el backend real: `GET/POST /worlds`, `POST /worlds/sync`
  devuelven exactamente los shapes del contrato; `DELETE` responde 204.
- Tests de componente: `WorldsPage.test.tsx` con `StrictMode` (sync una sola
  vez, fallback a metadata si el sync falla, re-sync con el botón).

---

## Fix — El mundo por defecto no aparecía en la lista de Mundos (2026-08-11)

> **Origen**: tras la Parte 1, el mundo por defecto que el servidor Bedrock
> auto-crea en su primer arranque ("Bedrock level") no aparecía en la lista,
> ni siquiera pulsando "Sincronizar". Diagnóstico en dos capas (backend y
> storage dev); el arreglo del frontend es el auto-sync al cargar la página.

### Causa raíz (backend/storage, tratada en `docs/change-log.md`)

1. **La lista es metadata de BD, no disco**: `GET /worlds` lee la tabla de
   mundos de Postgres; el mundo por defecto vive en disco (`/data/worlds/`) y
   solo se registra en la BD al llamar `POST /worlds/sync`. El create de
   servidor NO lo siembra.
2. **Desajuste de storage en dev**: el backend resolvía su raíz desde la fila
   `storage.base_path` de la BD (`/var/lib/bedrockpanel/data`), mientras los
   contenedores de juego montan `/var/lib/bedrockpanel/{id}` (sin `data/`) →
   `sync` escaneaba un directorio vacío y devolvía `[]`. Se alineó la fila a
   `/var/lib/bedrockpanel` y `docker-compose.dev.yml` ahora monta el storage
   del host en el contenedor del backend.

### Decisión (frontend)

- **Auto-sync al cargar la página de Mundos**: el sync vive **dentro del
  `queryFn` de `useWorlds`** (primero `POST /worlds/sync`, que ya devuelve la
  lista reconciliada, y si falla fallback a `GET /worlds`). Al ser parte de la
  query, React Query lo deduplica por `queryKey` y no hay que gatear el
  render: mientras la primera carga está en curso se muestra
  "Sincronizando mundos…". El botón "Sincronizar" hace
  `invalidateQueries(worldKeys.all(serverId))` → re-sync → refresco, y queda
  siempre activo con el spinner atado a `isFetching`. El diseño inicial usó
  un `useEffect` + `useRef` guard, pero quedaba atascado en dev porque
  StrictMode remonta el componente y la mutación del primer montaje queda
  huérfana (su `onSettled` no corre); ver corrección en `docs/change-log.md`.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/features/worlds/hooks.ts` | `useWorlds` con sync dentro del `queryFn` (dedup + fallback) |
| `src/features/worlds/WorldsPage.tsx` | Sin `useEffect`; botón Sincronizar con `invalidateQueries` |
| `src/features/worlds/WorldsPage.test.tsx` | Tests con `StrictMode`: sync una sola vez, fallback, re-sync |

### Verificación

- `pnpm typecheck` ✅ · `pnpm lint` ✅ · `pnpm test` (68 passed) ✅ ·
  `pnpm build` ✅.
- Backend verificado en vivo: `POST /worlds/sync` devuelve
  `{"name":"Bedrock level", ...}` y `GET /worlds` lo lista (antes devolvían
  `[]`).

## Fix — La importación de mundos no subía el archivo (2026-08-11)

> **Origen**: al importar un `.mcworld`, el backend respondía
> `HTTP.VALIDATION_ERROR` ("Field required" para `file` y `name`) aunque el
> archivo se hubiera adjuntado. La petición salía con cuerpo
> `{"file": {}, "name": "prueba importacion"}` — JSON, no multipart — así que
> FastAPI no encontraba los campos `UploadFile`/`Form`.

### Causa raíz

`src/lib/api/client.ts` fijaba `Content-Type: application/json` por defecto en
la instancia de axios. En axios, si el `Content-Type` ya es JSON y el payload
es un `FormData`, `transformRequest` lo **serializa a JSON**
(`formDataToJSON`) en vez de pasarlo como multipart; el archivo se perdía y el
backend no podía parsear el formulario.

### Cambio

- Se quitó el default global `Content-Type: application/json` de `apiClient`.
  Axios fija `application/json` automáticamente para payloads de objeto
  (`transformRequest`), y deja que el navegador genere el
  `multipart/form-data; boundary=…` cuando el payload es `FormData`.
- `importWorld` no cambia: ya construía el `FormData` con `file` + `name`;
  ahora el header correcto llega al backend.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/lib/api/client.ts` | Quitado el default `Content-Type: application/json` de la instancia |
| `src/lib/api/worlds.ts` | Comentario del multipart actualizado |
| `src/lib/api/client.test.ts` | Tests de regresión: sin default JSON, FormData llega como FormData, objetos siguen como JSON |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**74 passed**, 3 nuevos) ✅.

## Fase 4 — Parte 2: Plantillas (Templates)

> **Fecha**: 2026-08-12
> **Origen**: Parte 2 de la Fase 4 (después de Mundos). Página de plantillas:
> capturar el estado de un servidor (mundo + config) como `.mctemplate`,
> listarlas, aplicarlas a un servidor (reproduce el mundo y la config) y
> eliminarlas.

### Alcance

- `lib/api/templates.ts`: tipos y llamadas de la API de plantillas.
- `features/templates/`: `hooks.ts`, `TemplatesPage.tsx`, `TemplateList.tsx`,
  `CaptureTemplateDialog.tsx` y tests.
- Ruta `/servers/:serverId/templates` + ítem de sidebar "Plantillas"
  habilitado.

### Discrepancias con el plan detectadas contra el backend real

> Regla transversal §123-127: el plan proponía una API que **no** coincide con
> `apps/backend/src/app/modules/template/api/`; se implementó lo que el backend
> expone realmente:

| Aspecto | Propuesto | Backend real (implementado) |
|---|---|---|
| Rutas | Globales `/templates`, `/templates/{id}` | Scoped: `/servers/{id}/templates...` |
| `Template` | `description`, `kind`, `artifact_ref`, `tags` | `id, name, version, size_bytes, origin_server_id, origin_world, created_at, updated_at` |
| Listado | `{templates: []}` | array directo `list[TemplateResponse]` |
| Capture | `name` + `description`/`kind`/`include_world`/`tags` | solo `name` |
| Apply | devuelve `void`, `world_name` requerido | devuelve `TemplateResponse`, `world_name` opcional (vacío = el capturado) |
| UI | `Switch` y `sonner` | no instalados → switch eliminado, errores con el patrón de alerta del resto del frontend |

### Decisiones

- Los errores se muestran con el mismo patrón que `WorldsPage`
  (alerta roja con `getApiMessage`), no con toasts.
- Aplicar una plantilla invalida también `worldKeys` para que el mundo
  reproducido aparezca en Mundos sin pedir sync manual.
- El diálogo de captura solo pide el nombre (el backend no acepta más
  campos). Aplicar pregunta por el nombre del mundo destino con `prompt`
  (opcional: vacío = el capturado en la plantilla).

### Archivos

| Archivo | Cambio |
|---|---|
| `src/lib/api/templates.ts` | API de plantillas (keys + tipos + llamadas) |
| `src/features/templates/hooks.ts` | `useTemplates`, `useCaptureTemplate`, `useApplyTemplate`, `useDeleteTemplate` |
| `src/features/templates/TemplatesPage.tsx` | Página: listar, capturar, aplicar, eliminar |
| `src/features/templates/components/TemplateList.tsx` | Lista con aplicar y menú eliminar |
| `src/features/templates/components/CaptureTemplateDialog.tsx` | Diálogo de captura (nombre) |
| `src/features/templates/TemplatesPage.test.tsx` | Tests: listado, vacío, capturar, aplicar, eliminar |
| `src/app/router.tsx` | Ruta `/servers/:serverId/templates` |
| `src/components/layout/Sidebar.tsx` | Ítem "Plantillas" habilitado → `/servers/:id/templates` |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**79 passed**, 5 nuevos) ✅ · `build` ✅.
- E2E contra el backend real (JWT admin, servidor `5cd56500`): `capture` 201
  (mundo `village` capturado), `apply` crea `tpl-e2e-mundo` (visible tras
  `sync`), `delete` 204 del mundo y de la plantilla. Residuos limpiados.

## Refactor — Diálogos componentizados (sin `window.prompt`/`confirm`)

> **Fecha**: 2026-08-12
> **Origen**: feedback en la revisión de Plantillas — la UI usaba
> `window.prompt`/`window.confirm` del navegador para "Aplicar plantilla"
> (nombre del mundo destino) y para confirmar eliminaciones. El frontend debe
> usar modales React propios, con un componente padre que tenga los estilos y
> reciba el contenido (inputs, botones…) por props.

### Cambios

- Nuevo `src/components/ui/modal.tsx`: **modal base** (componente padre) que
  concentra el contenedor con estilos (overlay + panel pixel + encabezado);
  recibe `title`, `description`, `children` y `footer` por props.
- Nuevo `src/components/ui/confirm-dialog.tsx`: extiende `Modal` — reemplaza
  `window.confirm`. Props: título, descripción, labels de los botones,
  `destructive` (botón rojo) y `busy` (muestra "Confirmando…" y bloquea).
- Nuevo `src/components/ui/prompt-dialog.tsx`: extiende `Modal` — reemplaza
  `window.prompt`. Props: label + placeholder del campo, labels de los botones
  y `onConfirm(value)`.
- `TemplatesPage`: "Aplicar plantilla" usa `PromptDialog` (nombre del mundo
  destino, opcional) y "Eliminar" usa `ConfirmDialog`.
- `WorldsPage`: "Duplicar" usa `PromptDialog` y "Eliminar" usa
  `ConfirmDialog` (se eliminaron los `window.prompt`/`window.confirm`
  restantes del frontend).

### Archivos

| Archivo | Cambio |
|---|---|
| `src/components/ui/modal.tsx` | Nuevo: modal base reutilizable |
| `src/components/ui/confirm-dialog.tsx` | Nuevo: confirmación con variante destructiva |
| `src/components/ui/prompt-dialog.tsx` | Nuevo: prompt de un campo de texto |
| `src/features/templates/TemplatesPage.tsx` | Aplicar/Eliminar con los diálogos |
| `src/features/worlds/WorldsPage.tsx` | Duplicar/Eliminar con los diálogos |
| `src/features/templates/TemplatesPage.test.tsx` | Tests con los diálogos (sin mock de `prompt`/`confirm`) |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**79 passed**) ✅.
- `rg "window.(confirm|prompt|alert)"` → solo referencias en comentarios de
  los propios componentes, cero usos reales.

## Refactor — Formularios estandarizados (`FormDialog` + `FormField` + `Select`)

> **Fecha**: 2026-08-12
> **Origen**: continuación del refactor de diálogos. Los diálogos de
> creación/ajustes de Servidores, Mundos y Plantillas repetían la misma
> estructura (Dialog + alerta de error + footer Cancelar/Guardar + Label+Input)
> y cada uno la mantenía a mano. Se extrae el patrón a componentes
> reutilizables para que todos los formularios del frontend sean idénticos.

### Cambios

- Nuevo `src/components/ui/form-dialog.tsx`: extiende `Modal` — envuelve el
  contenido en un `<form>` real (submit con Enter incluido) con la alerta de
  error (`role="alert"`), el footer Cancelar/Confirmar y el estado `busy`.
  Props: `onSubmit`, `busy`, `error`, `submitLabel`/`submittingLabel`,
  `submitVariant`, `submitDisabled`, `submitTestId`, `cancelLabel`.
- Nuevo `src/components/ui/form-field.tsx`: estandariza cada campo
  (label + control + hint + error) para no repetir el marcado `space-y-2`.
- Nuevo `src/components/ui/select.tsx`: `Select` reutilizable que unifica el
  `selectClass` que `CreateWorldDialog` y `EditWorldDialog` duplicaban (mismas
  clases de focus/disabled y opciones con fondo oscuro legibles sobre el panel).
- Refactor a `FormDialog`/`FormField`/`Select`:
  - `CreateServerDialog` (Nombre + Versión; `SERVER.ALREADY_EXISTS` resalta el
    campo nombre).
  - `UpdateResourcesDialog` (CPU/RAM; aviso "se reiniciará" si el servidor está
    en línea; testids conservados).
  - `CreateWorldDialog` / `EditWorldDialog` (Modo de juego y Dificultad con el
    `Select` compartido; constantes `GAMEMODES`/`DIFFICULTIES` ahora duplicadas
    en el mismo archivo de cada diálogo).
  - `CaptureTemplateDialog` (nombre) y `ImportWorldDialog` (nombre + archivo
    `.mcworld`; submit deshabilitado hasta elegir archivo).
- Fix de tipos preexistentes por `exactOptionalPropertyTypes`: props opcionales
  de `Modal`/`ConfirmDialog`/`PromptDialog` (`description`, `className`) y de
  `ApplyTemplateRequest.world_name` aceptan `| undefined` (rompían `tsc` desde
  el commit de modales).
- `EditWorldDialog`: se re-monta el formulario con `key={world.id}` al abrir
  para precargar los valores actuales del mundo.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/components/ui/form-dialog.tsx` | Nuevo: modal de formulario con submit + error + footer |
| `src/components/ui/form-field.tsx` | Nuevo: label + control + hint + error |
| `src/components/ui/select.tsx` | Nuevo: select estándar reutilizable |
| `src/features/servers/components/CreateServerDialog.tsx` | Refactor a `FormDialog`/`FormField` |
| `src/features/servers/components/UpdateResourcesDialog.tsx` | Refactor (testids intactos) |
| `src/features/worlds/components/CreateWorldDialog.tsx` | Refactor + `Select` compartido |
| `src/features/worlds/components/EditWorldDialog.tsx` | Refactor + remount por `key` |
| `src/features/worlds/components/ImportWorldDialog.tsx` | Refactor |
| `src/features/templates/components/CaptureTemplateDialog.tsx` | Refactor |
| `src/components/ui/{modal,confirm-dialog,prompt-dialog}.tsx` | Props opcionales `\| undefined` (fix `tsc`) |
| `src/lib/api/templates.ts` | `world_name?: string \| undefined` (fix `tsc`) |

### Verificación

- `tsc` ✅ (arregla errores `exactOptionalPropertyTypes` que ya estaban desde
  el commit de modales) · `eslint` ✅ · `vitest` (**79 passed**) ✅ · `build` ✅.
- `rg "DialogContent|DialogHeader|<Label htmlFor"` en los diálogos refactorizados
  → cero (todo pasa por `Modal`/`FormDialog`/`FormField`).

## Fase 4 — Parte 3: Jugadores (bans/kick)

> **Fecha**: 2026-08-12
> **Origen**: Parte 3 de la Fase 4 (después de Plantillas). Página de jugadores:
> jugadores online, resolución gamertag → XUID, kick y bans (por servidor y
> global). El contrato se verificó contra el router real
> (`apps/backend/src/app/modules/player/api/router.py`), que difiere del
> borrador del plan en varios puntos (ver Discrepancias).

### Alcance

- Ruta `/servers/:serverId/players` + ítem de sidebar "Jugadores" habilitado.
- Buscador de jugador por gamertag: `GET /servers/{id}/players/search?name=`
  (resuelve a XUID; `PLAYER.NOT_FOUND` = no está en la caché del panel).
- Jugadores online: `GET /servers/{id}/players/online` → sesiones abiertas
  (solo XUID + joined_at + playtime; el gamertag NO viene en este endpoint).
- Acciones por jugador online: Kick (`player.manage`) y Ban por servidor
  (`permission.write`) — botones visibles según `useCan`.
- Ban global: `POST /players/bans/global` (solo admin/super_admin,
  `player.ban.global`) — botón oculto para viewer/operator.
- Nuevos tipos/API en `src/lib/api/players.ts` y hooks en
  `src/features/players/hooks.ts` (query keys, retry `false` para que el 404
  de `PLAYER.NOT_FOUND` no reintente).

### Discrepancias con el borrador (verificadas contra el backend real)

1. **Ban por servidor usa `permission.write`, no `player.manage`** — el
   `player.manage` solo autoriza el kick (`router.py:249/274/298`).
2. **No hay endpoint para LISTAR bans** (ni globales ni por servidor). Solo se
   puede banear/desbanear por id conocido; la página no muestra una lista de
   bans activos.
3. **Ban por servidor responde 204 SIN body** (no `GlobalBanResponse`); el path
   usa `{player_id}` (el XUID), mientras el kick usa `{xuid}`.
4. **`GET /players/search` devuelve UN objeto** `ResolvePlayerResponse
   {server_id, name, xuid}`, no una lista; y 404 si no resuelve.
5. **`online` devuelve `PlaySessionResponse`** sin gamertag → los nombres se
   resuelven con el buscador, no en la lista online.
6. **Kick devuelve `CommandAckResponse`** `{server_id, command, priority, seq,
   at}` (202) sin body de entrada; `BanPlayerRequest` = `{reason?, expires_at?}`.
7. **Errores**: `PLAYER.NOT_FOUND`/`PLAYER.BAN_NOT_FOUND` (404),
   `PLAYER.INVALID_PAYLOAD`. No existe `CONSOLE.SERVER_OFFLINE` en el dominio.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/lib/api/players.ts` | Nuevo: tipos + funciones de la API Player |
| `src/features/players/hooks.ts` | Nuevo: queries/mutations Player |
| `src/features/players/PlayersPage.tsx` | Nuevo: página de jugadores |
| `src/features/players/components/OnlinePlayerRow.tsx` | Nuevo: fila de jugador online |
| `src/features/players/components/BanPlayerDialog.tsx` | Nuevo: ban por servidor |
| `src/features/players/components/GlobalBanDialog.tsx` | Nuevo: ban global (admin) |
| `src/features/players/PlayersPage.test.tsx` | Nuevo: 8 tests |
| `src/lib/format.ts` | Nuevo: `formatDuration` |
| `src/app/router.tsx` | Ruta `/servers/:serverId/players` |
| `src/components/layout/Sidebar.tsx` | Ítem "Jugadores" habilitado |
| `src/lib/auth/useCan.ts` | Mínimos de rol: `player.manage`, `permission.write`, `player.ban.global` |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**87 passed**, 8 nuevos) ✅ · `build` ✅.
- E2E contra el backend real (token JWT dev de `super_admin`):
  - `GET /players/online` → `[]` (lista, sin wrapper) ✅
  - `GET /players/search?name=Notch` → 404 `PLAYER.NOT_FOUND` ✅
  - `POST /players/bans/global` → 201 con `GlobalBanResponse`; `DELETE` → 204 ✅
  - `POST /servers/{id}/players/{xuid}/ban` y `/kick` con XUID fake → 404
    `PLAYER.NOT_FOUND` (validación de caché) ✅
- Criterio de parada del plan ("banear a un jugador conectado lo expulsa en
  vivo") pendiente de prueba manual en navegador con un jugador real.

## Fase 4 — Parte 3 bis: Jugadores (search parcial + listado de bans)

> **Fecha**: 2026-08-12
> **Origen**: Feedback de QA sobre la Parte 3: (1) el ban global no cerraba con
> la X ni Cancelar, (2) la búsqueda era exacta (no encontraba "Cra" →
> "CrafterTec"), (3) no había lista de baneados → imposible desbanear, (4) el
> buscador nunca mostraba "Desbanear". Se aprobó resolverlo en el backend
> (search parcial + endpoints de listado) en lugar de solo maquillar el front.

### Backend (nuevo contrato)

- `GET /servers/{id}/players/search?name=` ahora devuelve **`list[ResolvePlayerResponse]`**
  por coincidencia parcial case-insensitive (ILIKE, orden por `last_seen_at`
  desc, límite 10). Ya no 404 ni devuelve un solo objeto. Mover la ruta ANTES
  de `/servers/{id}/players/{xuid}` para que `bans` no colisione con `{xuid}`.
- `GET /servers/{id}/players/bans` → `list[ServerBanResponse]` (nuevo schema:
  id, scope, server_id, gamertag, xuid, reason, banned_by, created_at,
  expires_at), `player.list`, orden por `created_at` desc.
- `GET /players/bans/global` → `list[GlobalBanResponse]`, admin global
  (`player.ban.global`), orden por `created_at` desc.
- `PlayerRepositoryPort.search_players(term, limit=10)`; `PlayerBanRepositoryPort`
  `list_global_bans()` / `list_server_bans(server_id)` — implementados en
  Postgres (`ilike`, `%term%`) y en memoria.

### Frontend

- `searchPlayer` ahora devuelve lista; los resultados se muestran como filas.
- Sección "Jugadores baneados" (globales + este servidor combinados, más
  recientes primero) siempre visible para quien puede escribir/admin — "a la
  mano", sin depender del buscador. Botón "Desbanear" con confirmación.
- Un resultado de búsqueda que está baneado muestra "Desbanear" en vez de
  Kick/Ban; si no, mantiene Kick/Ban.
- Fix del cierre: `GlobalBanDialog`/`BanPlayerDialog` ahora propagan SIEMPRE
  `onOpenChange(next)` al padre (antes se tragaban el close → no cerraban con
  X ni Cancelar).
- Nuevo `ServerBanResponse`, `formatDateTime` en `src/lib/format.ts`, keys de
  caché `serverBans`/`globalBans`, invalidación de listas tras ban/unban.

### Archivos

| Archivo | Cambio |
|---|---|
| `apps/backend/.../player/domain/repository.py` | Ports: `search_players`, `list_global_bans`, `list_server_bans` |
| `apps/backend/.../player/infrastructure/postgres_repository.py` | Implementaciones (ILIKE + orden) |
| `apps/backend/.../player/infrastructure/memory.py` | Implementaciones en memoria |
| `apps/backend/.../player/application/facade.py` | `search_players`, `list_global_bans`, `list_server_bans` |
| `apps/backend/.../player/api/schemas.py` | Nuevo `ServerBanResponse` |
| `apps/backend/.../player/api/router.py` | Search → lista; rutas `GET */players/bans` |
| `apps/backend/tests/test_api_integration.py` | Search parcial + listados (6 tests Player) |
| `apps/frontend/src/lib/api/players.ts` | Search → lista, `ServerBanResponse`, `listGlobalBans`/`listServerBans`, keys |
| `apps/frontend/src/features/players/hooks.ts` | `useGlobalBans`, `useServerBans`; invalidación de listas |
| `apps/frontend/src/features/players/PlayersPage.tsx` | Resultados en lista, sección de baneados, desbanear |
| `apps/frontend/src/features/players/banRows.ts` | Nuevo: `toBanRows` (conversión/fusión de listas) |
| `apps/frontend/src/features/players/components/BanListSection.tsx` | Nuevo: lista de baneados con "Desbanear" |
| `apps/frontend/src/features/players/PlayersPage.test.tsx` | 6 tests nuevos (14 total) |
| `apps/frontend/src/lib/format.ts` | Nuevo `formatDateTime` |

### Verificación

- Backend: `pytest` **909 passed** · `ruff` ✅ · `mypy` ✅.
- Frontend: `tsc` ✅ · `eslint` ✅ · `vitest` (**93 passed**, 6 nuevos) ✅ ·
  `build` ✅.
- E2E contra backend real (JWT dev `super_admin`):
  - `search?name=Cra` → `[{"name":"CrafterTec","xuid":"2535473172645342"}]` ✅
  - ban por servidor 204 → `GET .../players/bans` lista el ban → DELETE 204 →
    lista `[]` ✅
  - ban global 201 → `GET /players/bans/global` lista → DELETE 204 → `[]` ✅

## Fase 4 — Parte 4: Backups (cierre de la Fase 4)

> **Fecha**: 2026-08-12
> **Origen**: Última pieza pendiente de la Fase 4. El backend ya tenía el
> módulo Backup completo (paso 13 del change-log); faltaba la UI. Se verificó
> el contrato real contra `apps/backend/src/app/modules/backup/api/router.py`
> y `schemas.py` ANTES de escribir nada; el borrador del plan difería del
> backend real en varios puntos (ver Discrepancias).

### Alcance

- Ruta `/servers/:serverId/backups` + ítem de sidebar "Backups" habilitado.
- Lista de backups: `GET /servers/{id}/backups` (badge de estado, tamaño,
  fecha, duración, nº de entradas, marca "Protegido").
- Acciones por backup (según permiso): Restaurar (confirmación destructiva),
  Validar, Descargar (`.tar.zst`, dispara el `<a download>` con el nombre que
  envía el backend), Eliminar (deshabilitado si `protected`).
- "Crear backup": `POST /servers/{id}/backups` con selector de mundo (reusa
  `useWorlds` — el módulo Backup no expone listado propio) + preselección del
  primer mundo.
- "Retención" (prune): `POST /servers/{id}/backups/prune` con input
  `keep_last_n` (default 10), destructivo con confirmación.
- Tipos/API en `src/lib/api/backups.ts`, hooks en
  `src/features/backups/hooks.ts` (invalidación de listas; restore también
  invalida `worldKeys` porque reescribe el mundo en disco).
- `useCan`: mínimos `backup.create/restore/delete/validate/prune` → operator+,
  `backup.download` → viewer+.

### Discrepancias con el borrador del plan (verificadas contra el backend real)

1. **`BackupResponse` real** no tiene `kind/type/status/checksum_sha256/
   compression/entries_count/duration_ms/metadata/started_at`. Tiene:
   `{id, server_id, world_name, state, size_bytes, checksum, entries: list[str],
   duration_seconds, protected, orphaned, error, created_at, updated_at}`.
2. **`CreateBackupRequest` real** = `{world_name, protected?: bool}` (el borrador
   solo pedía `world_name`).
3. **Restore NO tiene body** (`{world_name?}` no existe): restaura sobre
   `worlds/<world_name>/` del propio backup y responde `BackupResponse`. El
   diálogo es una confirmación simple, sin campo de nombre.
4. **Validate responde `BackupResponse` (200)**, no 204.
5. **Prune usa `keep_last_n`** (no `keep_last`) y responde `list[BackupResponse]`.
6. **Download** es `application/zstd` (no octet-stream) y SÍ envía
   `Content-Disposition: attachment; filename="{world_name}-{id}.tar.zst"` —
   se reusa ese nombre para el `<a download>`.
7. **Errores**: `BACKUP.NOT_FOUND` (404); `BACKUP.INVALID_PAYLOAD`,
   `BACKUP.CORRUPT`, `BACKUP.IN_PROGRESS` son `ValidationError` → **422**, no 409.
8. Estados reales: `running | completed | failed | corrupt | deleted` (no hay
   `pending`).

### Archivos

| Archivo | Cambio |
|---|---|
| `apps/frontend/src/lib/api/backups.ts` | Nuevo: tipos + funciones de la API Backup |
| `apps/frontend/src/features/backups/hooks.ts` | Nuevo: queries/mutations Backup |
| `apps/frontend/src/features/backups/BackupsPage.tsx` | Nuevo: página de backups |
| `apps/frontend/src/features/backups/components/BackupList.tsx` | Nuevo: lista con badges y acciones por permiso |
| `apps/frontend/src/features/backups/components/CreateBackupDialog.tsx` | Nuevo: selector de mundo |
| `apps/frontend/src/features/backups/components/RestoreBackupDialog.tsx` | Nuevo: confirmación destructiva |
| `apps/frontend/src/features/backups/components/PruneDialog.tsx` | Nuevo: retención keep-last-N |
| `apps/frontend/src/features/backups/BackupsPage.test.tsx` | Nuevo: 10 tests |
| `apps/frontend/src/app/router.tsx` | Ruta `/servers/:serverId/backups` |
| `apps/frontend/src/components/layout/Sidebar.tsx` | Ítem "Backups" habilitado |
| `apps/frontend/src/lib/auth/useCan.ts` | Mínimos `backup.*` |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**103 passed**, 10 nuevos) ✅ · `build` ✅.
- E2E contra el backend real (JWT dev `super_admin`, servidor `…c39a2`):
  - `GET /backups` → 200 (vacío al inicio) ✅
  - `POST /backups {world_name: village}` → 201, `state=completed`, 21 MB,
    `entries` 20 ficheros, `checksum` SHA-256 ✅
  - `GET /backups/{id}` → 200 ✅
  - `GET /backups/{id}/download` → 200 `application/zstd`, header
    `filename="village-{id}.tar.zst"` ✅
  - `POST /backups/{id}/validate` → 200 (íntegro) ✅
  - `POST /backups/{id}/restore` → 200 ✅
  - `DELETE /backups/{id}` → 204 ✅
  - `POST /backups/prune {keep_last_n: 0}` → 200 ✅

## Fase 6 — Monitoring (métricas y gráficos)

> **Fecha**: 2026-08-12
> **Alcance**: página de monitoreo con gráficos en tiempo real de
> CPU/RAM/Jugadores/Disco, selector de rango temporal e integración con el WS
> de monitoring. Primera pieza de la Fase 6 (Scheduler, Permission y
> Configuration quedan pendientes de confirmación).

### Decisiones

- **No existe REST histórico**: se verificó `modules/monitoring/api/router.py`
  (solo el WS `/servers/{id}/monitoring/ws`), `schemas.py` (docstring: "No hay
  REST en esta iteración") y la facade (sin `get_metrics`). El plan asumía un
  `GET /servers/{id}/metrics` opcional → **no se implementa polling REST**; los
  datos vienen solo del WS en vivo y el selector de rango filtra el histórico
  en memoria.
- **Se amplió `useMonitoringStore`**: el plan asumía `snapshots:
  Record<string, MetricSample[]>` con histórico, pero el store real solo
  guardaba el ÚLTIMO snapshot (`Record<string, MonitoringSnapshot>`). Se añadió
  `history: Record<string, MetricSample[]>` (con `ts`, tope `MAX_SNAPSHOTS`
  = 2000 ≈ 2.7 h a 5 s) manteniendo `snapshots`/`currentSnapshot`/`clear`
  intactos para no romper StatCards/Header.
- **`useServerMonitoring`** ahora pasa el `ts` del envelope al store (campo que
  ya venía del WS).
- Gráficos de área con gradiente (Recharts), tema oscuro: CPU = cyan, RAM =
  violeta, Jugadores = verde, Disco = naranja; cada serie tiene toggle.
- El rango filtra en memoria por `ts` (`filterByRange`); el rango más largo
  (7d) muestra solo lo acumulado (aceptable, no hay histórico persistente).

### Discrepancias con el plan (verificadas contra el backend real)

1. **`GET /servers/{id}/metrics` NO existe** (ni en el router ni en la facade).
   Se usa solo el WS; no hay histórico persistente.
2. **`useMonitoringStore.snapshots` era `Record<string, MonitoringSnapshot>`
   (solo el último), no `Record<string, MetricSample[]>`**. Se añadió `history`
   sin romper los consumidores existentes (`currentSnapshot(snapshots,
   serverId)` mantiene su firma real).
3. **Payload WS real** = `{state, status, latency_ms, players, players_max,
   cpu, ram_mb, disk_mb}` — 8 campos, sin campos extra. Con el servidor parado
   `ram_mb`/`disk_mb` vienen `0.0` (número) y `cpu` `null`.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/stores/monitoring.ts` | Añadido `history: Record<string, MetricSample[]>` + `MAX_SNAPSHOTS`; `setSnapshot` con `ts` |
| `src/hooks/useServerMonitoring.ts` | Pasa `message.ts` al `setSnapshot` |
| `src/features/monitoring/hooks.ts` | `TIME_RANGES`, `rangeDurationMs`, `filterByRange`, `useMonitoringHistory` |
| `src/features/monitoring/MonitoringPage.tsx` | Página: stat cards en vivo + selector + chart |
| `src/features/monitoring/components/MetricsChart.tsx` | Área Recharts con 4 series toggleables |
| `src/features/monitoring/components/TimeRangeSelector.tsx` | Botones 15m/1h/6h/24h/7d |
| `src/features/monitoring/hooks.test.ts` | 7 tests (rangos + filtro) |
| `src/features/monitoring/components/TimeRangeSelector.test.tsx` | 2 tests |
| `src/features/monitoring/components/MetricsChart.test.tsx` | 3 tests |
| `src/features/monitoring/MonitoringPage.test.tsx` | 4 tests |
| `src/app/router.tsx` | Ruta `/servers/:serverId/monitoring` |
| `src/components/layout/Sidebar.tsx` | Ítem "Monitoreo" habilitado |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**119 passed**, 16 nuevos) ✅ ·
  `build` ✅.
- E2E contra el backend real (JWT dev `super_admin`, servidor `…c39a2`):
  `ws://…/monitoring/ws?token=` emite `SERVER.STATE` scope `monitoring` con
  `{state, status, latency_ms, players, players_max, cpu, ram_mb, disk_mb}`,
  `ts` y `seq` crecientes cada ~5 s ✅.

## Fase 6 — Monitoring bis: fixes de QA (dropdown + gráficos)

> **Fecha**: 2026-08-12
> **Origen**: QA de la página de Monitoring. (1) El dropdown de servidores, al
> estar en una subpágina (monitoring/backups/mundos/…), llevaba SIEMPRE al
> detalle `/servers/:id` en vez de cambiar el id manteniendo la página actual.
> (2) Los gráficos se veían "toscos" (áreas que arrancan en 0, picos angulosos)
> y la RAM sin límite dominaba el eje Y con valores absolutos (MB), dando la
> impresión de que algo fallaba.

### Fix 1 — Dropdown conserva la subpágina

`Header.selectServer` detecta la subpágina actual con `pathname.match(/^\/servers\/[^/]+\/([^/]+)/)`
y navega a `/servers/{nuevoId}/{subpagina}` en vez de `/servers/{nuevoId}`. Si
no hay subpágina (detalle exacto u otra ruta), sigue yendo al detalle. Los
datos del nuevo servidor cargan en la misma página.

### Fix 2 — Gráficos fluidos y eje coherente

- **Curvas `natural`** (spline) + `baseValue="dataMin"`: las áreas arrancan en
  el mínimo de los datos, no en 0 → look moderno, sin "picos rotos".
- **Normalización a % con límite del servidor** (la idea pedida: el límite lo
  pone el servidor):
  - CPU: ya viene en %.
  - RAM: `ram_mb / ramLimitMb * 100` (límite de `useServer().resources.ram_mb`).
  - Disco: `disk_mb / (diskLimitGb * 1024) * 100`.
  - Jugadores: `players / players_max * 100`.
  - Fallback sin límite configurado: RAM usa el máximo visto (evita el pico).
- Eje Y fijo `[0, 100] %` → todas las series comparables, sin que `ram_mb`
  bruto descoloque la escala.
- `MonitoringPage` ahora consulta `useServer(serverId)` para pasar los límites
  al chart.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/components/layout/Header.tsx` | `selectServer` conserva la subpágina |
| `src/components/layout/Header.test.tsx` | Test nuevo: subpágina conservada al cambiar servidor |
| `src/features/monitoring/components/MetricsChart.tsx` | Curvas natural + baseValue dataMin + normalización a % (props `ramLimitMb`/`diskLimitGb`) |
| `src/features/monitoring/MonitoringPage.tsx` | Pasa `useServer(...).resources` al chart |
| `src/features/monitoring/MonitoringPage.test.tsx` | Wrapper `QueryClientProvider` (la página usa `useServer`) |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**120 passed**, 1 nuevo) ✅ · `build` ✅.

## Fase 6 — Monitoring ter: CPU por núcleo + iconos en stat cards

> **Fecha**: 2026-08-12
> **Origen**: QA de la página de Monitoring. (1) La CPU llegaba a superar el
> 100% (p. ej. 185% al conectarse un jugador), que parece un bug. (2) Las stat
> cards de Monitoring se veían "tristes" frente a las de la página del servidor
> (sin iconos).

### CPU por núcleo — no es un bug del backend, es la convención de Docker

Se verificó el origen: `apps/backend/src/app/infrastructure/runtime/docker.py`
`_compute_cpu_percent` usa la fórmula estándar de Docker
`(cpu_delta / system_delta) * online_cpus * 100`, que reporta el % **por
núcleo** (100% = un núcleo). En un host multicore, un proceso usando más de un
núcleo da N×100% (el test `test_get_resources_computes_cpu_percent_from_delta`
documenta el 200% como comportamiento esperado). No se cambió el backend: el
valor crudo es correcto y lo consumen otros sitios.

**Fix en el frontend** (`normalizeCpu` en `features/monitoring/hooks.ts`):
divide el % por núcleo entre los núcleos asignados del servidor
(`useServer(...).resources.cpu_cores`) → 100% = toda la CPU asignada, y clampa
a 100 si el backend excede. Se aplica a:
- `MetricsChart` (serie CPU, ahora con prop `cpuCores`).
- `MonitoringPage` (stat card de CPU usa el % normalizado).
- `StatCards` de la página de detalle (barra de CPU también se disparaba).

### Iconos en las stat cards de Monitoring

`SummaryCard` de `MonitoringPage` ahora recibe un icono (patrón de `StatCards`):
Estado = Activity, Jugadores = Users, CPU = Zap, RAM = Cpu, Disco = HardDrive,
con el mismo bisel de bloque pixelado.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/features/monitoring/hooks.ts` | Nuevo `normalizeCpu` (÷ núcleos + clamp a 100) |
| `src/features/monitoring/components/MetricsChart.tsx` | Serie CPU usa `normalizeCpu`; prop `cpuCores` |
| `src/features/monitoring/MonitoringPage.tsx` | Pasa `cpuCores`; card de CPU normalizada; `SummaryCard` con iconos |
| `src/features/servers/components/StatCards.tsx` | CPU del detalle normalizada con `cpu_cores` |
| `src/features/monitoring/hooks.test.ts` | Tests de `normalizeCpu` (÷ núcleos, clamp, sin límite) |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**125 passed**, 5 nuevos) ✅ · `build` ✅.
- Backend sin cambios; el test `test_get_resources_computes_cpu_percent_from_delta`
  sigue documentando el % por núcleo como contrato.

## Fase 6 — Monitoring cuarta iteración: overshoot de la curva + barra de CPU

> **Fecha**: 2026-08-12
> **Origen**: QA tras el fix de CPU por núcleo. (1) La curva bajaba
> ligeramente por debajo de 0 al conectar un jugador (pico de CPU). (2) La
> barra de la card de CPU del servidor se llenaba de más.

### Overshoot de la curva (bajaba de 0)

La curva `type="natural"` (Catmull-Rom) overshotea: entre puntos en 0 y un
pico, crea un valle artificial por debajo de 0. Se cambió a `type="monotone"`
(cúbica monótona), que NO overshotea — respeta el rango de los datos — y se
añadió `clipPath` al `AreaChart` por si acaso el área intentara dibujar fuera
del área de trazado. Sigue siendo suave.

### Barra de CPU llena de más (bug introducido en la iteración anterior)

`StatCard.progress` espera una **fracción 0..1** (lo multiplica ×100 para el
ancho), igual que `ramPct`/`diskPct`. En la iteración anterior, al normalizar
la CPU dejé `cpuPct` en **percent 0..100** y lo pasé como `progress` → con CPU
real baja (ej. 2%) la barra se llenaba casi entera. Corregido: ahora se pasa
`cpuFraction` (0..1) y el label usa `(fraction * 100)`.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/features/monitoring/components/MetricsChart.tsx` | Curva `monotone` (sin overshoot) + `clipPath` |
| `src/features/servers/components/StatCards.tsx` | `progress` de CPU como fracción 0..1 (era percent) |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**125 passed**) ✅ · `build` ✅.

## Fase 6 — Monitoring: fix de intervalo del WS (2 min → ~5 s)

> **Fecha**: 2026-08-12. **Backend, sin cambios de frontend.** La página de
> Monitoring recibía muestras cada ~2 minutos: `get_state()`/`get_resources()`
> del adaptador Docker (síncronos) bloqueaban el event loop hasta `docker_timeout`
> (300 s). Se ejecutan ahora en un hilo (`asyncio.to_thread`) con timeout de 5 s
> (`monitoring.runtime_timeout`). Detalle en `docs/change-log.md`
> (Fix — Timeout de llamadas al runtime en el poller de Monitoring).
>
> Impacto en la UI: las muestras llegan cada ~5 s (servidor activo) o ~7 s
> (parado, por el timeout del ping RakNet) en lugar de ~2 min. Verificado por
> E2E contra el WS real.

## Fase 6 — Módulo Scheduler (Tareas Programadas)

> **Fecha**: 2026-08-14. **Frontend.** Página de tareas programadas en
> `/servers/:serverId/scheduler`, verificada contra el router y schemas reales
> del backend (`apps/backend/src/app/modules/scheduler/api/router.py` y
> `schemas.py`). Endpoints: `GET/POST /servers/{id}/schedule/tasks`,
> `PATCH/DELETE /servers/{id}/schedule/tasks/{task_id}` y
> `POST /servers/{id}/schedule/tasks/{task_id}/run` (NOTA: es `PATCH`, no
> `PUT`, como en el enunciado; se implementó lo que expone el backend).

### Alcance

- **API & tipos**: `src/lib/api/scheduler.ts` (claves `taskKeys`, interfaces
  `ScheduleTask`/`CreateTaskRequest`/`UpdateTaskRequest` y las 5 funciones
  HTTP) + `src/features/scheduler/types.ts` (`TaskType`, `TaskState`,
  `TaskFormValues`).
- **Hooks**: `useTasks`, `useCreateTask`, `useUpdateTask`, `useDeleteTask`,
  `useRunTask` + `buildCreatePayload`/`buildUpdatePayload` (payload por tipo:
  backup → `world_name`, command → `commands`).
- **Vista principal** `SchedulerPage.tsx`: lista con nombre, cron, estado, tipo,
  próxima/última ejecución, resultado y fallos; acciones Ejecutar/Editar/
  Eliminar (con `ConfirmDialog`).
- **Diálogos**: `CreateTaskDialog` y `EditTaskDialog` sobre `FormDialog` +
  `TaskFormFields` (selector de tipo reutilizado). Backup usa `useWorlds`
  (preselecciona el primer mundo al cargar), restart sin parámetros, command
  con área de texto de comandos (uno por línea).
- **Ruta y permisos**: ruta nueva en `apps/frontend/src/app/router.tsx` y
  ítem "Programador" habilitado en el `Sidebar` (`sub: 'scheduler'`). Página
  protegida con `useCan('task.list')` (acceso) y `useCan('task.write')`
  (acciones de escritura). Nuevas entradas `task.*` en `PANEL_MIN_ROLES`
  de `useCan.ts` alineadas con `iam/domain/permissions.py` (list/view = viewer+;
  create/update/delete/run = operator+).

### Archivos

| Archivo | Cambio |
|---|---|
| `src/lib/api/scheduler.ts` | Nuevo: claves, tipos y funciones HTTP |
| `src/features/scheduler/types.ts` | Nuevo: tipos del módulo |
| `src/features/scheduler/hooks.ts` | Nuevo: hooks + builders de payload |
| `src/features/scheduler/SchedulerPage.tsx` | Nuevo: vista principal |
| `src/features/scheduler/components/TaskList.tsx` | Nuevo: lista de tareas |
| `src/features/scheduler/components/CreateTaskDialog.tsx` | Nuevo: alta de tarea |
| `src/features/scheduler/components/EditTaskDialog.tsx` | Nuevo: edición de tarea |
| `src/features/scheduler/components/TaskFormFields.tsx` | Nuevo: selector tipo + payload |
| `src/features/scheduler/SchedulerPage.test.tsx` | Nuevo: 9 tests |
| `src/app/router.tsx` | Ruta `/servers/:serverId/scheduler` |
| `src/components/layout/Sidebar.tsx` | Ítem "Programador" habilitado |
| `src/lib/auth/useCan.ts` | Mapeos `task.*` (list/view/write/create/update/delete/run) |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**134 passed**, 9 nuevos del módulo) ✅.

## Fase 6 — Scheduler: editor cron intuitivo (presets + selectores)

> **Fecha**: 2026-08-14. **Frontend.** Reemplazo del campo cron de texto libre
> por un editor amigable en el diálogo de crear/editar tareas: presets, cinco
> selectores desglosados (minuto/hora/día/mes/día-semana) y modo avanzado para
> escritura manual. El valor enviado al backend sigue siendo la expresión cron.

### Alcance

- **`src/features/scheduler/cron.ts`** (nuevo helper, sin dependencias): `CRON_PRESETS`,
  `CRON_PART_LABELS`, `parseCronToParts`, `buildCronFromParts`, `isValidCron`
  y `describeCron` (traducción de la expresión a español, el "disfraz": `0 3 * * *`
  → "todos los días a las 03:00").
- **`components/CronEditor.tsx`** (nuevo, compartido por ambos diálogos): selector
  de plantilla rápida (cada minuto/hora, diario 00:00/03:00, semanal, mensual),
  5 selectores numerados (`*` o valor en rango), lector del cron generado en
  tiempo real con su descripción legible, y toggle "Modo avanzado"/"Usar
  selectores" para edición manual. Se inicializa desde `value` al montar y se
  remonta con `key` en el diálogo de creación (evita `setState` en `useEffect`).
- **`CreateTaskDialog` / `EditTaskDialog`**: sustituyen el `Input` de cron por
  `<CronEditor value onChange>`; el botón de guardar se deshabilita si el cron
  no es válido (`isValidCron`). Edición preserva el cron existente al abrir.
- La traducción humana (`describeCron`) se muestra bajo el cron para que el
  usuario confíe en el significado antes de guardar.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/features/scheduler/cron.ts` | Nuevo: helpers de cron (presets, partes, validación, descripción) |
| `src/features/scheduler/cron.test.ts` | Nuevo: 13 tests unitarios de cron |
| `src/features/scheduler/components/CronEditor.tsx` | Nuevo: editor intuitivo de cron |
| `src/features/scheduler/components/CreateTaskDialog.tsx` | Usa `CronEditor` + `isValidCron` |
| `src/features/scheduler/components/EditTaskDialog.tsx` | Usa `CronEditor` + `isValidCron` |
| `src/features/scheduler/SchedulerPage.test.tsx` | Test de creación usa el selector "Hora" |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**147 passed**, +13 del helper cron) ✅.

## Fase 6 — Scheduler: UI compacta del editor cron

> **Fecha**: 2026-08-14. **Frontend.** Rediseño de la distribución vertical del
> `CronEditor` para que el diálogo quepa sin scroll excesivo en pantallas
> verticales limitadas, manteniendo presets, selectores, lector y modo avanzado.

### Alcance

- **`components/CronEditor.tsx`**: distribución compacta y horizontal.
  - Presets como **botones** `size="sm"` compactos (`h-7 px-2 text-xs`) en línea
    con `flex-wrap` (en lugar del select de plantilla).
  - **5 selectores** con `flex-wrap items-end`, etiquetas cortas en
    mayúsculas (`text-[10px]`) sobre cada uno y `Select` estrecho (`w-14/w-16`,
    `h-8`, `text-xs`).
  - **Lector + descripción + toggle** en una sola línea (`flex-wrap items-center`)
    con `flex-1` para el cron, descripción en `text-muted-foreground` y el botón
    "Avanzado"/"Usar selectores" a la derecha (`ml-auto`).
  - Modo avanzado: el `Input` manual ocupa el lugar de los selectores; al volver
    a selectores se reusa la lógica de validación existente.
- **`components/ui/form-dialog.tsx`**: `space-y-4` → `space-y-3` para reducir el
  gap vertical entre campos de todos los formularios modales.
- Sin dependencias nuevas (no hay `Switch` en el kit; el toggle usa `Button`).

### Archivos

| Archivo | Cambio |
|---|---|
| `src/features/scheduler/components/CronEditor.tsx` | Redistribución compacta/horizontal |
| `src/components/ui/form-dialog.tsx` | Gap de campos `space-y-3` |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**147 passed**) ✅ · `build` ✅.

## Fase 6 — Módulo Permission (Allowlist y Operadores)

> **Fecha**: 2026-08-14. **Frontend.** Página de permisos del servidor en
> `/servers/:serverId/permissions`, verificada contra
> `apps/backend/src/app/modules/permission/api/router.py` y `schemas.py`.

### DISCREPANCIAS vs. el enunciado (backend real)

- El backend **NO expone** `GET /servers/{id}/permissions/operators` ni ningún
  GET del estado de la allowlist (`allowlist-enabled` es solo escritura; el
  toggle `ALLOW_LIST` se publica como evento). Consecuencias:
  - Los **operadores** se gestionan con **estado local de sesión**: `PUT
    /operators/{xuid}` añade/actualiza (devuelve `{xuid, level}`) y `DELETE`
    lo quita; la lista arranca vacía y refleja solo los cambios de la sesión.
    Se muestra un aviso en la UI y se documenta aquí.
  - El toggle **"Allowlist activada"** es de solo escritura: se muestra como
    botón que alterna un estado client-side y envía `PUT allowlist-enabled`;
    no se puede precargar el valor real.
- El `PUT /operators/{xuid}` recibe body `{level}` (`operator`/`member`/
  `visitor`), no "añadir xuid" puro; el alta de operador usa `level: operator`.
- La allowlist sí tiene CRUD completo. `POST allowlist` exige **xuid no vacío**
  (a diferencia de "xuid opcional" del enunciado); el diálogo lo pide.

### Alcance

- **API & tipos**: `src/lib/api/permissions.ts` (`permissionKeys`,
  `AllowlistEntry`, `AddAllowlistRequest`, `OperatorEntry`, `PermissionLevel`
  y las 6 funciones HTTP) + `src/features/permission/types.ts`.
- **Hooks**: `useAllowlist`, `useAddAllowlistEntry`, `useRemoveAllowlistEntry`,
  `useToggleAllowlistEnabled`, `useSetOperator`, `useRemoveOperator`.
- **Vista principal** `PermissionPage.tsx`: tabla de allowlist (gamertag + xuid
  + eliminar), tabla de operadores local (xuid + nivel + eliminar), botón
  toggle de allowlist (solo con escritura). Protegida con
  `useCan('permission.read')`; acciones con `useCan('permission.write')`.
- **Diálogos**: `AddAllowlistDialog` (gamertag + xuid) y `AddOperatorDialog`
  (xuid) sobre `FormDialog`/`FormField`; `ConfirmDialog` para las bajas.
- **Ruta y permisos**: `/servers/:serverId/permissions` en `router.tsx`, ítem
  "Permisos" habilitado en el `Sidebar`, y `permission.read` (viewer+) añadido
  a `PANEL_MIN_ROLES` de `useCan.ts`.

### Archivos

| Archivo | Cambio |
|---|---|
| `src/lib/api/permissions.ts` | Nuevo: claves, tipos y funciones HTTP |
| `src/features/permission/types.ts` | Nuevo: tipos del módulo |
| `src/features/permission/hooks.ts` | Nuevo: hooks de allowlist/operadores/toggle |
| `src/features/permission/PermissionPage.tsx` | Nuevo: vista principal |
| `src/features/permission/components/AddAllowlistDialog.tsx` | Nuevo: alta de entrada |
| `src/features/permission/components/AddOperatorDialog.tsx` | Nuevo: alta de operador |
| `src/features/permission/PermissionPage.test.tsx` | Nuevo: 9 tests |
| `src/app/router.tsx` | Ruta `/servers/:serverId/permissions` |
| `src/components/layout/Sidebar.tsx` | Ítem "Permisos" habilitado |
| `src/lib/auth/useCan.ts` | Mapeo `permission.read` (viewer+) |

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**156 passed**, +9 del módulo) ✅ · `build` ✅.

## Fase 6 — Módulo Permission bis: operadores desde el backend real (sin estado local)

> **Fecha**: 2026-08-14. **Backend + Frontend.** Corrección de la discrepancia
> anterior: el backend ahora expone `GET /servers/{id}/permissions/operators`
> (ver `docs/change-log.md`, "38"), y el frontend lo consume vía TanStack Query
> **eliminando el estado local de sesión** para los operadores.

### Cambios frontend

- `src/lib/api/permissions.ts`: nuevo `operatorKeys` y `getOperators(serverId)`
  → `GET /servers/{id}/permissions/operators` (lista de `OperatorEntry`).
  Actualizada la nota de discrepancias: ya NO aplica la de "no hay GET".
- `src/features/permission/hooks.ts`: nuevo `useOperators` (useQuery con
  `operatorKeys`, `refetchOnWindowFocus: false`); `useSetOperator` y
  `useRemoveOperator` ahora invalidan `operatorKeys.all(serverId)` al éxito.
- `src/features/permission/PermissionPage.tsx`: la tabla de operadores se
  alimenta de `useOperators` (con estados de carga/error/vacío como la
  allowlist); se elimina el `useState<OperatorEntry[]>` local, el push vía
  `onAdded` de `AddOperatorDialog` y el aviso "no hay GET / esta sesión".
- `src/features/permission/PermissionPage.test.tsx`: mock de `getOperators`/
  `operatorKeys`; los tests de operadores verifican el listado real.

### Discrepancia residual

- El toggle **"Allowlist activada"** sigue siendo de solo escritura (el backend
  no expone GET del estado de la allowlist) → se conserva el estado client-side
  documentado en la sección anterior.

### Verificación

- `tsc` ✅ · `eslint` ✅ · `vitest` (**156 passed**, sin cambios de conteo) ✅ ·
  `build` ✅.
