import { StrictMode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { SchedulerPage } from '@/features/scheduler/SchedulerPage'
import {
  createTask,
  deleteTask,
  listTasks,
  runTask,
  updateTask,
  type ScheduleTask,
} from '@/lib/api/scheduler'
import { syncWorlds } from '@/lib/api/worlds'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/lib/api/scheduler', () => ({
  taskKeys: {
    all: (serverId: string) => ['scheduler', serverId],
    list: (serverId: string) => ['scheduler', serverId, 'list'],
    detail: (serverId: string, taskId: string) => ['scheduler', serverId, taskId],
  },
  listTasks: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  deleteTask: vi.fn(),
  runTask: vi.fn(),
}))

vi.mock('@/lib/api/worlds', () => ({
  worldKeys: {
    all: (serverId: string) => ['worlds', serverId],
    detail: (serverId: string, name: string) => ['worlds', serverId, name],
  },
  syncWorlds: vi.fn(),
  listWorlds: vi.fn(),
}))

const TASK: ScheduleTask = {
  id: 't-1',
  server_id: 'srv-1',
  name: 'Backup diario',
  type: 'backup',
  cron: '0 3 * * *',
  payload: { world_name: 'Mi Mundo 1' },
  state: 'active',
  next_run_at: '2026-01-02T03:00:00Z',
  last_run_at: '2026-01-01T03:00:00Z',
  last_result: 'ok',
  failures: 0,
  max_retries: 3,
  backoff_seconds: 60,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function renderPage(roles: string[] = ['admin']) {
  useAuthStore.setState({ identity: { id: 'u1', username: 'admin', roles } })
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/servers/srv-1/scheduler']}>
          <Routes>
            <Route path="/servers/:serverId/scheduler" element={<SchedulerPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('SchedulerPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('muestra las tareas listadas', async () => {
    vi.mocked(listTasks).mockResolvedValue([TASK])

    renderPage()

    expect(await screen.findByText('Backup diario')).toBeInTheDocument()
    expect(screen.getByText(/0 3 \* \* \*/)).toBeInTheDocument()
    expect(screen.getByText('Backup')).toBeInTheDocument()
    expect(screen.getByText('Activa')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ejecutar/i })).toBeInTheDocument()
  })

  it('muestra el estado vacío cuando no hay tareas', async () => {
    vi.mocked(listTasks).mockResolvedValue([])

    renderPage()

    expect(await screen.findByText(/No hay tareas programadas/)).toBeInTheDocument()
  })

  it('crea una tarea de tipo backup', async () => {
    const user = userEvent.setup()
    vi.mocked(listTasks).mockResolvedValue([])
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
    vi.mocked(createTask).mockResolvedValue(TASK)

    renderPage()
    await screen.findByText(/No hay tareas programadas/)

    await user.click(screen.getByRole('button', { name: /nueva tarea/i }))
    await user.type(screen.getByLabelText(/nombre/i), 'Backup diario')
    await user.selectOptions(screen.getByLabelText('Hora'), '5')
    await screen.findByDisplayValue('Mi Mundo 1')
    await user.click(await screen.findByRole('button', { name: /^crear tarea$/i }))

    await waitFor(() => {
      expect(createTask).toHaveBeenCalledWith('srv-1', {
        name: 'Backup diario',
        type: 'backup',
        cron: '0 5 * * *',
        payload: { world_name: 'Mi Mundo 1' },
        max_retries: 3,
        backoff_seconds: 60,
      })
    })
  })

  it('crea una tarea de tipo command con sus comandos', async () => {
    const user = userEvent.setup()
    vi.mocked(listTasks).mockResolvedValue([])
    vi.mocked(createTask).mockResolvedValue({ ...TASK, type: 'command' })

    renderPage()
    await screen.findByText(/No hay tareas programadas/)

    await user.click(screen.getByRole('button', { name: /nueva tarea/i }))
    await user.type(screen.getByLabelText(/nombre/i), 'Broadcast')
    await user.selectOptions(screen.getByLabelText(/tipo/i), 'command')
    await user.type(screen.getByLabelText(/comandos/i), 'say hola\nsay mundo')
    await user.click(await screen.findByRole('button', { name: /^crear tarea$/i }))

    await waitFor(() => {
      expect(createTask).toHaveBeenCalledWith('srv-1', {
        name: 'Broadcast',
        type: 'command',
        cron: '0 3 * * *',
        payload: { commands: ['say hola', 'say mundo'] },
        max_retries: 3,
        backoff_seconds: 60,
      })
    })
  })

  it('ejecuta una tarea al pulsar Ejecutar', async () => {
    const user = userEvent.setup()
    vi.mocked(listTasks).mockResolvedValue([TASK])
    vi.mocked(runTask).mockResolvedValue(TASK)

    renderPage()
    await screen.findByText('Backup diario')

    await user.click(screen.getByRole('button', { name: /ejecutar/i }))

    await waitFor(() => {
      expect(runTask).toHaveBeenCalledWith('srv-1', 't-1')
    })
  })

  it('edita una tarea', async () => {
    const user = userEvent.setup()
    vi.mocked(listTasks).mockResolvedValue([TASK])
    vi.mocked(updateTask).mockResolvedValue({ ...TASK, name: 'Backup nocturno' })

    renderPage()
    await screen.findByText('Backup diario')

    await user.click(screen.getByRole('button', { name: '' }))
    await user.click(await screen.findByText('Editar'))
    const nameInput = await screen.findByLabelText(/nombre/i)
    await user.clear(nameInput)
    await user.type(nameInput, 'Backup nocturno')
    await user.click(await screen.findByRole('button', { name: /^guardar$/i }))

    await waitFor(() => {
      expect(updateTask).toHaveBeenCalledWith('srv-1', 't-1', expect.objectContaining({
        name: 'Backup nocturno',
        cron: '0 3 * * *',
      }))
    })
  })

  it('elimina una tarea tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(listTasks).mockResolvedValue([TASK])
    vi.mocked(deleteTask).mockResolvedValue(undefined)

    renderPage()
    await screen.findByText('Backup diario')

    await user.click(screen.getByRole('button', { name: '' }))
    await user.click(await screen.findByText('Eliminar'))
    await user.click(await screen.findByRole('button', { name: /^eliminar$/i }))

    await waitFor(() => {
      expect(deleteTask).toHaveBeenCalledWith('srv-1', 't-1')
    })
  })

  it('oculta las acciones de escritura a un viewer', async () => {
    vi.mocked(listTasks).mockResolvedValue([TASK])

    renderPage(['viewer'])
    await screen.findByText('Backup diario')

    expect(screen.queryByRole('button', { name: /nueva tarea/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /ejecutar/i })).not.toBeInTheDocument()
  })

  it('niega el acceso a quien no puede listar', async () => {
    renderPage([])
    expect(await screen.findByRole('alert')).toHaveTextContent(/no tienes permisos/i)
    expect(screen.queryByText('Backup diario')).not.toBeInTheDocument()
  })
})