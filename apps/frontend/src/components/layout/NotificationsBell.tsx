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
import { isErrorEvent, labelFor, relativeTime } from '@/lib/notifications'
import { unreadCount, useNotificationsStore } from '@/stores/notifications'
import { cn } from '@/lib/utils'

function NotificationIcon({ event }: { event: string }) {
  return (
    <span
      className={cn(
        'mt-0.5 flex size-2 shrink-0 rounded-none',
        isErrorEvent(event) ? 'bg-red-400' : 'bg-emerald-400',
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