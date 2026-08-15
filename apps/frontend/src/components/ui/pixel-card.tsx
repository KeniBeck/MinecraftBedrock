import * as React from 'react'

import { cn } from '@/lib/utils'

export interface PixelCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Desactiva el efecto hover (brillo + levante) que `pixel-card` aplica por
   * defecto. Útil para cards no interactivas, como las de Ajustes.
   */
  noHover?: boolean
}

/**
 * Card con el estilo del mockup `pixel-card` (textura + bisel Minecraft).
 * Por defecto tiene hover (brillo blanco + levante); `noHover` lo desactiva.
 */
export const PixelCard = React.forwardRef<HTMLDivElement, PixelCardProps>(
  ({ className, noHover, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('pixel-card', noHover && 'no-hover', className)}
      {...props}
    />
  ),
)
PixelCard.displayName = 'PixelCard'
