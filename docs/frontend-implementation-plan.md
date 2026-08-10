# Frontend Implementation Plan — BedrockPanel

> Referencia de fases para el agente. Regla de oro: **cada fase termina con
> el agente deteniéndose a reportar y esperando confirmación explícita del
> usuario antes de arrancar la siguiente.** No se avanza de fase solo porque
> los tests pasen — hace falta una prueba real (navegador, no solo `vitest`)
> confirmada por el usuario. Esto replica el mismo patrón que se usó para
> validar el backend (prueba real con dispositivo, no solo suite verde).

Ver `docs/frontend-standards.md` para el detalle técnico de cada pieza
(stack, endpoints reales, protocolo WS, modelo de permisos). Este documento
es solo la secuencia y los criterios de parada.

## Fase 1 — Cimientos (setup + auth + WS client)

**Alcance**: dependencias instaladas, shadcn/ui + tema Tailwind configurado,
login (incluyendo el paso de 2FA si la cuenta lo tiene activo), interceptor
Axios con manejo de 401/403, guard de rutas protegidas, y el cliente
WebSocket compartido (conexión, subscribe/unsubscribe, resume, reconexión
con backoff) — sin páginas de datos todavía. Una ruta de prueba simple
post-login (puede ser un placeholder "conectado como {usuario}") basta para
verificar que todo el cimiento funciona.

**Por qué se detiene aquí**: todo lo demás depende de esto. Un error acá se
replica en las 8 páginas siguientes si no se atrapa a tiempo.

**Criterio de parada — el agente reporta y espera cuando:**
- Login funciona con usuario real (con y sin 2FA si hay forma de probar
  ambos casos).
- El WS conecta, se ve en Network/consola del navegador que llegó al menos
  un evento tras un `subscribe`.
- `npm run build`/`vitest` en verde.

**No avanza a Fase 2 sin que el usuario confirme haber probado esto en el
navegador.**

## Fase 2 — Layout + Servidores (lectura y control básico)

**Alcance**: Sidebar + Header **siguiendo el mockup aprobado** (ver
`frontend-standards.md` §9 — glassmorphism, fondo dinámico detrás de las
superficies, sidebar con ítem activo verde sólido, header con selector de
servidor real, campana de notificaciones conectada al WS, menú de perfil),
página de detalle de servidor (card grande + stat cards + botones de
acción), start/stop/restart.

**Criterio de parada:**
- El layout se ve fiel al mockup (glassmorphism, fondo dinámico visible
  detrás de sidebar/cards, no un layout genérico de admin panel).
- El selector de servidor del header cambia realmente de servidor activo
  (probar con los 2+ servidores reales que ya existen tras el fix de
  multi-servidor).
- Start/stop desde la UI funciona contra un servidor real y el estado se
  actualiza solo (por WS), sin refrescar la página.

> **Estado (2026-08-10)**: criterio de parada **cumplido** — confirmado por el
> usuario en navegador (layout fiel al mockup, selector real, start/stop/
> restart con estado en vivo por WS), más las extensiones de la Fase 2 ya
> implementadas: campana de notificaciones, badge de jugadores del header,
> "Crear servidor", y "Actualizar recursos" CPU/RAM (modal con validación,
> recreación automática y `SERVER.BUSY` — ver change-log). Detalles en
> `docs/change-log-frontend.md` §Fase 2 y sus entradas posteriores.

## Fase 3 — Consola en vivo

**Alcance**: terminal con scroll, logs en vivo (líneas `CONSOLE.OUTPUT` del
WS dedicado por servidor `/servers/{id}/console/ws` — ADR-002, NO el canal
`server:{id}` del gateway, que no reenvía eventos de consola), envío de
comandos vía `POST /servers/{id}/console/commands` (202, `server.console.write`).

**Criterio de parada:**
- Logs reales de un servidor corriendo aparecen en vivo en la UI.
- Un comando enviado desde la UI se ve reflejado en `docker logs` del
  contenedor real.

> **Estado (2026-08-10)**: implementado (página `/servers/:serverId/console`,
> buffer con límite 1000 líneas, auto-scroll, input oculto sin
> `server.console.write`, aviso si no está en línea, ítem "Consola" del sidebar
> cableado). Tests unitarios + lint/typecheck/build en verde. **Pendiente de
> verificación manual por el usuario en navegador** (los dos criterios de
> parada) — no avanzar a Fase 4 sin esa confirmación. Detalles en
> `docs/change-log-frontend.md` §Fase 3.

## Fase 4 — Mundos, Backups, Plantillas

**Alcance**: las tres páginas de gestión de contenido del servidor. Se
agrupan porque comparten patrones de UI (listas + acciones + confirmaciones
destructivas) y todas dependen de Fase 2 ya funcionando.

**Criterio de parada:**
- Capturar/aplicar una plantilla desde la UI funciona de punta a punta
  contra un servidor real (mismo tipo de prueba que se hizo manualmente con
  curl para validar el backend).

## Fase 5 — Jugadores (bans/kick)

**Alcance**: lista de jugadores online/histórico, ban global, ban por
servidor, kick, deshacer ban.

**Criterio de parada:**
- Banear a un jugador conectado desde la UI lo expulsa en vivo (misma
  prueba que se hizo manual con el celular para el backend).

## Fase 6 — Scheduler, Monitoring, Permission, Configuration

**Alcance**: las páginas restantes de administración de un servidor
puntual.

**Criterio de parada:** cada una funciona contra datos reales del backend;
Monitoring muestra gráficos que se actualizan (no estáticos).

## Fase 7 — IAM + Settings del panel

**Alcance**: gestión de usuarios/roles/API keys/auditoría (solo
admin/super_admin), y ajustes personales (tema, fondo, 2FA propio, cambio
de contraseña).

**Criterio de parada:** un usuario `viewer` no ve el ítem de IAM en el
sidebar; un `admin` sí y puede operarlo.

## Reglas transversales para todas las fases

- Documentar cada fase completada en `docs/change-log-frontend.md` (mismo
  formato que `docs/change-log.md` del backend: fecha, alcance, decisiones,
  archivos, verificación).
- Si algo del backend no se comporta como dice `frontend-standards.md`
  (endpoint distinto, campo con otro nombre, etc.), el agente debe
  **verificar contra el código real del backend** (`apps/backend/src/app/
  modules/{modulo}/api/`), no adivinar ni inventar — y señalar la
  discrepancia encontrada en el resumen de la fase.
- Ninguna fase se da por completa solo con tests unitarios en verde. El
  criterio real es la prueba manual en navegador que el usuario confirma.
