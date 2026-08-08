import { afterEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, AxiosHeaders } from 'axios'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { LoginPage } from '@/features/auth/LoginPage'
import { loginRequest, verifyTwoFactorRequest } from '@/lib/api/auth'

vi.mock('@/lib/api/auth', () => ({
  loginRequest: vi.fn(),
  verifyTwoFactorRequest: vi.fn(),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('LoginPage — flujo de dos pasos', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('paso 1: sin 2FA entra directo guardando la sesión', async () => {
    const user = userEvent.setup()
    vi.mocked(loginRequest).mockResolvedValue({
      requires_2fa: false,
      temp_token: null,
      access_token: 'at-1',
      refresh_token: 'rt-1',
      expires_in: 900,
      identity: { id: 'u1', username: 'alice', roles: ['admin'] },
    })

    renderPage()
    await user.type(screen.getByLabelText('Usuario'), 'alice')
    await user.type(screen.getByLabelText('Contraseña'), 'pass')
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }))

    await waitFor(() => {
      expect(loginRequest).toHaveBeenCalledWith({ username: 'alice', password: 'pass' })
    })
    expect(verifyTwoFactorRequest).not.toHaveBeenCalled()
  })

  it('paso 2: si el login pide 2FA muestra el input de código y verifica', async () => {
    const user = userEvent.setup()
    vi.mocked(loginRequest).mockResolvedValue({
      requires_2fa: true,
      temp_token: 'tmp-1',
      access_token: null,
      refresh_token: null,
      expires_in: null,
      identity: null,
    })
    vi.mocked(verifyTwoFactorRequest).mockResolvedValue({
      access_token: 'at-2',
      refresh_token: 'rt-2',
      expires_in: 900,
      identity: { id: 'u1', username: 'alice', roles: ['admin'] },
    })

    renderPage()
    await user.type(screen.getByLabelText('Usuario'), 'alice')
    await user.type(screen.getByLabelText('Contraseña'), 'pass')
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }))

    // Segundo paso visible.
    await waitFor(() => {
      expect(screen.getByLabelText('Código 2FA')).toBeInTheDocument()
    })
    await user.type(screen.getByLabelText('Código 2FA'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verificar' }))

    await waitFor(() => {
      expect(verifyTwoFactorRequest).toHaveBeenCalledWith({
        temp_token: 'tmp-1',
        code: '123456',
      })
    })
  })

  it('muestra detail.message cuando el login falla (403/credenciales)', async () => {
    const user = userEvent.setup()
    const error = new AxiosError('unauthorized', '401', undefined, undefined, {
      status: 401,
      statusText: 'unauthorized',
      data: { detail: { code: 'AUTH.INVALID_CREDENTIALS', message: 'Credenciales inválidas' } },
      headers: {},
      config: { headers: new AxiosHeaders() },
    })
    vi.mocked(loginRequest).mockRejectedValue(error)

    renderPage()
    await user.type(screen.getByLabelText('Usuario'), 'alice')
    await user.type(screen.getByLabelText('Contraseña'), 'mala')
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Credenciales inválidas')
    })
  })
})
