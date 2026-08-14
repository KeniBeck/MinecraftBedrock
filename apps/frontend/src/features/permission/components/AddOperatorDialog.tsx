import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import type { OperatorEntry } from '@/lib/api/permissions'
import { useSetOperator } from '../hooks'

interface AddOperatorDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
  /** Se dispara tras asignar el operador para actualizar la lista local. */
  onAdded?: ((entry: OperatorEntry) => void) | undefined
}

/**
 * Asignar nivel de operador a un jugador por XUID:
 * `PUT /servers/{id}/permissions/operators/{xuid}` con `{level: 'operator'}`.
 */
export function AddOperatorDialog({ open, onOpenChange, serverId, onAdded }: AddOperatorDialogProps) {
  const [xuid, setXuid] = useState('')
  const [error, setError] = useState<string | null>(null)

  const setOperator = useSetOperator(serverId)

  const handleSubmit = async () => {
    setError(null)
    try {
      const entry = await setOperator.mutateAsync({ xuid: xuid.trim(), level: 'operator' })
      onAdded?.(entry)
      onOpenChange(false)
      setXuid('')
    } catch (err) {
      setError(getApiMessage(err, 'Error al añadir el operador'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setXuid('')
        onOpenChange(next)
      }}
      title="Añadir operador"
      description="El jugador obtendrá privilegios de operador en el servidor."
      onSubmit={handleSubmit}
      busy={setOperator.isPending}
      error={error}
      submitLabel="Añadir"
      submittingLabel="Añadiendo…"
      submitVariant="create"
      submitDisabled={!xuid.trim()}
      submitTestId="add-operator-submit"
    >
      <FormField
        label="XUID"
        htmlFor="operator-xuid"
        hint="Identificador único del jugador. El nivel se asigna como operator."
      >
        <Input
          id="operator-xuid"
          value={xuid}
          onChange={(e) => setXuid(e.target.value)}
          className="font-mono"
          placeholder="e.g. 2535461234567890"
        />
      </FormField>
    </FormDialog>
  )
}