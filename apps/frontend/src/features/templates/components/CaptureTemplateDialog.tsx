import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import { useCaptureTemplate } from '../hooks'

interface CaptureTemplateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
}

export function CaptureTemplateDialog({ open, onOpenChange, serverId }: CaptureTemplateDialogProps) {
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const capture = useCaptureTemplate(serverId)

  const handleSubmit = async () => {
    setError(null)
    try {
      await capture.mutateAsync({ name })
      onOpenChange(false)
      setName('')
    } catch (err) {
      setError(getApiMessage(err, 'Error al capturar la plantilla'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Capturar plantilla"
      description="Se guarda una copia del mundo activo y de la configuración del servidor para poder reproducirla en otro."
      onSubmit={handleSubmit}
      busy={capture.isPending}
      error={error}
      submitLabel="Capturar"
      submittingLabel="Capturando…"
      submitDisabled={!name.trim()}
    >
      <FormField label="Nombre" htmlFor="template-name">
        <Input
          id="template-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Mi plantilla"
          required
          maxLength={255}
        />
      </FormField>
    </FormDialog>
  )
}
