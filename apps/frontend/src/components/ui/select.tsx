import * as React from 'react'

import { cn } from '@/lib/utils'

/**
 * Select estándar (estilo de `CreateWorldDialog`/`EditWorldDialog`, que lo
 * repetían como `selectClass`). Mismas clases de focus/disabled y opciones con
 * fondo oscuro para que sean legibles sobre el panel pixelado.
 */
const Select = React.forwardRef<HTMLSelectElement, React.ComponentProps<'select'>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:cursor-not-allowed disabled:opacity-50',
        '[&>option]:bg-slate-900 [&>option]:text-slate-100',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
)
Select.displayName = 'Select'

export { Select }
