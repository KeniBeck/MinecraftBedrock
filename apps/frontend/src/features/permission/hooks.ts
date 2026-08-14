import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  addAllowlistEntry,
  getOperators,
  listAllowlist,
  operatorKeys,
  permissionKeys,
  removeAllowlistEntry,
  removeOperator,
  setAllowlistEnabled,
  setOperatorLevel,
  type AddAllowlistRequest,
  type PermissionLevel,
} from '@/lib/api/permissions'

export { permissionKeys, operatorKeys }

/** `GET /servers/{id}/permissions/allowlist` — lista de la allowlist. */
export function useAllowlist(serverId: string | undefined) {
  return useQuery({
    queryKey: permissionKeys.allowlist(serverId ?? ''),
    queryFn: () => listAllowlist(serverId!),
    enabled: Boolean(serverId),
    refetchOnWindowFocus: false,
  })
}

/** `POST /servers/{id}/permissions/allowlist` — añadir entrada. */
export function useAddAllowlistEntry(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: AddAllowlistRequest) => addAllowlistEntry(serverId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: permissionKeys.all(serverId) })
    },
  })
}

/** `DELETE /servers/{id}/permissions/allowlist/{xuid}` (204). */
export function useRemoveAllowlistEntry(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (xuid: string) => removeAllowlistEntry(serverId, xuid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: permissionKeys.all(serverId) })
    },
  })
}

/** `PUT /servers/{id}/permissions/allowlist-enabled` (204) — toggle ALLOW_LIST. */
export function useToggleAllowlistEnabled(serverId: string) {
  return useMutation({
    mutationFn: (enabled: boolean) => setAllowlistEnabled(serverId, enabled),
  })
}

/** `GET /servers/{id}/permissions/operators` — lista de permisos del servidor. */
export function useOperators(serverId: string | undefined) {
  return useQuery({
    queryKey: operatorKeys.all(serverId ?? ''),
    queryFn: () => getOperators(serverId!),
    enabled: Boolean(serverId),
    refetchOnWindowFocus: false,
  })
}

/** `PUT /servers/{id}/permissions/operators/{xuid}` — asignar nivel de permiso. */
export function useSetOperator(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ xuid, level }: { xuid: string; level: PermissionLevel }) =>
      setOperatorLevel(serverId, xuid, level),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: operatorKeys.all(serverId) })
    },
  })
}

/** `DELETE /servers/{id}/permissions/operators/{xuid}` (204). */
export function useRemoveOperator(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (xuid: string) => removeOperator(serverId, xuid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: operatorKeys.all(serverId) })
    },
  })
}