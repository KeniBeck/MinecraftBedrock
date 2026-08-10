import { describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { toConsoleLine, useSendCommand } from '@/features/console/hooks'
import { sendConsoleCommand } from '@/lib/api/console'
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
