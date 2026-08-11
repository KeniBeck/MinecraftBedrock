import { StrictMode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { WorldsPage } from '@/features/worlds/WorldsPage'
import { listWorlds, syncWorlds, type World } from '@/lib/api/worlds'

vi.mock('@/lib/api/worlds', () => ({
  worldKeys: {
    all: (serverId: string) => ['worlds', serverId],
    detail: (serverId: string, name: string) => ['worlds', serverId, name],
  },
  listWorlds: vi.fn(),
  syncWorlds: vi.fn(),
  activateWorld: vi.fn(),
  createWorld: vi.fn(),
  deleteWorld: vi.fn(),
  duplicateWorld: vi.fn(),
  exportWorld: vi.fn(),
  importWorld: vi.fn(),
  updateWorld: vi.fn(),
}))

const WORLD: World = {
  id: 'w-1',
  server_id: 'srv-1',
  name: 'Bedrock level',
  level_name: 'Bedrock level',
  activated: true,
  size_bytes: 100,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  seed: '-299205636354301287',
  gamemode: 'survival',
  difficulty: 'easy',
  view_distance: 32,
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/servers/srv-1/worlds']}>
          <Routes>
            <Route path="/servers/:serverId/worlds" element={<WorldsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('WorldsPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('sincroniza una sola vez (StrictMode) y muestra los mundos sin listWorlds', async () => {
    vi.mocked(syncWorlds).mockResolvedValue([WORLD])
    vi.mocked(listWorlds).mockResolvedValue([WORLD])

    renderPage()

    await waitFor(() => {
      expect(syncWorlds).toHaveBeenCalledTimes(1)
    })
    expect(listWorlds).not.toHaveBeenCalled()
    expect(await screen.findByText('Bedrock level')).toBeInTheDocument()
  })

  it('si el sync falla, carga la metadata existente', async () => {
    vi.mocked(syncWorlds).mockRejectedValue(new Error('sync down'))
    vi.mocked(listWorlds).mockResolvedValue([WORLD])

    renderPage()

    await waitFor(() => {
      expect(syncWorlds).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(listWorlds).toHaveBeenCalledTimes(1)
    })
    expect(await screen.findByText('Bedrock level')).toBeInTheDocument()
  })

  it('el botón Sincronizar vuelve a sincronizar', async () => {
    const user = userEvent.setup()
    vi.mocked(syncWorlds).mockResolvedValue([WORLD])
    vi.mocked(listWorlds).mockResolvedValue([WORLD])

    renderPage()
    await screen.findByText('Bedrock level')

    await user.click(screen.getByRole('button', { name: /sincronizar/i }))

    await waitFor(() => {
      expect(syncWorlds).toHaveBeenCalledTimes(2)
    })
  })
})
