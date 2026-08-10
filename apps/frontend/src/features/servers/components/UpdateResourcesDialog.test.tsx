import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { UpdateResourcesDialog } from '@/features/servers/components/UpdateResourcesDialog'
import { updateServerResources, type Server } from '@/lib/api/servers'
import { useCan } from '@/lib/auth/useCan'

vi.mock('@/lib/api/servers', () => ({
  updateServerResources: vi.fn(),
  serverKeys: { all: ['servers'], detail: (id: string) => ['server', id] },
}))

vi.mock('@/lib/auth/useCan', () => ({
  useCan: vi.fn(() => true),
  rolesCan: vi.fn(() => true),
}))

const SERVER: Server = {
  id: 'srv-1',
  name: 'Survival',
  state: 'stopped',
  version: '1.21.1',
  image_ref: 'img:latest',
  runtime_id: 'r1',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  connection: { host: 'localhost', port: 19132, port_v6: 19133, rcon_port: 25575, address: 'localhost:19132' },
  resources: { cpu_cores: 2, ram_mb: 2048, disk_gb: 10 },
}

function renderDialog(server: Server = SERVER) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <UpdateResourcesDialog server={server} />
    </QueryClientProvider>,
  )
}

async function openDialog(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByTestId('update-resources-button'))
}

describe('UpdateResourcesDialog', () => {
  beforeEach(() => {
    vi.mocked(useCan).mockReturnValue(true)
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCan).mockReset()
  })

  it('se oculta sin el permiso server.update', () => {
    vi.mocked(useCan).mockReturnValue(false)
    renderDialog()
    expect(screen.queryByTestId('update-resources-button')).not.toBeInTheDocument()
  })

  it('precarga los valores actuales de resources en el detalle', async () => {
    const user = userEvent.setup()
    renderDialog()
    await openDialog(user)
    expect(screen.getByTestId('update-resources-cpu')).toHaveValue('2')
    expect(screen.getByTestId('update-resources-ram')).toHaveValue('2048')
  })

  it('muestra el aviso de reinicio si el servidor está en línea', async () => {
    const user = userEvent.setup()
    renderDialog({ ...SERVER, state: 'running' })
    await openDialog(user)
    expect(screen.getByTestId('recreate-warning')).toBeInTheDocument()
  })

  it('oculta el aviso de reinicio si el servidor está detenido', async () => {
    const user = userEvent.setup()
    renderDialog({ ...SERVER, state: 'stopped' })
    await openDialog(user)
    expect(screen.queryByTestId('recreate-warning')).not.toBeInTheDocument()
  })

  it('valida CPU fuera de rango sin llamar al backend', async () => {
    const user = userEvent.setup()
    renderDialog()
    await openDialog(user)
    await user.clear(screen.getByTestId('update-resources-cpu'))
    await user.type(screen.getByTestId('update-resources-cpu'), '99')
    await user.click(screen.getByTestId('update-resources-submit'))

    expect(await screen.findByRole('alert')).toHaveTextContent('CPU debe estar entre 1 y 64 núcleos')
    expect(updateServerResources).not.toHaveBeenCalled()
  })

  it('valida RAM fuera de rango sin llamar al backend', async () => {
    const user = userEvent.setup()
    renderDialog()
    await openDialog(user)
    await user.clear(screen.getByTestId('update-resources-ram'))
    await user.type(screen.getByTestId('update-resources-ram'), '100')
    await user.click(screen.getByTestId('update-resources-submit'))

    expect(await screen.findByRole('alert')).toHaveTextContent('RAM debe estar entre 512 MB y 65536 MB')
    expect(updateServerResources).not.toHaveBeenCalled()
  })

  it('envía el payload con los campos cambiados y cierra al éxito', async () => {
    const user = userEvent.setup()
    vi.mocked(updateServerResources).mockResolvedValue({ ...SERVER, state: 'running' })
    renderDialog({ ...SERVER, state: 'running' })
    await openDialog(user)

    await user.clear(screen.getByTestId('update-resources-cpu'))
    await user.clear(screen.getByTestId('update-resources-ram'))
    await user.type(screen.getByTestId('update-resources-cpu'), '4')
    await user.click(screen.getByTestId('update-resources-submit'))

    await waitFor(() => {
      expect(updateServerResources).toHaveBeenCalledWith('srv-1', { cpu_cores: 4 })
    })
    await waitFor(() => {
      expect(screen.queryByTestId('update-resources-submit')).not.toBeInTheDocument()
    })
  })

  it('muestra detail.message tal cual si el backend responde 409 SERVER.BUSY', async () => {
    const user = userEvent.setup()
    const { AxiosError, AxiosHeaders } = await import('axios')
    vi.mocked(updateServerResources).mockRejectedValue(
      new AxiosError('busy', '409', undefined, undefined, {
        status: 409,
        statusText: 'busy',
        data: { detail: { code: 'SERVER.BUSY', message: 'El servidor está ocupado, inténtalo más tarde' } },
        headers: {},
        config: { headers: new AxiosHeaders() },
      }),
    )
    renderDialog({ ...SERVER, state: 'running' })
    await openDialog(user)
    await user.click(screen.getByTestId('update-resources-submit'))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'El servidor está ocupado, inténtalo más tarde',
    )
  })

  it('422 con detail de FastAPI muestra fallback y no rompe la UI', async () => {
    const user = userEvent.setup()
    const { AxiosError, AxiosHeaders } = await import('axios')
    vi.mocked(updateServerResources).mockRejectedValue(
      new AxiosError('validation', '422', undefined, undefined, {
        status: 422,
        statusText: 'validation',
        data: {
          detail: [{ loc: ['body', 'cpu_cores'], msg: 'Input should be less than or equal to 64', type: 'less_than_equal' }],
        },
        headers: {},
        config: { headers: new AxiosHeaders() },
      }),
    )
    renderDialog()
    await openDialog(user)
    await user.click(screen.getByTestId('update-resources-submit'))

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron actualizar los recursos')
    expect(screen.getByTestId('update-resources-submit')).toBeInTheDocument()
  })

  it('403 no rompe la UI: muestra el mensaje de detalle', async () => {
    const user = userEvent.setup()
    const { AxiosError, AxiosHeaders } = await import('axios')
    vi.mocked(updateServerResources).mockRejectedValue(
      new AxiosError('forbidden', '403', undefined, undefined, {
        status: 403,
        statusText: 'forbidden',
        data: { detail: { code: 'AUTH.FORBIDDEN', message: 'No autorizado para server.update' } },
        headers: {},
        config: { headers: new AxiosHeaders() },
      }),
    )
    renderDialog()
    await openDialog(user)
    await user.click(screen.getByTestId('update-resources-submit'))

    expect(await screen.findByRole('alert')).toHaveTextContent('No autorizado para server.update')
  })
})
