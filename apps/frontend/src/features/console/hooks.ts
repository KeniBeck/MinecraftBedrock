import { useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'

import { sendConsoleCommand } from '@/lib/api/console'
import { API_BASE } from '@/lib/api/client'
import type { WsEnvelope } from '@/lib/ws/types'
import { useAuthStore } from '@/stores/auth'
import { useConsoleStore, type ConsoleLine } from '@/stores/console'

const BACKOFF_BASE_MS = 1000
const BACKOFF_MAX_MS = 15_000

/** Coalesce de escrituras del WS: un `set` del store por lote (evita congelar
 *  la UI cuando el buffer reproduce el anillo completo al reconectar). */
const BATCH_MAX_LINES = 200
const FLUSH_INTERVAL_MS = 80

/** Estado compartido de UN socket de consola por servidor (estándar §4). */
interface SharedEntry {
  serverId: string
  refCount: number
  socket: WebSocket | null
  retryRef: ReturnType<typeof setTimeout> | null
  attempt: number
  closed: boolean
  pending: ConsoleLine[]
  flushTimer: ReturnType<typeof setTimeout> | null
}

const registry = new Map<string, SharedEntry>()

/**
 * URL del WS de consola `/servers/{id}/console/ws` (ADR-002, NO el gateway).
 * `after_seq` reanuda desde la última línea vista: `-1` reproduce todo el
 * buffer inicial (el `since()` del backend es exclusivo y los seq empiezan en 0).
 */
function consoleUrl(serverId: string, token: string, afterSeq: number): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const base = `${protocol}//${window.location.host}${API_BASE}`
  return `${base}/servers/${encodeURIComponent(serverId)}/console/ws?token=${encodeURIComponent(token)}&after_seq=${afterSeq}`
}

/** Envelope `CONSOLE.OUTPUT` → línea del store (`null` si no aplica). */
export function toConsoleLine(envelope: WsEnvelope, serverId: string): ConsoleLine | null {
  if (envelope.event !== 'CONSOLE.OUTPUT' || envelope.server_id !== serverId) return null
  const line = typeof envelope.payload?.line === 'string' ? envelope.payload.line : ''
  if (!line) return null
  return { seq: envelope.seq, line, timestamp: envelope.ts }
}

function openSocket(serverId: string, token: string, entry: SharedEntry): void {
  if (entry.closed) return
  // Resume: último seq recibido para este servidor (el store lo conserva aunque
  // desmontemos el hook, así volver a la página no duplica líneas).
  const afterSeq = useConsoleStore.getState().lastSeq[serverId] ?? -1
  entry.socket = new WebSocket(consoleUrl(serverId, token, afterSeq))
  entry.socket.onmessage = (event) => {
    let message: WsEnvelope
    try {
      message = JSON.parse(String(event.data)) as WsEnvelope
    } catch {
      return
    }
    const line = toConsoleLine(message, serverId)
    if (!line) return
    entry.attempt = 0
    // Acumula en el lote y lo vacía por tamaño o por intervalo, en vez de hacer
    // un `set` por línea (la reproducción inicial del buffer puede ser ~1000).
    entry.pending.push(line)
    if (entry.pending.length >= BATCH_MAX_LINES) {
      flushPending(serverId, entry)
    } else if (!entry.flushTimer) {
      entry.flushTimer = setTimeout(() => flushPending(serverId, entry), FLUSH_INTERVAL_MS)
    }
  }
  entry.socket.onclose = () => {
    if (entry.closed) return
    scheduleReconnect(serverId, token, entry)
  }
}

/** Vacía el lote pendiente en el store en una sola escritura. */
function flushPending(serverId: string, entry: SharedEntry): void {
  if (entry.flushTimer) {
    clearTimeout(entry.flushTimer)
    entry.flushTimer = null
  }
  const batch = entry.pending
  entry.pending = []
  if (batch.length > 0) {
    useConsoleStore.getState().addLines(serverId, batch)
  }
}function scheduleReconnect(serverId: string, token: string, entry: SharedEntry): void {
  if (entry.closed) return
  const delay = Math.min(BACKOFF_BASE_MS * 2 ** entry.attempt, BACKOFF_MAX_MS)
  entry.attempt += 1
  entry.retryRef = setTimeout(() => openSocket(serverId, token, entry), delay)
}

function closeSocket(entry: SharedEntry): void {
  entry.closed = true
  if (entry.retryRef) {
    clearTimeout(entry.retryRef)
    entry.retryRef = null
  }
  const socket = entry.socket
  entry.socket = null
  if (socket && socket.readyState !== WebSocket.CLOSED) {
    socket.onclose = null
    if (socket.readyState === WebSocket.CONNECTING) {
      // Cerrar en CONNECTING loguea "WebSocket is closed before the connection
      // is established" (ruido de dev con StrictMode); se difiere al open.
      socket.onopen = () => socket.close(1000, 'unmount')
    } else {
      socket.close(1000, 'unmount')
    }
  }
  // Vacía lo pendiente para no perder la última ráfaga al desmontar.
  if (entry.flushTimer) {
    clearTimeout(entry.flushTimer)
    entry.flushTimer = null
  }
  if (entry.pending.length > 0) {
    useConsoleStore.getState().addLines(entry.serverId, entry.pending)
    entry.pending = []
  }
  // No se limpia el buffer: el scrollback persiste en la sesión y el resume por
  // `lastSeq` evita duplicar al volver a conectar.
}

/**
 * Conecta el WebSocket de consola de un servidor (`/servers/{id}/console/ws`)
 * y escribe cada línea `CONSOLE.OUTPUT` en `useConsoleStore`. Idempotente:
 * comparte UN socket por servidor con refcount (estándar §4) y reconecta con
 * backoff, reanudando desde el último `seq` visto.
 */
export function useConsole(serverId: string | undefined): void {
  const accessToken = useAuthStore((state) => state.accessToken)

  useEffect(() => {
    if (!serverId || !accessToken) return

    let entry = registry.get(serverId)
    if (!entry) {
      entry = {
        serverId,
        refCount: 0,
        socket: null,
        retryRef: null,
        attempt: 0,
        closed: false,
        pending: [],
        flushTimer: null,
      }
      registry.set(serverId, entry)
    }
    entry.refCount += 1
    if (entry.refCount === 1) {
      entry.closed = false
      openSocket(serverId, accessToken, entry)
    }

    return () => {
      entry!.refCount -= 1
      if (entry!.refCount <= 0) {
        registry.delete(serverId)
        closeSocket(entry!)
      }
    }
  }, [serverId, accessToken])
}

/** `POST /servers/{id}/console/commands` — acuse 202. */
export function useSendCommand(serverId: string | undefined) {
  return useMutation({
    mutationFn: (command: string) => sendConsoleCommand(serverId!, command),
  })
}
