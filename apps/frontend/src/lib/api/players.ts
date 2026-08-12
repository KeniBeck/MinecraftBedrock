import { apiClient } from '@/lib/api/client'

/**
 * Claves de cache de TanStack Query para el módulo Player (frontend-standards
 * §13): `all(serverId)` es la base `['players', serverId]`; las listas y
 * detalles cuelgan de ahí.
 */
export const playerKeys = {
  all: (serverId: string) => ['players', serverId] as const,
  online: (serverId: string) => [...playerKeys.all(serverId), 'online'] as const,
  detail: (serverId: string, xuid: string) => [...playerKeys.all(serverId), xuid] as const,
  sessions: (serverId: string, xuid: string) =>
    [...playerKeys.detail(serverId, xuid), 'sessions'] as const,
  search: (serverId: string, name: string) => [...playerKeys.all(serverId), 'search', name] as const,
}

/**
 * Tipos del módulo Player — verificados contra
 * `apps/backend/src/app/modules/player/api/schemas.py` y el router real:
 * - `/servers/{id}/players/search?name=` → ResolvePlayerResponse (solo uno, no lista)
 * - `/servers/{id}/players/online` → list[PlaySessionResponse] (sin gamertag)
 * - `/servers/{id}/players/{xuid}` → PlayerResponse
 * - `/servers/{id}/players/{xuid}/sessions` → list[PlaySessionResponse]
 * - bans: POST/DELETE sin listado; ban por servidor usa `{player_id}` y responde 204
 * - kick: `{xuid}` y responde CommandAckResponse (202)
 */

/** `ResolvePlayerResponse` — resolver gamertag → XUID. */
export interface ResolvePlayerResponse {
  server_id: string
  name: string
  xuid: string
}

/** `PlayerResponse` — datos agregados de un jugador. */
export interface PlayerResponse {
  xuid: string
  name: string
  first_seen_at: string
  last_seen_at: string
  playtime_seconds: number
}

/** `PlaySessionResponse` — una sesión de juego (online o histórica). */
export interface PlaySessionResponse {
  id: string
  server_id: string
  xuid: string
  joined_at: string
  left_at: string | null
  reason: string | null
  playtime_seconds: number
}

/** `CommandAckResponse` — acuse del comando enviado a BDS (kick). */
export interface CommandAckResponse {
  server_id: string
  command: string
  priority: string
  seq: number
  at: string
}

/** `GlobalBanRequest` — ban panel-wide (admin). */
export interface GlobalBanRequest {
  gamertag: string
  xuid?: string | null
  reason?: string | null
  expires_at?: string | null
}

/** `GlobalBanResponse` — ban global creado (201). */
export interface GlobalBanResponse {
  id: string
  scope: string
  gamertag: string
  xuid: string | null
  reason: string | null
  banned_by: string
  created_at: string
  expires_at: string | null
}

/** `BanPlayerRequest` — ban por servidor. */
export interface BanPlayerRequest {
  reason?: string | null
  expires_at?: string | null
}

/** `GET /servers/{id}/players/search?name=` — gamertag → XUID. */
export async function searchPlayer(
  serverId: string,
  name: string,
): Promise<ResolvePlayerResponse> {
  const { data } = await apiClient.get<ResolvePlayerResponse>(
    `/servers/${serverId}/players/search`,
    { params: { name } },
  )
  return data
}

/** `GET /servers/{id}/players/online` — sesiones abiertas en el servidor. */
export async function onlinePlayers(serverId: string): Promise<PlaySessionResponse[]> {
  const { data } = await apiClient.get<PlaySessionResponse[]>(
    `/servers/${serverId}/players/online`,
  )
  return data
}

/** `GET /servers/{id}/players/{xuid}` — datos del jugador. */
export async function getPlayer(serverId: string, xuid: string): Promise<PlayerResponse> {
  const { data } = await apiClient.get<PlayerResponse>(
    `/servers/${serverId}/players/${encodeURIComponent(xuid)}`,
  )
  return data
}

/** `GET /servers/{id}/players/{xuid}/sessions?limit=` — historial. */
export async function playerSessions(
  serverId: string,
  xuid: string,
  limit = 20,
): Promise<PlaySessionResponse[]> {
  const { data } = await apiClient.get<PlaySessionResponse[]>(
    `/servers/${serverId}/players/${encodeURIComponent(xuid)}/sessions`,
    { params: { limit } },
  )
  return data
}

/** `POST /players/bans/global` (201) — ban panel-wide, solo admin/super_admin. */
export async function banPlayerGlobally(data: GlobalBanRequest): Promise<GlobalBanResponse> {
  const res = await apiClient.post<GlobalBanResponse>('/players/bans/global', data)
  return res.data
}

/** `DELETE /players/bans/global/{ban_id}` (204). */
export async function unbanPlayerGlobally(banId: string): Promise<void> {
  await apiClient.delete(`/players/bans/global/${encodeURIComponent(banId)}`)
}

/** `POST /servers/{id}/players/{player_id}/ban` (204, sin body de respuesta). */
export async function banPlayerOnServer(
  serverId: string,
  playerId: string,
  data: BanPlayerRequest,
): Promise<void> {
  await apiClient.post(
    `/servers/${serverId}/players/${encodeURIComponent(playerId)}/ban`,
    data,
  )
}

/** `DELETE /servers/{id}/players/{player_id}/ban` (204). */
export async function unbanPlayerOnServer(serverId: string, playerId: string): Promise<void> {
  await apiClient.delete(`/servers/${serverId}/players/${encodeURIComponent(playerId)}/ban`)
}

/** `POST /servers/{id}/players/{xuid}/kick` (202) — expulsa vía Console. */
export async function kickPlayer(
  serverId: string,
  xuid: string,
): Promise<CommandAckResponse> {
  const res = await apiClient.post<CommandAckResponse>(
    `/servers/${serverId}/players/${encodeURIComponent(xuid)}/kick`,
  )
  return res.data
}
