import { apiClient } from '@/lib/api/client'

/**
 * Claves de cache de TanStack Query para el módulo World (frontend-standards
 * §13): `all(serverId)` es la lista `['worlds', serverId]`; `detail` deja
 * sitio para un mundo concreto si hiciera falta.
 */
export const worldKeys = {
  all: (serverId: string) => ['worlds', serverId] as const,
  detail: (serverId: string, name: string) => [...worldKeys.all(serverId), name] as const,
}

/**
 * Tipos del módulo World — verificados contra
 * `apps/backend/src/app/modules/world/api/schemas.py` (WorldResponse,
 * CreateWorldRequest, DuplicateWorldRequest). El listado y el sync devuelven
 * un ARRAY (`list[WorldResponse]`), no un objeto envoltorio.
 */

export interface World {
  id: string
  server_id: string
  name: string
  level_name: string
  activated: boolean
  size_bytes: number
  created_at: string
  updated_at: string
  seed: string | null
  gamemode: string | null
  difficulty: string | null
  view_distance: number | null
}

/**
 * Ajustes opcionales del mundo (CreateWorldRequest/UpdateWorldRequest del
 * backend): se guardan en la metadata y se inyectan como env al activar
 * (`LEVEL_SEED`/`GAMEMODE`/`DIFFICULTY`/`VIEW_DISTANCE`).
 */
export interface WorldSettings {
  seed?: string
  gamemode?: 'survival' | 'creative' | 'adventure'
  difficulty?: 'peaceful' | 'easy' | 'normal' | 'hard'
  view_distance?: number
}

/** Cuerpo de `POST /servers/{id}/worlds` (CreateWorldRequest). */
export interface CreateWorldRequest extends WorldSettings {
  name: string
}

/** Cuerpo de `POST /servers/{id}/worlds/{name}/duplicate` (DuplicateWorldRequest). */
export interface DuplicateWorldRequest {
  target: string
}

/** Cuerpo de `PATCH /servers/{id}/worlds/{name}` (UpdateWorldRequest). */
export interface UpdateWorldRequest extends WorldSettings {
  name?: string
}

/** `GET /servers/{id}/worlds`. */
export async function listWorlds(serverId: string): Promise<World[]> {
  const { data } = await apiClient.get<World[]>(`/servers/${serverId}/worlds`)
  return data
}

/** `POST /servers/{id}/worlds` (201) — crea un mundo vacío. */
export async function createWorld(serverId: string, data: CreateWorldRequest): Promise<World> {
  const res = await apiClient.post<World>(`/servers/${serverId}/worlds`, data)
  return res.data
}

/** `PATCH /servers/{id}/worlds/{name}` — renombra y/o ajusta un mundo. */
export async function updateWorld(
  serverId: string,
  name: string,
  data: UpdateWorldRequest,
): Promise<World> {
  const res = await apiClient.patch<World>(
    `/servers/${serverId}/worlds/${encodeURIComponent(name)}`,
    data,
  )
  return res.data
}

/**
 * `POST /servers/{id}/worlds/import` (201) — multipart con `file` + `name`.
 * NO se fija `Content-Type` a mano: el navegador genera el
 * `multipart/form-data; boundary=…` y `apiClient` (sin default JSON) no lo
 * pisa, así el backend parsea los campos.
 */
export async function importWorld(serverId: string, data: ImportWorldRequest): Promise<World> {
  const form = new FormData()
  form.append('file', data.file)
  form.append('name', data.name)
  const res = await apiClient.post<World>(`/servers/${serverId}/worlds/import`, form)
  return res.data
}

export interface ImportWorldRequest {
  name: string
  file: File
}

/** `POST /servers/{id}/worlds/sync` (201) — reconcilia con el storage. */
export async function syncWorlds(serverId: string): Promise<World[]> {
  const { data } = await apiClient.post<World[]>(`/servers/${serverId}/worlds/sync`)
  return data
}

/** `GET /servers/{id}/worlds/{name}/export` — snapshot `.mcworld` (blob). */
export async function exportWorld(serverId: string, name: string): Promise<Blob> {
  const res = await apiClient.get(`/servers/${serverId}/worlds/${encodeURIComponent(name)}/export`, {
    responseType: 'blob',
  })
  return res.data
}

/** `POST /servers/{id}/worlds/{name}/duplicate` (201). */
export async function duplicateWorld(
  serverId: string,
  name: string,
  data: DuplicateWorldRequest,
): Promise<World> {
  const res = await apiClient.post<World>(
    `/servers/${serverId}/worlds/${encodeURIComponent(name)}/duplicate`,
    data,
  )
  return res.data
}

/** `POST /servers/{id}/worlds/{name}/activate` — exclusivo del servidor. */
export async function activateWorld(serverId: string, name: string): Promise<World> {
  const res = await apiClient.post<World>(
    `/servers/${serverId}/worlds/${encodeURIComponent(name)}/activate`,
  )
  return res.data
}

/** `DELETE /servers/{id}/worlds/{name}` (204). */
export async function deleteWorld(serverId: string, name: string): Promise<void> {
  await apiClient.delete(`/servers/${serverId}/worlds/${encodeURIComponent(name)}`)
}
