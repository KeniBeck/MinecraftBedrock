import { create } from 'zustand'

import { WebSocketClient, type WsConnectionStatus } from '@/lib/ws/WebSocketClient'
import type { WsEnvelope } from '@/lib/ws/types'

/**
 * Store del WebSocket compartido. Existe UN solo `WebSocketClient` a nivel de
 * app; los componentes se suscriben al store para saber el estado y los últimos
 * eventos (por canal), nunca abren sockets propios (frontend-standards §4).
 */
interface WsState {
  client: WebSocketClient
  status: WsConnectionStatus
  /** Cola por canal de los últimos envelopes (para renders/notificaciones). */
  latest: Record<string, WsEnvelope>
  connect: (token: string) => void
  disconnect: () => void
  subscribe: (...channels: string[]) => void
  unsubscribe: (...channels: string[]) => void
}

const client = new WebSocketClient()

function initialLatest(): Record<string, WsEnvelope> {
  return {}
}

export const useWebSocketStore = create<WsState>()((set, get) => {
  client.onStatus((status) => set({ status }))
  client.onEvent((envelope) => {
    const channel = envelope.scope === 'server' && envelope.server_id
      ? `server:${envelope.server_id}`
      : envelope.scope === 'user'
        ? 'user'
        : 'global'
    set({ latest: { ...get().latest, [channel]: envelope } })
  })

  return {
    client,
    status: client.connectionStatus,
    latest: initialLatest(),
    connect: (token) => client.connect(token),
    disconnect: () => client.close(1000, 'logout'),
    subscribe: (...channels) => client.subscribe(...channels),
    unsubscribe: (...channels) => client.unsubscribe(...channels),
  }
})
