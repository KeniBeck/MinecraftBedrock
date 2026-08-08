import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios, { AxiosError, AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

import { API_BASE, apiClient, getApiCode, getApiMessage } from '@/lib/api/client'
import { useAuthStore } from '@/stores/auth'

function axiosErrorWith(status: number, data: unknown): AxiosError {
  return new AxiosError('boom', undefined, undefined, undefined, {
    status,
    statusText: 'error',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data,
  })
}

describe('getApiMessage / getApiCode', () => {
  it('extrae detail.message del body de error del backend', () => {
    const error = axiosErrorWith(403, {
      detail: { code: 'AUTH.FORBIDDEN', message: 'Sin permiso para server.start' },
    })
    expect(getApiMessage(error)).toBe('Sin permiso para server.start')
    expect(getApiCode(error)).toBe('AUTH.FORBIDDEN')
  })

  it('devuelve el fallback si el backend responde con formato de error sin message', () => {
    const error = axiosErrorWith(500, { detail: { code: 'X', message: '' } })
    expect(getApiMessage(error, 'fallback')).toBe('fallback')
    expect(getApiMessage(undefined, 'fallback')).toBe('fallback')
  })

  it('no inventa código si el body no es el formato del backend', () => {
    const error = axiosErrorWith(500, {})
    expect(getApiCode(error)).toBeUndefined()
  })
})

describe('interceptor de autenticación', () => {
  const originalHref = window.location.href

  /** Instala un adapter mock para `apiClient` (interceptores reales). */
  function withAdapter(handler: (config: InternalAxiosRequestConfig) => AxiosResponse | Promise<AxiosResponse>) {
    apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
      const response = await handler(config)
      return { ...response, config, headers: new AxiosHeaders() }
    }
  }

  beforeEach(() => {
    useAuthStore.getState().clear()
    Object.defineProperty(window, 'location', {
      value: { href: 'http://localhost:5173/', pathname: '/', assign: vi.fn() },
      writable: true,
    })
  })

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: { href: originalHref },
      writable: true,
    })
    vi.restoreAllMocks()
  })

  it('adjunta el Bearer del store en cada request', async () => {
    let seenHeader: unknown
    withAdapter((config) => {
      seenHeader = (config.headers as AxiosHeaders).get('Authorization')
      return { status: 200, statusText: 'ok', data: {}, headers: {}, config }
    })
    useAuthStore.getState().setSession({
      accessToken: 'at-1',
      refreshToken: 'rt-1',
      identity: { id: 'u1', username: 'alice', roles: ['admin'] },
    })

    await apiClient.get('/auth/me')

    expect(seenHeader).toBe('Bearer at-1')
  })

  it('ante 401 con refresh válido reintenta y NO redirige a login', async () => {
    let calls = 0
    withAdapter((config) => {
      calls += 1
      if (calls === 1) {
        throw new AxiosError('expired', '401', config, undefined, {
          status: 401,
          statusText: 'unauthorized',
          data: { detail: { code: 'AUTH.TOKEN_EXPIRED', message: 'exp' } },
          headers: {},
          config,
        })
      }
      return { status: 200, statusText: 'ok', data: { ok: true }, headers: {}, config }
    })
    const refreshSpy = vi
      .spyOn(axios, 'post')
      .mockResolvedValue({ data: { access_token: 'at-new' } } as AxiosResponse)

    useAuthStore.getState().setSession({
      accessToken: 'at-old',
      refreshToken: 'rt-1',
      identity: { id: 'u1', username: 'alice', roles: ['admin'] },
    })

    const result = await apiClient.get('/auth/me')
    expect(result.data).toEqual({ ok: true })
    expect(calls).toBe(2)
    expect(refreshSpy).toHaveBeenCalledWith(
      `${API_BASE}/auth/refresh`,
      { refresh_token: 'rt-1' },
    )
    expect(useAuthStore.getState().accessToken).toBe('at-new')
    expect(window.location.assign).not.toHaveBeenCalled()
    expect(window.location.href).not.toContain('/login')
  })

  it('ante 403 NO redirige a login (problema de permisos, no de sesión)', async () => {
    withAdapter((config) => {
      throw new AxiosError('forbidden', '403', config, undefined, {
        status: 403,
        statusText: 'forbidden',
        data: { detail: { code: 'AUTH.FORBIDDEN', message: 'No autorizado' } },
        headers: {},
        config,
      })
    })
    useAuthStore.getState().setSession({
      accessToken: 'at-1',
      refreshToken: 'rt-1',
      identity: { id: 'u1', username: 'alice', roles: ['viewer'] },
    })

    await expect(apiClient.get('/servers/abc/start')).rejects.toMatchObject({
      response: { status: 403 },
    })
    expect(window.location.assign).not.toHaveBeenCalled()
    expect(window.location.href).not.toContain('/login')
  })

  it('ante 401 sin refresh válido hace logout y redirige a /login', async () => {
    withAdapter((config) => {
      throw new AxiosError('expired', '401', config, undefined, {
        status: 401,
        statusText: 'unauthorized',
        data: { detail: { code: 'AUTH.TOKEN_EXPIRED', message: 'exp' } },
        headers: {},
        config,
      })
    })
    vi.spyOn(axios, 'post').mockRejectedValue(
      axiosErrorWith(401, { detail: { code: 'AUTH.TOKEN_EXPIRED', message: 'exp' } }),
    )
    useAuthStore.getState().setSession({
      accessToken: 'at-old',
      refreshToken: 'rt-1',
      identity: { id: 'u1', username: 'alice', roles: ['admin'] },
    })

    await expect(apiClient.get('/auth/me')).rejects.toBeDefined()
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})
