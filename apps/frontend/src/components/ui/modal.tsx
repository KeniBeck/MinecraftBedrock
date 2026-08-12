import * as React from 'react'

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

/**
 * Modal base reutilizable (componente padre de los modales del frontend):
 * concentra el contenedor con estilos (overlay + panel pixel) y el encabezado;
 * el contenido (inputs, selects, botones…) se pasa por `children`/`footer`.
 * Los diálogos específicos (`ConfirmDialog`, `PromptDialog`, los de cada
 * feature) extienden este componente en vez de repetir el marcado de Dialog.
 */
export interface ModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string | undefined
  children?: React.ReactNode
  footer?: React.ReactNode
  className?: string | undefined
}

export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  className,
}: ModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn('max-w-md', className)}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {children}
        {footer && <div className="flex justify-end gap-2 pt-2">{footer}</div>}
      </DialogContent>
    </Dialog>
  )
}
