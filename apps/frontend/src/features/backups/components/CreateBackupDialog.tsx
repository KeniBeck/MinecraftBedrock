import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Select } from '@/components/ui/select'
import { getApiMessage } from '@/lib/api/client'
import { useWorlds } from '@/features/worlds/hooks'
import { useCreateBackup } from '../hooks'

interface CreateBackupDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
}

/**
 * Crear un backup manual: `POST /servers/{id}/backups` con `{world_name,
 * protected?}`. El backend NO expone un listado de mundos propio; se reusa
 * `useWorlds` (ya existente) para el selector.
 */
export function CreateBackupDialog({ open, onOpenChange, serverId }: CreateBackupDialogProps) {
  const [worldName, setWorldName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { data: worlds } = useWorlds(serverId, { enabled: open })
  const create = useCreateBackup(serverId)

  // Valor efectivo: si no hay selección previa, preselecciona el primer mundo.
  const effectiveWorld = worldName || worlds?.[0]?.name || ''

  const handleSubmit = async () => {
    setError(null)
    try {
      await create.mutateAsync({ world_name: effectiveWorld })
      onOpenChange(false)
      setWorldName('')
    } catch (err) {
      setError(getApiMessage(err, 'Error al crear el backup'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setWorldName('')
        onOpenChange(next)
      }}
      title="Crear backup"
      description="Se hace una copia del mundo elegido. El servidor no se detiene."
      onSubmit={handleSubmit}
      busy={create.isPending}
      error={error}
      submitLabel="Crear backup"
      submittingLabel="Creando…"
      submitDisabled={!effectiveWorld.trim()}
    >
      <FormField label="Mundo" htmlFor="backup-world">
        <Select
          id="backup-world"
          value={effectiveWorld}
          onChange={(e) => setWorldName(e.target.value)}
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
    </FormDialog>
  )
}
