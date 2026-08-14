import { apiClient } from './client'

/**
 * Claves de cache de TanStack Query para el módulo Permission: `all(serverId)`
 * es la base `['permissions', serverId]`; `allowlist` recoge el listado.
 */
export const permissionKeys = {
  all: (serverId: string) => ['permissions', serverId] as const,
  allowlist: (serverId: string) => [...permissionKeys.all(serverId), 'allowlist'] as const,
}

/** Claves del listado de operadores/permisos del servidor. */
export const operatorKeys = {
  all: (serverId: string) => ['permissions', serverId, 'operators'] as const,
}

/**
 * Tipos del módulo Permission — verificados contra
 * `apps/backend/src/app/modules/permission/api/schemas.py` y el router real:
 * - `GET /servers/{id}/permissions/allowlist` → `list[AllowlistEntryResponse]`
 * - `POST /servers/{id}/permissions/allowlist` → `AllowlistEntryResponse` (201)
 * - `DELETE /servers/{id}/permissions/allowlist/{xuid}` → 204
 * - `PUT /servers/{id}/permissions/allowlist-enabled` → 204 (`{enabled}`)
 * - `GET /servers/{id}/permissions/operators` → `list[OperatorResponse]`
 * - `PUT /servers/{id}/permissions/operators/{xuid}` → `PermissionEntryResponse` (`{level}`)
 * - `DELETE /servers/{id}/permissions/operators/{xuid}` → 204
 *
 * DISCREPANCIA vs. el enunciado: el backend NO expone un GET del estado de la
 * allowlist (el toggle es solo escritura), por lo que ese valor no se precarga.
 */

/** `AllowlistEntryResponse` — entrada de la allowlist del servidor. */
export interface AllowlistEntry {
  name: string
  xuid: string
  ignores_player_limit: boolean
}

/** `AllowlistAddRequest` — body de `POST .../allowlist` (xuid OBLIGATORIO). */
export interface AddAllowlistRequest {
  name: string
  xuid: string
  ignores_player_limit?: boolean
}

/** Niveles de permiso aceptados por el backend (`PermissionLevel`). */
export type PermissionLevel = 'operator' | 'member' | 'visitor'

/** `PermissionEntryResponse` — permiso asignado a un jugador. */
export interface OperatorEntry {
  xuid: string
  level: PermissionLevel
}

/** `GET /servers/{id}/permissions/allowlist` — lista de la allowlist. */
export async function listAllowlist(serverId: string): Promise<AllowlistEntry[]> {
  const { data } = await apiClient.get<AllowlistEntry[]>(
    `/servers/${serverId}/permissions/allowlist`,
  )
  return data
}

/** `POST /servers/{id}/permissions/allowlist` (201) — añadir entrada. */
export async function addAllowlistEntry(
  serverId: string,
  data: AddAllowlistRequest,
): Promise<AllowlistEntry> {
  const res = await apiClient.post<AllowlistEntry>(
    `/servers/${serverId}/permissions/allowlist`,
    data,
  )
  return res.data
}

/** `DELETE /servers/{id}/permissions/allowlist/{xuid}` (204). */
export async function removeAllowlistEntry(serverId: string, xuid: string): Promise<void> {
  await apiClient.delete(
    `/servers/${serverId}/permissions/allowlist/${encodeURIComponent(xuid)}`,
  )
}

/** `PUT /servers/{id}/permissions/allowlist-enabled` (204) — toggle ALLOW_LIST. */
export async function setAllowlistEnabled(serverId: string, enabled: boolean): Promise<void> {
  await apiClient.put(`/servers/${serverId}/permissions/allowlist-enabled`, { enabled })
}

/** `GET /servers/{id}/permissions/operators` — lista de permisos del servidor. */
export async function getOperators(serverId: string): Promise<OperatorEntry[]> {
  const { data } = await apiClient.get<OperatorEntry[]>(
    `/servers/${serverId}/permissions/operators`,
  )
  return data
}

/** `PUT /servers/{id}/permissions/operators/{xuid}` — asignar nivel de permiso. */
export async function setOperatorLevel(
  serverId: string,
  xuid: string,
  level: PermissionLevel,
): Promise<OperatorEntry> {
  const res = await apiClient.put<OperatorEntry>(
    `/servers/${serverId}/permissions/operators/${encodeURIComponent(xuid)}`,
    { level },
  )
  return res.data
}

/** `DELETE /servers/{id}/permissions/operators/{xuid}` (204). */
export async function removeOperator(serverId: string, xuid: string): Promise<void> {
  await apiClient.delete(
    `/servers/${serverId}/permissions/operators/${encodeURIComponent(xuid)}`,
  )
}