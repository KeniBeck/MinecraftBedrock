import { create } from 'zustand'

import type { WsEnvelope } from '@/lib/ws/types'

/**
 * Notificaciones de la campana (frontend-standards §13). Estado local en el
 * frontend: no hay endpoint REST de notificaciones en el backend (verificado),
 * el "leído" vive aquí y no se persiste server-side. Cada envelope filtrado se
 * guarda; el badge cuenta los no leídos.
 */
export interface NotificationItem {
  key: string
  event: string
  serverId: string | null
  payload: Record<string, unknown>
  ts: string
  read: boolean
}

interface NotificationsState {
  items: NotificationItem[]
  /** El último `seq` visto (para no duplicar por re-emisión del resume). */
  lastSeq: number
  push: (envelope: WsEnvelope) => void
  markAllRead: () => void
  clear: () => void
}

const MAX_ITEMS = 50

export const useNotificationsStore = create<NotificationsState>()((set) => ({
  items: [],
  lastSeq: 0,
  push: (envelope) =>
    set((state) => {
      if (envelope.seq <= state.lastSeq) return state
      const item: NotificationItem = {
        key: `${envelope.seq}-${envelope.event}-${envelope.server_id ?? 'g'}`,
        event: envelope.event,
        serverId: envelope.server_id,
        payload: envelope.payload,
        ts: envelope.ts,
        read: false,
      }
      return {
        items: [item, ...state.items].slice(0, MAX_ITEMS),
        lastSeq: envelope.seq,
      }
    }),
  markAllRead: () => set((state) => ({ items: state.items.map((i) => ({ ...i, read: true })) })),
  clear: () => set({ items: [], lastSeq: 0 }),
}))

/** Número de notificaciones no leídas. */
export function unreadCount(items: NotificationItem[]): number {
  return items.reduce((acc, item) => (item.read ? acc : acc + 1), 0)
}