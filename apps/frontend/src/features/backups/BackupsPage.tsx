import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { getApiCode, getApiMessage } from '@/lib/api/client'
import { useCan } from '@/lib/auth/useCan'
import type { Backup } from '@/lib/api/backups'
import { BackupList } from './components/BackupList'
import { CreateBackupDialog } from './components/CreateBackupDialog'
import { PruneDialog } from './components/PruneDialog'
import { RestoreBackupDialog } from './components/RestoreBackupDialog'
import {
  useBackups,
  useDeleteBackup,
  useDownloadBackup,
  usePruneBackups,
  useRestoreBackup,
  useValidateBackup,
} from './hooks'
import { Plus, Scissors } from 'lucide-react'

export function BackupsPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const canCreate = useCan('backup.create')
  const canRestore = useCan('backup.restore')
  const canDelete = useCan('backup.delete')
  const canPrune = useCan('backup.prune')
  const canValidate = useCan('backup.validate')
  const canDownload = useCan('backup.download')

  const [createOpen, setCreateOpen] = useState(false)
  const [pruneOpen, setPruneOpen] = useState(false)
  const [restoring, setRestoring] = useState<Backup | null>(null)
  const [deleting, setDeleting] = useState<Backup | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [workingId, setWorkingId] = useState<string | null>(null)
  const downloadAnchor = useRef<HTMLAnchorElement | null>(null)

  const { data: backups, isLoading, isError, error } = useBackups(serverId)
  const restore = useRestoreBackup(serverId ?? '')
  const validate = useValidateBackup(serverId ?? '')
  const download = useDownloadBackup(serverId ?? '')
  const remove = useDeleteBackup(serverId ?? '')
  const prune = usePruneBackups(serverId ?? '')

  if (!serverId) return null

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Cargando backups…</div>
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        {getApiMessage(error, 'No se pudieron cargar los backups')}
      </div>
    )
  }

  const handleRestore = () => {
    if (!restoring) return
    const backup = restoring
    setRestoring(null)
    restore.mutate(backup.id, {
      onError: (err) => setActionError(getApiMessage(err)),
    })
  }

  const handleValidate = (backup: Backup) => {
    setWorkingId(backup.id)
    validate.mutate(backup.id, {
      onSettled: () => setWorkingId(null),
      onError: (err) => {
        if (getApiCode(err) === 'BACKUP.CORRUPT') {
          setActionError(`El backup de "${backup.world_name}" está corrupto (${new Date(backup.created_at).toLocaleString()}).`)
        } else {
          setActionError(getApiMessage(err))
        }
      },
    })
  }

  const handleDownload = async (backup: Backup) => {
    setWorkingId(backup.id)
    try {
      const blob = await download.mutateAsync(backup.id)
      const url = URL.createObjectURL(blob)
      const anchor = downloadAnchor.current
      if (anchor) {
        anchor.href = url
        anchor.download = `${backup.world_name}-${backup.id}.tar.zst`
        anchor.click()
      }
      URL.revokeObjectURL(url)
    } catch (err) {
      setActionError(getApiMessage(err, 'Error al descargar el backup'))
    } finally {
      setWorkingId(null)
    }
  }

  const handleDelete = () => {
    if (!deleting) return
    const backup = deleting
    setDeleting(null)
    remove.mutate(backup.id, {
      onError: (err) => setActionError(getApiMessage(err)),
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Backups</h1>
        <div className="flex gap-2">
          {canPrune && (
            <Button variant="secondary" pixel onClick={() => setPruneOpen(true)}>
              <Scissors className="mr-1 h-4 w-4" />
              Retención
            </Button>
          )}
          {canCreate && (
            <Button variant="create" pixel onClick={() => setCreateOpen(true)}>
              <Plus className="mr-1 h-4 w-4" />
              Crear backup
            </Button>
          )}
        </div>
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
        >
          {actionError}
        </div>
      )}

      <BackupList
        backups={backups ?? []}
        onRestore={canRestore ? (backup) => setRestoring(backup) : undefined}
        onValidate={canValidate ? handleValidate : undefined}
        onDownload={canDownload ? handleDownload : undefined}
        onDelete={canDelete ? (backup) => setDeleting(backup) : undefined}
        isWorking={workingId !== null || restore.isPending || remove.isPending}
      />

      <a ref={downloadAnchor} className="hidden" aria-hidden="true" />

      <CreateBackupDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        serverId={serverId}
      />

      <PruneDialog
        open={pruneOpen}
        onOpenChange={setPruneOpen}
        busy={prune.isPending}
        onSubmit={async (keepLastN) => {
          await prune.mutateAsync(keepLastN)
        }}
      />

      <RestoreBackupDialog
        backup={restoring}
        onOpenChange={(next) => {
          if (!next) setRestoring(null)
        }}
        busy={restore.isPending}
        onConfirm={handleRestore}
      />

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(next) => {
          if (!next) setDeleting(null)
        }}
        title="Eliminar backup"
        description={
          deleting
            ? `¿Eliminar el backup de "${deleting.world_name}" del ${new Date(deleting.created_at).toLocaleString()}? El artefacto y su registro se borrarán.`
            : undefined
        }
        confirmLabel="Eliminar"
        destructive
        busy={remove.isPending}
        onConfirm={handleDelete}
      />
    </div>
  )
}
