import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import { isValidCron } from '../cron'
import { buildCreatePayload, useCreateTask } from '../hooks'
import type { TaskType } from '../types'
import { TaskFormFields } from './TaskFormFields'
import { CronEditor } from './CronEditor'

interface CreateTaskDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
}

/**
 * Crear una tarea programada: `POST /servers/{id}/schedule/tasks`. El payload
 * se arma según el tipo (backup → `world_name`, command → `commands`).
 */
export function CreateTaskDialog({ open, onOpenChange, serverId }: CreateTaskDialogProps) {
  const [name, setName] = useState('')
  const [type, setType] = useState<TaskType>('backup')
  const [cron, setCron] = useState('0 3 * * *')
  const [worldName, setWorldName] = useState('')
  const [commands, setCommands] = useState('')
  const [error, setError] = useState<string | null>(null)

  const create = useCreateTask(serverId)

  const handleSubmit = async () => {
    setError(null)
    try {
      const payload = buildCreatePayload({ name, type, cron, worldName, commands })
      await create.mutateAsync(payload)
      onOpenChange(false)
      setName('')
      setCron('0 3 * * *')
      setWorldName('')
      setCommands('')
      setType('backup')
    } catch (err) {
      setError(getApiMessage(err, 'Error al crear la tarea'))
    }
  }

  const commandsValid = type !== 'command' || commands.trim().length > 0

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setName('')
          setCron('0 3 * * *')
          setWorldName('')
          setCommands('')
          setType('backup')
        }
        onOpenChange(next)
      }}
      title="Nueva tarea"
      description="Programa una acción recurrente del servidor."
      onSubmit={handleSubmit}
      busy={create.isPending}
      error={error}
      submitLabel="Crear tarea"
      submittingLabel="Creando…"
      submitDisabled={!name.trim() || !isValidCron(cron) || !commandsValid}
    >
      <FormField label="Nombre" htmlFor="task-name">
        <Input
          id="task-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Backup diario del mundo"
        />
      </FormField>

      <CronEditor key={open ? 'open' : 'closed'} value={cron} onChange={setCron} />

      <TaskFormFields
        type={type}
        onTypeChange={setType}
        worldName={worldName}
        onWorldNameChange={setWorldName}
        commands={commands}
        onCommandsChange={setCommands}
        serverId={serverId}
        enabled={open}
      />
    </FormDialog>
  )
}