import * as React from 'react'

import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

/**
 * Campo de formulario estándar: label + control (hijo) + hint + error. Se usa
 * dentro de los formularios de los diálogos para evitar repetir el marcado de
 * `space-y-2` + Label + mensaje de error en cada campo.
 */
export interface FormFieldProps {
  label: string
  htmlFor?: string | undefined
  hint?: string | undefined
  error?: string | undefined
  className?: string | undefined
  children: React.ReactNode
}

export function FormField({ label, htmlFor, hint, error, className, children }: FormFieldProps) {
  return (
    <div className={cn('space-y-2', className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="text-xs text-red-300">{error}</p>}
    </div>
  )
}
