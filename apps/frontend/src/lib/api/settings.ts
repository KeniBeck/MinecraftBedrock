import { apiClient } from './client'

/**
 * Claves de cache de TanStack Query para el módulo Settings (ajustes globales
 * del panel). `all` es el listado `['settings']`.
 */
export const settingsKeys = {
  all: ['settings'] as const,
}

/**
 * `SettingResponse` del backend (modules/settings/api/schemas.py): el valor
 * viaja como JSON arbitrario y el tipo (int/float/str/bool/path/any) sirve
 * para renderizar el control de edición.
 */
export interface PanelSetting {
  key: string
  value: unknown
  category: string
  description: string | null
  type: string
  default: unknown
}

/** `SettingsListResponse`. */
export interface SettingsListResponse {
  settings: PanelSetting[]
}

/** Cuerpo de `PATCH /settings` (actualización múltiple atómica). */
export interface PatchSettingsRequest {
  values: Record<string, unknown>
}

/** `GET /settings` — lista completa (requiere `settings.view`). */
export async function listSettings(): Promise<SettingsListResponse> {
  const { data } = await apiClient.get<SettingsListResponse>('/settings')
  return data
}

/** `PATCH /settings` — actualiza varios ajustes a la vez (requiere `settings.update`). */
export async function patchSettings(payload: PatchSettingsRequest): Promise<SettingsListResponse> {
  const { data } = await apiClient.patch<SettingsListResponse>('/settings', payload)
  return data
}

/** `DELETE /settings/{key}` — resetea un ajuste a su valor por defecto. */
export async function resetSetting(key: string): Promise<PanelSetting> {
  const { data } = await apiClient.delete<PanelSetting>(`/settings/${key}`)
  return data
}
