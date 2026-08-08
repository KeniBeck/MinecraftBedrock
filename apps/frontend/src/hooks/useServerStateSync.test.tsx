import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { useServerStateSync } from '@/hooks/useServerStateSync'
import { useWebSocketStore } from '@/stores/ws'
import { useAuthStore } from '@/stores/auth'
import type { Server } from '@/lib/api/servers'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static OPEN = 1
  static CLOSED = 3
  readyState = 0
  url: string
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close() {
    this.readyState = FakeWebSocket.CLOSED
  }
  emitOpen() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }
  emitMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
  }
}

const SERVER: Server = {
  id: 'srv-1',
  name: 'Survival',
  state: 'stopped',
  version: '1.21.1',
  image_ref: 'img:latest',
  runtime_id: 'r1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  connection: { host: 'localhost', port: 19132, port_v6: 19133, rcon_port: 25575, address: 'localhost:19132' },
}

function Probe({ serverId }: { serverId: string }) {
  const queryClient = useQueryClient()
  useServerStateSync(serverId)
  useEffect(() => {
    queryClient.setQueryData(['server', serverId], SERVER)
  }, [queryClient, serverId])
  return null
}

describe('useServerStateSync', () => {
  function socketAt(index: number): FakeWebSocket {
    const socket = FakeWebSocket.instances[index]
    if (!socket) throw new Error(`FakeWebSocket[${index}] no existe`)
    return socket
  }

  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    Object.defineProperty(window, 'location', {
      value: { protocol: 'http:', host: 'localhost:5173', href: 'http://localhost:5173/' },
      writable: true,
    })
    // `useWebSocket` solo conecta si hay sesión (requiere access token).
    useAuthStore.getState().setSession({
      accessToken: 'at-1',
      refreshToken: 'rt-1',
      identity: { id: 'u1', username: 'alice', roles: ['admin'] },
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    useWebSocketStore.getState().disconnect()
    useAuthStore.getState().clear()
  })

  it('actualiza el estado del server en cache al recibir SERVER.STARTED', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <Probe serverId="srv-1" />
      </QueryClientProvider>,
    )

    const socket = socketAt(0)
    socket.emitOpen()
    expect(socket.sent).toContain(JSON.stringify({ action: 'subscribe', channels: ['server:srv-1'] }))

    socket.emitMessage({
      event: 'SERVER.STARTED',
      server_id: 'srv-1',
      scope: 'server',
      payload: {},
      ts: '2026-01-01T00:00:00Z',
      seq: 5,
    })

    await waitFor(() => {
      expect(queryClient.getQueryData<Server>(['server', 'srv-1'])?.state).toBe('running')
    })
  })

  it('ignora eventos de otros servidores', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <Probe serverId="srv-1" />
      </QueryClientProvider>,
    )

    const socket = socketAt(0)
    socket.emitOpen()
    socket.emitMessage({
      event: 'SERVER.STARTED',
      server_id: 'srv-2',
      scope: 'server',
      payload: {},
      ts: '2026-01-01T00:00:00Z',
      seq: 5,
    })

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(queryClient.getQueryData<Server>(['server', 'srv-1'])?.state).toBe('stopped')
  })
})
