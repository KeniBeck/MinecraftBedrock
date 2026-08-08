import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { useWebSocket } from '@/hooks/useWebSocket'
import type { Server, ServerState } from '@/lib/api/servers'
import { useWebSocketStore } from '@/stores/ws'

/** Eventos del canal `server:{id}` que cambian el estado del dominio. */
const STATE_EVENTS: Record<string, ServerState> = {
  'SERVER.STARTING': 'starting',
  'SERVER.STARTED': 'running',
  'SERVER.STOPPING': 'stopping',
  'SERVER.STOPPED': 'stopped',
  'SERVER.CRASHED': 'crashed',
}

/**
 * Suscribe al canal `server:{id}` y aplica en vivo los cambios de estado al
 * server en la cache de TanStack Query — el criterio de la Fase 2 (el estado
 * se actualiza solo por WS, sin refrescar la página).
 */
export function useServerStateSync(serverId: string | undefined): void {
  const queryClient = useQueryClient()
  const channels = serverId ? [`server:${serverId}`] : []

  useWebSocket(channels)

  useEffect(() => {
    if (!serverId) return
    const client = useWebSocketStore.getState().client
    const unsubscribe = client.onEvent((envelope) => {
      const newState = STATE_EVENTS[envelope.event]
      if (!newState) return
      const channelMatch =
        envelope.scope === 'server' && (envelope.server_id ?? '') === serverId
      if (!channelMatch) return

      queryClient.setQueryData<Server>(['server', serverId], (current) => {
        if (!current) return current
        return { ...current, state: newState }
      })
    })
    return unsubscribe
  }, [serverId, queryClient])
}
