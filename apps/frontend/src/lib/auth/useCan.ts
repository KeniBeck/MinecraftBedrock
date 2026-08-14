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
  // `server.update` es WRITE_ACTION (ámbito server) → la tienen operator,
  // admin y super_admin (modules/iam/domain/permissions.py). No es PANEL_ACTION
  // como `server.create`, por eso su mínimo de rol es más amplio.
  'server.update': ['operator', 'admin', 'super_admin'],
  // `server.console.write` también es WRITE_ACTION (operator+) — oculta el
  // input de comandos de la consola sin permiso.
  'server.console.write': ['operator', 'admin', 'super_admin'],
  // `player.manage` (kick) es WRITE_ACTION → operator+.
  'player.manage': ['operator', 'admin', 'super_admin'],
  // `permission.read` es READ_ACTION (viewer+); `permission.write` (ban/unban
  // por servidor) es WRITE_ACTION → operator+.
  'permission.read': ['viewer', 'operator', 'admin', 'super_admin'],
  'permission.write': ['operator', 'admin', 'super_admin'],
  // `player.ban.global` es PANEL_ACTION → solo admin/super_admin.
  'player.ban.global': ['admin', 'super_admin'],
  // `backup.list/view/download` son READ_ACTION (viewer+); `backup.create/
  // restore/delete/validate/prune` son WRITE_ACTION → operator+.
  'backup.create': ['operator', 'admin', 'super_admin'],
  'backup.restore': ['operator', 'admin', 'super_admin'],
  'backup.delete': ['operator', 'admin', 'super_admin'],
  'backup.validate': ['operator', 'admin', 'super_admin'],
  'backup.prune': ['operator', 'admin', 'super_admin'],
  'backup.download': ['viewer', 'operator', 'admin', 'super_admin'],
  // `task.list`/`task.view` son READ_ACTION (viewer+); el resto del catálogo
  // scheduler (create/update/delete/run) son WRITE_ACTION → operator+.
  'task.list': ['viewer', 'operator', 'admin', 'super_admin'],
  'task.view': ['viewer', 'operator', 'admin', 'super_admin'],
  'task.write': ['operator', 'admin', 'super_admin'],
  'task.create': ['operator', 'admin', 'super_admin'],
  'task.update': ['operator', 'admin', 'super_admin'],
  'task.delete': ['operator', 'admin', 'super_admin'],
  'task.run': ['operator', 'admin', 'super_admin'],
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