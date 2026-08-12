import { StrictMode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { TemplatesPage } from '@/features/templates/TemplatesPage'
import { applyTemplate, captureTemplate, deleteTemplate, listTemplates, type Template } from '@/lib/api/templates'

vi.mock('@/lib/api/templates', () => ({
  templateKeys: {
    all: (serverId: string) => ['templates', serverId],
    detail: (serverId: string, id: string) => ['templates', serverId, id],
  },
  listTemplates: vi.fn(),
  getTemplate: vi.fn(),
  captureTemplate: vi.fn(),
  applyTemplate: vi.fn(),
  deleteTemplate: vi.fn(),
}))

vi.mock('@/lib/api/worlds', () => ({
  worldKeys: {
    all: (serverId: string) => ['worlds', serverId],
    detail: (serverId: string, name: string) => ['worlds', serverId, name],
  },
}))

const TEMPLATE: Template = {
  id: 't-1',
  name: 'Server plano',
  version: '1',
  size_bytes: 2048,
  origin_server_id: 'srv-1',
  origin_world: 'plano',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/servers/srv-1/templates']}>
          <Routes>
            <Route path="/servers/:serverId/templates" element={<TemplatesPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </StrictMode>,
  )
}

describe('TemplatesPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.restoreAllMocks()
  })

  it('muestra las plantillas listadas', async () => {
    vi.mocked(listTemplates).mockResolvedValue([TEMPLATE])

    renderPage()

    expect(await screen.findByText('Server plano')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
  })

  it('muestra el estado vacío cuando no hay plantillas', async () => {
    vi.mocked(listTemplates).mockResolvedValue([])

    renderPage()

    expect(await screen.findByText(/No hay plantillas aún/)).toBeInTheDocument()
  })

  it('permite capturar una plantilla nueva', async () => {
    const user = userEvent.setup()
    vi.mocked(listTemplates).mockResolvedValue([])
    vi.mocked(captureTemplate).mockResolvedValue(TEMPLATE)

    renderPage()
    await screen.findByText(/No hay plantillas aún/)

    await user.click(screen.getByRole('button', { name: /capturar plantilla/i }))
    await user.type(screen.getByLabelText(/nombre/i), 'Nueva plantilla')
    await user.click(screen.getByRole('button', { name: /^capturar$/i }))

    await waitFor(() => {
      expect(captureTemplate).toHaveBeenCalledWith('srv-1', { name: 'Nueva plantilla' })
    })
  })

  it('aplica una plantilla con el nombre de mundo indicado', async () => {
    const user = userEvent.setup()
    vi.mocked(listTemplates).mockResolvedValue([TEMPLATE])
    vi.mocked(applyTemplate).mockResolvedValue(TEMPLATE)

    renderPage()
    await screen.findByText('Server plano')

    await user.click(screen.getByRole('button', { name: /aplicar/i }))
    await user.type(screen.getByLabelText(/nombre del mundo destino/i), 'mundo2')
    await user.click(screen.getByRole('button', { name: /^aplicar$/i }))

    await waitFor(() => {
      expect(applyTemplate).toHaveBeenCalledWith('srv-1', 't-1', { world_name: 'mundo2' })
    })
  })

  it('elimina una plantilla tras confirmar', async () => {
    const user = userEvent.setup()
    vi.mocked(listTemplates).mockResolvedValue([TEMPLATE])
    vi.mocked(deleteTemplate).mockResolvedValue(undefined)

    renderPage()
    await screen.findByText('Server plano')

    const trigger = screen.getByRole('button', { name: '' })
    await user.click(trigger)
    await user.click(await screen.findByText('Eliminar'))
    await user.click(await screen.findByRole('button', { name: /^eliminar$/i }))

    await waitFor(() => {
      expect(deleteTemplate).toHaveBeenCalledWith('srv-1', 't-1')
    })
  })
})
