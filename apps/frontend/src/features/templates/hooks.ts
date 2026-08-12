import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  applyTemplate,
  captureTemplate,
  deleteTemplate,
  listTemplates,
  templateKeys,
  type ApplyTemplateRequest,
  type CaptureTemplateRequest,
} from '@/lib/api/templates'
import { worldKeys } from '@/lib/api/worlds'

export { templateKeys }

/** `GET /servers/{id}/templates` — plantillas visibles para el servidor. */
export function useTemplates(serverId: string | undefined) {
  return useQuery({
    queryKey: templateKeys.all(serverId ?? ''),
    queryFn: () => listTemplates(serverId!),
    enabled: Boolean(serverId),
    refetchOnWindowFocus: false,
  })
}

/** `POST /servers/{id}/templates/capture`. */
export function useCaptureTemplate(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CaptureTemplateRequest) => captureTemplate(serverId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.all(serverId) })
    },
  })
}

/** `POST /servers/{id}/templates/{template_id}/apply`. */
export function useApplyTemplate(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ templateId, payload }: { templateId: string; payload: ApplyTemplateRequest }) =>
      applyTemplate(serverId, templateId, payload),
    onSuccess: () => {
      // Aplicar reproduce un mundo nuevo en el servidor: refresca también la
      // lista de mundos para que aparezca sin pedir sync manual.
      queryClient.invalidateQueries({ queryKey: templateKeys.all(serverId) })
      queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    },
  })
}

/** `DELETE /servers/{id}/templates/{template_id}`. */
export function useDeleteTemplate(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (templateId: string) => deleteTemplate(serverId, templateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.all(serverId) })
    },
  })
}
