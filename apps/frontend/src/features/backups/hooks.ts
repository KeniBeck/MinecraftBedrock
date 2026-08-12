import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  backupKeys,
  createBackup,
  deleteBackup,
  downloadBackup,
  getBackup,
  listBackups,
  pruneBackups,
  restoreBackup,
  validateBackup,
  type CreateBackupRequest,
} from '@/lib/api/backups'
import { worldKeys } from '@/lib/api/worlds'

export { backupKeys }

/** `GET /servers/{id}/backups?world_name=&limit=` — lista de backups. */
export function useBackups(serverId: string | undefined, worldName?: string) {
  return useQuery({
    queryKey: backupKeys.list(serverId ?? '', worldName),
    queryFn: () => listBackups(serverId!, worldName, 50),
    enabled: Boolean(serverId),
    refetchOnWindowFocus: false,
  })
}

/** `GET /servers/{id}/backups/{backup_id}` — detalle de un backup. */
export function useBackup(serverId: string | undefined, backupId: string | undefined) {
  return useQuery({
    queryKey: backupKeys.detail(serverId ?? '', backupId ?? ''),
    queryFn: () => getBackup(serverId!, backupId!),
    enabled: Boolean(serverId) && Boolean(backupId),
    refetchOnWindowFocus: false,
    retry: false,
  })
}

/** `POST /servers/{id}/backups` — crear backup manual. */
export function useCreateBackup(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateBackupRequest) => createBackup(serverId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: backupKeys.all(serverId) })
    },
  })
}

/** `POST /servers/{id}/backups/{backup_id}/restore` — restaurar sobre su mundo. */
export function useRestoreBackup(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (backupId: string) => restoreBackup(serverId, backupId),
    onSuccess: () => {
      // Restaurar reescribe el mundo en disco: refresca backups y mundos.
      queryClient.invalidateQueries({ queryKey: backupKeys.all(serverId) })
      queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    },
  })
}

/** `POST /servers/{id}/backups/{backup_id}/validate` — verifica integridad. */
export function useValidateBackup(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (backupId: string) => validateBackup(serverId, backupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: backupKeys.all(serverId) })
    },
  })
}

/** `GET /servers/{id}/backups/{backup_id}/download` — artefacto `.tar.zst`. */
export function useDownloadBackup(serverId: string) {
  return useMutation({
    mutationFn: (backupId: string) => downloadBackup(serverId, backupId),
  })
}

/** `DELETE /servers/{id}/backups/{backup_id}` (204). */
export function useDeleteBackup(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (backupId: string) => deleteBackup(serverId, backupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: backupKeys.all(serverId) })
    },
  })
}

/** `POST /servers/{id}/backups/prune` — retención keep-last-N por mundo. */
export function usePruneBackups(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (keepLastN?: number) => pruneBackups(serverId, keepLastN),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: backupKeys.all(serverId) })
    },
  })
}
