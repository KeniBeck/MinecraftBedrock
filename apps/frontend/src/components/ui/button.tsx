import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-black text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          'bg-slate-600 text-white border-white/10 shadow-[inset_1px_1px_0_rgba(255,255,255,0.16),inset_-1px_-1px_0_rgba(0,0,0,0.64)] hover:bg-slate-500',
        destructive:
          'bg-red-700 text-white border-white/10 shadow-[inset_1px_1px_0_rgba(255,255,255,0.16),inset_-1px_-1px_0_rgba(0,0,0,0.64)] hover:bg-red-600',
        outline:
          'border-white/10 bg-slate-900/70 text-foreground shadow-[inset_1px_1px_0_rgba(255,255,255,.15),inset_-1px_-1px_0_rgba(0,0,0,.4)] hover:bg-white/10',
        secondary:
          'bg-slate-700 text-white border-white/10 shadow-[inset_1px_1px_0_rgba(255,255,255,0.16),inset_-1px_-1px_0_rgba(0,0,0,0.64)] hover:bg-slate-600',
        ghost:
          'border-transparent bg-transparent text-foreground hover:bg-white/10',
        link: 'text-primary underline-offset-4 hover:underline',
        // Colores semánticos del mockup (frontend-standards §9.3) con bisel Minecraft.
        start:
          'bg-emerald-500 text-white border-white/10 shadow-[inset_1px_1px_0_rgba(255,255,255,0.16),inset_-1px_-1px_0_rgba(0,0,0,0.64)] hover:bg-emerald-600',
        stop:
          'bg-red-600 text-white border-white/10 shadow-[inset_1px_1px_0_rgba(255,255,255,0.16),inset_-1px_-1px_0_rgba(0,0,0,0.64)] hover:bg-red-700',
        restart:
          'bg-slate-600 text-white border-white/10 shadow-[inset_1px_1px_0_rgba(255,255,255,0.16),inset_-1px_-1px_0_rgba(0,0,0,0.64)] hover:bg-slate-700',
        backup:
          'bg-amber-600 text-white border-white/10 shadow-[inset_1px_1px_0_rgba(255,255,255,0.16),inset_-1px_-1px_0_rgba(0,0,0,0.64)] hover:bg-amber-700',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 px-3',
        lg: 'h-11 px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }
