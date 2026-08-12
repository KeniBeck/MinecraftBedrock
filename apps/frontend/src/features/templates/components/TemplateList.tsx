import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatBytes } from '@/lib/utils'
import type { Template } from '@/lib/api/templates'
import { MoreHorizontal, Trash2 } from 'lucide-react'

interface TemplateListProps {
  templates: Template[]
  onApply: (id: string) => void
  onDelete: (id: string) => void
  isApplying?: boolean
  isDeleting?: boolean
}

export function TemplateList({
  templates,
  onApply,
  onDelete,
  isApplying = false,
  isDeleting = false,
}: TemplateListProps) {
  if (templates.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No hay plantillas aún. Captura una desde un servidor.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {templates.map((template) => (
        <div
          key={template.id}
          className="flex items-center justify-between rounded-xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <span className="truncate font-medium">{template.name}</span>
            </div>
            <div className="mt-1 flex gap-4 text-xs text-muted-foreground">
              <span>v{template.version}</span>
              <span>{formatBytes(template.size_bytes)}</span>
              {template.created_at && (
                <span>{new Date(template.created_at).toLocaleDateString()}</span>
              )}
              {template.origin_world && <span>Mundo: {template.origin_world}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              pixel
              onClick={() => onApply(template.id)}
              disabled={isApplying}
            >
              Aplicar
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  className="text-red-500"
                  onClick={() => onDelete(template.id)}
                  disabled={isDeleting}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Eliminar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      ))}
    </div>
  )
}
