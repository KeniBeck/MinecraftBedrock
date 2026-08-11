import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatBytes } from '@/lib/utils'
import type { World } from '@/lib/api/worlds'
import { CheckCircle, Copy, Download, MoreHorizontal, Settings2, Trash2 } from 'lucide-react'

interface WorldListProps {
  worlds: World[]
  onActivate: (name: string) => void
  onEdit: (world: World) => void
  onDuplicate: (name: string) => void
  onExport: (name: string) => void
  onDelete: (name: string) => void
  isActivating?: boolean
  isDuplicating?: boolean
  isExporting?: boolean
  isDeleting?: boolean
}

export function WorldList({
  worlds,
  onActivate,
  onEdit,
  onDuplicate,
  onExport,
  onDelete,
  isActivating = false,
  isDuplicating = false,
  isExporting = false,
  isDeleting = false,
}: WorldListProps) {
  if (worlds.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No hay mundos aún. Crea uno o importa un `.mcworld`.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {worlds.map((world) => (
        <div
          key={world.id}
          className="flex items-center justify-between rounded-xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <span className="truncate font-medium">{world.name}</span>
              {world.activated && (
                <Badge
                  variant="default"
                  className="border-emerald-500/30 bg-emerald-500/20 text-emerald-300"
                >
                  Activo
                </Badge>
              )}
            </div>
            <div className="mt-1 flex gap-4 text-xs text-muted-foreground">
              <span>{formatBytes(world.size_bytes)}</span>
              <span>{new Date(world.created_at).toLocaleDateString()}</span>
              {world.gamemode && <span>Modo: {world.gamemode}</span>}
              {world.difficulty && <span>Dificultad: {world.difficulty}</span>}
              {world.view_distance != null && <span>Chunks: {world.view_distance}</span>}
              {world.seed && <span className="truncate">Semilla: {world.seed}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              pixel
              disabled={world.activated || isActivating}
              onClick={() => onActivate(world.name)}
            >
              <CheckCircle className="mr-1 h-4 w-4" />
              Activar
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onEdit(world)}>
                  <Settings2 className="mr-2 h-4 w-4" />
                  Ajustar
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onExport(world.name)} disabled={isExporting}>
                  <Download className="mr-2 h-4 w-4" />
                  Exportar
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onDuplicate(world.name)} disabled={isDuplicating}>
                  <Copy className="mr-2 h-4 w-4" />
                  Duplicar
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="text-red-500"
                  onClick={() => onDelete(world.name)}
                  disabled={world.activated || isDeleting}
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
