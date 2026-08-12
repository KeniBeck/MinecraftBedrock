import { type FormEvent, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Modal } from '@/components/ui/modal'

/**
 * Modal de formulario (extiende `Modal`): envuelve el contenido en un `<form>`
 * con la alerta de error, los botones Cancelar/Confirmar en el footer y el
 * estado `busy`. Los diálogos de creación/ajustes de cada feature lo usan en
 * vez de repetir la estructura de Dialog + error + footer.
 *
 * El botón de confirmar está DENTRO del `<form>` (submit nativo, se envía con
 * Enter); `onSubmit` recibe la acción async del diálogo. `error` se muestra en
 * una alerta `role="alert"` (mismo estilo que el resto del frontend).
 */
export interface FormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string | undefined
  onSubmit: () => void | Promise<void>
  busy?: boolean
  error?: string | null
  submitLabel?: string
  submittingLabel?: string
  submitVariant?: 'default' | 'create' | 'destructive' | 'secondary'
  submitDisabled?: boolean
  cancelLabel?: string
  /** testid para el botón de confirmar (los tests de los diálogos lo usan). */
  submitTestId?: string | undefined
  className?: string | undefined
  children: ReactNode
}

export function FormDialog({
  open,
  onOpenChange,
  title,
  description,
  onSubmit,
  busy = false,
  error,
  submitLabel = 'Guardar',
  submittingLabel = 'Guardando…',
  submitVariant = 'create',
  submitDisabled = false,
  cancelLabel = 'Cancelar',
  submitTestId,
  className,
  children,
}: FormDialogProps) {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    void onSubmit()
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      className={className}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div
            role="alert"
            className="rounded-none border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300"
          >
            {error}
          </div>
        )}
        {children}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button
            type="submit"
            variant={submitVariant}
            pixel
            disabled={busy || submitDisabled}
            data-testid={submitTestId}
          >
            {busy ? submittingLabel : submitLabel}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
