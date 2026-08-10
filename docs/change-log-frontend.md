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
- **Pendiente de verificación manual por el usuario** (criterios de parada de
  Fase 3: logs en vivo y comando visible en `docker logs`).
