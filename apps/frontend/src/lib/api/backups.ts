import { apiClient } from './client'

/**
 * Claves de cache de TanStack Query para el módulo Backup (frontend-standards
 * §13): `all(serverId)` es la base `['backups', serverId]`; `list` añade el
 * filtro por mundo si lo hay; `detail` deja sitio para un backup concreto.
 */
export const backupKeys = {
  all: (serverId: string) => ['backups', serverId] as const,
  list: (serverId: string, worldName?: string) =>
    [...backupKeys.all(serverId), 'list', worldName ?? ''] as const,
  detail: (serverId: string, backupId: string) =>
    [...backupKeys.all(serverId), backupId] as const,
}

/**
 * Tipos del módulo Backup — verificados contra
 * `apps/backend/src/app/modules/backup/api/schemas.py` y el router real:
 * - `GET /servers/{id}/backups?world_name=&limit=` → `list[BackupResponse]`
 * - `POST /servers/{id}/backups` → `BackupResponse` (201)
 * - `GET /servers/{id}/backups/{backup_id}` → `BackupResponse`
 * - `POST /servers/{id}/backups/{backup_id}/restore` → `BackupResponse` (SIN body)
 * - `POST /servers/{id}/backups/{backup_id}/validate` → `BackupResponse` (200)
 * - `GET /servers/{id}/backups/{backup_id}/download` → stream `application/zstd`
 * - `DELETE /servers/{id}/backups/{backup_id}` → 204
 * - `POST /servers/{id}/backups/prune` → `list[BackupResponse]` (body `keep_last_n`)
 */

/** `BackupResponse` — registro de un backup del servidor. */
export interface Backup {
  id: string
  server_id: string
  world_name: string
  state: 'running' | 'completed' | 'failed' | 'corrupt' | 'deleted'
  size_bytes: number
  checksum: string
  entries: string[]
  duration_seconds: number | null
  protected: boolean
  orphaned: boolean
  error: string | null
  created_at: string
  updated_at: string
}

/** `CreateBackupRequest` — crear backup manual (con opción de proteger). */
export interface CreateBackupRequest {
  world_name: string
  protected?: boolean
}

/** `PruneBackupRequest` — retención keep-last-N por mundo. */
export interface PruneBackupsRequest {
  keep_last_n: number
}

/** `GET /servers/{id}/backups?world_name=&limit=` — lista de backups. */
export async function listBackups(
  serverId: string,
  worldName?: string,
  limit = 50,
): Promise<Backup[]> {
  const { data } = await apiClient.get<Backup[]>(`/servers/${serverId}/backups`, {
    params: { world_name: worldName || undefined, limit },
  })
  return data
}

/** `GET /servers/{id}/backups/{backup_id}` — detalle de un backup. */
export async function getBackup(serverId: string, backupId: string): Promise<Backup> {
  const { data } = await apiClient.get<Backup>(
    `/servers/${serverId}/backups/${encodeURIComponent(backupId)}`,
  )
  return data
}

/** `POST /servers/{id}/backups` (201) — crear backup manual. */
export async function createBackup(
  serverId: string,
  data: CreateBackupRequest,
): Promise<Backup> {
  const res = await apiClient.post<Backup>(`/servers/${serverId}/backups`, data)
  return res.data
}

/** `POST /servers/{id}/backups/{backup_id}/restore` — restaura sobre su mundo. */
export async function restoreBackup(serverId: string, backupId: string): Promise<Backup> {
  const res = await apiClient.post<Backup>(
    `/servers/${serverId}/backups/${encodeURIComponent(backupId)}/restore`,
  )
  return res.data
}

/** `POST /servers/{id}/backups/{backup_id}/validate` — verifica integridad. */
export async function validateBackup(serverId: string, backupId: string): Promise<Backup> {
  const res = await apiClient.post<Backup>(
    `/servers/${serverId}/backups/${encodeURIComponent(backupId)}/validate`,
  )
  return res.data
}

/** `GET /servers/{id}/backups/{backup_id}/download` — artefacto `.tar.zst`. */
export async function downloadBackup(serverId: string, backupId: string): Promise<Blob> {
  const res = await apiClient.get<Blob>(
    `/servers/${serverId}/backups/${encodeURIComponent(backupId)}/download`,
    { responseType: 'blob' },
  )
  return res.data
}

/** `DELETE /servers/{id}/backups/{backup_id}` (204). */
export async function deleteBackup(serverId: string, backupId: string): Promise<void> {
  await apiClient.delete(`/servers/${serverId}/backups/${encodeURIComponent(backupId)}`)
}

/** `POST /servers/{id}/backups/prune` — retención keep-last-N por mundo. */
export async function pruneBackups(
  serverId: string,
  keepLastN?: number,
): Promise<Backup[]> {
  const { data } = await apiClient.post<Backup[]>(`/servers/${serverId}/backups/prune`, {
    keep_last_n: keepLastN ?? 10,
  } satisfies PruneBackupsRequest)
  return data
}
