import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import { NotificationsBell } from '@/components/layout/NotificationsBell'
import { listServers } from '@/lib/api/servers'
import { useNotificationsStore } from '@/stores/notifications'
import type { WsEnvelope } from '@/lib/ws/types'

vi.mock('@/lib/api/servers', () => ({
  listServers: vi.fn(),
  startServer: vi.fn(),
  stopServer: vi.fn(),
  restartServer: vi.fn(),
  getServer: vi.fn(),
  serverKeys: { all: ['servers'], detail: (id: string) => ['server', id] },
}))

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => undefined,
}))

function envelope(event: string, overrides: Partial<WsEnvelope> = {}): WsEnvelope {
  return {
    event,
    server_id: 'srv-1',
    scope: 'server',
    payload: { name: 'Steve' },
    ts: new Date().toISOString(),
    seq: 1,
    ...overrides,
  }
}

function renderBell() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  vi.mocked(listServers).mockResolvedValue([])
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <NotificationsBell />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('NotificationsBell', () => {
  afterEach(() => {
    vi.clearAllMocks()
    useNotificationsStore.setState({ items: [], lastSeq: 0 })
  })

  it('muestra badge con el número de no leídos', () => {
    useNotificationsStore.getState().push(envelope('SERVER.STARTED'))
    useNotificationsStore.getState().push(envelope('PLAYER.JOINED', { seq: 2 }))
    renderBell()
    expect(screen.getByTestId('notifications-badge')).toHaveTextContent('2')
  })

  it('sin notificaciones no muestra badge', () => {
    renderBell()
    expect(screen.queryByTestId('notifications-badge')).not.toBeInTheDocument()
  })

  it('al abrir el dropdown se marcan todas como leídas y el badge desaparece', async () => {
    const user = userEvent.setup()
    useNotificationsStore.getState().push(envelope('SERVER.CRASHED'))
    renderBell()

    expect(screen.getByTestId('notifications-badge')).toHaveTextContent('1')
    await user.click(screen.getByTestId('notifications-bell'))

    await waitFor(() => {
      expect(screen.getAllByTestId('notification-item')).toHaveLength(1)
      expect(screen.queryByTestId('notifications-badge')).not.toBeInTheDocument()
    })
    expect(useNotificationsStore.getState().items[0]?.read).toBe(true)
  })

  it('no duplica eventos re-emitidos con el mismo seq (resume)', () => {
    const { push } = useNotificationsStore.getState()
    push(envelope('SERVER.STARTED', { seq: 5 }))
    push(envelope('SERVER.STARTED', { seq: 5 })) // resume re-emite el mismo seq
    expect(useNotificationsStore.getState().items).toHaveLength(1)
  })

  it('mantiene el orden más reciente primero (seq descendente)', () => {
    const { push } = useNotificationsStore.getState()
    push(envelope('SERVER.STARTED', { seq: 1 }))
    push(envelope('PLAYER.JOINED', { seq: 2 }))
    const items = useNotificationsStore.getState().items
    expect(items[0]?.event).toBe('PLAYER.JOINED')
    expect(items[1]?.event).toBe('SERVER.STARTED')
  })
})
