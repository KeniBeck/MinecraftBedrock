import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  listSettings,
  patchSettings,
  resetSetting,
  settingsKeys,
  type PatchSettingsRequest,
  type SettingsListResponse,
} from '@/lib/api/settings'

export { settingsKeys } from '@/lib/api/settings'

/** `GET /settings` — ajustes globales del panel (requiere `settings.view`). */
export function useSettings() {
  return useQuery({
    queryKey: settingsKeys.all,
    queryFn: listSettings,
  })
}

/** `PATCH /settings` — guarda varios ajustes (atómico, requiere `settings.update`). */
export function usePatchSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values: PatchSettingsRequest['values']) => patchSettings({ values }),
    onSuccess: (response) => {
      queryClient.setQueryData(settingsKeys.all, (current: SettingsListResponse | undefined) => {
        if (!current) return current
        const byKey = new Map(current.settings.map((setting) => [setting.key, setting]))
        for (const setting of response.settings) byKey.set(setting.key, setting)
        return { settings: [...byKey.values()] }
      })
    },
  })
}

/** `DELETE /settings/{key}` — resetea un ajuste a su valor por defecto. */
export function useResetSetting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (key: string) => resetSetting(key),
    onSuccess: (setting) => {
      queryClient.setQueryData(settingsKeys.all, (current: SettingsListResponse | undefined) => {
        if (!current) return current
        return {
          settings: current.settings.map((item) => (item.key === setting.key ? setting : item)),
        }
      })
    },
  })
}
