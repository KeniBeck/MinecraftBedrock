import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { MetricsChart } from './MetricsChart'
import type { MetricSample } from '@/stores/monitoring'

function sample(ts: string, overrides: Partial<MetricSample> = {}): MetricSample {
  return {
    ts,
    state: 'running',
    status: 'online',
    latency_ms: 1,
    players: 1,
    players_max: 10,
    cpu: 5,
    ram_mb: 512,
    disk_mb: 2048,
    ...overrides,
  }
}

const DATA = [
  sample('2026-08-12T11:59:00Z'),
  sample('2026-08-12T12:00:00Z', { cpu: 12.5, players: 3 }),
]

// ResponsiveContainer en jsdom no mide tamaño; se rellena a una altura fija.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 600, height: 320 }}>{children}</div>
    ),
  }
})

describe('MetricsChart', () => {
  it('muestra espera cuando no hay datos', () => {
    render(<MetricsChart data={[]} />)
    expect(screen.getByText(/esperando datos del servidor/i)).toBeInTheDocument()
  })

  it('muestra los toggles de series', () => {
    render(<MetricsChart data={DATA} />)
    for (const label of ['CPU', 'RAM', 'Jugadores', 'Disco']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
  })

  it('oculta una serie al hacer clic en su toggle', async () => {
    const user = userEvent.setup()
    render(<MetricsChart data={DATA} />)

    const cpuToggle = screen.getByRole('button', { name: 'CPU' })
    expect(cpuToggle).toHaveAttribute('aria-pressed', 'true')
    await user.click(cpuToggle)
    expect(cpuToggle).toHaveAttribute('aria-pressed', 'false')
  })
})
