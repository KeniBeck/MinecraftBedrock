import { Link } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { Archive, Box, Gamepad2, Keyboard, Settings2, Shield, Users, Globe } from 'lucide-react'

import { useDashboardServers } from '../hooks'
import { useActiveServer } from '@/stores/servers'

interface Action {
  label: string
  icon: LucideIcon
  /** Ruta dentro de `/servers/:id` (para acciones dependientes de servidor). */
  sub?: string
  /** Ruta fija (independiente de servidor). */
  href?: string
}

const ACTIONS: Action[] = [
  { label: 'Servidores', icon: Gamepad2, href: '/servers' },
  { label: 'Consola', icon: Keyboard, sub: 'console' },
  { label: 'Jugadores', icon: Users, sub: 'players' },
  { label: 'Mundos', icon: Globe, sub: 'worlds' },
  { label: 'Backups', icon: Archive, sub: 'backups' },
  { label: 'Plantillas', icon: Box, sub: 'templates' },
  { label: 'Permisos', icon: Shield, sub: 'permissions' },
  { label: 'Configuración', icon: Settings2, href: '/admin/settings' },
]

/**
 * Grid de accesos rápidos a las páginas principales. Las rutas dependientes de
 * servidor usan el servidor activo (o el primero visible); si no hay ninguno,
 * esos accesos se deshabilitan (no hay a dónde navegar).
 */
export function QuickActions() {
  const servers = useDashboardServers()
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const resolvedServerId =
    activeServerId && servers.some((server) => server.id === activeServerId)
      ? activeServerId
      : servers[0]?.id

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {ACTIONS.map((action) => {
        const Icon = action.icon
        const href = action.href ?? (resolvedServerId ? `/servers/${resolvedServerId}/${action.sub}` : null)
        const disabled = href === null
        const content = (
          <>
            <Icon className="size-5" />
            <span className="text-sm">{action.label}</span>
          </>
        )
        const classes = `flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3 transition-colors ${
          disabled
            ? 'cursor-not-allowed opacity-40'
            : 'hover:bg-white/10 hover:text-white'
        }`
        if (disabled) {
          return (
            <span key={action.label} className={classes} title="Sin servidores disponibles">
              {content}
            </span>
          )
        }
        return (
          <Link
            key={action.label}
            to={href}
            className={classes}
            data-testid={`quick-action-${action.label}`}
          >
            {content}
          </Link>
        )
      })}
    </div>
  )
}