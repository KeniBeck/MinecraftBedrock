import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { PromptDialog } from '@/components/ui/prompt-dialog'
import { getApiMessage } from '@/lib/api/client'
import { Plus } from 'lucide-react'
import type { Template } from '@/lib/api/templates'

import { CaptureTemplateDialog } from './components/CaptureTemplateDialog'
import { TemplateList } from './components/TemplateList'
import { useApplyTemplate, useDeleteTemplate, useTemplates } from './hooks'

export function TemplatesPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const [captureOpen, setCaptureOpen] = useState(false)
  const [applying, setApplying] = useState<Template | null>(null)
  const [deleting, setDeleting] = useState<Template | null>(null)
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

  const handleApply = (worldName: string) => {
    if (!applying) return
    const id = applying.id
    setApplying(null)
    apply.mutate(
      { templateId: id, payload: { world_name: worldName.trim() || undefined } },
      { onError: (err) => setActionError(getApiMessage(err)) },
    )
  }

  const handleDelete = () => {
    if (!deleting) return
    const id = deleting.id
    setDeleting(null)
    deleteTemplate.mutate(id, { onError: (err) => setActionError(getApiMessage(err)) })
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
        onApply={(id) => setApplying(templates?.find((t) => t.id === id) ?? null)}
        onDelete={(id) => setDeleting(templates?.find((t) => t.id === id) ?? null)}
        isApplying={apply.isPending}
        isDeleting={deleteTemplate.isPending}
      />

      <PromptDialog
        open={applying !== null}
        onOpenChange={(next) => {
          if (!next) setApplying(null)
        }}
        title="Aplicar plantilla"
        description={
          applying
            ? `Se reproducirá "${applying.name}" en este servidor con el mundo y la configuración capturados.`
            : undefined
        }
        label="Nombre del mundo destino"
        placeholder="Vacío = el capturado en la plantilla"
        confirmLabel="Aplicar"
        busy={apply.isPending}
        onConfirm={handleApply}
      />

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(next) => {
          if (!next) setDeleting(null)
        }}
        title="Eliminar plantilla"
        description={
          deleting
            ? `¿Eliminar la plantilla "${deleting.name}"? Esta acción no se puede deshacer.`
            : undefined
        }
        confirmLabel="Eliminar"
        destructive
        busy={deleteTemplate.isPending}
        onConfirm={handleDelete}
      />

      <CaptureTemplateDialog
        open={captureOpen}
        onOpenChange={setCaptureOpen}
        serverId={serverId}
      />
    </div>
  )
}
