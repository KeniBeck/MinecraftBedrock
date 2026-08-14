import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import { useAddAllowlistEntry } from '../hooks'

interface AddAllowlistDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
}

/**
 * Añadir una entrada a la allowlist: `POST /servers/{id}/permissions/allowlist`
 * con `{name, xuid}`. El backend exige xuid no vacío (a diferencia de lo
 * sugerido en el enunciado, no es opcional).
 */
export function AddAllowlistDialog({ open, onOpenChange, serverId }: AddAllowlistDialogProps) {
  const [name, setName] = useState('')
  const [xuid, setXuid] = useState('')
  const [error, setError] = useState<string | null>(null)

  const add = useAddAllowlistEntry(serverId)

  const handleSubmit = async () => {
    setError(null)
    try {
      await add.mutateAsync({ name: name.trim(), xuid: xuid.trim() })
      onOpenChange(false)
      setName('')
      setXuid('')
    } catch (err) {
      setError(getApiMessage(err, 'Error al añadir a la allowlist'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setName('')
          setXuid('')
        }
        onOpenChange(next)
      }}
      title="Añadir a la allowlist"
      description="El jugador quedará habilitado para entrar al servidor."
      onSubmit={handleSubmit}
      busy={add.isPending}
      error={error}
      submitLabel="Añadir"
      submittingLabel="Añadiendo…"
      submitVariant="create"
      submitDisabled={!name.trim() || !xuid.trim()}
      submitTestId="add-allowlist-submit"
    >
      <FormField label="Gamertag" htmlFor="allowlist-name">
        <Input
          id="allowlist-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nombre dentro del juego"
        />
      </FormField>
      <FormField label="XUID" htmlFor="allowlist-xuid" hint="Identificador único del jugador.">
        <Input
          id="allowlist-xuid"
          value={xuid}
          onChange={(e) => setXuid(e.target.value)}
          className="font-mono"
          placeholder="e.g. 2535461234567890"
        />
      </FormField>
    </FormDialog>
  )
}