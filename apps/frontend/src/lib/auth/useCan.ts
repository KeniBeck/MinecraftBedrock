import { useAuthStore } from '@/stores/auth'

/**
 * Deriva si la identidad actual puede ejecutar una acción de permisos de ámbito
 * panel. El backend declara `server.create` como PANEL_ACTION (solo
 * admin/super_admin — ver `modules/iam/domain/permissions.py`). Este es un
 * *mínimo de rol* a falta de un endpoint de "mis permisos"; la autorización
 * real siempre la aplica el backend (403 si no puede).
 *
 * frontend-standards §3: no hardcodear "si rol === admin" en cada botón; este
 * helper centraliza el mapeo rol→permiso panel y es reutilizable.
 */
const PANEL_MIN_ROLES: Record<string, readonly string[]> = {
  'server.create': ['admin', 'super_admin'],
}

export function rolesCan(action: string, roles: readonly string[] | undefined): boolean {
  const allowed = PANEL_MIN_ROLES[action]
  if (!allowed) return false
  return Boolean(roles?.some((role) => allowed.includes(role)))
}

/** Hook que usa la identidad almacenada en el store. `true` = puede ejecutar. */
export function useCan(action: string): boolean {
  const roles = useAuthStore((state) => state.identity)?.roles
  return rolesCan(action, roles)
}