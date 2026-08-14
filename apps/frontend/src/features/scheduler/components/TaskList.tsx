import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatDateTime } from '@/lib/format'
import type { ScheduleTask } from '@/lib/api/scheduler'
import type { TaskType } from '../types'
import { CalendarClock, MoreHorizontal, Play, Pencil, Trash2 } from 'lucide-react'

interface TaskListProps {
  tasks: ScheduleTask[]
  /** Solo se renderiza si hay permiso (`task.run`). */
  onRun?: ((task: ScheduleTask) => void) | undefined
  /** Solo se renderiza si hay permiso (`task.update`). */
  onEdit?: ((task: ScheduleTask) => void) | undefined
  /** Solo se renderiza si hay permiso (`task.delete`). */
  onDelete?: ((task: ScheduleTask) => void) | undefined
  isWorking: boolean
}

const TYPE_LABELS: Record<TaskType, string> = {
  backup: 'Backup',
  restart: 'Reinicio',
  command: 'Comando',
}

const STATE_LABELS: Record<string, string> = {
  active: 'Activa',
  paused: 'Pausada',
  running: 'Ejecutando',
  disabled: 'Desactivada',
}

/** Badge de estado con los colores acordados (activa=verde, otras=gris/ámbar). */
function StateBadge({ task }: { task: ScheduleTask }) {
  const styles: Record<string, string> = {
    active: 'border-emerald-500/30 bg-emerald-500/20 text-emerald-300',
    paused: 'border-amber-500/30 bg-amber-500/20 text-amber-300',
    running: 'border-amber-500/50 bg-amber-500/30 text-amber-300',
    disabled: 'border-white/10 bg-white/5 text-muted-foreground',
  }
  const label = STATE_LABELS[task.state] ?? task.state
  return (
    <span
      className={`rounded-none border px-2 py-0.5 text-xs font-medium ${styles[task.state] ?? styles.disabled}`}
    >
      {label}
    </span>
  )
}

export function TaskList({ tasks, onRun, onEdit, onDelete, isWorking }: TaskListProps) {
  if (tasks.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No hay tareas programadas. Crea una desde el botón "Nueva tarea".
      </div>
    )
  }

  const hasMenu = Boolean(onEdit || onDelete)

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <div
          key={task.id}
          className="flex items-center justify-between rounded-xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <CalendarClock className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="truncate font-medium">{task.name}</span>
              <StateBadge task={task} />
              <span className="rounded-none border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-muted-foreground">
                {TYPE_LABELS[task.type as TaskType] ?? task.type}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
              <span className="font-mono">{task.cron}</span>
              {task.next_run_at && <span>Próxima: {formatDateTime(task.next_run_at)}</span>}
              {task.last_run_at && <span>Última: {formatDateTime(task.last_run_at)}</span>}
              {task.last_result === 'ok' && <span className="text-emerald-300">Éxito</span>}
              {task.last_result && task.last_result !== 'ok' && (
                <span className="text-red-300">Falló</span>
              )}
              {task.failures > 0 && <span className="text-red-300">{task.failures} fallos</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onRun && (
              <Button
                variant="default"
                size="sm"
                pixel
                onClick={() => onRun(task)}
                disabled={isWorking || task.state === 'running'}
              >
                <Play className="mr-1 h-4 w-4" />
                Ejecutar
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
                  {onEdit && (
                    <DropdownMenuItem onClick={() => onEdit(task)} disabled={isWorking}>
                      <Pencil className="mr-2 h-4 w-4" />
                      Editar
                    </DropdownMenuItem>
                  )}
                  {onDelete && (
                    <DropdownMenuItem
                      className="text-red-500"
                      onClick={() => onDelete(task)}
                      disabled={isWorking || task.state === 'running'}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Eliminar
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