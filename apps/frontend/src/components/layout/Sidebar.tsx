import { useState } from 'react'
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

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { serverId } = useParams<{ serverId: string }>()
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const resolvedServerId = serverId ?? activeServerId

  return (
    <aside
      className={cn(
        'sticky top-0 flex h-screen shrink-0 flex-col border-r border-white/10 bg-slate-900/60 backdrop-blur-xl transition-[width]',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      {/* Logo + flecha de colapso (mockup §9.1). */}
      <div className="flex items-center justify-between px-4 py-4">
        {!collapsed && (
          <span className="font-pixel text-sm tracking-widest text-white">BEDROCK PANEL</span>
        )}
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          className="rounded-lg p-1.5 text-muted-foreground hover:bg-white/10 hover:text-white"
          aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          <ChevronLeft className={cn('size-4 transition-transform', collapsed && 'rotate-180')} />
        </button>
      </div>

      <nav className="flex-1 space-y-1 px-2 py-2">
        {SIDEBAR_ITEMS.map((item) => {
          const Icon = item.icon
          const active = item.href === '/servers' && Boolean(resolvedServerId)
          const itemContent = (
            <>
              <Icon className="size-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </>
          )
          const classes = cn(
            'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
            active
              ? 'bg-emerald-500 text-white'
              : 'text-muted-foreground hover:bg-white/10 hover:text-white',
            item.disabled && 'cursor-not-allowed opacity-40 hover:bg-transparent hover:text-muted-foreground',
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
      <div className="border-t border-white/10 px-4 py-3">
        {!collapsed && (
          <p className="text-xs text-muted-foreground">
            v0.1.0 · <span className="text-white/60">Open Source</span>
          </p>
        )}
      </div>
    </aside>
  )
}
