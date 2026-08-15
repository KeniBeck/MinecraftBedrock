import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

import { SettingsPage } from '@/features/settings/SettingsPage'
import { listSettings, patchSettings, resetSetting } from '@/lib/api/settings'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/settings', () => ({
  listSettings: vi.fn(),
  patchSettings: vi.fn(),
  resetSetting: vi.fn(),
  settingsKeys: { all: ['settings'] },
}))

const SETTINGS = [
  {
    key: 'storage.base_path',
    value: '/var/lib/bedrockpanel/data',
    category: 'storage',
    description: 'Ruta base para los datos de los servidores',
    type: 'path',
    default: '/var/lib/bedrockpanel/data',
  },
  {
    key: 'limits.max_backups_per_server',
    value: 10,
    category: 'limits',
    description: 'Número máximo de backups por servidor',
    type: 'int',
    default: 10,
  },
  {
    key: 'system.maintenance_mode',
    value: false,
    category: 'system',
    description: 'Panel en mantenimiento',
    type: 'bool',
    default: false,
  },
  {
    key: 'defaults.version',
    value: 'LATEST',
    category: 'defaults',
    description: 'Versión BDS por defecto',
    type: 'str',
    default: 'LATEST',
  },
]

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <SettingsPage />
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.mocked(listSettings).mockResolvedValue({ settings: SETTINGS })
    useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles: ['admin'] } })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
    useAuthStore.setState({ identity: null })
  })

  it('agrupa los ajustes por categoría', async () => {
    renderPage()
    expect(await screen.findByText('Almacenamiento')).toBeInTheDocument()
    expect(screen.getByText('Límites y recursos')).toBeInTheDocument()
    expect(screen.getByText('Valores por defecto')).toBeInTheDocument()
    expect(screen.getByText('Sistema')).toBeInTheDocument()
    expect(screen.getByText('storage.base_path')).toBeInTheDocument()
    expect(screen.getByText('limits.max_backups_per_server')).toBeInTheDocument()
  })

  it('permite editar y guardar los cambios por categoría (PATCH)', async () => {
    const user = userEvent.setup()
    vi.mocked(patchSettings).mockResolvedValue({ settings: [] })
    renderPage()

    const input = await screen.findByLabelText('limits.max_backups_per_server')
    await user.clear(input)
    await user.type(input, '15')

    await user.click(screen.getByTestId('save-limits'))
    expect(patchSettings).toHaveBeenCalledWith({
      values: { 'limits.max_backups_per_server': 15 },
    })
    expect(await screen.findByText(/Límites y recursos" guardados/)).toBeInTheDocument()
  })

  it('resetea un ajuste a su valor por defecto (DELETE)', async () => {
    const user = userEvent.setup()
    vi.mocked(resetSetting).mockResolvedValue({
      key: 'system.maintenance_mode',
      value: false,
      category: 'system',
      description: null,
      type: 'bool',
      default: false,
    })
    renderPage()

    await screen.findByText('system.maintenance_mode')
    await user.click(screen.getByLabelText('Resetear system.maintenance_mode'))
    expect(resetSetting).toHaveBeenCalledWith('system.maintenance_mode')
  })

  it('muestra advertencia sin permisos de lectura', async () => {
    useAuthStore.setState({ identity: { id: 'u1', username: 'ghost', roles: ['ghost'] } })
    renderPage()
    expect(
      await screen.findByText('No tienes permisos para ver la configuración del panel.'),
    ).toBeInTheDocument()
  })

  it('deshabilita edición y reset para roles sin settings.update', async () => {
    useAuthStore.setState({ identity: { id: 'u1', username: 'viewer', roles: ['viewer'] } })
    renderPage()
    await screen.findByText('storage.base_path')
    expect(screen.getByLabelText('storage.base_path')).toBeDisabled()
    expect(screen.getByLabelText('Resetear storage.base_path')).toBeDisabled()
  })
})
