import { useEffect } from 'react'

import { useAuthStore } from '@/stores/auth'
import { useWebSocketStore } from '@/stores/ws'

/**
 * Hook de alto nivel para conectar el WS compartido con el token actual y
 * suscribirse a canales. Idempotente: si el socket ya está conectado no vuelve
 * a abrir (el store es un singleton).
 */
export function useWebSocket(channels: string[] = []): void {
  const accessToken = useAuthStore((state) => state.accessToken)
  const connect = useWebSocketStore((state) => state.connect)
  const disconnect = useWebSocketStore((state) => state.disconnect)
  const subscribe = useWebSocketStore((state) => state.subscribe)
  const unsubscribe = useWebSocketStore((state) => state.unsubscribe)

  // Conectar/desconectar según haya sesión.
  useEffect(() => {
    if (!accessToken) {
      disconnect()
      return
    }
    connect(accessToken)
    return () => disconnect()
  }, [accessToken, connect, disconnect])

  // Suscribirse/desuscribirse a los canales pedidos por la página actual.
  useEffect(() => {
    if (!accessToken || channels.length === 0) return
    subscribe(...channels)
    return () => unsubscribe(...channels)
  }, [accessToken, channels, subscribe, unsubscribe])
}
