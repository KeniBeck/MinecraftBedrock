import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

/**
 * Guard de rutas protegidas: sin sesión (access token), redirige a /login.
 * Conserva la ubicación de origen para poder volver tras autenticarse.
 */
export function RequireAuth() {
  const accessToken = useAuthStore((state) => state.accessToken)
  const location = useLocation()

  if (!accessToken) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

/** Guard inverso: si ya hay sesión, las páginas de auth redirigen al inicio. */
export function RequireGuest() {
  const accessToken = useAuthStore((state) => state.accessToken)
  if (accessToken) {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}
