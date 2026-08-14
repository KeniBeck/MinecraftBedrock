import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import type { ScheduleTask } from '@/lib/api/scheduler'
import { isValidCron } from '../cron'
import { buildUpdatePayload, useUpdateTask } from '../hooks'
import type { TaskType } from '../types'
import { TaskFormFields } from './TaskFormFields'
import { CronEditor } from './CronEditor'

interface EditTaskDialogProps {
  task: ScheduleTask | null
  onOpenChange: (open: boolean) => void
  serverId: string
}

/** Deriva los valores iniciales del formulario a partir de la tarea. */
function initialValues(task: ScheduleTask) {
  const commands = Array.isArray(task.payload.commands)
    ? (task.payload.commands as string[]).join('\n')
    : ''
  return {
    name: task.name,
    type: (task.type as TaskType) ?? 'backup',
    cron: task.cron,
    worldName: typeof task.payload.world_name === 'string' ? task.payload.world_name : '',
    commands,
  }
}

/**
 * Editar una tarea programada: `PATCH /servers/{id}/schedule/tasks/{task_id}`.
 * Reutiliza el selector de tipo/payload de `TaskFormFields`.
 */
export function EditTaskDialog({ task, onOpenChange, serverId }: EditTaskDialogProps) {
  const initial = task ? initialValues(task) : null
  const [name, setName] = useState(initial?.name ?? '')
  const [type, setType] = useState<TaskType>(initial?.type ?? 'backup')
  const [cron, setCron] = useState(initial?.cron ?? '')
  const [worldName, setWorldName] = useState(initial?.worldName ?? '')
  const [commands, setCommands] = useState(initial?.commands ?? '')
  const [error, setError] = useState<string | null>(null)

  const update = useUpdateTask(serverId)

  if (!task) return null

  const handleSubmit = async () => {
    setError(null)
    try {
      const payload = buildUpdatePayload(task, { name, type, cron, worldName, commands })
      await update.mutateAsync({ taskId: task.id, payload })
      onOpenChange(false)
    } catch (err) {
      setError(getApiMessage(err, 'Error al guardar la tarea'))
    }
  }

  const commandsValid = type !== 'command' || commands.trim().length > 0

  return (
    <FormDialog
      open
      onOpenChange={onOpenChange}
      title="Editar tarea"
      description={task.name}
      onSubmit={handleSubmit}
      busy={update.isPending}
      error={error}
      submitLabel="Guardar"
      submittingLabel="Guardando…"
      submitDisabled={!name.trim() || !isValidCron(cron) || !commandsValid}
    >
      <FormField label="Nombre" htmlFor="task-name">
        <Input
          id="task-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </FormField>

      <CronEditor value={cron} onChange={setCron} />

      <TaskFormFields
        type={type}
        onTypeChange={setType}
        worldName={worldName}
        onWorldNameChange={setWorldName}
        commands={commands}
        onCommandsChange={setCommands}
        serverId={serverId}
        enabled={Boolean(task)}
      />
    </FormDialog>
  )
}