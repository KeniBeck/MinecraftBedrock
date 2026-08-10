import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { useWebSocket } from '@/hooks/useWebSocket'
import { serverKeys, type Server, type ServerState } from '@/lib/api/servers'
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
 * Aplica un cambio de estado a las DOS cachés de TanStack Query que guardan el
 * mismo servidor: el detalle `['server', id]` y la lista `['servers']` que lee
 * el selector del header (frontend-standards §13). Sin esto, la card cambia a
 * "En línea" pero la pastilla del header se queda con el estado viejo.
 */
function applyState(queryClient: ReturnType<typeof useQueryClient>, serverId: string, state: ServerState): void {
  queryClient.setQueryData<Server>(serverKeys.detail(serverId), (current) =>
    current ? { ...current, state } : current,
  )
  queryClient.setQueryData<Server[]>(serverKeys.all, (list) =>
    list?.map((server) => (server.id === serverId ? { ...server, state } : server)),
  )
}

/**
 * Suscribe al canal `server:{id}` y aplica en vivo los cambios de estado al
 * server en las cachés de detalle y de lista — el criterio de la Fase 2 (el
 * estado se actualiza solo por WS, sin refrescar la página), extendido para
 * que el header sincronice (§13).
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
      applyState(queryClient, serverId, newState)
    })
    return unsubscribe
  }, [serverId, queryClient])
}