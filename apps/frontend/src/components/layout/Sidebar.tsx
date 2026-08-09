import { Link, useParams } from 'react-router-dom'
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
  Settings2,
  Shield,
  Users,
} from 'lucide-react'

import { useActiveServer } from '@/stores/servers'
import { cn } from '@/lib/utils'

/**
 * Ítems del sidebar según frontend-standards §6 (naming y orden exactos del
 * mockup). En Fase 2 solo "Servidor" navega a la página de detalle; el resto
 * se muestran como placeholders deshabilitados (fases posteriores).
 */
const SIDEBAR_ITEMS = [
  { label: 'Dashboard', icon: LayoutDashboard, href: '/', disabled: true },
  { label: 'Servidor', icon: Gamepad2, href: '/servers', disabled: false },
  { label: 'Consola', icon: Keyboard, disabled: true },
  { label: 'Jugadores', icon: Users, disabled: true },
  { label: 'Mundos', icon: Globe, disabled: true },
  { label: 'Backups', icon: Archive, disabled: true },
  { label: 'Programador', icon: CircleGauge, disabled: true },
  { label: 'Monitoreo', icon: Bell, disabled: true },
  { label: 'Plantillas', icon: Boxes, disabled: true },
  { label: 'Permisos', icon: Shield, disabled: true },
  { label: 'Configuración', icon: Settings2, disabled: true },
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
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const resolvedServerId = serverId ?? activeServerId

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

      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-2">
        {SIDEBAR_ITEMS.map((item) => {
          const Icon = item.icon
          const active = item.href === '/servers' && Boolean(resolvedServerId)
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
          if (item.disabled || !item.href) {
            return (
              <span key={item.label} className={classes} title={item.disabled ? 'Próximamente' : undefined}>
                {itemContent}
              </span>
            )
          }
          const href = item.href === '/servers' && resolvedServerId
            ? `/servers/${resolvedServerId}`
            : item.href
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
