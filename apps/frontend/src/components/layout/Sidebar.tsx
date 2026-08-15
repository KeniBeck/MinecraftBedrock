import { Link, useLocation, useParams } from 'react-router-dom'
import {
  Archive,
  Bell,
  Boxes,
  ChevronLeft,
  CircleGauge,
  Database,
  Gamepad2,
  Globe,
  Keyboard,
  LayoutDashboard,
  ScrollText,
  Settings2,
  Shield,
  UserCircle,
  Users,
} from 'lucide-react'

import { useActiveServer } from '@/stores/servers'
import { useCan } from '@/lib/auth/useCan'
import { cn } from '@/lib/utils'

/**
 * Ítems del sidebar según frontend-standards §6 (naming y orden exactos del
 * mockup). "Servidor" y "Consola" navegan a `/servers/:id` y
 * `/servers/:id/console` usando el servidor activo; el resto se muestran como
 * placeholders deshabilitados (fases posteriores).
 */
interface SidebarItem {
  label: string
  icon: typeof Gamepad2
  href?: string
  /** Ruta hija dentro de `/servers/:serverId` (p. ej. `console`). */
  sub?: string
  disabled?: boolean
  /** Añadido a la matriz de `useCan`; el ítem se oculta si no puede. */
  gate?: string
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  { label: 'Dashboard', icon: LayoutDashboard, disabled: true },
  { label: 'Servidor', icon: Gamepad2, href: '/servers', disabled: false },
  { label: 'Consola', icon: Keyboard, href: '/servers', sub: 'console', disabled: false },
  { label: 'Jugadores', icon: Users, href: '/servers', sub: 'players', disabled: false },
  { label: 'Mundos', icon: Globe, href: '/servers', sub: 'worlds', disabled: false },
  { label: 'Backups', icon: Archive, href: '/servers', sub: 'backups', disabled: false },
  { label: 'Programador', icon: CircleGauge, href: '/servers', sub: 'scheduler', disabled: false },
  { label: 'Monitoreo', icon: Bell, href: '/servers', sub: 'monitoring', disabled: false },
  { label: 'Plantillas', icon: Boxes, href: '/servers', sub: 'templates', disabled: false },
  { label: 'Permisos', icon: Shield, href: '/servers', sub: 'permissions', disabled: false },
  { label: 'Configuración', icon: Settings2, href: '/servers', sub: 'configuration', disabled: false },
  { label: 'Mi perfil', icon: UserCircle, href: '/profile', disabled: false },
  { label: 'Administración', icon: ScrollText, href: '/admin/iam', gate: 'iam.manage' },
  { label: 'Logs', icon: Database, disabled: true },
]

/**
 * Sidebar con estilo de inventario de Minecraft (prototipo card-pixelada-v2):
 * superficie texturizada con bisel de dos tonos, borde negro, ítem activo como
 * bloque esmeralda y hover con el "wash" blanco translúcido de los slots.
 */
export function Sidebar({
  collapsed,
  onToggleCollapsed,
}: {
  collapsed: boolean
  onToggleCollapsed: () => void
}) {
  const { serverId } = useParams<{ serverId: string }>()
  const { pathname } = useLocation()
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const resolvedServerId = serverId ?? activeServerId
  const canManageIam = useCan('iam.manage')

  const visibleItems = SIDEBAR_ITEMS.filter((item) => !item.gate || canManageIam)

  /** `/servers/:id[/sub]` si el ítem depende del servidor activo, o `null`. */
  function resolveHref(item: SidebarItem): string | null {
    if (!item.href) return null
    if (item.href !== '/servers') return item.href
    if (!resolvedServerId) return null
    return `/servers/${resolvedServerId}${item.sub ? `/${item.sub}` : ''}`
  }

  return (
    <aside
      className={cn(
        'pixel-panel sticky top-0 flex h-screen shrink-0 flex-col transition-[width]',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Logo + flecha de colapso (mockup §9.1). */}
      <div className="flex items-center justify-between border-b border-black px-4 py-4">
        {!collapsed && (
          <span className="pixel-title text-sm tracking-widest text-white">BEDROCK PANEL</span>
        )}
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="rounded-none border border-black bg-slate-800/80 p-1.5 text-slate-300 shadow-[inset_1px_1px_0_rgba(255,255,255,.2),inset_-1px_-1px_0_rgba(0,0,0,.4)] hover:bg-white/10 hover:text-white"
          aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          <ChevronLeft className={cn('size-4 transition-transform', collapsed && 'rotate-180')} />
        </button>
      </div>

      <nav className="sidebar-scroll flex-1 space-y-1 overflow-y-auto px-2 py-2">
        {visibleItems.map((item) => {
          const Icon = item.icon
          const href = resolveHref(item)
          const active = href ? pathname === href : false
          const itemContent = (
            <>
              <Icon className="size-5 shrink-0" />
              {!collapsed && <span className="text-sm">{item.label}</span>}
            </>
          )
          const classes = cn(
            'flex items-center gap-3 px-3 py-2',
            active
              ? 'pixel-nav-active text-sm font-bold'
              : 'pixel-nav text-slate-300',
            item.disabled && 'cursor-not-allowed opacity-40 hover:bg-transparent hover:shadow-none',
          )
          if (item.disabled || !href) {
            return (
              <span key={item.label} className={classes} title={item.disabled ? 'Próximamente' : undefined}>
                {itemContent}
              </span>
            )
          }
          return (
            <Link key={item.label} to={href} className={classes} data-testid={`sidebar-${item.label}`}>
              {itemContent}
            </Link>
          )
        })}
      </nav>

      {/* Pie: versión + Open Source (mockup §9.1). */}
      <div className="border-t border-black px-4 py-3">
        {!collapsed && (
          <p className="pixel-overline text-slate-400">
            v0.1.0 · <span className="text-slate-300">Open Source</span>
          </p>
        )}
      </div>
    </aside>
  )
}
