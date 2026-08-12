import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  banPlayerGlobally,
  banPlayerOnServer,
  getPlayer,
  kickPlayer,
  listGlobalBans,
  listServerBans,
  onlinePlayers,
  playerKeys,
  playerSessions,
  searchPlayer,
  unbanPlayerGlobally,
  unbanPlayerOnServer,
  type BanPlayerRequest,
  type GlobalBanRequest,
} from '@/lib/api/players'

export { playerKeys }

/** `GET /servers/{id}/players/online` — sesiones abiertas en el servidor. */
export function useOnlinePlayers(serverId: string | undefined) {
  return useQuery({
    queryKey: playerKeys.online(serverId ?? ''),
    queryFn: () => onlinePlayers(serverId!),
    enabled: Boolean(serverId),
    refetchOnWindowFocus: false,
  })
}

/**
 * `GET /servers/{id}/players/search?name=` — búsqueda parcial de gamertags.
 * Query controlada: solo se dispara cuando `name` tiene contenido (debounce en
 * el componente); `keepPreviousData` evita el flash de loading entre términos.
 */
export function useSearchPlayer(serverId: string | undefined, name: string) {
  const trimmed = name.trim()
  return useQuery({
    queryKey: playerKeys.search(serverId ?? '', trimmed),
    queryFn: () => searchPlayer(serverId!, trimmed),
    enabled: Boolean(serverId) && trimmed.length > 0,
    refetchOnWindowFocus: false,
    retry: false,
  })
}

/** `GET /players/bans/global` — bans panel-wide (admin/super_admin). */
export function useGlobalBans(enabled = true) {
  return useQuery({
    queryKey: playerKeys.globalBans(),
    queryFn: () => listGlobalBans(),
    enabled,
    refetchOnWindowFocus: false,
    retry: false,
  })
}

/** `GET /servers/{id}/players/bans` — bans de un servidor. */
export function useServerBans(serverId: string | undefined) {
  return useQuery({
    queryKey: playerKeys.serverBans(serverId ?? ''),
    queryFn: () => listServerBans(serverId!),
    enabled: Boolean(serverId),
    refetchOnWindowFocus: false,
    retry: false,
  })
}

/** `GET /servers/{id}/players/{xuid}` — datos de un jugador concreto. */
export function usePlayer(serverId: string | undefined, xuid: string | undefined) {
  return useQuery({
    queryKey: playerKeys.detail(serverId ?? '', xuid ?? ''),
    queryFn: () => getPlayer(serverId!, xuid!),
    enabled: Boolean(serverId) && Boolean(xuid),
    refetchOnWindowFocus: false,
    retry: false,
  })
}

/** `GET /servers/{id}/players/{xuid}/sessions?limit=` — historial de sesiones. */
export function usePlayerSessions(serverId: string | undefined, xuid: string | undefined) {
  return useQuery({
    queryKey: playerKeys.sessions(serverId ?? '', xuid ?? ''),
    queryFn: () => playerSessions(serverId!, xuid!, 20),
    enabled: Boolean(serverId) && Boolean(xuid),
    refetchOnWindowFocus: false,
    retry: false,
  })
}

/** `POST /players/bans/global` (201) — ban panel-wide, solo admin/super_admin. */
export function useBanPlayerGlobally() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: GlobalBanRequest) => banPlayerGlobally(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: playerKeys.globalBans() })
    },
  })
}

/** `DELETE /players/bans/global/{ban_id}` (204). */
export function useUnbanPlayerGlobally() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (banId: string) => unbanPlayerGlobally(banId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: playerKeys.globalBans() })
    },
  })
}

/** `POST /servers/{id}/players/{player_id}/ban` (204). */
export function useBanPlayerOnServer(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ playerId, payload }: { playerId: string; payload: BanPlayerRequest }) =>
      banPlayerOnServer(serverId, playerId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: playerKeys.online(serverId) })
      queryClient.invalidateQueries({ queryKey: playerKeys.serverBans(serverId) })
    },
  })
}

/** `DELETE /servers/{id}/players/{player_id}/ban` (204). */
export function useUnbanPlayerOnServer(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (playerId: string) => unbanPlayerOnServer(serverId, playerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: playerKeys.online(serverId) })
      queryClient.invalidateQueries({ queryKey: playerKeys.serverBans(serverId) })
    },
  })
}

/** `POST /servers/{id}/players/{xuid}/kick` (202) — acuse del comando. */
export function useKickPlayer(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (xuid: string) => kickPlayer(serverId, xuid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: playerKeys.online(serverId) })
    },
  })
}
