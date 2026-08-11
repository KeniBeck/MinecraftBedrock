import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  activateWorld,
  createWorld,
  deleteWorld,
  duplicateWorld,
  exportWorld,
  importWorld,
  listWorlds,
  syncWorlds,
  updateWorld,
  worldKeys,
  type CreateWorldRequest,
  type ImportWorldRequest,
  type UpdateWorldRequest,
} from '@/lib/api/worlds'

export { worldKeys }

/** `GET /servers/{id}/worlds` — lista de mundos del servidor. */
export function useWorlds(serverId: string | undefined, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: worldKeys.all(serverId ?? ''),
    queryFn: async () => {
      const id = serverId!
      try {
        // El sync reconcilia con el storage y devuelve la lista (201); al
        // vivir dentro del queryFn, React Query deduplica la petición aunque
        // StrictMode monte el componente dos veces, garantizando sync → lista.
        return await syncWorlds(id)
      } catch {
        // Si el sync falla, servimos la metadata existente en vez de romper.
        return listWorlds(id)
      }
    },
    enabled: Boolean(serverId) && (options?.enabled ?? true),
    refetchOnWindowFocus: false,
  })
}

/** `POST /servers/{id}/worlds`. */
export function useCreateWorld(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateWorldRequest) => createWorld(serverId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    },
  })
}

/** `POST /servers/{id}/worlds/import` — multipart (file + name). */
export function useImportWorld(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ImportWorldRequest) => importWorld(serverId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    },
  })
}

/** `GET /servers/{id}/worlds/{name}/export` — descarga el blob. */
export function useExportWorld(serverId: string) {
  return useMutation({
    mutationFn: ({ name }: { name: string }) => exportWorld(serverId, name),
  })
}

/** `POST /servers/{id}/worlds/{name}/duplicate`. */
export function useDuplicateWorld(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ name, newName }: { name: string; newName: string }) =>
      duplicateWorld(serverId, name, { target: newName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    },
  })
}

/** `PATCH /servers/{id}/worlds/{name}` — renombra y/o ajusta un mundo. */
export function useUpdateWorld(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ name, payload }: { name: string; payload: UpdateWorldRequest }) =>
      updateWorld(serverId, name, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    },
  })
}

/** `POST /servers/{id}/worlds/{name}/activate`. */
export function useActivateWorld(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => activateWorld(serverId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    },
  })
}

/** `DELETE /servers/{id}/worlds/{name}`. */
export function useDeleteWorld(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => deleteWorld(serverId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: worldKeys.all(serverId) })
    },
  })
}
