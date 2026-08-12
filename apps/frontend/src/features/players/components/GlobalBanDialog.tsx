import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiCode, getApiMessage } from '@/lib/api/client'
import { useBanPlayerGlobally } from '../hooks'

interface GlobalBanDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * Ban panel-wide (admin/super_admin, `player.ban.global`): `POST /players/bans/
 * global` con `{gamertag, xuid?, reason?, expires_at?}`. `gamertag` es
 * obligatorio (schema GlobalBanRequest); la fecha se envía como ISO local
 * (el backend la normaliza a UTC).
 */
export function GlobalBanDialog({ open, onOpenChange }: GlobalBanDialogProps) {
  const [gamertag, setGamertag] = useState('')
  const [xuid, setXuid] = useState('')
  const [reason, setReason] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [error, setError] = useState<string | null>(null)
  const ban = useBanPlayerGlobally()

  function reset() {
    setGamertag('')
    setXuid('')
    setReason('')
    setExpiresAt('')
    setError(null)
  }

  async function handleSubmit() {
    setError(null)
    try {
      await ban.mutateAsync({
        gamertag: gamertag.trim(),
        ...(xuid.trim() ? { xuid: xuid.trim() } : {}),
        ...(reason.trim() ? { reason: reason.trim() } : {}),
        ...(expiresAt ? { expires_at: new Date(expiresAt).toISOString() } : {}),
      })
      onOpenChange(false)
      reset()
    } catch (err) {
      setError(getApiMessage(err, 'No se pudo aplicar el ban global'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset()
      }}
      title="Ban global"
      description="Bloquea al jugador en TODOS los servidores del panel. Solo admin/super_admin."
      onSubmit={handleSubmit}
      busy={ban.isPending}
      error={error}
      submitLabel="Banear"
      submittingLabel="Baneando…"
      submitTestId="global-ban-submit"
      submitDisabled={!gamertag.trim()}
    >
      <FormField
        label="Gamertag"
        htmlFor="global-ban-gamertag"
        error={
          getApiCode(error) === 'PLAYER.NOT_FOUND' ? 'El gamertag no se encontró en el panel' : undefined
        }
      >
        <Input
          id="global-ban-gamertag"
          value={gamertag}
          onChange={(e) => setGamertag(e.target.value)}
          placeholder="Gamertag de Xbox"
          required
          maxLength={64}
        />
      </FormField>
      <FormField label="XUID (opcional)" htmlFor="global-ban-xuid">
        <Input
          id="global-ban-xuid"
          value={xuid}
          onChange={(e) => setXuid(e.target.value)}
          placeholder="Si lo conoces, evita resolverlo"
          maxLength={32}
        />
      </FormField>
      <FormField label="Motivo (opcional)" htmlFor="global-ban-reason">
        <Input
          id="global-ban-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Ej. Tóxico en el chat"
          maxLength={255}
        />
      </FormField>
      <FormField label="Expira (opcional)" htmlFor="global-ban-expires">
        <Input
          id="global-ban-expires"
          type="datetime-local"
          value={expiresAt}
          onChange={(e) => setExpiresAt(e.target.value)}
        />
      </FormField>
    </FormDialog>
  )
}
