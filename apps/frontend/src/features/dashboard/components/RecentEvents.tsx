import { useNotificationsStore } from '@/stores/notifications'
import { isErrorEvent, labelFor, relativeTime } from '@/lib/notifications'
import { cn } from '@/lib/utils'

const MAX_EVENTS = 10

/**
 * Feed de los últimos eventos globales (panel + servidores). Lee
 * `useNotificationsStore`, alimentado por `useNotifications` (que escucha el
 * canal `global`, `user:{id}` y todos los `server:*` del gateway WS singleton),
 * sin abrir sockets extra.
 */
export function RecentEvents() {
  const items = useNotificationsStore((state) => state.items)

  if (items.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Sin eventos recientes todavía.
      </div>
    )
  }

  return (
    <ul className="space-y-2">
      {items.slice(0, MAX_EVENTS).map((item) => (
        <li
          key={item.key}
          className="flex items-start gap-3 rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2"
          data-testid="recent-event"
        >
          <span
            className={cn(
              'mt-1.5 flex size-2 shrink-0 rounded-none',
              isErrorEvent(item.event) ? 'bg-red-400' : 'bg-emerald-400',
            )}
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-slate-100">{labelFor(item)}</p>
            <p className="text-[11px] text-slate-400">
              {item.serverId ? `Servidor ${item.serverId.slice(0, 8)}` : 'Panel'} ·{' '}
              {relativeTime(item.ts)}
            </p>
          </div>
        </li>
      ))}
    </ul>
  )
}
