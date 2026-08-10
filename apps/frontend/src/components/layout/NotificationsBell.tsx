import { useState } from 'react'

import { Bell, Check } from 'lucide-react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useNotifications } from '@/hooks/useNotifications'
import { unreadCount, useNotificationsStore } from '@/stores/notifications'
import { cn } from '@/lib/utils'

/** Tiempo relativo corto ("hace 2 m") a partir de `ts` ISO. */
function relativeTime(ts: string): string {
  const then = new Date(ts).getTime()
  const diffMs = Math.max(0, Date.now() - then)
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) return 'ahora'
  if (minutes < 60) return `hace ${minutes} m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `hace ${hours} h`
  return `hace ${Math.floor(hours / 24)} d`
}

const EVENT_LABEL: Record<string, string> = {
  'SERVER.STARTED': 'Servidor en línea',
  'SERVER.STOPPED': 'Servidor detenido',
  'SERVER.CRASHED': 'Servidor caído',
  'PLAYER.JOINED': 'Jugador conectado',
  'PLAYER.LEFT': 'Jugador desconectado',
  'BACKUP.COMPLETED': 'Backup completado',
  'BACKUP.FAILED': 'Backup fallido',
  'TASK.FAILED': 'Tarea fallida',
}

function labelFor(item: { event: string; payload: Record<string, unknown> }): string {
  const base = EVENT_LABEL[item.event] ?? item.event
  const name = typeof item.payload.name === 'string' ? item.payload.name : undefined
  return name ? `${base}: ${name}` : base
}

function NotificationIcon({ event }: { event: string }) {
  const isError = event.endsWith('.FAILED') || event.endsWith('CRASHED')
  return (
    <span
      className={cn(
        'mt-0.5 flex size-2 shrink-0 rounded-none',
        isError ? 'bg-red-400' : 'bg-emerald-400',
      )}
      aria-hidden
    />
  )
}

/**
 * Campana de notificaciones del header (mockup §9.1). Badge = no leídos;
 * al abrir se marcan todos como leídos (estado local zustand — no hay
 * persistencia server-side todavía, frontend-standards §13).
 */
export function NotificationsBell() {
  const [open, setOpen] = useState(false)
  const items = useNotificationsStore((state) => state.items)
  const markAllRead = useNotificationsStore((state) => state.markAllRead)

  useNotifications()

  const unread = unreadCount(items)

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (next) markAllRead()
  }

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Notificaciones"
          title="Notificaciones"
          className="relative rounded-lg p-1.5 text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
          data-testid="notifications-bell"
        >
          <Bell className="size-5" />
          {unread > 0 && (
            <span
              className="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white"
              data-testid="notifications-badge"
            >
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>Notificaciones</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {items.length === 0 ? (
          <div className="px-3 py-4 text-center text-sm text-slate-400">Sin notificaciones</div>
        ) : (
          items.map((item) => (
            <DropdownMenuItem key={item.key} disabled className="cursor-default items-start gap-2" data-testid="notification-item">
              <NotificationIcon event={item.event} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-slate-100">{labelFor(item)}</span>
                <span className="block text-[11px] text-slate-400">
                  {item.serverId ? `Servidor ${item.serverId.slice(0, 8)}` : 'Panel'} ·{' '}
                  {relativeTime(item.ts)}
                </span>
              </span>
              {!item.read && <Check className="size-3 text-emerald-400" />}
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}