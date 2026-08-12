import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import { useBanPlayerOnServer } from '../hooks'

interface BanPlayerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
  /** XUID del jugador a banear (path `{player_id}` del endpoint). */
  xuid: string
}

/**
 * Ban por servidor (operator+, `permission.write`): `POST /servers/{id}/
 * players/{player_id}/ban` con `{reason?, expires_at?}` — responde 204 sin
 * body. El path usa `player_id` (el XUID del jugador). La gestión de bans por
 * servidor no tiene endpoint de listado; solo banear/desbanear.
 */
export function BanPlayerDialog({ open, onOpenChange, serverId, xuid }: BanPlayerDialogProps) {
  const [reason, setReason] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [error, setError] = useState<string | null>(null)
  const ban = useBanPlayerOnServer(serverId)

  function reset() {
    setReason('')
    setExpiresAt('')
    setError(null)
  }

  async function handleSubmit() {
    setError(null)
    try {
      await ban.mutateAsync({
        playerId: xuid,
        payload: {
          ...(reason.trim() ? { reason: reason.trim() } : {}),
          ...(expiresAt ? { expires_at: new Date(expiresAt).toISOString() } : {}),
        },
      })
      onOpenChange(false)
      reset()
    } catch (err) {
      setError(getApiMessage(err, 'No se pudo banear al jugador'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset()
      }}
      title="Banear jugador"
      description={`Se bloqueará al jugador ${xuid} en ESTE servidor.`}
      onSubmit={handleSubmit}
      busy={ban.isPending}
      error={error}
      submitLabel="Banear"
      submittingLabel="Baneando…"
    >
      <FormField label="Motivo (opcional)" htmlFor="ban-reason">
        <Input
          id="ban-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Ej. Griefing"
          maxLength={255}
        />
      </FormField>
      <FormField label="Expira (opcional)" htmlFor="ban-expires">
        <Input
          id="ban-expires"
          type="datetime-local"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
        />
      </FormField>
    </FormDialog>
  )
}
