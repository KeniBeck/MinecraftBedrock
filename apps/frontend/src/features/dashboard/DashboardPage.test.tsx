import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { listServers, type Server } from '@/lib/api/servers'
import { useNotificationsStore } from '@/stores/notifications'

vi.mock('@/lib/api/servers', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/servers')>()
  return { ...actual, listServers: vi.fn() }
})

function makeServer(overrides: Partial<Server> & { id: string; name: string }): Server {
  return {
    state: 'running',
    version: '1.21.1',
    image_ref: 'mc:latest',
    runtime_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    connection: { host: 'localhost', port: 19132, port_v6: 0, rcon_port: null, address: 'localhost:19132' },
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  useNotificationsStore.setState({ items: [], lastSeq: 0 })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.mocked(listServers).mockResolvedValue([])
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
    useNotificationsStore.setState({ items: [], lastSeq: 0 })
  })

  it('muestra las cards de resumen y el título', async () => {
    vi.mocked(listServers).mockResolvedValue([
      makeServer({ id: 's1', name: 'Sobrevivencia', state: 'running' }),
      makeServer({ id: 's2', name: 'Creador', state: 'stopped' }),
    ])
    renderPage()

    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
    expect(screen.getAllByText('Servidores').length).toBeGreaterThan(0)
    expect(screen.getByText('En línea')).toBeInTheDocument()
  })

  it('calcula total, online y offline a partir de la lista', async () => {
    vi.mocked(listServers).mockResolvedValue([
      makeServer({ id: 's1', name: 'A', state: 'running' }),
      makeServer({ id: 's2', name: 'B', state: 'starting' }),
      makeServer({ id: 's3', name: 'C', state: 'stopped' }),
    ])
    renderPage()

    await screen.findByText('C')
    expect(screen.getByText('2 / 3')).toBeInTheDocument()
    expect(screen.getByText(/1 detenido/)).toBeInTheDocument()
    expect(screen.getAllByText(/En línea/).length).toBeGreaterThan(0)
  })

  it('no expone jugadores: muestra "—"', async () => {
    renderPage()
    await screen.findAllByText('Jugadores')
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText(/No expuesto por GET \/servers/)).toBeInTheDocument()
  })

  it('lista los servidores como tabla con estado y versión', async () => {
    vi.mocked(listServers).mockResolvedValue([
      makeServer({ id: 's1', name: 'Sobrevivencia', state: 'running', version: '1.21.1' }),
    ])
    renderPage()

    const link = await screen.findByTestId('dashboard-server-Sobrevivencia')
    expect(link).toHaveAttribute('href', '/servers/s1')
    expect(screen.getByText('1.21.1')).toBeInTheDocument()
  })

  it('muestra accesos rápidos a las páginas principales', async () => {
    vi.mocked(listServers).mockResolvedValue([
      makeServer({ id: 's1', name: 'Sobrevivencia', state: 'running' }),
    ])
    renderPage()

    // Esperar a que la lista de servidores esté disponible (la query resuelve
    // de forma asíncrona) antes de validar los accesos rápidos dependientes.
    await screen.findByTestId('dashboard-server-Sobrevivencia')

    expect(screen.getByTestId('quick-action-Servidores')).toHaveAttribute('href', '/servers')
    expect(screen.getByTestId('quick-action-Consola')).toHaveAttribute('href', '/servers/s1/console')
  })

  it('muestra el feed de eventos recientes', async () => {
    renderPage()
    // Poblar el feed tras el render (re-render disparado por el store selector).
    useNotificationsStore.setState({
      items: [
        {
          key: '1-SERVER.STARTED-s1',
          event: 'SERVER.STARTED',
          serverId: 's1',
          payload: { name: 'Sobrevivencia' },
          ts: new Date().toISOString(),
          read: false,
        },
      ],
      lastSeq: 1,
    })

    expect(await screen.findByText(/Servidor en línea: Sobrevivencia/)).toBeInTheDocument()
    expect(screen.getByTestId('recent-event')).toBeInTheDocument()
  })
})