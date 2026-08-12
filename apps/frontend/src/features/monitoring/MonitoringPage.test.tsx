import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { MonitoringPage } from './MonitoringPage'
import { useMonitoringStore, type MonitoringSnapshot } from '@/stores/monitoring'

vi.mock('@/hooks/useServerMonitoring', () => ({
  useServerMonitoring: vi.fn(),
}))

vi.mock('@/lib/api/servers', () => ({
  getServer: vi.fn(),
  listServers: vi.fn(),
  serverKeys: { all: ['servers'], detail: (id: string) => ['server', id] },
}))

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 600, height: 320 }}>{children}</div>
    ),
  }
})

function snapshot(overrides: Partial<MonitoringSnapshot> = {}): MonitoringSnapshot {
  return {
    state: 'running',
    status: 'online',
    latency_ms: 1,
    players: 3,
    players_max: 10,
    cpu: 15.2,
    ram_mb: 2048,
    disk_mb: 4096,
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/servers/srv-1/monitoring']}>
        <Routes>
          <Route path="/servers/:serverId/monitoring" element={<MonitoringPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('MonitoringPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
    useMonitoringStore.getState().clear('srv-1')
  })

  it('muestra espera cuando no hay muestras', () => {
    renderPage()
    expect(screen.getByText(/conectando al monitoreo del servidor/i)).toBeInTheDocument()
  })

  it('muestra las métricas del snapshot en vivo', () => {
    useMonitoringStore.getState().setSnapshot('srv-1', snapshot())

    renderPage()

    expect(screen.getByText('online')).toBeInTheDocument()
    expect(screen.getByText('3 / 10')).toBeInTheDocument()
    expect(screen.getByText('15.2 %')).toBeInTheDocument()
    expect(screen.getByText('2048 MB')).toBeInTheDocument()
  })

  it('filtra el histórico por rango seleccionado', async () => {
    const user = userEvent.setup()
    const now = Date.now()
    // Una muestra hace 2h (fuera del rango 1h default) y otra reciente.
    useMonitoringStore.getState().setSnapshot(
      'srv-1',
      snapshot({ cpu: 1 }),
      new Date(now - 2 * 60 * 60 * 1000).toISOString(),
    )
    useMonitoringStore.getState().setSnapshot(
      'srv-1',
      snapshot({ cpu: 50 }),
      new Date(now - 10 * 1000).toISOString(),
    )

    renderPage()

    // Rango default 1h: solo la muestra reciente.
    expect(screen.getByText(/1 muestras/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '7d' }))

    expect(screen.getByText(/2 muestras/)).toBeInTheDocument()
  })

  it('muestra mensaje de rango sin datos cuando hay histórico pero fuera del rango', async () => {
    const user = userEvent.setup()
    const now = Date.now()
    useMonitoringStore.getState().setSnapshot(
      'srv-1',
      snapshot(),
      new Date(now - 2 * 60 * 60 * 1000).toISOString(),
    )

    renderPage()

    expect(screen.getByText(/no hay datos dentro de este rango todavía/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '6h' }))

    expect(screen.getByText(/1 muestras/)).toBeInTheDocument()
  })
})
