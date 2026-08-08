import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getServer,
  listServers,
  restartServer,
  startServer,
  stopServer,
  type Server,
} from '@/lib/api/servers'
import { useServerStateSync } from '@/hooks/useServerStateSync'

export const serverKeys = {
  all: ['servers'] as const,
  detail: (serverId: string) => ['server', serverId] as const,
}

/** `GET /servers` — lista de servidores visibles (para el selector del header). */
export function useServers() {
  return useQuery({
    queryKey: serverKeys.all,
    queryFn: listServers,
  })
}

/**
 * `GET /servers/{id}` + sync de estado por WS. `enabled` permite no disparar
 * cuando no hay servidor seleccionado.
 */
export function useServer(serverId: string | undefined) {
  const query = useQuery({
    queryKey: serverKeys.detail(serverId ?? ''),
    queryFn: () => getServer(serverId!),
    enabled: Boolean(serverId),
  })
  useServerStateSync(serverId)
  return query
}

/** `POST /servers/{id}/start`. */
export function useStartServer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ serverId }: { serverId: string }) => startServer(serverId),
    onSuccess: (server) => {
      queryClient.setQueryData(serverKeys.detail(server.id), server)
    },
  })
}

/** `POST /servers/{id}/stop`. */
export function useStopServer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ serverId }: { serverId: string }) => stopServer(serverId, 30),
    onSuccess: (server) => {
      queryClient.setQueryData(serverKeys.detail(server.id), server)
    },
  })
}

/** `POST /servers/{id}/restart`. */
export function useRestartServer() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ serverId }: { serverId: string }) => restartServer(serverId, 30),
    onSuccess: (server) => {
      queryClient.setQueryData(serverKeys.detail(server.id), server)
    },
  })
}

/** Setter por callback para actualizar el server en la cache (sync WS usa esto). */
export function useServerCacheUpdater() {
  const queryClient = useQueryClient()
  return (serverId: string, updater: (current: Server | undefined) => Server | undefined) => {
    queryClient.setQueryData(serverKeys.detail(serverId), updater)
  }
}
