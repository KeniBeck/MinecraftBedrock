import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import { ProfilePage } from '@/features/iam/ProfilePage'
import { enable2FA, confirm2FA, regenerateBackupCodes } from '@/lib/api/iam'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/iam', () => ({
  enable2FA: vi.fn(),
  confirm2FA: vi.fn(),
  regenerateBackupCodes: vi.fn(),
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ProfilePage />
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('ProfilePage', () => {
  beforeEach(() => {
    useAuthStore.setState({
      identity: { id: 'u1', username: 'admin', roles: ['admin'] },
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('muestra el nombre y los roles de la sesión', () => {
    renderPage()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText(/Roles:.*admin/)).toBeInTheDocument()
  })

  it('habilita 2FA y muestra secreto + backup codes, luego confirma', async () => {
    const user = userEvent.setup()
    vi.mocked(enable2FA).mockResolvedValue({
      secret: 'SECRET123',
      provisioning_uri: 'otpauth://totp/BedrockPanel:admin?secret=SECRET123',
      backup_codes: ['11111111', '22222222'],
    })
    vi.mocked(confirm2FA).mockResolvedValue(undefined)
    renderPage()

    await user.click(screen.getByRole('button', { name: /habilitar 2fa/i }))
    expect(await screen.findByText('SECRET123')).toBeInTheDocument()
    expect(screen.getByText('11111111')).toBeInTheDocument()

    await user.type(screen.getByLabelText(/código de confirmación/i), '000000')
    await user.click(screen.getByRole('button', { name: /confirmar 2fa/i }))

    expect(await screen.findByText('2FA activado')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /regenerar backup codes/i })).toBeInTheDocument()
  })

  it('regenera los backup codes una vez activado', async () => {
    const user = userEvent.setup()
    vi.mocked(enable2FA).mockResolvedValue({
      secret: 'SECRET123',
      provisioning_uri: 'otpauth://totp/x?secret=SECRET123',
      backup_codes: ['11111111'],
    })
    vi.mocked(confirm2FA).mockResolvedValue(undefined)
    vi.mocked(regenerateBackupCodes).mockResolvedValue({ backup_codes: ['99999999'] })
    renderPage()

    await user.click(screen.getByRole('button', { name: /habilitar 2fa/i }))
    await screen.findByText('SECRET123')
    await user.type(screen.getByLabelText(/código de confirmación/i), '000000')
    await user.click(screen.getByRole('button', { name: /confirmar 2fa/i }))
    await screen.findByText('2FA activado')

    await user.click(await screen.findByRole('button', { name: /regenerar backup codes/i }))
    expect(await screen.findByText('99999999')).toBeInTheDocument()
  })
})