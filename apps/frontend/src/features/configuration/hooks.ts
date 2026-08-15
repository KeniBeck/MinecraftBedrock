import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  configKeys,
  getConfig,
  updateConfig,
  type ConfigPropertyValue,
  type UpdateConfigRequest,
} from '@/lib/api/configuration'

export { configKeys }

/** `GET /servers/{id}/configuration` — perfil de configuración actual. */
export function useConfig(serverId: string | undefined) {
  return useQuery({
    queryKey: configKeys.profile(serverId ?? ''),
    queryFn: () => getConfig(serverId!),
    enabled: Boolean(serverId),
    refetchOnWindowFocus: false,
  })
}

/** `PUT /servers/{id}/configuration` — guardar propiedades (solo las editables). */
export function useUpdateConfig(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: UpdateConfigRequest) => updateConfig(serverId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configKeys.all(serverId) })
    },
  })
}

/**
 * Construye el objeto `properties` que se envía al backend a partir de los
 * valores del formulario y el perfil original. Solo se incluyen las claves del
 * catálogo editable y, si `onlyChanged` es true, únicamente las que difieren.
 */
export function buildPropertiesPayload(
  values: Record<string, ConfigPropertyValue>,
  original: Record<string, ConfigPropertyValue>,
  onlyChanged: boolean,
): Record<string, ConfigPropertyValue> {
  const entries = Object.entries(values).filter(([key]) => key in original)
  if (!onlyChanged) return Object.fromEntries(entries)
  return Object.fromEntries(
    entries.filter(([key, value]) => (original[key] ?? '') !== (value ?? '')),
  )
}