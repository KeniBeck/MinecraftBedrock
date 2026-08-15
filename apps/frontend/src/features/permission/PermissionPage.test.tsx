import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { PermissionPage } from '@/features/permission/PermissionPage'
import {
  addAllowlistEntry,
  getOperators,
  listAllowlist,
  removeAllowlistEntry,
  removeOperator,
  setAllowlistEnabled,
  setOperatorLevel,
  type AllowlistEntry,
  type OperatorEntry,
} from '@/lib/api/permissions'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/permissions', () => ({
  permissionKeys: {
    all: (serverId: string) => ['permissions', serverId],
    allowlist: (serverId: string) => ['permissions', serverId, 'allowlist'],
  },
  operatorKeys: {
    all: (serverId: string) => ['permissions', serverId, 'operators'],
  },
  listAllowlist: vi.fn(),
  addAllowlistEntry: vi.fn(),
  removeAllowlistEntry: vi.fn(),
  setAllowlistEnabled: vi.fn(),
  getOperators: vi.fn(),
  setOperatorLevel: vi.fn(),
  removeOperator: vi.fn(),
}))

const ENTRY: AllowlistEntry = {
  name: 'Steve',
  xuid: '2535461234567890',
  ignores_player_limit: false,
}

const OPERATOR: OperatorEntry = { xuid: '9990001112223333', level: 'operator' }

function renderPage(roles: string[] = ['admin']) {
  useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles } })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/servers/srv-1/permissions']}>
          <Routes>
            <Route path="/servers/:serverId/permissions" element={<PermissionPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('PermissionPage', () => {
  beforeEach(() => {
    vi.mocked(getOperators).mockResolvedValue([])
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('muestra la allowlist listada', async () => {
    vi.mocked(listAllowlist).mockResolvedValue([ENTRY])

    renderPage()

    expect(await screen.findByText('Steve')).toBeInTheDocument()
    expect(screen.getByText('2535461234567890')).toBeInTheDocument()
  })

  it('muestra el estado vacío de la allowlist', async () => {
    vi.mocked(listAllowlist).mockResolvedValue([])

    renderPage()

    expect(await screen.findByText(/La allowlist está vacía/)).toBeInTheDocument()
  })

  it('añade una entrada a la allowlist', async () => {
    const user = userEvent.setup()
    vi.mocked(listAllowlist).mockResolvedValue([])
    vi.mocked(addAllowlistEntry).mockResolvedValue(ENTRY)

    renderPage()
    await screen.findByText(/La allowlist está vacía/)

    await user.click(screen.getByRole('button', { name: 'Añadir' }))
    await user.type(screen.getByLabelText(/gamertag/i), 'Steve')
    await user.type(screen.getByLabelText(/xuid/i), '2535461234567890')
    await user.click(await screen.findByTestId('add-allowlist-submit'))

    await waitFor(() => {
      expect(addAllowlistEntry).toHaveBeenCalledWith('srv-1', {
        name: 'Steve',
        xuid: '2535461234567890',
      })
    })
  })

  it('quita una entrada de la allowlist tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(listAllowlist).mockResolvedValue([ENTRY])
    vi.mocked(removeAllowlistEntry).mockResolvedValue(undefined)

    renderPage()
    await screen.findByText('Steve')

    await user.click(screen.getByRole('button', { name: '' }))
    await user.click(await screen.findByRole('button', { name: /^quitar$/i }))

    await waitFor(() => {
      expect(removeAllowlistEntry).toHaveBeenCalledWith('srv-1', '2535461234567890')
    })
  })

  it('alterna la allowlist activada y llama al backend', async () => {
    const user = userEvent.setup()
    vi.mocked(listAllowlist).mockResolvedValue([])
    vi.mocked(setAllowlistEnabled).mockResolvedValue(undefined)

    renderPage()
    await screen.findByText(/La allowlist está vacía/)

    const toggle = screen.getByRole('button', { name: /desactivada/i })
    await user.click(toggle)

    await waitFor(() => {
      expect(setAllowlistEnabled).toHaveBeenCalledWith('srv-1', true)
    })
    expect(screen.getByRole('button', { name: /activada/i })).toBeInTheDocument()
  })

  it('añade un operador y lo muestra en la tabla', async () => {
    const user = userEvent.setup()
    vi.mocked(listAllowlist).mockResolvedValue([])
    vi.mocked(getOperators).mockResolvedValue([OPERATOR])
    vi.mocked(setOperatorLevel).mockResolvedValue(OPERATOR)

    renderPage()
    await screen.findByText(/La allowlist está vacía/)

    await user.click(screen.getByRole('button', { name: /añadir operador/i }))
    await user.type(screen.getByLabelText(/xuid/i), '9990001112223333')
    await user.click(await screen.findByTestId('add-operator-submit'))

    await waitFor(() => {
      expect(setOperatorLevel).toHaveBeenCalledWith('srv-1', '9990001112223333', 'operator')
    })
    expect(await screen.findByText('9990001112223333')).toBeInTheDocument()
    expect(screen.getByText('operator')).toBeInTheDocument()
  })

  it('quita un operador tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(listAllowlist).mockResolvedValue([])
    vi.mocked(getOperators).mockResolvedValue([OPERATOR])
    vi.mocked(removeOperator).mockResolvedValue(undefined)

    renderPage()
    await screen.findByText('9990001112223333')

    await user.click(screen.getByRole('button', { name: '' }))
    await user.click(await screen.findByRole('button', { name: /^quitar$/i }))

    await waitFor(() => {
      expect(removeOperator).toHaveBeenCalledWith('srv-1', '9990001112223333')
    })
  })

  it('oculta las acciones de escritura a un viewer', async () => {
    vi.mocked(listAllowlist).mockResolvedValue([ENTRY])

    renderPage(['viewer'])
    await screen.findByText('Steve')

    expect(screen.queryByRole('button', { name: /añadir/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /añadir operador/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/allowlist activada/i)).not.toBeInTheDocument()
  })

  it('niega el acceso a quien no puede leer', async () => {
    renderPage([])
    expect(await screen.findByRole('alert')).toHaveTextContent(/no tienes permisos/i)
  })
})