import { useEffect, useMemo } from 'react'

import { useServers } from '@/features/servers/hooks'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WsEnvelope } from '@/lib/ws/types'
import { useNotificationsStore } from '@/stores/notifications'
import { useAuthStore } from '@/stores/auth'
import { useWebSocketStore } from '@/stores/ws'

/**
 * Eventos que generan una notificación visible en la campana (frontend-standards
 * §13). El resto de envelopes (p. ej. `SERVER.STATE` de monitoring, `CONSOLE.OUTPUT`)
 * actualizan datos en silencio y se filtran aquí explícitamente.
 */
const NOTIFICATION_EVENTS = new Set([
  'SERVER.STARTED',
  'SERVER.STOPPED',
  'SERVER.CRASHED',
  'PLAYER.JOINED',
  'PLAYER.LEFT',
  'BACKUP.COMPLETED',
  'BACKUP.FAILED',
  'TASK.FAILED',
])

function isNotificationEvent(envelope: WsEnvelope): boolean {
  return NOTIFICATION_EVENTS.has(envelope.event)
}

/**
 * Alimenta la campana de notificaciones. Se suscribe a `global`, `user:{id}` y
 * `server:{id}` de los servidores visibles (el WS del gateway es un singleton;
 * estas suscripciones se suman a las de `useServerStateSync`).
 */
export function useNotifications(): void {
  const identity = useAuthStore((state) => state.identity)
  const { data: servers = [] } = useServers()
  const push = useNotificationsStore((state) => state.push)

  const channels = useMemo(
    () => [
      'global',
      ...(identity ? [`user:${identity.id}`] : []),
      ...servers.map((server) => `server:${server.id}`),
    ],
    [identity, servers],
  )

  useWebSocket(channels)

  useEffect(() => {
    const client = useWebSocketStore.getState().client
    const unsubscribe = client.onEvent((envelope) => {
      if (!isNotificationEvent(envelope)) return
      push(envelope)
    })
    return unsubscribe
  }, [push])
}