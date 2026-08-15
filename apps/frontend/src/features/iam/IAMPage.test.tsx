import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { IAMPage } from '@/features/iam/IAMPage'
import {
  createApiKey,
  createUser,
  deleteUser,
  listApiKeys,
  listAuditLogs,
  listUsers,
  revokeApiKey,
  updateUser,
  type ApiKey,
  type User,
} from '@/lib/api/iam'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/iam', () => ({
  apiKeyKeys: { all: ['iam', 'api-keys'] },
  userKeys: { all: ['users'], detail: (id: string) => ['users', id] },
  roleKeys: { all: ['iam', 'roles'] },
  auditKeys: { all: ['iam', 'audit'], verify: ['iam', 'audit', 'verify'] },
  listApiKeys: vi.fn(),
  createApiKey: vi.fn(),
  createUser: vi.fn(),
  assignRole: vi.fn(),
  revokeApiKey: vi.fn(),
  regenerateApiKey: vi.fn(),
  verifyAuditChain: vi.fn(),
  listUsers: vi.fn(),
  listRoles: vi.fn(),
  listAuditLogs: vi.fn(),
  updateUser: vi.fn(),
  deleteUser: vi.fn(),
}))

const KEY: ApiKey = {
  id: 'key-1',
  name: 'CI',
  scopes: ['server.list', 'server.status'],
  created_at: '2026-08-14T10:00:00Z',
  last_used_at: null,
  expires_at: null,
}

const USER: User = {
  id: 'u1',
  username: 'mike',
  display_name: '',
  status: 'active',
  roles: ['viewer'],
  created_at: null,
  last_login_at: null,
  email: null,
  avatar: null,
}

function renderPage(roles: string[] = ['admin']) {
  useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles } })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/admin/iam']}>
          <Routes>
            <Route path="/admin/iam" element={<IAMPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('IAMPage', () => {
  beforeEach(() => {
    vi.mocked(listApiKeys).mockResolvedValue([])
    vi.mocked(listUsers).mockResolvedValue([])
    vi.mocked(listAuditLogs).mockResolvedValue({ items: [], total: 0 })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('niega el acceso a quien no tiene permisos de IAM', async () => {
    renderPage([])
    expect(await screen.findByRole('alert')).toHaveTextContent(/no tienes permisos/i)
  })

  it('un viewer ve la página en modo lectura (sin acciones de gestión)', async () => {
    vi.mocked(listUsers).mockResolvedValue([USER])
    renderPage(['viewer'])
    expect(await screen.findByText('Usuarios')).toBeInTheDocument()
    expect(await screen.findByText('@mike')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /crear usuario/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /editar mike/i })).not.toBeInTheDocument()
  })

  it('muestra las pestañas y lista usuarios con roles', async () => {
    vi.mocked(listUsers).mockResolvedValue([USER])
    renderPage()
    expect(screen.getByText('Usuarios')).toBeInTheDocument()
    expect(screen.getByText('API Keys')).toBeInTheDocument()
    expect(screen.getByText('Auditoría')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /crear usuario/i })).toBeInTheDocument()
    expect(await screen.findByText('@mike')).toBeInTheDocument()
  })

  it('lista las API keys y revoca una tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(listApiKeys).mockResolvedValue([KEY])
    vi.mocked(revokeApiKey).mockResolvedValue(undefined)
    renderPage()

    await user.click(screen.getByText('API Keys'))
    expect(await screen.findByText('CI')).toBeInTheDocument()
    expect(screen.getByText('server.list')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /revocar CI/i }))
    await user.click(await screen.findByRole('button', { name: /^revocar$/i }))

    await waitFor(() => {
      expect(revokeApiKey).toHaveBeenCalledWith('key-1')
    })
  })

  it('muestra el material una sola vez al crear una API key', async () => {
    const user = userEvent.setup()
    vi.mocked(listApiKeys).mockResolvedValue([])
    vi.mocked(createApiKey).mockResolvedValue({ ...KEY, material: 'sk.secret-material' })
    renderPage()

    await user.click(screen.getByText('API Keys'))
    await screen.findByText(/no hay api keys/i)

    await user.click(screen.getByRole('button', { name: /crear api key/i }))
    await user.type(screen.getByLabelText(/nombre/i), 'CI')
    await user.click(await screen.findByTestId('create-apikey-submit'))

    expect(await screen.findByText('sk.secret-material')).toBeInTheDocument()
  })

  it('crea un usuario', async () => {
    const user = userEvent.setup()
    vi.mocked(createUser).mockResolvedValue(USER)
    renderPage()

    await user.click(screen.getByRole('button', { name: /crear usuario/i }))
    await user.type(screen.getByLabelText(/nombre de usuario/i), 'mike')
    await user.type(screen.getByLabelText(/^contraseña$/i), 's3cret!pw')
    await user.click(await screen.findByTestId('create-user-submit'))

    await waitFor(() => {
      expect(createUser).toHaveBeenCalledWith(
        expect.objectContaining({ username: 'mike', password: 's3cret!pw', role: 'viewer' }),
      )
    })
    expect(await screen.findByRole('status')).toHaveTextContent(/mike/i)
  })

  it('suspende a un usuario tras confirmar', async () => {
    const user = userEvent.setup()
    const OTHER: User = { ...USER, display_name: 'Mike Palmer', email: 'm@example.com' }
    vi.mocked(listUsers).mockResolvedValue([OTHER])
    vi.mocked(deleteUser).mockResolvedValue(undefined)
    renderPage()

    await screen.findByText('Mike Palmer')
    await user.click(screen.getByRole('button', { name: /suspender mike/i }))
    await user.click(await screen.findByRole('button', { name: /^suspender$/i }))

    await waitFor(() => {
      expect(deleteUser).toHaveBeenCalledWith('u1')
    })
  })

  it('edita un usuario (email y rol)', async () => {
    const user = userEvent.setup()
    const OTHER: User = { ...USER, display_name: 'Mike P.' }
    vi.mocked(listUsers).mockResolvedValue([OTHER])
    vi.mocked(updateUser).mockResolvedValue({ ...OTHER, email: 'new@example.com' })
    renderPage()

    await screen.findByText('Mike P.')
    await user.click(screen.getByRole('button', { name: /editar mike/i }))

    const emailInput = screen.getByLabelText(/email/i)
    await user.clear(emailInput)
    await user.type(emailInput, 'new@example.com')
    await user.click(await screen.findByRole('button', { name: /^guardar$/i }))

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith(
        'u1',
        expect.objectContaining({ email: 'new@example.com', status: 'active' }),
      )
    })
  })
})