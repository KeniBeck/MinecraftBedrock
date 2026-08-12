import { StrictMode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { BackupsPage } from '@/features/backups/BackupsPage'
import {
  createBackup,
  deleteBackup,
  downloadBackup,
  listBackups,
  pruneBackups,
  restoreBackup,
  validateBackup,
  type Backup,
} from '@/lib/api/backups'
import { syncWorlds } from '@/lib/api/worlds'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/backups', () => ({
  backupKeys: {
    all: (serverId: string) => ['backups', serverId],
    list: (serverId: string, worldName?: string) => ['backups', serverId, 'list', worldName ?? ''],
    detail: (serverId: string, backupId: string) => ['backups', serverId, backupId],
  },
  listBackups: vi.fn(),
  getBackup: vi.fn(),
  createBackup: vi.fn(),
  restoreBackup: vi.fn(),
  validateBackup: vi.fn(),
  downloadBackup: vi.fn(),
  deleteBackup: vi.fn(),
  pruneBackups: vi.fn(),
}))

vi.mock('@/lib/api/worlds', () => ({
  worldKeys: {
    all: (serverId: string) => ['worlds', serverId],
    detail: (serverId: string, name: string) => ['worlds', serverId, name],
  },
  syncWorlds: vi.fn(),
  listWorlds: vi.fn(),
}))

const BACKUP: Backup = {
  id: 'b-1',
  server_id: 'srv-1',
  world_name: 'Mi Mundo 1',
  state: 'completed',
  size_bytes: 4096,
  checksum: 'abc',
  entries: ['db'],
  duration_seconds: 3,
  protected: false,
  orphaned: false,
  error: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const PROTECTED: Backup = { ...BACKUP, id: 'b-2', protected: true }

function renderPage(roles: string[] = ['admin']) {
  useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles } })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/servers/srv-1/backups']}>
          <Routes>
            <Route path="/servers/:serverId/backups" element={<BackupsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('BackupsPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('muestra los backups listados', async () => {
    vi.mocked(listBackups).mockResolvedValue([BACKUP])

    renderPage()

    expect(await screen.findByText('Mi Mundo 1')).toBeInTheDocument()
    expect(screen.getByText(/completed/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /restaurar/i })).toBeInTheDocument()
  })

  it('muestra el estado vacío cuando no hay backups', async () => {
    vi.mocked(listBackups).mockResolvedValue([])

    renderPage()

    expect(await screen.findByText(/No hay backups aún/)).toBeInTheDocument()
  })

  it('crea un backup del mundo elegido', async () => {
    const user = userEvent.setup()
    vi.mocked(listBackups).mockResolvedValue([])
    vi.mocked(syncWorlds).mockResolvedValue([
      {
        id: 'w-1',
        server_id: 'srv-1',
        name: 'Mi Mundo 1',
        level_name: 'Mi Mundo 1',
        activated: true,
        size_bytes: 4096,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        seed: null,
        gamemode: null,
        difficulty: null,
        view_distance: null,
      },
    ])
    vi.mocked(createBackup).mockResolvedValue(BACKUP)

    renderPage()
    await screen.findByText(/No hay backups aún/)

    await user.click(screen.getByRole('button', { name: /crear backup/i }))
    await user.click(await screen.findByRole('button', { name: /^crear backup$/i }))

    await waitFor(() => {
      expect(createBackup).toHaveBeenCalledWith('srv-1', { world_name: 'Mi Mundo 1' })
    })
  })

  it('restaura un backup tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(listBackups).mockResolvedValue([BACKUP])
    vi.mocked(restoreBackup).mockResolvedValue(BACKUP)

    renderPage()
    await screen.findByText('Mi Mundo 1')

    await user.click(screen.getByRole('button', { name: /restaurar/i }))
    await user.click(await screen.findByRole('button', { name: /^restaurar$/i }))

    await waitFor(() => {
      expect(restoreBackup).toHaveBeenCalledWith('srv-1', 'b-1')
    })
  })

  it('valida un backup y no muestra error si está íntegro', async () => {
    const user = userEvent.setup()
    vi.mocked(listBackups).mockResolvedValue([BACKUP])
    vi.mocked(validateBackup).mockResolvedValue(BACKUP)

    renderPage()
    await screen.findByText('Mi Mundo 1')

    await user.click(screen.getByRole('button', { name: '' }))
    await user.click(await screen.findByText('Validar'))

    await waitFor(() => {
      expect(validateBackup).toHaveBeenCalledWith('srv-1', 'b-1')
    })
  })

  it('descarga un backup completado', async () => {
    const user = userEvent.setup()
    vi.mocked(listBackups).mockResolvedValue([BACKUP])
    vi.mocked(downloadBackup).mockResolvedValue(new Blob(['data']))
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    renderPage()
    await screen.findByText('Mi Mundo 1')

    await user.click(screen.getByRole('button', { name: '' }))
    await user.click(await screen.findByText('Descargar'))

    await waitFor(() => {
      expect(downloadBackup).toHaveBeenCalledWith('srv-1', 'b-1')
    })
    expect(clickSpy).toHaveBeenCalled()
  })

  it('elimina un backup tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(listBackups).mockResolvedValue([BACKUP])
    vi.mocked(deleteBackup).mockResolvedValue(undefined)

    renderPage()
    await screen.findByText('Mi Mundo 1')

    await user.click(screen.getByRole('button', { name: '' }))
    await user.click(await screen.findByText('Eliminar'))
    await user.click(await screen.findByRole('button', { name: /^eliminar$/i }))

    await waitFor(() => {
      expect(deleteBackup).toHaveBeenCalledWith('srv-1', 'b-1')
    })
  })

  it('no permite eliminar un backup protegido', async () => {
    vi.mocked(listBackups).mockResolvedValue([PROTECTED])

    renderPage()
    await screen.findByText('Mi Mundo 1')

    await userEvent.setup().click(screen.getByRole('button', { name: '' }))

    expect(screen.getByText(/eliminar \(protegido\)/i)).toHaveAttribute('aria-disabled', 'true')
  })

  it('aplica retención con el número de backups indicado', async () => {
    const user = userEvent.setup()
    vi.mocked(listBackups).mockResolvedValue([BACKUP])
    vi.mocked(pruneBackups).mockResolvedValue([BACKUP])

    renderPage()
    await screen.findByText('Mi Mundo 1')

    await user.click(screen.getByRole('button', { name: /retención/i }))
    await user.clear(await screen.findByLabelText(/backups a conservar/i))
    await user.type(screen.getByLabelText(/backups a conservar/i), '5')
    await user.click(await screen.findByRole('button', { name: /^aplicar$/i }))

    await waitFor(() => {
      expect(pruneBackups).toHaveBeenCalledWith('srv-1', 5)
    })
  })

  it('oculta las acciones de escritura a un viewer', async () => {
    vi.mocked(listBackups).mockResolvedValue([BACKUP])

    renderPage(['viewer'])
    await screen.findByText('Mi Mundo 1')

    expect(screen.queryByRole('button', { name: /crear backup/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /retención/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /restaurar/i })).not.toBeInTheDocument()
  })
})
