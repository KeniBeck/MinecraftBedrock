import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { getApiMessage } from '@/lib/api/client'
import { worldKeys } from '@/lib/api/worlds'
import { Plus, RefreshCw, Upload } from 'lucide-react'

import { CreateWorldDialog } from './components/CreateWorldDialog'
import { EditWorldDialog } from './components/EditWorldDialog'
import { ImportWorldDialog } from './components/ImportWorldDialog'
import { WorldList } from './components/WorldList'
import { useActivateWorld, useDeleteWorld, useDuplicateWorld, useExportWorld, useWorlds } from './hooks'
import type { World } from '@/lib/api/worlds'

export function WorldsPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const [createOpen, setCreateOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [editingWorld, setEditingWorld] = useState<World | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const activate = useActivateWorld(serverId ?? '')
  const exportWorld = useExportWorld(serverId ?? '')
  const duplicate = useDuplicateWorld(serverId ?? '')
  const deleteWorld = useDeleteWorld(serverId ?? '')
  const { data: worlds, isLoading, isFetching, isError, error } = useWorlds(serverId)

  const resync = () => {
    if (serverId) {
      void queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    }
  }

  if (!serverId) return null

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Sincronizando mundos…</div>
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        {getApiMessage(error, 'No se pudieron cargar los mundos')}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Mundos</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={resync}>
            <RefreshCw className={`mr-1 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            {isFetching ? 'Sincronizando…' : 'Sincronizar'}
          </Button>
          <Button variant="default" pixel onClick={() => setImportOpen(true)}>
            <Upload className="mr-1 h-4 w-4" />
            Importar
          </Button>
          <Button variant="create" pixel onClick={() => setCreateOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Crear mundo
          </Button>
        </div>
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
        >
          {actionError}
        </div>
      )}

      <WorldList
        worlds={worlds ?? []}
        onActivate={(name) =>
          activate.mutate(name, { onError: (err) => setActionError(getApiMessage(err)) })
        }
        onEdit={(world) => setEditingWorld(world)}
        onDuplicate={(name) => {
          const newName = window.prompt('Nombre del nuevo mundo:')
          if (newName) {
            duplicate.mutate(
              { name, newName },
              { onError: (err) => setActionError(getApiMessage(err)) },
            )
          }
        }}
        onExport={(name) => {
          exportWorld.mutate(
            { name },
            {
              onSuccess: (blob) => {
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `${name}.mcworld`
                a.click()
                URL.revokeObjectURL(url)
              },
              onError: (err) => setActionError(getApiMessage(err)),
            },
          )
        }}
        onDelete={(name) => {
          if (window.confirm(`¿Eliminar el mundo "${name}"? Esta acción no se puede deshacer.`)) {
            deleteWorld.mutate(name, { onError: (err) => setActionError(getApiMessage(err)) })
          }
        }}
        isActivating={activate.isPending}
        isDuplicating={duplicate.isPending}
        isExporting={exportWorld.isPending}
        isDeleting={deleteWorld.isPending}
      />

      <CreateWorldDialog open={createOpen} onOpenChange={setCreateOpen} serverId={serverId} />
      <EditWorldDialog
        open={editingWorld !== null}
        onOpenChange={(open) => {
          if (!open) setEditingWorld(null)
        }}
        serverId={serverId}
        world={editingWorld}
      />
      <ImportWorldDialog open={importOpen} onOpenChange={setImportOpen} serverId={serverId} />
    </div>
  )
}
