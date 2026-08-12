import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'

interface PruneDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  busy: boolean
  onSubmit: (keepLastN: number) => Promise<void>
}

/**
 * Aplicar retención keep-last-N por mundo: `POST /servers/{id}/backups/prune`
 * con `{keep_last_n}` (default 10). Destructivo — elimina los backups que
 * excedan el límite (los protegidos se conservan siempre).
 */
export function PruneDialog({ open, onOpenChange, busy, onSubmit }: PruneDialogProps) {
  const [keepLast, setKeepLast] = useState('10')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    setError(null)
    const parsed = Number(keepLast)
    if (!Number.isInteger(parsed) || parsed < 0) {
      setError('Debe ser un número entero mayor o igual a 0')
      return
    }
    try {
      await onSubmit(parsed)
      onOpenChange(false)
      setKeepLast('10')
    } catch (err) {
      setError(getApiMessage(err, 'Error al aplicar la retención'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setKeepLast('10')
        onOpenChange(next)
      }}
      title="Aplicar retención"
      description="Conserva solo los N backups más recientes de cada mundo y elimina el resto (los protegidos se mantienen siempre)."
      onSubmit={handleSubmit}
      busy={busy}
      error={error}
      submitLabel="Aplicar"
      submittingLabel="Aplicando…"
      submitVariant="destructive"
      submitDisabled={keepLast.trim() === ''}
    >
      <FormField
        label="Backups a conservar por mundo"
        htmlFor="prune-keep-last"
        hint="0 elimina todos los backups no protegidos."
      >
        <Input
          id="prune-keep-last"
          type="number"
          min={0}
          step={1}
          value={keepLast}
          onChange={(e) => setKeepLast(e.target.value)}
          required
        />
      </FormField>
    </FormDialog>
  )
}
