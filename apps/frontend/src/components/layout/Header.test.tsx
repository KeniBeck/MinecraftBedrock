import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

import { Header } from '@/components/layout/Header'
import { listServers, type Server } from '@/lib/api/servers'
import { useActiveServer } from '@/stores/servers'
import { useMonitoringStore } from '@/stores/monitoring'
import { useAuthStore } from '@/stores/auth'

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

function renderHeader(route = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Header />
        <Routes>
          <Route path="/servers/:serverId" element={<div data-testid="detail-page" />} />
          <Route path="/servers/:serverId/console" element={<div data-testid="console-page" />} />
          <Route path="/servers/:serverId/monitoring" element={<div data-testid="monitoring-page" />} />
          <Route path="/profile" element={<div data-testid="profile-page" />} />
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
    useAuthStore.setState({ identity: null })
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

  it('conserva la subpágina al cambiar de servidor desde una ruta hija', async () => {
    const user = userEvent.setup()
    vi.mocked(listServers).mockResolvedValue([
      makeServer('s1', 'Survival', 'running'),
      makeServer('s2', 'Skyblock', 'stopped'),
    ])
    useActiveServer.getState().setActiveServer('s1')

    renderHeader('/servers/s1/monitoring')
    await waitFor(() => expect(screen.getByTestId('server-selector')).toBeInTheDocument())
    expect(screen.getByTestId('monitoring-page')).toBeInTheDocument()

    await user.click(screen.getByTestId('server-selector'))
    await waitFor(() => expect(screen.getByTestId('server-option-s2')).toBeInTheDocument())
    await user.click(screen.getByTestId('server-option-s2'))

    expect(useActiveServer.getState().activeServerId).toBe('s2')
    // Sigue en la misma subpágina, con el id del nuevo servidor.
    expect(screen.getByTestId('monitoring-page')).toBeInTheDocument()
    expect(screen.queryByTestId('detail-page')).not.toBeInTheDocument()
  })

  it('en una página que no es de servidor solo cambia el activo, sin navegar', async () => {
    const user = userEvent.setup()
    vi.mocked(listServers).mockResolvedValue([
      makeServer('s1', 'Survival', 'running'),
      makeServer('s2', 'Skyblock', 'stopped'),
    ])
    useActiveServer.getState().setActiveServer('s1')

    // La raíz (dashboard) no es una ruta de servidor.
    renderHeader('/')
    await waitFor(() => expect(screen.getByTestId('server-selector')).toBeInTheDocument())

    await user.click(screen.getByTestId('server-selector'))
    await waitFor(() => expect(screen.getByTestId('server-option-s2')).toBeInTheDocument())
    await user.click(screen.getByTestId('server-option-s2'))

    expect(useActiveServer.getState().activeServerId).toBe('s2')
    // No navega al detalle: no aparece la página de detalle.
    expect(screen.queryByTestId('detail-page')).not.toBeInTheDocument()
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

describe('Header — menú de perfil (avatar)', () => {
  afterEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({ identity: null })
  })

  it('ofrece "Mi perfil" que navega a /profile', async () => {
    const user = userEvent.setup()
    useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles: ['admin'] } })

    renderHeader('/')
    await waitFor(() => expect(screen.getByTestId('profile-menu')).toBeInTheDocument())

    await user.click(screen.getByTestId('profile-menu'))
    await waitFor(() => expect(screen.getByTestId('profile-item')).toBeInTheDocument())
    await user.click(screen.getByTestId('profile-item'))

    expect(screen.getByTestId('profile-page')).toBeInTheDocument()
  })
})

describe('Header — botón "Crear servidor"', () => {
  afterEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({ identity: null })
  })

  it('aparece solo en el detalle exacto /servers/:id', async () => {
    useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles: ['admin'] } })
    renderHeader('/servers/s1')
    expect(screen.getByTestId('create-server-button')).toBeInTheDocument()
  })

  it('no aparece en /servers/:id/console ni en la raíz', async () => {
    useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles: ['admin'] } })

    renderHeader('/servers/s1/console')
    expect(screen.queryByTestId('create-server-button')).not.toBeInTheDocument()

    renderHeader('/')
    expect(screen.queryByTestId('create-server-button')).not.toBeInTheDocument()
  })
})
