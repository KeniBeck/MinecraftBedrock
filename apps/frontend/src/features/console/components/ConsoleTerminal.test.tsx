import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { ConsoleTerminal } from '@/features/console/components/ConsoleTerminal'
import { sendConsoleCommand } from '@/lib/api/console'
import { useCan } from '@/lib/auth/useCan'
import { useConsoleStore, type ConsoleLine } from '@/stores/console'

vi.mock('@/lib/api/console', () => ({
  sendConsoleCommand: vi.fn(),
}))

vi.mock('@/lib/auth/useCan', () => ({
  useCan: vi.fn(() => true),
  rolesCan: vi.fn(() => true),
}))

function line(seq: number): ConsoleLine {
  return { seq, line: `line-${seq}`, timestamp: '2026-01-01T00:00:00Z' }
}

function renderTerminal({ state = 'running' }: { state?: string } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <ConsoleTerminal serverId="srv-1" serverState={state as 'running' | 'stopped'} />,
    { wrapper },
  )
}

describe('ConsoleTerminal', () => {
  beforeEach(() => {
    useConsoleStore.setState({ lines: {}, lastSeq: {} })
    vi.mocked(useCan).mockReturnValue(true)
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCan).mockReset()
  })

  it('muestra las líneas del store', () => {
    useConsoleStore.setState({ lines: { 'srv-1': [line(0), line(1)] } })
    renderTerminal()
    expect(screen.getByText('line-0')).toBeInTheDocument()
    expect(screen.getByText('line-1')).toBeInTheDocument()
  })

  it('muestra el estado vacío sin líneas', () => {
    renderTerminal()
    expect(screen.getByTestId('console-empty')).toBeInTheDocument()
  })

  it('con el servidor detenido muestra aviso y deshabilita el input', () => {
    renderTerminal({ state: 'stopped' })
    expect(screen.getByTestId('console-banner')).toHaveTextContent('no se pueden enviar comandos')
    expect(screen.getByTestId('console-input')).toBeDisabled()
    expect(screen.getByTestId('console-send')).toBeDisabled()
  })

  it('oculta el input sin permiso server.console.write', () => {
    vi.mocked(useCan).mockReturnValue(false)
    renderTerminal()
    expect(screen.queryByTestId('console-input')).not.toBeInTheDocument()
    expect(screen.queryByTestId('console-send')).not.toBeInTheDocument()
  })

  it('envía el comando y limpia el input al éxito', async () => {
    const user = userEvent.setup()
    vi.mocked(sendConsoleCommand).mockResolvedValue({
      server_id: 'srv-1',
      command: 'say hola',
      priority: 'normal',
      seq: 1,
      at: '2026-01-01T00:00:00Z',
    })
    renderTerminal()

    await user.type(screen.getByTestId('console-input'), 'say hola')
    await user.click(screen.getByTestId('console-send'))

    await waitFor(() => {
      expect(sendConsoleCommand).toHaveBeenCalledWith('srv-1', 'say hola')
    })
    await waitFor(() => {
      expect(screen.getByTestId('console-input')).toHaveValue('')
    })
    expect(screen.getByTestId('console-input')).toHaveFocus()
  })

  it('muestra detail.message del backend si falla con CONSOLE.SERVER_OFFLINE', async () => {
    const user = userEvent.setup()
    const { AxiosError, AxiosHeaders } = await import('axios')
    vi.mocked(sendConsoleCommand).mockRejectedValue(
      new AxiosError('offline', '409', undefined, undefined, {
        status: 409,
        statusText: 'offline',
        data: { detail: { code: 'CONSOLE.SERVER_OFFLINE', message: 'El servidor no está en línea' } },
        headers: {},
        config: { headers: new AxiosHeaders() },
      }),
    )
    renderTerminal()

    await user.type(screen.getByTestId('console-input'), 'list')
    await user.click(screen.getByTestId('console-send'))

    expect(await screen.findByRole('alert')).toHaveTextContent('El servidor no está en línea')
  })
})
