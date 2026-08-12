import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatBytes } from '@/lib/utils'
import { formatDateTime } from '@/lib/format'
import type { Backup } from '@/lib/api/backups'
import { Archive, CheckCircle2, Download, MoreHorizontal, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react'

interface BackupListProps {
  backups: Backup[]
  /** Solo se renderiza si hay permiso (`backup.restore`). */
  onRestore?: ((backup: Backup) => void) | undefined
  /** Solo se renderiza si hay permiso (`backup.validate`). */
  onValidate?: ((backup: Backup) => void) | undefined
  /** Solo se renderiza si hay permiso (`backup.download`). */
  onDownload?: ((backup: Backup) => void) | undefined
  /** Solo se renderiza si hay permiso (`backup.delete`). */
  onDelete?: ((backup: Backup) => void) | undefined
  isWorking: boolean
}

/** Badge de estado del backup con los colores acordados. */
function StatusBadge({ backup }: { backup: Backup }) {
  const styles: Record<Backup['state'], string> = {
    completed: 'border-emerald-500/30 bg-emerald-500/20 text-emerald-300',
    running: 'border-amber-500/30 bg-amber-500/20 text-amber-300',
    failed: 'border-red-500/30 bg-red-500/20 text-red-300',
    corrupt: 'border-red-500/50 bg-red-500/30 text-red-300',
    deleted: 'border-white/10 bg-white/5 text-muted-foreground',
  }
  return (
    <span
      className={`rounded-none border px-2 py-0.5 text-xs font-medium ${styles[backup.state]}`}
    >
      {backup.state === 'running' ? 'En progreso' : backup.state}
    </span>
  )
}

export function BackupList({
  backups,
  onRestore,
  onValidate,
  onDownload,
  onDelete,
  isWorking,
}: BackupListProps) {
  if (backups.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No hay backups aún. Crea uno desde el botón "Crear backup".
      </div>
    )
  }

  const hasMenu = Boolean(onValidate || onDownload || onDelete)

  return (
    <div className="space-y-3">
      {backups.map((backup) => (
        <div
          key={backup.id}
          className="flex items-center justify-between rounded-xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <Archive className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate font-medium">{backup.world_name}</span>
              <StatusBadge backup={backup} />
              {backup.protected && (
                <span className="flex items-center gap-1 text-xs text-amber-300">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Protegido
                </span>
              )}
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
              <span>{formatBytes(backup.size_bytes)}</span>
              <span>{formatDateTime(backup.created_at)}</span>
              {backup.entries.length > 0 && <span>{backup.entries.length} entradas</span>}
              {backup.duration_seconds !== null && backup.duration_seconds !== undefined && (
                <span>{backup.duration_seconds}s</span>
              )}
              {backup.error && <span className="text-red-300">{backup.error}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onRestore && (
              <Button
                variant="default"
                size="sm"
                pixel
                onClick={() => onRestore(backup)}
                disabled={isWorking || backup.state === 'running'}
              >
                <RotateCcw className="mr-1 h-4 w-4" />
                Restaurar
              </Button>
            )}
            {hasMenu && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" disabled={isWorking}>
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {onDownload && (
                    <DropdownMenuItem
                      onClick={() => onDownload(backup)}
                      disabled={backup.state !== 'completed'}
                    >
                      <Download className="mr-2 h-4 w-4" />
                      Descargar
                    </DropdownMenuItem>
                  )}
                  {onValidate && (
                    <DropdownMenuItem onClick={() => onValidate(backup)} disabled={isWorking}>
                      <CheckCircle2 className="mr-2 h-4 w-4" />
                      Validar
                    </DropdownMenuItem>
                  )}
                  {onDelete && (
                    <DropdownMenuItem
                      className="text-red-500"
                      onClick={() => onDelete(backup)}
                      disabled={backup.protected || backup.state === 'running'}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      {backup.protected ? 'Eliminar (protegido)' : 'Eliminar'}
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
