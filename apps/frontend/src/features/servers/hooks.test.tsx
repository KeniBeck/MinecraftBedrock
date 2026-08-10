import { describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { useUpdateResources } from '@/features/servers/hooks'
import { updateServerResources, type Server } from '@/lib/api/servers'

vi.mock('@/lib/api/servers', () => ({
  updateServerResources: vi.fn(),
  getServer: vi.fn(),
  serverKeys: { all: ['servers'], detail: (id: string) => ['server', id] },
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
}

function renderWithClient(client: QueryClient) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return renderHook(() => useUpdateResources(), { wrapper })
}

describe('useUpdateResources', () => {
  it('éxito: escribe el detalle en cache e invalida detalle y lista', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const updated: Server = { ...SERVER, state: 'starting' }
    vi.mocked(updateServerResources).mockResolvedValue(updated)
    queryClient.setQueryData(['server', 'srv-1'], SERVER)

    const { result } = renderWithClient(queryClient)
    await act(() =>
      result.current.mutateAsync({ serverId: 'srv-1', payload: { cpu_cores: 4 } }),
    )

    expect(updateServerResources).toHaveBeenCalledWith('srv-1', { cpu_cores: 4 })
    expect(queryClient.getQueryData(['server', 'srv-1'])).toEqual(updated)
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['server', 'srv-1'] }),
    )
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['servers'] }),
    )
  })

  it('envía solo los campos presentes en el payload', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.mocked(updateServerResources).mockResolvedValue(SERVER)

    const { result } = renderWithClient(queryClient)
    await act(() =>
      result.current.mutateAsync({ serverId: 'srv-1', payload: { ram_mb: 4096 } }),
    )

    expect(updateServerResources).toHaveBeenCalledWith('srv-1', { ram_mb: 4096 })
  })

  it('422: rechaza sin invalidar ni tocar la cache', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const { AxiosError, AxiosHeaders } = await import('axios')
    vi.mocked(updateServerResources).mockRejectedValue(
      new AxiosError('validation', '422', undefined, undefined, {
        status: 422,
        statusText: 'validation',
        data: { detail: [] },
        headers: {},
        config: { headers: new AxiosHeaders() },
      }),
    )
    queryClient.setQueryData(['server', 'srv-1'], SERVER)

    const { result } = renderWithClient(queryClient)
    await act(async () => {
      await expect(
        result.current.mutateAsync({ serverId: 'srv-1', payload: { cpu_cores: 999 } }),
      ).rejects.toThrow()
    })

    expect(invalidateSpy).not.toHaveBeenCalled()
    expect(queryClient.getQueryData(['server', 'srv-1'])).toEqual(SERVER)
  })

  it('403: rechaza (el caller muestra el mensaje) sin invalidar', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')
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

    const { result } = renderWithClient(queryClient)
    await act(async () => {
      await expect(
        result.current.mutateAsync({ serverId: 'srv-1', payload: { cpu_cores: 4 } }),
      ).rejects.toThrow()
    })

    expect(invalidateSpy).not.toHaveBeenCalled()
  })
})
