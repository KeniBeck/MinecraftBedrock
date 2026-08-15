import type { RoleName } from '@/lib/api/iam'

/** Roles globales que el panel puede asignar (schema IAM `RoleName`). */
export const ROLE_OPTIONS: readonly { value: RoleName; label: string }[] = [
  { value: 'super_admin', label: 'Super administrador' },
  { value: 'admin', label: 'Administrador' },
  { value: 'operator', label: 'Operador' },
  { value: 'viewer', label: 'Espectador' },
]

/**
 * Scopes predefinidos ofrecidos al crear una API key (permisos `Permiso.accion`
 * del catálogo del backend). Se persisten tal cual; la autorización real la
 * aplica el backend (intersección en `AccessControlService.authorize`).
 */
export const SCOPE_OPTIONS: readonly { value: string; label: string }[] = [
  { value: 'server.list', label: 'Listar servidores' },
  { value: 'server.status', label: 'Estado de servidores' },
  { value: 'server.start', label: 'Iniciar servidor' },
  { value: 'server.stop', label: 'Detener servidor' },
  { value: 'server.console.write', label: 'Enviar comandos a la consola' },
  { value: 'backup.list', label: 'Listar backups' },
  { value: 'backup.create', label: 'Crear backups' },
  { value: 'player.list', label: 'Listar jugadores' },
]

/** Label legible de un rol global. */
export function roleLabel(role: string): string {
  return ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role
}