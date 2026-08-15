import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ConfigurationPage } from '@/features/configuration/ConfigurationPage'
import { getConfig, updateConfig, type ConfigProfile } from '@/lib/api/configuration'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/configuration', () => ({
  configKeys: {
    all: (serverId: string) => ['configuration', serverId],
    profile: (serverId: string) => ['configuration', serverId, 'profile'],
  },
  getConfig: vi.fn(),
  updateConfig: vi.fn(),
}))

const PROFILE: ConfigProfile = {
  server_id: 'srv-1',
  version: 'LATEST',
  config_rev: 1,
  properties: { gamemode: 'creative', 'max-players': '20' },
  applied: null,
  applied_at: null,
  updated_at: '2026-08-14T10:00:00Z',
}

function renderPage(roles: string[] = ['admin']) {
  useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles } })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/servers/srv-1/configuration']}>
          <Routes>
            <Route path="/servers/:serverId/configuration" element={<ConfigurationPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('ConfigurationPage', () => {
  beforeEach(() => {
    vi.mocked(getConfig).mockResolvedValue(PROFILE)
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('carga y muestra los grupos y las propiedades perfiladas', async () => {
    renderPage()
    expect(await screen.findByLabelText(/modo de juego/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/jugadores máximos/i)).toHaveValue(20)
    expect(screen.getByLabelText(/dificultad/i)).toBeInTheDocument()
    expect(screen.getByText('General')).toBeInTheDocument()
  })

  it('guarda los cambios al pulsar "Guardar cambios"', async () => {
    const user = userEvent.setup()
    vi.mocked(updateConfig).mockResolvedValue({
      ...PROFILE,
      properties: { gamemode: 'adventure', 'max-players': '20' },
    })
    renderPage()
    await screen.findByLabelText(/modo de juego/i)

    await user.selectOptions(screen.getByLabelText(/modo de juego/i), 'adventure')
    await user.click(screen.getByRole('button', { name: /guardar cambios/i }))

    await waitFor(() => {
      expect(updateConfig).toHaveBeenCalledWith('srv-1', {
        properties: expect.objectContaining({ gamemode: 'adventure' }),
      })
    })
    expect(await screen.findByRole('status')).toBeInTheDocument()
  })

  it('muestra error de validación inline antes de guardar', async () => {
    const user = userEvent.setup()
    renderPage()
    const input = await screen.findByLabelText(/jugadores máximos/i)

    await user.clear(input)
    await user.type(input, '41')
    await user.click(screen.getByRole('button', { name: /guardar cambios/i }))

    expect(screen.getByText('Máximo 40.')).toBeInTheDocument()
    expect(updateConfig).not.toHaveBeenCalled()
  })

  it('deshabilita los controles para un viewer', async () => {
    renderPage(['viewer'])
    expect(await screen.findByLabelText(/modo de juego/i)).toBeDisabled()
    expect(
      screen.queryByRole('button', { name: /guardar cambios/i }),
    ).not.toBeInTheDocument()
  })

  it('niega el acceso a quien no puede leer', async () => {
    renderPage([])
    expect(await screen.findByRole('alert')).toHaveTextContent(/no tienes permisos/i)
  })
})