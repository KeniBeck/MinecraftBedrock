import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { toConsoleLine, useConsole, useSendCommand } from '@/features/console/hooks'
import { sendConsoleCommand } from '@/lib/api/console'
import { useConsoleStore } from '@/stores/console'
import { useAuthStore } from '@/stores/auth'
import type { WsEnvelope } from '@/lib/ws/types'

vi.mock('@/lib/api/console', () => ({
  sendConsoleCommand: vi.fn(),
}))

function envelope(event: string, overrides: Partial<WsEnvelope> = {}): WsEnvelope {
  return {
    event,
    server_id: 'srv-1',
    scope: 'console',
    payload: { line: 'hello' },
    ts: '2026-01-01T00:00:00Z',
    seq: 42,
    ...overrides,
  }
}

describe('toConsoleLine', () => {
  it('convierte un envelope CONSOLE.OUTPUT del servidor a línea', () => {
    const result = toConsoleLine(envelope('CONSOLE.OUTPUT'), 'srv-1')
    expect(result).toEqual({ seq: 42, line: 'hello', timestamp: '2026-01-01T00:00:00Z' })
  })

  it('ignora eventos que no son CONSOLE.OUTPUT', () => {
    expect(toConsoleLine(envelope('SERVER.STARTED'), 'srv-1')).toBeNull()
  })

  it('ignora líneas de otros servidores', () => {
    expect(toConsoleLine(envelope('CONSOLE.OUTPUT', { server_id: 'srv-2' }), 'srv-1')).toBeNull()
  })

  it('ignora payload sin línea o línea vacía', () => {
    expect(toConsoleLine(envelope('CONSOLE.OUTPUT', { payload: {} }), 'srv-1')).toBeNull()
    expect(toConsoleLine(envelope('CONSOLE.OUTPUT', { payload: { line: '' } }), 'srv-1')).toBeNull()
  })
})

describe('useSendCommand', () => {
  function wrapper({ children }: { children: ReactNode }) {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }

  it('envía el comando al endpoint del servidor', async () => {
    vi.mocked(sendConsoleCommand).mockResolvedValue({
      server_id: 'srv-1',
      command: 'list',
      priority: 'normal',
      seq: 7,
      at: '2026-01-01T00:00:00Z',
    })
    const { result } = renderHook(() => useSendCommand('srv-1'), { wrapper })

    await act(async () => {
      await result.current.mutateAsync('list')
    })

    expect(sendConsoleCommand).toHaveBeenCalledWith('srv-1', 'list')
  })
})

describe('useConsole — batching de la reproducción', () => {
  afterEach(() => {
    vi.useRealTimers()
    useConsoleStore.setState({ lines: {}, lastSeq: {} })
  })

  it('coalesce líneas y las vacía en lotes en el store', async () => {
    vi.useFakeTimers()

    // WebSocket fake: expone onmessage/onclose y dispara la reproducción.
    class FakeSocket {
      static instance: FakeSocket | null = null
      readyState = 0
      url = ''
      onmessage: ((event: MessageEvent<string>) => void) | null = null
      onclose: (() => void) | null = null
      onopen: (() => void) | null = null
      constructor(url: string) {
        this.url = url
        FakeSocket.instance = this
      }
      close = vi.fn()
    }

    vi.stubGlobal('WebSocket', FakeSocket)

    useAuthStore.setState({ accessToken: 'tok' })

    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        {children}
      </QueryClientProvider>
    )

    const { unmount } = renderHook(() => useConsole('srv-1'), { wrapper })

    // Esperar a que el socket fake se haya creado (openSocket se ejecuta en el effect).
    await act(async () => {
      await Promise.resolve()
    })
    const socket = FakeSocket.instance
    expect(socket).not.toBeNull()

    // Reproducción del buffer: 250 líneas en ráfaga.
    await act(async () => {
      for (let i = 0; i < 250; i += 1) {
        socket!.onmessage?.({
          data: JSON.stringify(envelope('CONSOLE.OUTPUT', { seq: i, payload: { line: `line-${i}` } })),
        } as MessageEvent<string>)
      }
      // Avanzar el timer para que el flush por intervalo/vacío por tamaño ocurra.
      vi.advanceTimersByTime(200)
    })

    // Tras el flush: el store tiene las 250 líneas y el último seq.
    expect(useConsoleStore.getState().lines['srv-1']).toHaveLength(250)
    expect(useConsoleStore.getState().lastSeq['srv-1']).toBe(249)

    unmount()
    vi.unstubAllGlobals()
  })
})
