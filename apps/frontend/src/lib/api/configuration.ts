import { apiClient } from './client'

/** Valores de `server.properties` viajan como strings (esquema backend). */
export type ConfigPropertyValue = string

/**
 * Claves de cache de TanStack Query para el módulo Configuration.
 */
export const configKeys = {
  all: (serverId: string) => ['configuration', serverId] as const,
  profile: (serverId: string) => [...configKeys.all(serverId), 'profile'] as const,
}

/**
 * Tipos del módulo Configuration — verificados contra
 * `apps/backend/src/app/modules/configuration/api/schemas.py` y el router real:
 * - `GET /servers/{id}/configuration` → `ConfigProfileResponse`
 * - `PUT /servers/{id}/configuration` → `ConfigProfileResponse`
 *
 * Nota: el backend valida (max-players ≤ 40) y publica `CONFIG.CHANGED`; la
 * recreación del contenedor con la nueva config ocurre en segundo plano.
 */

/** `ConfigProfileResponse` — config deseada (server.properties) y metadatos. */
export interface ConfigProfile {
  server_id: string
  version: string
  config_rev: number
  properties: Record<string, ConfigPropertyValue>
  applied: Record<string, ConfigPropertyValue> | null
  applied_at: string | null
  updated_at: string | null
}

/** `UpdateConfigRequest` — cuerpo de `PUT .../configuration`. */
export interface UpdateConfigRequest {
  properties: Record<string, ConfigPropertyValue>
}

/** `GET /servers/{id}/configuration` — perfil de configuración actual. */
export async function getConfig(serverId: string): Promise<ConfigProfile> {
  const { data } = await apiClient.get<ConfigProfile>(
    `/servers/${serverId}/configuration`,
  )
  return data
}

/** `PUT /servers/{id}/configuration` — actualizar config deseada. */
export async function updateConfig(
  serverId: string,
  request: UpdateConfigRequest,
): Promise<ConfigProfile> {
  const { data } = await apiClient.put<ConfigProfile>(
    `/servers/${serverId}/configuration`,
    request,
  )
  return data
}