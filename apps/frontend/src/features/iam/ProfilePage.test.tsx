import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import { ProfilePage } from '@/features/iam/ProfilePage'
import { enable2FA, confirm2FA, regenerateBackupCodes, disable2FA, twoFactorStatus, getMe, setAvatar } from '@/lib/api/iam'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/iam', () => ({
  enable2FA: vi.fn(),
  confirm2FA: vi.fn(),
  regenerateBackupCodes: vi.fn(),
  disable2FA: vi.fn(),
  twoFactorStatus: vi.fn(),
  getMe: vi.fn(),
  setAvatar: vi.fn(),
  twoFactorKeys: { status: ['iam', '2fa', 'status'] },
  profileKeys: { me: ['iam', 'me'] },
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
    vi.mocked(twoFactorStatus).mockResolvedValue({ enabled: false })
    vi.mocked(getMe).mockResolvedValue({
      id: 'u1',
      username: 'admin',
      display_name: 'admin',
      status: 'active',
      roles: ['admin'],
      created_at: null,
      last_login_at: null,
      email: null,
      avatar: null,
    })
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

  it('desactiva 2FA y vuelve al estado inicial', async () => {
    const user = userEvent.setup()
    vi.mocked(enable2FA).mockResolvedValue({
      secret: 'SECRET123',
      provisioning_uri: 'otpauth://totp/x?secret=SECRET123',
      backup_codes: ['11111111'],
    })
    vi.mocked(confirm2FA).mockResolvedValue(undefined)
    vi.mocked(disable2FA).mockResolvedValue(undefined)
    renderPage()

    await user.click(screen.getByRole('button', { name: /habilitar 2fa/i }))
    await screen.findByText('SECRET123')
    await user.type(screen.getByLabelText(/código de confirmación/i), '000000')
    await user.click(screen.getByRole('button', { name: /confirmar 2fa/i }))
    await screen.findByText('2FA activado')

    await user.click(screen.getByRole('button', { name: /desactivar 2fa/i }))
    expect(disable2FA).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('button', { name: /habilitar 2fa/i })).toBeInTheDocument()
  })

  it('muestra 2FA como activado si el backend lo reporta al entrar', async () => {
    vi.mocked(twoFactorStatus).mockResolvedValue({ enabled: true })
    renderPage()

    expect(await screen.findByText('2FA activado')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /habilitar 2fa/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /desactivar 2fa/i })).toBeInTheDocument()
  })

  it('muestra el avatar del perfil (data URL del backend)', async () => {
    vi.mocked(getMe).mockResolvedValue({
      id: 'u1',
      username: 'admin',
      display_name: 'admin',
      status: 'active',
      roles: ['admin'],
      created_at: null,
      last_login_at: null,
      email: null,
      avatar: 'data:image/png;base64,AAAA',
    })
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('profile-avatar')).toHaveAttribute(
        'src',
        'data:image/png;base64,AAAA',
      )
    })
  })

  it('usa el avatar por defecto si el backend no trae avatar', async () => {
    renderPage()

    const avatar = await screen.findByTestId('profile-avatar')
    expect(avatar.getAttribute('src')).toContain('skinmc-avatar.png')
  })

  it('cambia el avatar desde el dialog (overlay → elegir → guardar)', async () => {
    const user = userEvent.setup()
    vi.mocked(setAvatar).mockResolvedValue({
      id: 'u1',
      username: 'admin',
      display_name: 'admin',
      status: 'active',
      roles: ['admin'],
      created_at: null,
      last_login_at: null,
      email: null,
      avatar: 'data:image/png;base64,NUEVO',
    })
    renderPage()

    await screen.findByTestId('profile-avatar')
    // El overlay abre el dialog de cambio.
    await user.click(screen.getByTestId('profile-avatar-change'))
    expect(await screen.findByText('Cambiar avatar')).toBeInTheDocument()

    const file = new File(['x'], 'avatar.png', { type: 'image/png' })
    await user.upload(screen.getByTestId('profile-avatar-file'), file)
    await user.click(screen.getByTestId('profile-avatar-save'))

    expect(setAvatar).toHaveBeenCalledWith(file)
    await waitFor(() => {
      expect(screen.getByTestId('profile-avatar')).toHaveAttribute(
        'src',
        'data:image/png;base64,NUEVO',
      )
    })
  })

  it('el dialog se cierra tras guardar el avatar', async () => {
    const user = userEvent.setup()
    vi.mocked(setAvatar).mockResolvedValue({
      id: 'u1',
      username: 'admin',
      display_name: 'admin',
      status: 'active',
      roles: ['admin'],
      created_at: null,
      last_login_at: null,
      email: null,
      avatar: 'data:image/png;base64,NUEVO',
    })
    renderPage()

    await screen.findByTestId('profile-avatar')
    await user.click(screen.getByTestId('profile-avatar-change'))
    await screen.findByText('Cambiar avatar')

    const file = new File(['x'], 'avatar.png', { type: 'image/png' })
    await user.upload(screen.getByTestId('profile-avatar-file'), file)
    await user.click(screen.getByTestId('profile-avatar-save'))

    await waitFor(() => {
      expect(screen.queryByText('Cambiar avatar')).not.toBeInTheDocument()
    })
  })
})