import { Navigate } from 'react-router-dom'

import { useActiveServer } from '@/stores/servers'
import { useServers } from '@/features/servers/hooks'

/**
 * Redirige al detalle del servidor activo (o al primero disponible). Se usa en
 * `/` y `/servers` como índice del layout.
 */
export function ServerRedirect() {
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const { data: servers = [], isLoading } = useServers()

  if (isLoading) return null

  if (activeServerId) {
    return <Navigate to={`/servers/${activeServerId}`} replace />
  }
  const first = servers[0]
  if (first) {
    return <Navigate to={`/servers/${first.id}`} replace />
  }
  // Sin servidores visibles: pantalla vacía.
  return <div className="py-24 text-center text-muted-foreground">Sin servidores</div>
}
