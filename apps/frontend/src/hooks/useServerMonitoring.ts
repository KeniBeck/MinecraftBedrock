import { useEffect, useRef } from 'react'

import { API_BASE } from '@/lib/api/client'
import type { WsEnvelope } from '@/lib/ws/types'
import { useAuthStore } from '@/stores/auth'
import { useMonitoringStore, type MonitoringSnapshot } from '@/stores/monitoring'

const BACKOFF_BASE_MS = 1000
const BACKOFF_MAX_MS = 15_000

function monitoringUrl(serverId: string, token: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const base = `${protocol}//${window.location.host}${API_BASE}`
  return `${base}/servers/${encodeURIComponent(serverId)}/monitoring/ws?token=${encodeURIComponent(token)}`
}

/**
 * Conecta el WebSocket de monitoreo de un servidor (`/servers/{id}/monitoring/ws`)
 * y escribe cada snapshot en `useMonitoringStore`. Un socket propio por servidor
 * (este endpoint no es el gateway compartido `/ws`), con reconexión por backoff.
 */
export function useServerMonitoring(serverId: string | undefined): void {
  const accessToken = useAuthStore((state) => state.accessToken)
  const setSnapshot = useMonitoringStore((state) => state.setSnapshot)
  const clear = useMonitoringStore((state) => state.clear)

  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptRef = useRef(0)
  const manuallyClosed = useRef(false)

  useEffect(() => {
    if (!serverId || !accessToken) return
    manuallyClosed.current = false
    const setter = (envelope: WsEnvelope) => {
      const p = envelope.payload
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
      attemptRef.current = 0
      setSnapshot(serverId, snapshot)
    }

    let socket: WebSocket | null = null
    let closed = false

    const open = () => {
      if (closed || manuallyClosed.current || !serverId || !accessToken) return
      socket = new WebSocket(monitoringUrl(serverId, accessToken))
      socket.onmessage = (event) => {
        let message: WsEnvelope
        try {
          message = JSON.parse(String(event.data)) as WsEnvelope
        } catch {
          return
        }
        // Solo envelopes de monitoreo (event SERVER.STATE) para este servidor.
        if (message.event === 'SERVER.STATE' && message.server_id === serverId) {
          setter(message)
        }
      }
      socket.onclose = () => {
        if (closed) return
        scheduleReconnect()
      }
    }

    const scheduleReconnect = () => {
      if (closed || manuallyClosed.current) return
      const delay = Math.min(
        BACKOFF_BASE_MS * 2 ** attemptRef.current,
        BACKOFF_MAX_MS,
      )
      attemptRef.current += 1
      retryRef.current = setTimeout(open, delay)
    }

    open()

    return () => {
      closed = true
      manuallyClosed.current = true
      if (retryRef.current) clearTimeout(retryRef.current)
      retryRef.current = null
      socket?.close(1000, 'unmount')
      socket = null
      clear(serverId)
    }
  }, [serverId, accessToken, setSnapshot, clear])
}