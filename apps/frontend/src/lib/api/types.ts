/**
 * Tipos de la API del backend — verificados contra los schemas reales en
 * `apps/backend/src/app/modules/iam/api/schemas.py` (LoginResponse, TokenResponse).
 *
 * La regla del standard: nunca inventar la forma; leer el schema del endpoint.
 */

/** `IdentityResponse` — subobjeto de TokenResponse/LoginResponse. */
export interface IdentityResponse {
  id: string
  username: string
  roles: string[]
}

/**
 * Respuesta de `POST /auth/login` (schema `LoginResponse`): **o** trae tokens
 * (cuenta sin 2FA) **o** pide el segundo factor. Ambas variantes comparten el
 * objeto; los campos no presentes vienen `null`.
 */
export interface LoginResponse {
  requires_2fa: boolean
  temp_token: string | null
  access_token: string | null
  refresh_token: string | null
  expires_in: number | null
  identity: IdentityResponse | null
}

/** Respuesta de `POST /auth/verify-2fa` y `POST /auth/refresh` (schema `TokenResponse`). */
export interface TokenResponse {
  access_token: string
  refresh_token: string
  expires_in: number
  identity: IdentityResponse
}

/** Cuerpo de `POST /auth/login`. */
export interface LoginRequest {
  username: string
  password: string
}

/** Cuerpo de `POST /auth/verify-2fa`. */
export interface VerifyTwoFactorRequest {
  temp_token: string
  code: string
}

/** Cuerpo de `POST /auth/refresh`. */
export interface RefreshRequest {
  refresh_token: string
}

/** Cuerpo de `POST /auth/logout` (204). */
export interface LogoutRequest {
  refresh_token: string
}

/**
 * Formato de error uniforme del backend:
 * `{ "detail": { "code", "message", "context" } }` (frontend-standards §8).
 */
export interface ApiErrorDetail {
  code: string
  message: string
  context?: Record<string, unknown>
}

export interface ApiErrorBody {
  detail: ApiErrorDetail
}
