import { useEffect } from 'react'

import { API_BASE } from '@/lib/api/client'
import type { WsEnvelope } from '@/lib/ws/types'
import { useAuthStore } from '@/stores/auth'
import { useMonitoringStore, type MonitoringSnapshot } from '@/stores/monitoring'

const BACKOFF_BASE_MS = 1000
const BACKOFF_MAX_MS = 15_000

/** Estado compartido de UN socket de monitoreo por servidor (estándar §4). */
interface SharedEntry {
  refCount: number
  socket: WebSocket | null
  retryRef: ReturnType<typeof setTimeout> | null
  attempt: number
  closed: boolean
}

const registry = new Map<string, SharedEntry>()

function monitoringUrl(serverId: string, token: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const base = `${protocol}//${window.location.host}${API_BASE}`
  return `${base}/servers/${encodeURIComponent(serverId)}/monitoring/ws?token=${encodeURIComponent(token)}`
}

function openSocket(serverId: string, token: string, entry: SharedEntry): void {
  if (entry.closed) return
  entry.socket = new WebSocket(monitoringUrl(serverId, token))
  entry.socket.onmessage = (event) => {
    let message: WsEnvelope
    try {
      message = JSON.parse(String(event.data)) as WsEnvelope
    } catch {
      return
    }
    // Solo envelopes de monitoreo (event SERVER.STATE) para este servidor.
    if (message.event !== 'SERVER.STATE' || message.server_id !== serverId) return
    const p = message.payload
    const snapshot: MonitoringSnapshot = {
      state: typeof p.state === 'string' ? p.state : 'unknown',
      status: typeof p.status === 'string' ? p.status : 'unknown',
      latency_ms: typeof p.latency_ms === 'number' ? p.latency_ms : null,
      players: typeof p.players === 'number' ? p.players : 0,
      players_max: typeof p.players_max === 'number' ? p.players_max : 0,
      cpu: typeof p.cpu === 'number' ? p.cpu : null,
      ram_mb: typeof p.ram_mb === 'number' ? p.ram_mb : null,
      disk_mb: typeof p.disk_mb === 'number' ? p.disk_mb : null,
    }
    entry.attempt = 0
    useMonitoringStore.getState().setSnapshot(serverId, snapshot, message.ts)
  }
  entry.socket.onclose = () => {
    if (entry.closed) return
    scheduleReconnect(serverId, token, entry)
  }
}

function scheduleReconnect(serverId: string, token: string, entry: SharedEntry): void {
  if (entry.closed) return
  const delay = Math.min(BACKOFF_BASE_MS * 2 ** entry.attempt, BACKOFF_MAX_MS)
  entry.attempt += 1
  entry.retryRef = setTimeout(() => openSocket(serverId, token, entry), delay)
}

function closeSocket(serverId: string, entry: SharedEntry): void {
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
  useMonitoringStore.getState().clear(serverId)
}

/**
 * Conecta el WebSocket de monitoreo de un servidor (`/servers/{id}/monitoring/ws`)
 * y escribe cada snapshot en `useMonitoringStore`. Idempotente: comparte UN
 * socket por servidor entre todos los componentes que lo necesitan (estándar §4 —
 * los componentes leen del store, no abren sockets propios). Con reconexión por
 * backoff. El snapshot se limpia cuando el ÚLTIMO suscriptor se desmonta.
 */
export function useServerMonitoring(serverId: string | undefined): void {
  const accessToken = useAuthStore((state) => state.accessToken)

  useEffect(() => {
    if (!serverId || !accessToken) return

    let entry = registry.get(serverId)
    if (!entry) {
      entry = { refCount: 0, socket: null, retryRef: null, attempt: 0, closed: false }
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
        closeSocket(serverId, entry!)
      }
    }
  }, [serverId, accessToken])
}
