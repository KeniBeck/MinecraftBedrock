import { useNotificationsStore } from '@/stores/notifications'
import { useServers } from '@/features/servers/hooks'
import type { Server } from '@/lib/api/servers'
import type { DashboardStats } from './types'

/** Estados que cuentan como "en línea" (verde) para el resumen. */
const ONLINE_STATES = new Set(['running', 'starting'])

/** Eventos que cuentan como "backup reciente" en el resumen. */
const BACKUP_EVENTS = new Set(['BACKUP.COMPLETED', 'BACKUP.FAILED'])

/**
 * Estadísticas del dashboard derivadas de la lista `GET /servers` (cache de
 * TanStack Query, sincronizada en vivo por el WS vía `useServerStateSync`) y
 * del feed global de eventos (`useNotificationsStore`, alimentado por
 * `useNotifications` que ya escucha `global` + `user` + todos los `server:*`).
 *
 * No abre sockets de monitoreo adicionales: los jugadores online no vienen en
 * `ServerResponse` (verificado en `api/schemas.py`), por lo que se reportan
 * como `null` ("—") — criterio de la Fase 8: no inventar métricas ni abrir un
 * WS por servidor desde el dashboard.
 */
export function useDashboardStats(): DashboardStats {
  const { data: servers = [] } = useServers()
  const items = useNotificationsStore((state) => state.items)

  const online = servers.filter((server) => ONLINE_STATES.has(server.state)).length
  const recentBackups = items.filter((item) => BACKUP_EVENTS.has(item.event)).length

  return {
    total: servers.length,
    online,
    offline: servers.length - online,
    players: null,
    recentBackups,
  }
}

/** Lista de servidores para la tabla (misma cache que `useServers`). */
export function useDashboardServers(): Server[] {
  const { data = [] } = useServers()
  return data
}
