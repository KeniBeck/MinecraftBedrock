import { apiClient } from '@/lib/api/client'
import type {
  LoginRequest,
  LoginResponse,
  LogoutRequest,
  RefreshRequest,
  TokenResponse,
  VerifyTwoFactorRequest,
} from '@/lib/api/types'

/** `POST /auth/login` — devuelve tokens O challenge 2FA (schema LoginResponse). */
export async function loginRequest(payload: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login', payload)
  return data
}

/** `POST /auth/verify-2fa` — completa el segundo factor y devuelve tokens. */
export async function verifyTwoFactorRequest(
  payload: VerifyTwoFactorRequest,
): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/verify-2fa', payload)
  return data
}

/** `POST /auth/refresh` — rota el refresh token y devuelve uno nuevo. */
export async function refreshRequest(payload: RefreshRequest): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/refresh', payload)
  return data
}

/** `POST /auth/logout` (204) — revoca el refresh token en el servidor. */
export async function logoutRequest(payload: LogoutRequest): Promise<void> {
  await apiClient.post('/auth/logout', payload)
}
