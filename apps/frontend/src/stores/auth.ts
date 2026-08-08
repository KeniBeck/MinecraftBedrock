import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type { IdentityResponse } from '@/lib/api/types'

/**
 * Sesión del frontend: access/refresh tokens + identidad. Persistida en
 * localStorage. No contiene datos de servidor — solo credenciales de sesión.
 *
 * Nota: el backend no tiene logout stateful más allá de revocar el refresh
 * token (confirmado en el router de IAM); `clear` borra la sesión local y, si
 * hay refresh token, lo revoca vía `POST /auth/logout` (best-effort).
 */
interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  identity: IdentityResponse | null
  setSession: (session: {
    accessToken: string
    refreshToken: string
    identity: IdentityResponse
  }) => void
  setAccessToken: (token: string) => void
  clear: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      identity: null,
      setSession: ({ accessToken, refreshToken, identity }) =>
        set({ accessToken, refreshToken, identity }),
      setAccessToken: (accessToken) => set({ accessToken }),
      clear: () => set({ accessToken: null, refreshToken: null, identity: null }),
    }),
    { name: 'bedrock-panel-auth' },
  ),
)
