import { useEffect } from 'react'

import { FormField } from '@/components/ui/form-field'
import { Select } from '@/components/ui/select'
import { useWorlds } from '@/features/worlds/hooks'
import type { TaskType } from '../types'

interface TaskFormFieldsProps {
  type: TaskType
  onTypeChange: (type: TaskType) => void
  worldName: string
  onWorldNameChange: (name: string) => void
  commands: string
  onCommandsChange: (value: string) => void
  serverId: string
  enabled?: boolean
}

/**
 * Selector de tipo de tarea + campos de payload según el tipo:
 * - `backup` → lista de mundos (usa `useWorlds`, solo cuando `enabled`)
 * - `restart` → sin parámetros
 * - `command` → área de texto con comandos de consola (uno por línea)
 */
export function TaskFormFields({
  type,
  onTypeChange,
  worldName,
  onWorldNameChange,
  commands,
  onCommandsChange,
  serverId,
  enabled = true,
}: TaskFormFieldsProps) {
  const { data: worlds } = useWorlds(serverId, { enabled })
  const firstWorld = worlds?.[0]?.name ?? ''
  const effectiveWorld = worldName || firstWorld

  // Cuando cargan los mundos y aún no hay selección, preselecciona el primero
  // para que el payload del backup no quede vacío si no se toca el selector.
  useEffect(() => {
    if (worldName === '' && firstWorld) {
      onWorldNameChange(firstWorld)
    }
  }, [firstWorld, worldName, onWorldNameChange])

  return (
    <>
      <FormField label="Tipo" htmlFor="task-type">
        <Select
          id="task-type"
          value={type}
          onChange={(e) => onTypeChange(e.target.value as TaskType)}
        >
          <option value="backup">Backup (guardar un mundo)</option>
          <option value="restart">Reinicio (sin parámetros)</option>
          <option value="command">Comando (consola)</option>
        </Select>
      </FormField>

      {type === 'backup' && (
        <FormField
          label="Mundo"
          htmlFor="task-world"
          hint="La tarea hará un snapshot de este mundo."
        >
          <Select
            id="task-world"
            value={effectiveWorld}
            onChange={(e) => onWorldNameChange(e.target.value)}
            disabled={!worlds || worlds.length === 0}
          >
            {worlds && worlds.length > 0 ? (
              worlds.map((world) => (
                <option key={world.name} value={world.name}>
                  {world.name}
                </option>
              ))
            ) : (
              <option value="">No hay mundos en el servidor</option>
            )}
          </Select>
        </FormField>
      )}

      {type === 'command' && (
        <FormField
          label="Comandos"
          htmlFor="task-commands"
          hint="Uno por línea. Se ejecutan en la consola del servidor."
        >
          <textarea
            id="task-commands"
            value={commands}
            onChange={(e) => onCommandsChange(e.target.value)}
            rows={4}
            className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
          />
        </FormField>
      )}

      {type === 'restart' && (
        <p className="text-xs text-muted-foreground">Esta tarea reinicia el servidor.</p>
      )}
    </>
  )
}