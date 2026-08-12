import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios'

import type { ApiErrorBody } from '@/lib/api/types'
import { useAuthStore } from '@/stores/auth'

/** Base de la API — el proxy de Vite reenvía `/api` al backend (ver vite.config). */
export const API_BASE = '/api/v1'

/**
 * Sin `Content-Type` por defecto a nivel de instancia: axios fija
 * `application/json` automáticamente para payloads JSON (transformRequest) y
 * deja que el navegador genere `multipart/form-data; boundary=…` para
 * `FormData`. Forzarlo aquí rompía los uploads: con `application/json`,
 * axios serializaba el FormData a JSON y el backend no encontraba los campos.
 */
export const apiClient = axios.create({
  baseURL: API_BASE,
})

/** Parsea `{detail: {code, message}}` al mensaje legible (frontend-standards §8). */
export function getApiMessage(error: unknown, fallback = 'Error inesperado'): string {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as ApiErrorBody | undefined
    const message = body?.detail?.message
    if (typeof message === 'string' && message.length > 0) {
      return message
    }
    // El backend respondió con el formato de error pero sin message legible:
    // preferir el fallback antes que el mensaje genérico de axios.
    if (body?.detail) {
      return fallback
    }
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

/** Código de error del backend (p. ej. `TEMPLATE.EXISTS`) o `undefined`. */
export function getApiCode(error: unknown): string | undefined {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as ApiErrorBody | undefined
    return body?.detail?.code
  }
  return undefined
}

/**
 * Refresca la sesión con single-flight: si varias peticiones reciben 401 a la
 * vez, solo una lanza el refresh y el resto espera ese token nuevo.
 */
let refreshPromise: Promise<string | null> | null = null

async function refreshSession(): Promise<string | null> {
  const refreshToken = useAuthStore.getState().refreshToken
  if (!refreshToken) return null
  try {
    const { data } = await axios.post<{ access_token: string }>(
      `${API_BASE}/auth/refresh`,
      { refresh_token: refreshToken },
    )
    useAuthStore.getState().setAccessToken(data.access_token)
    return data.access_token
  } catch {
    // Refresh fallido → sesión muerta: logout local + ir a /login.
    useAuthStore.getState().clear()
    redirectToLogin()
    return null
  }
}

function redirectToLogin(): void {
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

// -- Request: adjuntar el Bearer ----------------------------------------------

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

// -- Response: manejar 401 (refresh una vez) y 403 (mensaje, no redirect) -----

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status

    if (status === 401) {
      const original = error.config as
        | (AxiosRequestConfig & { _retried?: boolean })
        | undefined
      if (original && !original._retried) {
        original._retried = true
        refreshPromise ??= refreshSession().finally(() => {
          refreshPromise = null
        })
        const newToken = await refreshPromise
        if (newToken) {
          original.headers = {
            ...(original.headers as Record<string, string>),
            Authorization: `Bearer ${newToken}`,
          }
          return apiClient.request(original)
        }
        // Refresh fallido: `refreshSession` ya hizo clear + redirect.
        return Promise.reject(error)
      }
      return Promise.reject(error)
    }

    // 403 y demás: NO redirigir a login — es un problema de permisos, no de
    // sesión. El componente muestra `detail.message` (frontend-standards §2).
    return Promise.reject(error)
  },
)
