import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { getApiMessage } from '@/lib/api/client'
import { useCan } from '@/lib/auth/useCan'
import type { ScheduleTask } from '@/lib/api/scheduler'
import { TaskList } from './components/TaskList'
import { CreateTaskDialog } from './components/CreateTaskDialog'
import { EditTaskDialog } from './components/EditTaskDialog'
import { useDeleteTask, useRunTask, useTasks } from './hooks'
import { Plus } from 'lucide-react'

export function SchedulerPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const canList = useCan('task.list')
  const canWrite = useCan('task.write')

  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState<ScheduleTask | null>(null)
  const [deleting, setDeleting] = useState<ScheduleTask | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [workingId, setWorkingId] = useState<string | null>(null)

  const { data: tasks, isLoading, isError, error } = useTasks(serverId)
  const remove = useDeleteTask(serverId ?? '')
  const run = useRunTask(serverId ?? '')

  if (!serverId) return null

  if (!canList) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        No tienes permisos para ver las tareas programadas.
      </div>
    )
  }

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Cargando tareas…</div>
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        {getApiMessage(error, 'No se pudieron cargar las tareas')}
      </div>
    )
  }

  const handleRun = (task: ScheduleTask) => {
    setWorkingId(task.id)
    run.mutate(task.id, {
      onSettled: () => setWorkingId(null),
      onError: (err) => setActionError(getApiMessage(err)),
    })
  }

  const handleDelete = () => {
    if (!deleting) return
    const task = deleting
    setDeleting(null)
    remove.mutate(task.id, {
      onError: (err) => setActionError(getApiMessage(err)),
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Programador</h1>
        {canWrite && (
          <Button variant="create" pixel onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Nueva tarea
          </Button>
        )}
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
        >
          {actionError}
        </div>
      )}

      <TaskList
        tasks={tasks ?? []}
        onRun={canWrite ? handleRun : undefined}
        onEdit={canWrite ? (task) => setEditing(task) : undefined}
        onDelete={canWrite ? (task) => setDeleting(task) : undefined}
        isWorking={workingId !== null || run.isPending || remove.isPending}
      />

      <CreateTaskDialog open={createOpen} onOpenChange={setCreateOpen} serverId={serverId} />

      {editing && (
        <EditTaskDialog task={editing} onOpenChange={(next) => { if (!next) setEditing(null) }} serverId={serverId} />
      )}

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(next) => {
          if (!next) setDeleting(null)
        }}
        title="Eliminar tarea"
        description={
          deleting
            ? `¿Eliminar la tarea "${deleting.name}"? Se borrará su programación y su historial.`
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