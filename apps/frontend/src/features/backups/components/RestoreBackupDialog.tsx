import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import type { Backup } from '@/lib/api/backups'

interface RestoreBackupDialogProps {
  backup: Backup | null
  onOpenChange: (open: boolean) => void
  busy: boolean
  onConfirm: () => void
}

/**
 * Restaurar un backup sobre su mundo. El backend real NO acepta un
 * `world_name` destino: `POST /servers/{id}/backups/{backup_id}/restore` sin
 * body restaura sobre `worlds/<world_name>/` del propio backup (§8.6), así
 * que esto es una confirmación destructiva simple.
 */
export function RestoreBackupDialog({
  backup,
  onOpenChange,
  busy,
  onConfirm,
}: RestoreBackupDialogProps) {
  return (
    <ConfirmDialog
      open={backup !== null}
      onOpenChange={onOpenChange}
      title="Restaurar backup"
      description={
        backup
          ? `Se sobrescribirá el mundo "${backup.world_name}" con el contenido de este backup (${backup.created_at}). Esta acción no se puede deshacer.`
          : undefined
      }
      confirmLabel="Restaurar"
      destructive
      busy={busy}
      onConfirm={onConfirm}
    />
  )
}
