# Architecture Decision Records — BedrockPanel

> **Serie**: ADR-001 … ADR-013
> **Fecha**: 2026-08-05
> **Origen**: Architecture Review v1.0
> **Regla**: el `technical-design.md` (TDD) es **inmutable**. Los ADR registran problemas,
> contexto, alternativas, decisión, justificación y consecuencias **sin modificar el TDD**;
> cuando una decisión afecta al TDD, su actualización queda programada para la siguiente
> versión del documento y se indica explícitamente en cada ADR.

---

## Índice

| ADR | Título | Estado |
|---|---|---|
| [ADR-001](#adr-001--calendarización-del-outbox-durable) | Calendarización del Outbox durable | Proposed |
| [ADR-002](#adr-002--gateway-websocket-dentro-del-mvp) | Gateway WebSocket dentro del MVP | Accepted |
| [ADR-003](#adr-003--enmascarado-de-last_ip) | Enmascarado de `last_ip` | Accepted |
| [ADR-004](#adr-004--configprofile-deseado-aplicado-y-versión) | ConfigProfile: deseado/aplicado/versión | Accepted |
| [ADR-005](#adr-005--catálogo-de-eventos-una-sola-fuente) | Catálogo de eventos: una sola fuente | Accepted |
| [ADR-006](#adr-006--eliminar-el-kind-de-backup-auto-mvp) | Eliminar el kind de backup `auto-mvp` | Accepted |
| [ADR-007](#adr-007--auditoría-como-sub-api-de-iam) | Auditoría como sub-API de IAM | Accepted |
| [ADR-008](#adr-008--notación-del-mapa-de-dependencias) | Notación del mapa de dependencias | Accepted |
| [ADR-009](#adr-009--formato-unificado-de-allowlistjson) | Formato unificado de `allowlist.json` | Accepted |
| [ADR-010](#adr-010--factoría-de-cliente-docker-en-infrastructure) | Factoría de cliente Docker en Infrastructure | Accepted |
| [ADR-011](#adr-011--bans-persistidos-globales-y-por-servidor) | Bans persistentes: globales y por servidor | Accepted |
| [ADR-012](#adr-012--discrepancia-de-identidad-player--tdd-155) | Discrepancia de identidad `Player` vs TDD §15.5 | Accepted |
| [ADR-013](#adr-013--migración-del-monitoring-al-gateway-único) | Migración del Monitoring al gateway único `/ws` | Proposed |

---

## ADR-001 — Calendarización del Outbox durable

- **Estado**: Proposed
- **Fecha**: 2026-08-05
- **Origen**: Architecture Review v1.0, hallazgo **M2**
- **Documento(s) afectados**: `technical-design.md` §7.1, §17 (Fase 2); `implementation-blueprint.md` §2 (Fase A), §4.6

### Problema

El TDD §7.1 define el bus de eventos **en proceso** y declara el patrón **Outbox** como
*"opcional/etapa 2"*; su roadmap (§17, Fase 2) incluye *"Outbox durable"*. El blueprint
(Fase A, paso 5) construye **outbox sobre Postgres como parte de la base técnica**. Existe
una discrepancia de calendarización: el blueprint adelanta una capacidad que el TDD agenda
para Fase 2.

### Contexto

- Los eventos se publican dentro de la misma transacción del cambio de dominio; sin outbox,
  una caída del proceso entre la transacción y la difusión pierde el evento.
- En MVP no hay réplicas: el bus es en proceso y los consumidores viven en el mismo proceso.
- Los eventos que son *órdenes* (`TASK.STARTED`) necesitan durabilidad; los eventos de *estado*
  (`SERVER.STARTED`, `PLAYER.JOINED`) son reconciliables por otros mecanismos (ping, parsers,
  snapshots periódicos).

### Alternativas consideradas

1. **Outbox en Fase A (estado actual del blueprint)**: durabilidad desde el inicio; mayor
   costo (tabla, dispatcher, idempotencia) en el MVP.
2. **Outbox en Fase 2 (alineado al TDD)**: MVP más simple; riesgo de perder órdenes en crash.
3. **Bus en proceso + publicación síncrona con reintento en Fase A, y outbox real en Fase 2**
   (compromiso).

### Decisión

Alinear el blueprint con el TDD: en **Fase A** solo el **bus en proceso** con publicación
síncrona y reintento en memoria; el **outbox durable sobre Postgres** se construye en **Fase 2**
junto con las réplicas (TDD §7.1, §17). Las órdenes que requieran durabilidad en MVP usan el
**job store persistente de APScheduler** (migración a `task_` ya prevista en el TDD).

### Justificación

- El TDD es inmutable y el blueprint declara respetarlo al 100% (Blueprint, encabezado).
- El MVP no tiene réplicas; la pérdida de eventos de estado es recuperable por reconciliación
  (Monitoring re-sondea, parsers re-leen logs, snapshots de estado cada 5 s).
- La durabilidad de órdenes se cubre con el job store de APScheduler, ya contemplado en el TDD.

### Consecuencias

**Positivas**:
- MVP con menor complejidad infraestructural.
- No se viola la inmutabilidad del TDD.
- La inversión en outbox se hace cuando realmente aporta (multi-réplica).

**Negativas**:
- Una caída del proceso en MVP puede perder eventos no-durables (aceptado, mitigable por
  reconciliación).
- Se requiere disciplina para distinguir *órdenes* (durables vía job store) de *estados*.

### Impacto en el Blueprint y futuras implementaciones

- `implementation-blueprint.md` §2, Fase A, paso 5: reducir a "bus en proceso + publicación
  síncrona"; mover el outbox a Fase 2.
- §4.6 `EventBusPort`: marcar `publish` durable (outbox) como garantía vigente desde Fase 2.
- Checklist §16.1: añadir "publicación vía bus; durabilidad de órdenes vía job store en MVP".

### Nota (2026-08-08)

Diferido a Fase 2. No se implementa en el MVP; el bus en proceso es suficiente para el alcance
actual. El estado del ADR se mantiene **Proposed** sin cambios.

---

## ADR-002 — Gateway WebSocket dentro del MVP

- **Estado**: Accepted
- **Fecha**: 2026-08-05 (Actualizado: 2026-08-06 — promovido a Accepted al implementar el
  WS mínimo de Console en Fase B y el de Monitoring en Fase D)
- **Origen**: Architecture Review v1.0, hallazgo **M3**
- **Documento(s) afectados**: `technical-design.md` §17 (Fase 1); `implementation-blueprint.md` §2 (Fases B, D, H)

### Problema

El TDD (§17, Fase 1 / MVP) exige *"WebSocket: estado + logs + consola en tiempo real"* como
parte del MVP. El blueprint ubica el módulo Notification/WebSocket gateway como **paso 17 de
la Fase H** (la última), y el frontend depende de un *stub* de eventos hasta entonces. Las
capacidades de consola (Fase B) y monitoring (Fase D) quedarían sin canal de entrega en tiempo
real durante el MVP.

### Contexto

- Console (Fase B) y Monitoring (Fase D) ya emiten eventos (`CONSOLE.OUTPUT`, estados, métricas).
- El canal WS es la vía prevista (TDD §13) para estado, logs y consola en vivo.
- El resume por `seq`, las suscripciones por canal y el rate limiting son capacidades avanzadas
  que sí pueden diferirse.

### Alternativas consideradas

1. **Gateway WS mínimo en Fases B/D + gateway completo en Fase H** (propuesto).
2. **Todo el gateway en Fase H** (estado actual): MVP sin tiempo real; rompe la promesa del TDD.
3. **Eliminar el WS del MVP**: inválido, contradice el TDD.

### Decisión

Introducir en el blueprint un **gateway WebSocket mínimo** junto a Console (Fase B) y Monitoring
(Fase D): canal por servidor para **estado, logs y consola** con autenticación por token y
autorización por membresía. Las capacidades avanzadas —canales globales, suscripciones
complejas, `resume` por `seq`, backpressure y rate limits— se mantienen en la **Fase H**.

### Justificación

- Cumple la promesa del MVP del TDD sin ampliar el alcance.
- El gateway es un adaptador delgado: reutiliza el bus de eventos ya existente en Fase A.
- Diferir solo lo accesorio evita reescribir el módulo Notification después.

### Consecuencias

**Positivas**:
- MVP completo según TDD (tiempo real de estado/logs/consola).
- Frontend puede construir la capa `ws` contra un destino real, no un stub.

**Negativas**:
- El módulo Notification se entrega en dos fases (mínimo en B/D, completo en H).
- Coste inicial ligeramente mayor en Fases B/D.

### Impacto en el Blueprint y futuras implementaciones

- `implementation-blueprint.md` §2: añadir "gateway WS mínimo (estado, logs, consola)" a Fase B/D;
  Fase H conserva canales globales, resume y control de flujo.
- §3.12 Notification: distinguir entregables MVP vs Fase H.
- §16.13: checklist mínima para el gateway MVP (authN/AuthZ por canal) y avanzada para Fase H.

### Nota de implementación (2026-08-06)

El MVP implementa **un canal WebSocket por servidor** (`/servers/{server_id}/console/ws` en
Fase B y `/servers/{server_id}/monitoring/ws` en Fase D), no el endpoint único `/ws` del TDD
§13.1. Se mantiene este diseño deliberadamente: authN por token en el handshake y authZ por
membresía por canal (§13.1), y deja los canales globales/por-usuario y el `/ws` único para la
Fase H (Notification completo). **El TDD §13.1 queda pendiente de actualizar** en su próxima
revisión para reflejar esta decisión (mismo criterio que otros ADR Accepted: el TDD es inmutable
y su actualización se agenda).

---

## ADR-003 — Enmascarado de `last_ip`

- **Estado**: Accepted
- **Fecha**: 2026-08-05
- **Origen**: Architecture Review v1.0, hallazgo **M4**
- **Documento(s) afectados**: `technical-design.md` §15.5; `implementation-blueprint.md` §12.2, §16.6

### Problema

El TDD §15.5 modela `Player.last_ip` (IP íntegra), mientras que el blueprint §12.2 y §16.6
exigen *"IPs enmascaradas en logs/persistencia salvo política explícita"*. Hay una contradicción
entre el modelo de datos y la política de privacidad.

### Contexto

- La IP completa es dato personal (PII); su retención aumenta el riesgo en caso de fuga.
- El módulo Player necesita una referencia para futuros bloqueos/reportes; no necesita la IP
  íntegra para el MVP.
- El TDD es inmutable: el campo no se elimina ni se renombra hasta su siguiente versión.

### Alternativas consideradas

1. **Almacenar IP enmascarada por defecto** (p. ej. los tres primeros octetos) y una setting
   global `player.store_full_ip` (default `false`) que, si se activa, conserva la IP completa
   con acceso auditado.
2. **Almacenar IP completa siempre**: contradice la política del propio blueprint.
3. **No almacenar IP**: pierde información de diagnóstico necesaria para soporte.

### Decisión

`Player.last_ip` se persiste **enmascarada** (sin el último octeto) por defecto. Se añade la
setting global `player.store_full_ip` (`false` por defecto); si un administrador la activa, la
IP completa se conserva en la tabla de sesiones con acceso auditado. Mientras el TDD permanezca
inmutable, la implementación aplica el enmascarado sobre el campo existente sin cambiar su nombre.

### Justificación

- La privacidad por defecto es un requisito transversal (blueprint §12.2, §16.6).
- Mantener el nombre del campo respeta el modelo del TDD y evita migraciones innecesarias.
- El hashing + enmascarado preserva utilidad (detección de IPs repetidas) sin retener PII completa.

### Consecuencias

**Positivas**:
- Reducción de superficie de PII; cumplimiento de la política documentada.
- Sigue siendo posible detectar reincidencias por rango/IP parcial.

**Negativas**:
- No se puede geolocalizar ni identificar con precisión total sin la setting explícita.
- Una setting adicional que administrar.

### Impacto en el Blueprint y futuras implementaciones

- `implementation-blueprint.md` §16.6: referencia al enmascarado como comportamiento por defecto.
- TDD §15.5: actualizar la nota del campo `last_ip` en la próxima versión del TDD.
- Migraciones: ningún cambio de esquema hasta la actualización del TDD (el enmascarado es lógico).

---

## ADR-004 — ConfigProfile: deseado/aplicado/versión

- **Estado**: Accepted
- **Fecha**: 2026-08-05 (Actualizado: 2026-08-08 — promovido a Accepted al implementarlo)
- **Origen**: Architecture Review v1.0, hallazgo **M6**
- **Documento(s) afectados**: `technical-design.md` §15.2, §15.9; `implementation-blueprint.md` §5.4

### Problema

El TDD §15.9 afirma que `ConfigProfile` guarda *"el deseado y el aplicado"* y que los cambios de
config *"se versionan"*, pero §15.2 solo define `properties(jsonb, "config deseada")` y `active`.
El modelo conceptual está subespecificado respecto a las garantías que el propio TDD declara.

### Contexto

- El estado *deseado vs aplicado* es, según el TDD §18.4, la mayor complejidad del sistema
  ("pending changes" tras un fallo de recreación).
- El blueprint §5.4 asume que la *config deseada* viaja en `CONFIG.CHANGED` y que Server la
  aplica; sin un campo `applied` no se puede detectar una config cambiada pero no aplicada.
- El TDD es inmutable: el cambio de modelo es un ADR, no una edición directa.

### Alternativas consideradas

1. **ConfigProfile con `properties` (deseado) + `applied` (JSON nullable) + `applied_at` +
   `version`**, e historial en tabla `config_history` (append-only).
2. **Una sola columna `properties`** y derivar "aplicado" del estado del servidor (p. ej.
   `Server.runtime_spec`): menos tablas, pero sin historial ni detección fiable de pending changes.
3. **Tabla separada de versiones por servidor** (solo historial): sin estado "deseado" explícito.

### Decisión

Adoptar la alternativa 1: ampliar `ConfigProfile` con `applied` (JSON, nullable), `applied_at`
y `version`; añadir una tabla `config_history` append-only por servidor. La migración se agenda
junto con la próxima versión del TDD; mientras tanto, el blueprint tratará `applied` como campo
previsto y `config_history` como tabla prevista.

### Justificación

- Detección explícita de "pending changes" (deseado ≠ aplicado) tras recreaciones fallidas.
- Historial auditado y compatible con la política de auditoría (TDD §14.5, §15.9).
- Alineado con la recomendación del TDD §18.4 (máquina de estados de config explícita y testeada).

### Consecuencias

**Positivas**:
- El sistema puede reportar "config sin aplicar" y reintentar recreaciones de forma segura.
- Historial completo de config (rollback de config posible).

**Negativas**:
- Más tablas y más código en el dominio Configuration.
- La migración del TDD requiere sincronización con el blueprint §5.4.

### Impacto en el Blueprint y futuras implementaciones

- `implementation-blueprint.md` §5.4: modelar `applied`/`applied_at`/`version` en el flujo de config.
- Checklist §16.8: añadir "detectar pending changes entre `properties` y `applied`".
- TDD §15.2/§15.9: actualizar en la próxima versión.

### Nota de implementación (2026-08-08)

Implementado en la Fase D (paso 10). El modelo `ConfigProfile` incluye `applied`, `applied_at`,
`version` y la tabla `config_history` para historial append-only. Pendiente de actualización del
TDD en su próxima versión.

---

## ADR-005 — Catálogo de eventos: una sola fuente

- **Estado**: Accepted
- **Fecha**: 2026-08-05 (Actualizado: 2026-08-08 — promovido a Accepted como fuente operativa)
- **Origen**: Architecture Review v1.0, hallazgo **B1**
- **Documento(s) afectados**: `technical-design.md` §7.2; `implementation-blueprint.md` §9

### Problema

El catálogo de eventos está **duplicado** (TDD §7.2 ↔ blueprint §9, declarados idénticos). La
duplicación ya provocó *drift real*: la revisión previa detectó y corrigió divergencias
(`UPDATE.AVAILABLE`, `PLAYER.OPERATOR_CHANGED`, `TASK.FAILED`, `BACKUP.RESTORE_FAILED`,
`SERVER.CONFIG_CHANGED`) entre ambas copias.

### Contexto

- El blueprint §9 es el contrato operativo que siguen los agentes de código.
- El TDD §7.2 es la referencia arquitectónica y es inmutable.
- El costo de mantener dos copias sincronizadas a mano es alto y propenso a error.

### Alternativas consideradas

1. **Blueprint §9 como catálogo canónico**; el TDD §7.2 se reduce a un resumen con referencia
   a §9 (próxima versión del TDD).
2. **TDD §7.2 como canónico**; el blueprint referencia: obliga a versionar el TDD para cualquier
   evento nuevo, demasiado rígido para el contrato de implementación.
3. **Mantener ambas con un test de paridad en CI**: mitiga el drift pero conserva la duplicación.

### Decisión

El **§9 del blueprint es el catálogo canónico operativo**. En la próxima versión del TDD, §7.2
se reduce a una referencia/resumen que apunta a §9. Se añade un **test de arquitectura** que
verifica que todo evento publicado/consumido en código existe en el catálogo §9.

### Justificación

- El blueprint es el contrato de los agentes (Blueprint, Apéndice A).
- Una sola fuente elimina la causa raíz del drift.
- El test de arquitectura convierte la garantía en comprobable en CI.

### Consecuencias

**Positivas**:
- Una sola fuente de verdad para el catálogo.
- El drift se vuelve detectable por CI, no por revisión manual.

**Negativas**:
- El TDD pierde el detalle del catálogo (pasa a referencia).
- Requiere coordinar la próxima versión del TDD.

### Impacto en el Blueprint y futuras implementaciones

- `implementation-blueprint.md` §9: permanece como canónico; se añade la nota de "fuente única".
- §16.1: añadir el test de paridad del catálogo al checklist transversal.
- TDD §7.2: pasar a resumen + referencia en la próxima versión.

### Nota de implementación (2026-08-08)

El Blueprint §9 es la fuente canónica operativa. El TDD §7.2 se reduce a referencia/resumen. El
test de paridad en CI queda como deuda técnica no bloqueante.

---

## ADR-006 — Eliminar el kind de backup `auto-mvp`

- **Estado**: Accepted
- **Fecha**: 2026-08-05
- **Origen**: Architecture Review v1.0, hallazgo **B2**
- **Documento(s) afectados**: `technical-design.md` §8.1, §15.4

### Problema

El TDD §8.1 lista el kind de origen `auto-mvp` (junto a `manual`, `scheduled`, `pre-upgrade`,
`pre-restore`) sin definición, uso posterior en §15.4 ni presencia en el blueprint.

### Contexto

- El roadmap no define ningún "backup automático de MVP" distinto de los backups programados
  (`scheduled`).
- Un concepto no definido en el contrato genera ambigüedad para implementadores.

### Alternativas consideradas

1. **Eliminar `auto-mvp`** de la lista de kinds.
2. **Definirlo** (respaldo automático periódico del MVP para protección mínima): añade
   funcionalidad nueva, fuera del alcance de esta revisión.

### Decisión

Eliminar `auto-mvp` de la lista de kinds del TDD. Los kinds vigentes son: `manual`, `scheduled`,
`pre-upgrade`, `pre-restore`.

### Justificación

- Concepto huérfano sin semántica ni consumidor.
- No se introducen funcionalidades nuevas (regla de la revisión).

### Consecuencias

**Positivas**:
- Sin ambigüedad en el contrato de backups.

**Negativas**:
- Ninguna (el blueprint no lo usaba).

### Impacto en el Blueprint y futuras implementaciones

- Ninguno funcional: el blueprint no referencia `auto-mvp`.
- TDD §8.1: eliminar el término en la próxima versión del TDD.

---

## ADR-007 — Auditoría como sub-API de IAM

- **Estado**: Accepted
- **Fecha**: 2026-08-05
- **Origen**: Architecture Review v1.0, hallazgo **B3**
- **Documento(s) afectados**: `technical-design.md` §12, §5.1; `implementation-blueprint.md` §3.1

### Problema

El TDD §12 (API por dominios) lista el módulo API **Audit**, que no existe como dominio en el
catálogo §5.1. La auditoría es una responsabilidad del módulo **IAM** (TDD §14.5, blueprint §3.1).

### Contexto

- La auditoría no tiene agregado raíz propio; es un aspecto transversal implementado por IAM.
- La tabla `AuditLog` pertenece al dominio IAM (TDD §15.1).
- El blueprint §3.1 ya trata la auditoría dentro de IAM.

### Alternativas consideradas

1. **Auditoría como sub-API de IAM** (p. ej. `GET /iam/audit`), no como módulo/dominio propio.
2. **Módulo API separado "Audit"** (nuevo bounded context): sobre-ingeniería; no hay lógica de
   negocio propia.
3. **Endpoint global `/audit` servido por IAM**: equivalente a la opción 1 con otra ruta.

### Decisión

La auditoría se expone como **sub-API del módulo IAM** (`/iam/audit`, solo admins). No se crea
un módulo ni dominio "Audit". En la próxima versión del TDD, §12 renombra la fila a
**"IAM · Auditoría"** y se elimina la entrada como módulo independiente.

### Justificación

- Evita un bounded context sin agregado ni lógica propia.
- Consistente con §5.1, §15.1 y con el blueprint §3.1.

### Consecuencias

**Positivas**:
- Catálogo de dominios y de APIs alineados.
- Menos superficie de API.

**Negativas**:
- Ninguna funcional.

### Impacto en el Blueprint y futuras implementaciones

- Ninguno: el blueprint ya modela la auditoría en IAM.
- TDD §12: ajustar en la próxima versión.

---

## ADR-008 — Notación del mapa de dependencias

- **Estado**: Accepted
- **Fecha**: 2026-08-05
- **Origen**: Architecture Review v1.0, hallazgo **B4**
- **Documento(s) afectados**: `technical-design.md` §5.3; `implementation-blueprint.md` §1.3, §3.11

### Problema

El mapa del TDD §5.3 dibuja *"Template ──► Server, World"*, lo que sugiere que Template depende
de Server/World, mientras el blueprint (§1.3, §3.11) define lo contrario: **Server → Template**
(Server consume la facade de Template en la creación). La dirección de la flecha es ambigua.

### Contexto

- TDD §5.2 Template: *"usado por Server al crear instancias y por World al importar"* → la
  dependencia real es de los consumidores hacia Template.
- El blueprint ya modela la dirección correcta.

### Alternativas consideradas

1. **Documentar la flecha como "es usado por"** en la leyenda del mapa.
2. **Invertir el mapa** para que las flechas signifiquen "depende de" (coherente con el blueprint).

### Decisión

En la próxima versión del TDD, el mapa §5.3 usará flechas que significan **"depende de"** y la
arista de Template pasará a `Server → Template` y `World → Template` (vía Server). Mientras
tanto, esta nota documenta que la flecha original indicaba "es usado por".

### Justificación

- La ambigüedad de dirección genera interpretaciones erróneas al implementar.
- La dirección del blueprint es la que respeta las reglas de módulos.

### Consecuencias

**Positivas**:
- Mapa y matriz coherentes; implementación sin ambigüedad.

**Negativas**:
- Cambio cosmético en el TDD (próxima versión).

### Impacto en el Blueprint y futuras implementaciones

- Ninguno: el blueprint ya es correcto.
- TDD §5.3: ajustar notación en la próxima versión.

---

## ADR-009 — Formato unificado de `allowlist.json`

- **Estado**: Accepted
- **Fecha**: 2026-08-05
- **Origen**: Architecture Review v1.0, hallazgo **B8**
- **Documento(s) afectados**: `analisis-proyecto-base.md` §2.5, §6.4; `implementation-blueprint.md` §3.6, §16.7

### Problema

El análisis muestra el formato de `allowlist.json` de dos formas: §2.5 como
`[{"name","xuid"}]` y §6.4 como `[{"ignoresPlayerLimit":false,"name","xuid"}]`. El campo
`ignoresPlayerLimit` no se declara como opcional, lo que puede inducir a generar ficheros
incompatibles.

### Contexto

- BDS acepta `ignoresPlayerLimit` como campo opcional (default `false`).
- El dominio Permission (blueprint §3.6) escribe este fichero; el formato canónico debe ser
  único para que el panel genere entradas válidas.

### Alternativas consideradas

1. **Documentar el formato canónico con `ignoresPlayerLimit` opcional** en ambas secciones.
2. **Omitir el campo de la documentación**: incompleto y riesgoso.

### Decisión

El formato canónico es `[{"name": "<gamertag>", "xuid": "<xuid>", "ignoresPlayerLimit": false}]`
con `ignoresPlayerLimit` **opcional**. El análisis unificará §2.5 y §6.4 en su próxima revisión;
el blueprint referencia este formato canónico.

### Justificación

- Exactitud respecto al formato real de BDS.
- Evita ficheros inválidos o con campos inesperados.

### Consecuencias

**Positivas**:
- Única fuente del formato; implementación de Permission sin ambigüedad.

**Negativas**:
- Ninguna.

### Impacto en el Blueprint y futuras implementaciones

- `implementation-blueprint.md` §3.6/§16.7: referencia al formato canónico con el campo opcional.
- `analisis-proyecto-base.md` §2.5/§6.4: unificar en la próxima revisión del análisis.

---

## ADR-010 — Factoría de cliente Docker en Infrastructure

> **Estado**: Accepted
> **Fecha**: 2026-08-06
> **Origen**: hardening de la FASE A

### Problema

`DockerRuntimeAdapter` construía su cliente directamente con `docker.from_env()`
dentro de `_client()`, mezclando la lógica de negocio del adaptador con el
cableado del SDK Docker. Esto acoplaba el adaptador a una implementación
concreta de conexión (socket/TLS/contexto de la CLI) y dificultaba el mocking y
las implementaciones alternativas de runtime.

Además, el constructor de `DockerClient` es **eager** (negocia la versión de la
API en `__init__`), por lo que los errores de transporte (incluido el
`PermissionError` del socket) pueden aparecer en la construcción, no solo en las
operaciones.

### Contexto

- FASE A gestiona un único contenedor vía docker-py; no hay `subprocess`.
- El contrato §4.1 (`ServerRuntimePort`) es inmutable en esta fase.
- docker-py 7.2 no distribuye `py.typed`.
- La factoría pertenece a Infrastructure (capa de adaptadores); el adaptador
  depende solo de la interfaz y de sus errores del kernel.

### Alternativas consideradas

1. **Inyectar el cliente ya construido** (`docker_client=`): trivial pero obliga
   a que el llamador (bootstrap/tests) conozca el SDK Docker, arrastrando
   `docker.*` a la composición y a los tests.
2. **Factory como abstracción propia** (`DockerClientFactory` Protocol +
   `DockerFromEnvClientFactory`): aísla la construcción, permite `base_url`
   explícito (tcp/ssh/unix), traduce errores de construcción a `DockerError` y
   facilita mocks y futuras implementaciones (podman, remote engine).
3. **Helper suelto `build_docker_client()`**: menos ceremonioso pero sin punto de
   extensión claro ni trazabilidad por DI.

### Decisión

Se adopta la **opción 2**. `DockerClientFactory` (Protocol, `create() -> Any`) y
`DockerFromEnvClientFactory` viven en
`apps/backend/src/app/infrastructure/runtime/client_factory.py`. El adaptador
recibe el factory por constructor (obligatorio) y cachea el cliente creado;
nunca llama a `docker.from_env()` ni importa el SDK. `build_container()` registra
el factory en el DI usando `DockerRuntimeSettings.docker_timeout`.

La factoría traduce los errores de construcción a `DockerError` del kernel:
`DockerException`→`DockerError` (con detección de `PermissionError` en la cadena
`__cause__`/`__context__`/`args` para marcarlo como no retryable), `PermissionError`
nativo→`DockerError` no retryable y `OSError`→`DockerError` retryable.

### Justificación

- El adaptador deja de conocer el SDK; cumple la regla de que Infrastructure
  exponga abstracciones y el bootstrap cablee implementaciones.
- Los tests ya no dependen de `docker.from_env` (mock del factory).
- El manejo de `PermissionError` en la cadena de causas del SDK es observable y
  verificable (fallo del socket → `DockerError` no retryable).

### Consecuencias

**Positivas**:
- Creación de cliente aislada, testeada y configurable (env, `base_url`, timeout).
- Base de extensión para podman/runtime remoto en fases futuras.

**Negativas**:
- Cambio de constructor en `DockerRuntimeAdapter` (`docker_client=` →
  `docker_client_factory=`): rompe los tests de FASE A; se han actualizado.
- Una capa más de indirección (necesaria por la eager-construction del SDK).

### Impacto en el Blueprint y futuras implementaciones

- `technical-design.md` (inmutable): la factoría de clientes queda propuesta
  para incorporarse a §16 (bootstrap) en la próxima versión del TDD.
- Fase B (Console/Backups): cualquier adaptador Docker futuro usará
  `DockerClientFactory` en lugar de crear clientes.

---

## ADR-011 — Bans persistentes: globales y por servidor

> **Estado**: Accepted
> **Fecha**: 2026-08-07
> **Origen**: implementación del sistema de bans (Fase E paso 11, alcance ampliado)

### Problema

El ban del MVP era un **comando de consola sin persistencia** (`ban <name>` vía
`ConsoleFacade`): se perdía al reiniciar el contenedor, no se podía consultar
desde la API y no había forma de aplicar bans de panel-wide ni de expirarlos.

### Contexto

- La identidad del jugador es el **XUID** (`player_players` es identidad global,
  sin `server_id`); el gamertag es un apodo mutable.
- En modo offline/LAN el XUID reportado por BDS suele ser `0` o no confiable.
- Existen dos alcances con sentido de negocio distinto: **ban global**
  (decisión panel-wide, aplica en todos los servidores) y **ban por servidor**
  (atado a `server_id`, sin colisionar con la identidad global).
- El enforcement debe ser efectivo aunque el jugador ya esté conectado: expulsar
  en el momento del ban si hay presencia, y también en el siguiente `PLAYER.JOINED`.

### Alternativas consideradas

1. **Campos de ban en `player_players`** (TDD §15.5): `banned`,
   `ban_reason`, `ban_expires_at`. Rechazado: `player_players` es identidad
   global por XUID sin `server_id`; meter un ban por servidor ahí exigiría una
   columna `server_id` y duplicar filas, rompiendo la unicidad de identidad.
   (Ver ADR-012.)
2. **Ban global y por servidor en una sola tabla** con `scope`:
   ahorra una tabla pero mezcla dos agregados con reglas distintas (unicidad,
   índices, query por servidor).
3. **Dos tablas** (`player_global_bans` y `player_server_bans`), cada una su
   propio agregado (`GlobalBan`/`ServerBan`) y sus índices de unicidad.

### Decisión

Se adopta la **opción 3**: dos agregados y dos tablas.

- `player_global_bans` (`id`, `xuid` nullable, `gamertag`, `reason`,
  `banned_by`, `created_at`, `expires_at`) con unicidad sobre `lower(gamertag)`.
- `player_server_bans` (mismos campos + `server_id`) con unicidad sobre
  `(server_id, lower(gamertag))`.

El **matching en `PLAYER.JOINED`** (`BanEnforcementHandler`) chequea primero el
ban global y luego el por servidor; cuando el XUID es `0`/ausente hace fallback a
`gamertag` **case-insensitive** (misma regla que la unicidad). Un ban es un "ban
blando" en offline: disuasión, no seguridad real, porque el gamertag es
mutable y no autentica. `expires_at` vencido = el ban no aplica. Al banear por
servidor a un jugador con presencia en vivo se ejecuta el kick en el mismo
request (`_kick_best_effort`, sin romper el request si el server no corre).

### Justificación

- Separa agregados con reglas de unicidad y vida propias.
- No toca `player_players` (identidad global, ADR-012) ni `server_id` en ella.
- El fallback gamertag case-insensitive reutiliza `normalize_gamertag`
  (lower-case), coherente con los índices `uq_*`.

### Consecuencias

**Positivas**:
- Bans durables, consultables y con expiración; enforcement en join y en ban
  inmediato si hay presencia.
- API REST de gestión: `POST /players/bans/global` (admin global),
  `DELETE /players/bans/global/{ban_id}`, `POST/DELETE
  /servers/{server_id}/players/{player_id}/ban` (operator+, ACL por servidor).
- Eventos `PLAYER.BANNED`/`PLAYER.UNBANNED` publicados por los use cases.

**Negativas**:
- Dos tablas en vez de una (más superficie de migración, ADR-011 y ADR-012).
- El matching por gamertag en offline es un "ban blando": no es seguridad real
  si el jugador cambia de gamertag (advertencia documentada en la API y el
  dominio `bans.py`).
- El ban por servidor exige que el jugador esté en la caché del panel
  (`player_players`): sin `PLAYER.JOINED` previo, el POST devuelve 404.

### Impacto en el Blueprint y futuras implementaciones

- `technical-design.md` (inmutable): el TDD §15.5 propone campos de ban en
  `Player`; la implementación los mueve a agregados propios (programado para la
  próxima versión del TDD, ver ADR-012).
- Los pasos de API (§16) ya expuestos; el outbox durable (ADR-001) entregaría
  `PLAYER.BANNED`/`PLAYER.UNBANNED` de forma fiable entre procesos.

---

## ADR-012 — Discrepancia de identidad `Player` vs TDD §15.5

> **Estado**: Accepted
> **Fecha**: 2026-08-07
> **Origen**: hallazgo al diseñar el ban por servidor (dónde guardar el ban)

### Problema

El TDD §15.5 modela `Player` como **N:1 `Server`** con `server_id` y campos de
ban en la propia entidad (`id, server_id, xuid, gamertag, …, banned,
ban_reason, ban_expires_at`). La implementación real (`player_players`) es una
**tabla de identidad global por XUID, sin `server_id`**: una fila por jugador
que existe con independencia del servidor.

### Contexto

- El TDD asume que cada servidor tiene su propio `Player` (presencia,
  playtime y estado de ban por servidor).
- La implementación llegada hasta Fase E resuelve la identidad como **cache
  global** (`player_players`, clave primaria `xuid`) y guarda la presencia en
  `player_sessions` (con `server_id`), separando identidad y presencia.
- Al necesitar un ban por servidor, plantear guardarlo en `player_players`
  chocaba con esa decisión: o se añade `server_id` (duplicando la identidad) o
  se usan columnas sin server_id (mezclando alcances).

### Decisión

Se **mantiene la implementación actual** (identidad global por XUID en
`player_players`) y los bans por servidor viven en su propia tabla
(`player_server_bans`, ADR-011), no en `player_players`. No se añade
`server_id` a `player_players`; `player_players` queda como identidad global.

### Justificación

- Evita duplicar la fila de identidad por servidor (un jugador en 3 servidores
  tendría 3 filas con el mismo XUID).
- La presencia ya tiene su propio agregado (`PlaySession` con `server_id`);
  el estado por servidor no pertenece a la identidad.
- Cambiar la semántica de `player_players` para ajustarse al TDD sería
  retrocompatible-rotura de datos en producción (FK de `player_sessions`,
  queries existentes).

### Consecuencias

**Positivas**:
- Identidad única y sin ambigüedad; los datos per-servidor viven en tablas con
  `server_id`.

**Negativas**:
- `technical-design.md` §15.5 queda desactualizado respecto a la implementación
  (identidad global vs N:1 `Server`). **TODO no bloqueante**: actualizar el TDD
  en la próxima versión del documento (los ADR no modifican el TDD inmutable).

### Impacto en el Blueprint y futuras implementaciones

- La próxima versión del TDD debe alinear §15.5 con `player_players`
  (identidad global, sin `server_id`) y mover los campos de ban a los agregados
  `GlobalBan`/`ServerBan` (ADR-011).
- Las fases futuras (historial por servidor, métricas por jugador por servidor)
  deben usar `PlaySession`/`player_server_bans`, no `player_players`.

---

## ADR-013 — Migración del Monitoring al gateway único `/ws`

> **Estado**: Proposed (pendiente de decisión — **NO ejecutar en esta pasada**)
> **Fecha**: 2026-08-10
> **Origen**: pasada de verificación del panel (change-log §30); revisión del
> badge de jugadores del header y de la fuente en vivo de métricas

### Problema

Hoy conviven **dos endpoints WS** para el mismo servidor (verificado contra el
código, frontend-standards §4):

1. El **gateway único `/ws`** (`modules/notification`): eventos de negocio de
   todos los dominios (estado, consola, jugadores, backups…), con canales
   `global`/`server:{id}`/`user:{id}` y `resume` por `seq`.
2. El **WS de monitoring por servidor** (`/servers/{id}/monitoring/ws`,
   ADR-002, desviación aceptada): snapshots de CPU/RAM/disco/jugadores cada
   `poll_interval` (~5 s) en un envelope `SERVER.STATE` con `scope="monitoring"`.

Esto obliga al frontend a mantener **dos clientes WS** (gateway compartido +
un socket de monitoring por servidor activo) y duplica el transporte de métricas.

### Alternativas consideradas

1. **Migrar las métricas de Monitoring al gateway único `/ws`** como canal
   `server:{id}` (o un canal `monitoring:{id}`), eliminando el endpoint
   `/servers/{id}/monitoring/ws` y el segundo cliente.
2. **Mantener el estado actual** (ADR-002): dos endpoints, un socket de
   monitoring por servidor, uno de gateway compartido.
3. **Publicar métricas en el bus** para que el gateway las enrute, pero
   conservar el WS de monitoring como retro-compat.

### Decisión

**Sin decisión ejecutada.** Se deja anotada como **candidata de arquitectura
(backlog/ADR Proposed)** para evaluarse fuera de la pasada de verificación. La
implementación actual está **confirmada funcionando** (gateway para negocio,
WS de monitoring para métricas, cabecera y StatCards leyendo de
`useMonitoringStore`), por lo que la migración es **riesgo sin beneficio
funcional inmediato**.

### Justificación de no ejecutarla ahora

- Cambio transversal (backend: transporte/enrutado de métricas; frontend: un
  único cliente WS) sin impacto funcional observable para el usuario.
- El estado actual respeta la regla práctica de §4 (negocio → gateway;
  métricas → WS de monitoring por servidor) y ya está cubierto por tests.
- La migración solo debería dispararse si aparece un motivo concreto
  (latencia, coste de sockets, simplificación del frontend, consolidación de
  `resume`/`seq`).

### Consecuencias

**Positivas (de ejecutarse en el futuro)**:
- Un solo cliente WS y un solo transporte para estado + métricas.
- `resume` por `seq` y control de flujo del gateway también para métricas.

**Negativas (de no ejecutarse)**:
- El frontend mantiene un socket de monitoring por servidor activo además del
  gateway (coste acotado: uno a la vez, con refcount compartido).

### Impacto en el Blueprint y futuras implementaciones

- Si se acepta, actualizar `technical-design.md` §17/Fase H y
  `implementation-blueprint.md` §3.12 Notification para consolidar el endpoint.
- Actualizar `frontend-standards.md` §4 y la capa `ws` del frontend a un único
  cliente; `useServerMonitoring` pasaría a escribir desde el gateway.
- Mientras tanto, **no crear más sockets de métricas por componente**: seguir
  la regla de leer de `useMonitoringStore` (un socket por servidor, §4).

---

*Los ADR Accepted marcan decisiones aceptadas cuyo reflejo documental en el TDD/análisis queda
programado para la siguiente versión de esos documentos (inmutables en esta revisión).*
