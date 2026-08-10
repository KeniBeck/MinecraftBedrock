/**
 * Tipos del protocolo WebSocket — verificados contra
 * `apps/backend/src/app/modules/notification/application/event_dispatcher.py
 * ::serialize_envelope` (campos `event/server_id/scope/payload/ts/seq`) y el
 * router `/ws` (`modules/notification/api/router.py`).
 *
 * No inventar campos: estas interfaces reflejan el wire real.
 */

/**
 * Envelope que llega del servidor tras un evento. Campos exactos de
 * `serialize_envelope`:
 * - `event`: tipo canónico (p. ej. `SERVER.STARTED`).
 * - `server_id`: servidor destino (o `null` para global/user).
 * - `scope`: `global` | `server` | `user` | `console` (el WS de consola usa
 *   `console` — `modules/console/api/router.py::_envelope`).
 * - `payload`: objeto arbitrario por evento.
 * - `ts`: ISO timestamp de publicación.
 * - `seq`: número global monótono (para resume).
 */
export interface WsEnvelope {
  event: string
  server_id: string | null
  scope: 'global' | 'server' | 'user' | 'console'
  payload: Record<string, unknown>
  ts: string
  seq: number
}

/** Mensajes que el cliente envía (router `/ws`): subscribe/unsubscribe/resume/pong. */
export type WsClientMessage =
  | { action: 'subscribe'; channels: string[] }
  | { action: 'unsubscribe'; channels: string[] }
  | { action: 'resume'; last_seq: number; channels: string[] }
  | { action: 'pong' }

/**
 * Respuesta de control del servidor. El server manda **dos formas** distintas
 * por el mismo socket:
 * - **Envelopes** (eventos): traen `event`/`server_id`/`scope`/`payload`/`ts`/
 *   `seq` (serialize_envelope) — sin campo `type`.
 * - **Mensajes de control** (acks/errores): traen `type` (`subscribed`,
 *   `resume`, `error`, …) con campos opcionales.
 * Este tipo cubre ambas formas de forma conservadora.
 */
export interface WsControlMessage {
  type?: string
  // Envelope (eventos):
  event?: string
  server_id?: string | null
  scope?: 'global' | 'server' | 'user' | string
  payload?: Record<string, unknown>
  ts?: string
  seq?: number
  // Control:
  results?: Array<{ channel: string; allowed: boolean; reason?: string }>
  events?: WsEnvelope[]
  exceeded?: boolean
  code?: string
  last_seq?: number
}
