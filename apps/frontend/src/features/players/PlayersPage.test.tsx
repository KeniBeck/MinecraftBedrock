import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError } from 'axios'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { PlayersPage } from '@/features/players/PlayersPage'
import {
  banPlayerGlobally,
  banPlayerOnServer,
  kickPlayer,
  listGlobalBans,
  listServerBans,
  onlinePlayers,
  searchPlayer,
  unbanPlayerGlobally,
  unbanPlayerOnServer,
  type PlaySessionResponse,
} from '@/lib/api/players'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/players', () => ({
  playerKeys: {
    all: (serverId: string) => ['players', serverId],
    online: (serverId: string) => ['players', serverId, 'online'],
    detail: (serverId: string, xuid: string) => ['players', serverId, xuid],
    sessions: (serverId: string, xuid: string) => ['players', serverId, xuid, 'sessions'],
    search: (serverId: string, name: string) => ['players', serverId, 'search', name],
    serverBans: (serverId: string) => ['players', serverId, 'bans'],
    globalBans: () => ['players', 'global', 'bans'],
  },
  onlinePlayers: vi.fn(),
  searchPlayer: vi.fn(),
  getPlayer: vi.fn(),
  playerSessions: vi.fn(),
  listGlobalBans: vi.fn(),
  listServerBans: vi.fn(),
  banPlayerGlobally: vi.fn(),
  unbanPlayerGlobally: vi.fn(),
  banPlayerOnServer: vi.fn(),
  unbanPlayerOnServer: vi.fn(),
  kickPlayer: vi.fn(),
}))

const SESSION: PlaySessionResponse = {
  id: 's-1',
  server_id: 'srv-1',
  xuid: '2535462000000000',
  joined_at: '2026-01-01T12:00:00Z',
  left_at: null,
  reason: null,
  playtime_seconds: 3600,
}

/** AxiosError real con la forma del error del backend (para getApiCode). */
function apiError(code: string): AxiosError {
  return new AxiosError(
    'Request failed',
    undefined,
    undefined,
    undefined,
    {
      status: 404,
      statusText: 'Not Found',
      headers: {},
      config: {} as never,
      data: { detail: { code, message: 'no encontrado' } },
    },
  )
}

function renderPage(roles: string[] = ['admin']) {
  useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles } })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/servers/srv-1/players']}>
          <Routes>
            <Route path="/servers/:serverId/players" element={<PlayersPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('PlayersPage', () => {
  beforeEach(() => {
    vi.mocked(listGlobalBans).mockResolvedValue([])
    vi.mocked(listServerBans).mockResolvedValue([])
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('muestra los jugadores online con su XUID', async () => {
    vi.mocked(onlinePlayers).mockResolvedValue([SESSION])

    renderPage()

    expect(await screen.findByText('2535462000000000')).toBeInTheDocument()
    expect(screen.getAllByText(/en línea/i).length).toBeGreaterThan(0)
  })

  it('muestra estado vacío cuando no hay jugadores', async () => {
    vi.mocked(onlinePlayers).mockResolvedValue([])

    renderPage()

    expect(await screen.findByText(/no hay jugadores conectados/i)).toBeInTheDocument()
  })

  it('resuelve un gamertag a XUID con el buscador', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(searchPlayer).mockResolvedValue([
      {
        server_id: 'srv-1',
        name: 'Notch',
        xuid: '2535462000000000',
      },
    ])

    renderPage()
    await screen.findByText(/no hay jugadores conectados/i)

    await user.type(screen.getByLabelText(/buscar jugador por gamertag/i), 'Notch')

    expect(await screen.findByText(/xuid: 2535462000000000/i)).toBeInTheDocument()
  })

  it('busca por coincidencia parcial (lista de resultados)', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(searchPlayer).mockResolvedValue([
      { server_id: 'srv-1', name: 'CrafterTec', xuid: '2535462000000001' },
      { server_id: 'srv-1', name: 'Crazy', xuid: '2535462000000002' },
    ])

    renderPage()
    await screen.findByText(/no hay jugadores conectados/i)

    await user.type(screen.getByLabelText(/buscar jugador por gamertag/i), 'Cra')

    expect(await screen.findByText('CrafterTec')).toBeInTheDocument()
    expect(await screen.findByText('Crazy')).toBeInTheDocument()
  })

  it('muestra mensaje cuando no hay coincidencias de búsqueda', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(searchPlayer).mockResolvedValue([])

    renderPage()
    await screen.findByText(/no hay jugadores conectados/i)

    await user.type(screen.getByLabelText(/buscar jugador por gamertag/i), 'zzz')

    expect(await screen.findByText(/sin coincidencias para "zzz"/i)).toBeInTheDocument()
  })

  it('muestra mensaje cuando el gamertag no está en la caché', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(searchPlayer).mockRejectedValue(apiError('PLAYER.NOT_FOUND'))

    renderPage()
    await screen.findByText(/no hay jugadores conectados/i)

    await user.type(screen.getByLabelText(/buscar jugador por gamertag/i), 'zzz')

    expect(await screen.findByText(/no se encontró "zzz"/i)).toBeInTheDocument()
  })

  it('expulsa a un jugador online tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([SESSION])
    vi.mocked(kickPlayer).mockResolvedValue({
      server_id: 'srv-1',
      command: 'kick 2535462000000000',
      priority: 'normal',
      seq: 1,
      at: '2026-01-01T12:00:00Z',
    })

    renderPage()
    await screen.findByText('2535462000000000')

    await user.click(screen.getByRole('button', { name: /^kick$/i }))
    await user.click(await screen.findByRole('button', { name: /^expulsar$/i }))

    await waitFor(() => {
      expect(kickPlayer).toHaveBeenCalledWith('srv-1', '2535462000000000')
    })
  })

  it('banea a un jugador por servidor con motivo', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([SESSION])
    vi.mocked(banPlayerOnServer).mockResolvedValue(undefined)

    renderPage()
    await screen.findByText('2535462000000000')

    await user.click(screen.getByRole('button', { name: /^ban$/i }))
    await user.type(screen.getByLabelText(/^motivo/i), 'Griefing')
    await user.click(await screen.findByRole('button', { name: /^banear$/i }))

    await waitFor(() => {
      expect(banPlayerOnServer).toHaveBeenCalledWith('srv-1', '2535462000000000', {
        reason: 'Griefing',
      })
    })
  })

  it('lista los jugadores baneados con opción de desbanear', async () => {
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(listGlobalBans).mockResolvedValue([
      {
        id: 'g-1',
        scope: 'global',
        gamertag: 'Toxic',
        xuid: null,
        reason: 'Tóxico',
        banned_by: 'u1',
        created_at: '2026-01-01T00:00:00Z',
        expires_at: null,
      },
    ])
    vi.mocked(listServerBans).mockResolvedValue([
      {
        id: 's-1',
        scope: 'server',
        server_id: 'srv-1',
        gamertag: 'Griefer',
        xuid: '2535462000000009',
        reason: 'Griefing',
        banned_by: 'u1',
        created_at: '2026-01-02T00:00:00Z',
        expires_at: null,
      },
    ])

    renderPage()
    await screen.findByText(/no hay jugadores conectados/i)

    expect(await screen.findByText('Toxic')).toBeInTheDocument()
    expect(await screen.findByText('Griefer')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^desbanear$/i }).length).toBe(2)
  })

  it('desbanea a un jugador baneado en el servidor tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(listServerBans).mockResolvedValue([
      {
        id: 's-1',
        scope: 'server',
        server_id: 'srv-1',
        gamertag: 'Griefer',
        xuid: '2535462000000009',
        reason: 'Griefing',
        banned_by: 'u1',
        created_at: '2026-01-02T00:00:00Z',
        expires_at: null,
      },
    ])

    renderPage()
    await screen.findByText(/no hay jugadores conectados/i)

    await user.click(await screen.findByRole('button', { name: /^desbanear$/i }))
    await user.click(await screen.findByRole('button', { name: /^desbanear$/i }))

    await waitFor(() => {
      expect(unbanPlayerOnServer).toHaveBeenCalledWith('srv-1', '2535462000000009')
    })
  })

  it('desbanea a un jugador baneado globalmente tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(listGlobalBans).mockResolvedValue([
      {
        id: 'g-1',
        scope: 'global',
        gamertag: 'Toxic',
        xuid: null,
        reason: 'Tóxico',
        banned_by: 'u1',
        created_at: '2026-01-01T00:00:00Z',
        expires_at: null,
      },
    ])

    renderPage()
    await screen.findByText(/no hay jugadores conectados/i)

    await user.click(await screen.findByRole('button', { name: /^desbanear$/i }))
    await user.click(await screen.findByRole('button', { name: /^desbanear$/i }))

    await waitFor(() => {
      expect(unbanPlayerGlobally).toHaveBeenCalledWith('g-1')
    })
  })

  it('ofrece desbanear a un jugador baneado en los resultados de búsqueda', async () => {
    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(listServerBans).mockResolvedValue([
      {
        id: 's-1',
        scope: 'server',
        server_id: 'srv-1',
        gamertag: 'CrafterTec',
        xuid: '2535462000000001',
        reason: null,
        banned_by: 'u1',
        created_at: '2026-01-02T00:00:00Z',
        expires_at: null,
      },
    ])
    vi.mocked(searchPlayer).mockResolvedValue([
      { server_id: 'srv-1', name: 'CrafterTec', xuid: '2535462000000001' },
    ])

    renderPage()
    await screen.findByText(/no hay jugadores conectados/i)

    await user.type(screen.getByLabelText(/buscar jugador por gamertag/i), 'Cra')

    const unbanButtons = await screen.findAllByRole('button', { name: /^desbanear$/i })
    expect(unbanButtons.length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /^ban$/i })).not.toBeInTheDocument()
  })

  it('aplica un ban global solo con admin', async () => {    const user = userEvent.setup()
    vi.mocked(onlinePlayers).mockResolvedValue([])
    vi.mocked(banPlayerGlobally).mockResolvedValue({
      id: 'g-1',
      scope: 'global',
      gamertag: 'Toxic',
      xuid: null,
      reason: 'Tóxico',
      banned_by: 'u1',
      created_at: '2026-01-01T00:00:00Z',
      expires_at: null,
    })

    renderPage(['admin'])
    await screen.findByText(/no hay jugadores conectados/i)

    await user.click(screen.getByRole('button', { name: /ban global/i }))
    await user.type(screen.getByLabelText(/^gamertag$/i), 'Toxic')
    await user.click(await screen.findByRole('button', { name: /^banear$/i }))

    await waitFor(() => {
      expect(banPlayerGlobally).toHaveBeenCalledWith(
        expect.objectContaining({ gamertag: 'Toxic' }),
      )
    })
  })

  it('oculta el botón de ban global a un viewer', async () => {
    vi.mocked(onlinePlayers).mockResolvedValue([])

    renderPage(['viewer'])
    await screen.findByText(/no hay jugadores conectados/i)

    expect(screen.queryByRole('button', { name: /ban global/i })).not.toBeInTheDocument()
  })
})
