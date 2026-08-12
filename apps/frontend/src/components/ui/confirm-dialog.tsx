import { Button } from '@/components/ui/button'
import { Modal } from '@/components/ui/modal'

/**
 * Diálogo de confirmación (reemplaza `window.confirm`): título + descripción
 * + botones Cancelar/Confirmar. El color del botón de confirmar es
 * `destructive` si la acción es peligrosa; `busy` muestra "Confirmando…" y
 * deshabilita el cierre vía overlay. `onConfirm` decide si cierra el diálogo.
 */
export interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string | undefined
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
  busy?: boolean
  onConfirm: () => void
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  destructive = false,
  busy = false,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      footer={
        <>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={destructive ? 'destructive' : 'default'}
            pixel
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? 'Confirmando…' : confirmLabel}
          </Button>
        </>
      }
    />
  )
}
