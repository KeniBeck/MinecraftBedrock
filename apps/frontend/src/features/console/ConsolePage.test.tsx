import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ConsolePage } from '@/features/console/ConsolePage'
import { useConsole } from '@/features/console/hooks'
import { useServer } from '@/features/servers/hooks'
import type { Server } from '@/lib/api/servers'

vi.mock('@/features/servers/hooks', () => ({
  useServer: vi.fn(),
}))

vi.mock('@/features/console/hooks', () => ({
  useConsole: vi.fn(),
  useSendCommand: vi.fn(() => ({ isPending: false, mutateAsync: vi.fn() })),
  toConsoleLine: vi.fn(),
}))

const SERVER: Server = {
  id: 'srv-1',
  name: 'Survival',
  state: 'running',
  version: '1.21.1',
  image_ref: 'img:latest',
  runtime_id: 'r1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  connection: { host: 'localhost', port: 19132, port_v6: 19133, rcon_port: 25575, address: 'localhost:19132' },
}

type QueryResult = ReturnType<typeof useServer>

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/servers/srv-1/console']}>
      <Routes>
        <Route path="/servers/:serverId/console" element={<ConsolePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ConsolePage', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('muestra el terminal cuando el servidor carga', async () => {
    vi.mocked(useServer).mockReturnValue({ data: SERVER, isLoading: false, isError: false, error: null } as QueryResult)
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Consola en vivo')).toBeInTheDocument()
    })
    expect(useConsole).toHaveBeenCalledWith('srv-1')
  })

  it('muestra el loader mientras carga', () => {
    vi.mocked(useServer).mockReturnValue({ data: undefined, isLoading: true, isError: false, error: null } as QueryResult)
    renderPage()
    expect(screen.getByTestId('console-loading')).toBeInTheDocument()
  })

  it('muestra el mensaje de error si falla la carga', async () => {
    vi.mocked(useServer).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('boom'),
    } as QueryResult)
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('boom')
  })
})
