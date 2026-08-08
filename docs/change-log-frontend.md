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
- Pendiente de prueba manual en navegador (criterio de parada de la Fase 1):
  login con usuario real (con y sin 2FA) y ver el WS conectado + al menos un
  evento en la consola tras suscribirse al canal `global`.

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
- Pendiente de prueba manual en navegador (criterio de parada de la Fase 2):
  layout fiel al mockup, selector de servidor cambiando entre los servidores
  reales, y start/stop con el estado actualizándose por WS sin refrescar.

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
