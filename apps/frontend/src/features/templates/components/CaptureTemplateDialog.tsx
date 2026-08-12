import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCaptureTemplate } from '../hooks'
import { getApiMessage } from '@/lib/api/client'

interface CaptureTemplateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
}

export function CaptureTemplateDialog({ open, onOpenChange, serverId }: CaptureTemplateDialogProps) {
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const capture = useCaptureTemplate(serverId)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Capturar plantilla</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="template-name">Nombre</Label>
            <Input
              id="template-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Mi plantilla"
              required
              maxLength={255}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Se guarda una copia del mundo activo y de la configuración del
            servidor para poder reproducirla en otro servidor.
          </p>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" variant="create" pixel disabled={capture.isPending || !name}>
              {capture.isPending ? 'Capturando…' : 'Capturar'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
