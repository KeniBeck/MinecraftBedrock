import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import { ServerDetailPage } from '@/features/servers/ServerDetailPage'
import { getServer, restartServer, startServer, stopServer, type Server } from '@/lib/api/servers'

vi.mock('@/lib/api/servers', () => ({
  getServer: vi.fn(),
  startServer: vi.fn(),
  stopServer: vi.fn(),
  restartServer: vi.fn(),
}))

// El sync por WS usa el store/WebSocketClient real; lo neutralizamos.
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => undefined,
}))

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

function renderPage(server = SERVER) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  vi.mocked(getServer).mockResolvedValue(server)
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/servers/srv-1']}>
        <Routes>
          <Route path="/servers/:serverId" element={<ServerDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ServerDetailPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('muestra la card del servidor con estado y metadata', async () => {
    renderPage()
    await waitFor(() => expect(screen.getAllByText('Survival').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Detenido').length).toBeGreaterThan(0)
    expect(screen.getAllByText('localhost:19132').length).toBeGreaterThan(0)
  })

  it('start está habilitado en stopped y llama al endpoint', async () => {
    const user = userEvent.setup()
    vi.mocked(startServer).mockResolvedValue({ ...SERVER, state: 'starting' })
    renderPage()

    await waitFor(() => expect(screen.getByTestId('start-button')).toBeEnabled())
    await user.click(screen.getByTestId('start-button'))

    await waitFor(() => {
      expect(startServer).toHaveBeenCalledWith('srv-1')
    })
  })

  it('stop está deshabilitado en stopped', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByTestId('stop-button')).toBeDisabled())
  })

  it('en running, stop y restart están habilitados y start deshabilitado', async () => {
    const user = userEvent.setup()
    vi.mocked(stopServer).mockResolvedValue({ ...SERVER, state: 'stopping' })
    renderPage({ ...SERVER, state: 'running' })

    await waitFor(() => expect(screen.getByTestId('stop-button')).toBeEnabled())
    expect(screen.getByTestId('restart-button')).toBeEnabled()
    expect(screen.getByTestId('start-button')).toBeDisabled()

    await user.click(screen.getByTestId('stop-button'))
    await waitFor(() => {
      expect(stopServer).toHaveBeenCalledWith('srv-1', 30)
    })
  })

  it('muestra detail.message si start falla con 403', async () => {
    const user = userEvent.setup()
    const { AxiosError, AxiosHeaders } = await import('axios')
    vi.mocked(startServer).mockRejectedValue(
      new AxiosError('forbidden', '403', undefined, undefined, {
        status: 403,
        statusText: 'forbidden',
        data: { detail: { code: 'AUTH.FORBIDDEN', message: 'No autorizado para server.start' } },
        headers: {},
        config: { headers: new AxiosHeaders() },
      }),
    )
    renderPage()

    await waitFor(() => expect(screen.getByTestId('start-button')).toBeEnabled())
    await user.click(screen.getByTestId('start-button'))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('No autorizado para server.start')
    })
    expect(restartServer).not.toHaveBeenCalled()
  })
})
