import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import { Header } from '@/components/layout/Header'
import { listServers, type Server } from '@/lib/api/servers'
import { useActiveServer } from '@/stores/servers'
import { useMonitoringStore } from '@/stores/monitoring'

vi.mock('@/lib/api/servers', () => ({
  listServers: vi.fn(),
  startServer: vi.fn(),
  stopServer: vi.fn(),
  restartServer: vi.fn(),
  getServer: vi.fn(),
  serverKeys: { all: ['servers'], detail: (id: string) => ['server', id] },
}))

function makeServer(id: string, name: string, state: Server['state']): Server {
  return {
    id,
    name,
    state,
    version: '1.21.1',
    image_ref: 'img:latest',
    runtime_id: `r-${id}`,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    connection: { host: 'localhost', port: 19132, port_v6: 19133, rcon_port: 25575, address: 'localhost:19132' },
  }
}

function renderHeader() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Header />
        <Routes>
          <Route path="/servers/:serverId" element={<div data-testid="detail-page" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Header — selector de servidor', () => {
  afterEach(() => {
    vi.clearAllMocks()
    useActiveServer.getState().setActiveServer(null)
    useMonitoringStore.getState().clear('s1')
  })

  it('muestra el servidor activo en la pastilla', async () => {
    vi.mocked(listServers).mockResolvedValue([makeServer('s1', 'Survival', 'running')])
    useActiveServer.getState().setActiveServer('s1')

    renderHeader()

    await waitFor(() => {
      expect(screen.getByTestId('server-selector')).toHaveTextContent('Survival')
    })
  })

  it('abre el dropdown y cambia de servidor activo al elegir otro', async () => {
    const user = userEvent.setup()
    vi.mocked(listServers).mockResolvedValue([
      makeServer('s1', 'Survival', 'running'),
      makeServer('s2', 'Skyblock', 'stopped'),
    ])
    useActiveServer.getState().setActiveServer('s1')

    renderHeader()
    await waitFor(() => expect(screen.getByTestId('server-selector')).toBeInTheDocument())

    await user.click(screen.getByTestId('server-selector'))
    await waitFor(() => expect(screen.getByTestId('server-option-s2')).toBeInTheDocument())
    await user.click(screen.getByTestId('server-option-s2'))

    expect(useActiveServer.getState().activeServerId).toBe('s2')
  })

  it('muestra el estado de cada servidor en el dropdown', async () => {
    const user = userEvent.setup()
    vi.mocked(listServers).mockResolvedValue([
      makeServer('s1', 'Survival', 'running'),
      makeServer('s2', 'Skyblock', 'stopped'),
    ])
    renderHeader()
    await waitFor(() => expect(screen.getByTestId('server-selector')).toBeInTheDocument())

    await user.click(screen.getByTestId('server-selector'))
    await waitFor(() => expect(screen.getByText('En línea')).toBeInTheDocument())
    expect(screen.getByText('Detenido')).toBeInTheDocument()
  })

  it('muestra los jugadores en vivo del WS de monitoreo del servidor activo', async () => {
    vi.mocked(listServers).mockResolvedValue([makeServer('s1', 'Survival', 'running')])
    useActiveServer.getState().setActiveServer('s1')
    useMonitoringStore.getState().setSnapshot('s1', {
      state: 'running',
      status: 'running',
      latency_ms: null,
      players: 7,
      players_max: 10,
      cpu: null,
      ram_mb: null,
      disk_mb: null,
    })

    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('7 / 10 jugadores')).toBeInTheDocument()
    })
  })
})
