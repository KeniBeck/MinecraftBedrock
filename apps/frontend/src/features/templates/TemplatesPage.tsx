import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getApiMessage } from '@/lib/api/client'
import { Plus } from 'lucide-react'

import { CaptureTemplateDialog } from './components/CaptureTemplateDialog'
import { TemplateList } from './components/TemplateList'
import { useApplyTemplate, useDeleteTemplate, useTemplates } from './hooks'

export function TemplatesPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const [captureOpen, setCaptureOpen] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: templates, isLoading, isError, error } = useTemplates(serverId)
  const apply = useApplyTemplate(serverId ?? '')
  const deleteTemplate = useDeleteTemplate(serverId ?? '')

  if (!serverId) return null

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Cargando plantillas…</div>
  }

  if (isError) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        {getApiMessage(error, 'No se pudieron cargar las plantillas')}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Plantillas</h1>
        <Button variant="create" pixel onClick={() => setCaptureOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          Capturar plantilla
        </Button>
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
        >
          {actionError}
        </div>
      )}

      <TemplateList
        templates={templates ?? []}
        onApply={(id) => {
          const worldName = window.prompt(
            'Nombre del mundo destino (vacío = el capturado en la plantilla):',
          )
          if (worldName !== null) {
            apply.mutate(
              {
                templateId: id,
                payload: { world_name: worldName.trim() || undefined },
              },
              { onError: (err) => setActionError(getApiMessage(err)) },
            )
          }
        }}
        onDelete={(id) => {
          if (window.confirm('¿Eliminar esta plantilla? Esta acción no se puede deshacer.')) {
            deleteTemplate.mutate(id, { onError: (err) => setActionError(getApiMessage(err)) })
          }
        }}
        isApplying={apply.isPending}
        isDeleting={deleteTemplate.isPending}
      />

      <CaptureTemplateDialog
        open={captureOpen}
        onOpenChange={setCaptureOpen}
        serverId={serverId}
      />
    </div>
  )
}
