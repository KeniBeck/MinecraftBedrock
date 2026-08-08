import { apiClient } from '@/lib/api/client'

/**
 * Tipos del módulo Server — verificados contra
 * `apps/backend/src/app/modules/server/api/schemas.py` (ServerResponse,
 * ServerConnectionResponse). El backend define `state` como enum de strings:
 * `created | starting | running | stopping | stopped | crashed | removed`.
 */

export type ServerState =
  | 'created'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'stopped'
  | 'crashed'
  | 'removed'

export interface ServerConnection {
  host: string
  port: number
  port_v6: number
  rcon_port: number | null
  address: string
}

/** `ServerResponse` real. */
export interface Server {
  id: string
  name: string
  state: ServerState
  version: string
  image_ref: string
  runtime_id: string | null
  created_at: string
  updated_at: string
  connection: ServerConnection
}

/** Cuerpo de `POST /servers` (CreateServerRequest). */
export interface CreateServerRequest {
  name: string
  version?: string | null
  template_id?: string | null
}

/** `GET /servers` — lista filtrada por `server.view`. */
export async function listServers(): Promise<Server[]> {
  const { data } = await apiClient.get<Server[]>('/servers')
  return data
}

/** `GET /servers/{id}`. */
export async function getServer(serverId: string): Promise<Server> {
  const { data } = await apiClient.get<Server>(`/servers/${serverId}`)
  return data
}

/** `POST /servers` (admin). */
export async function createServer(payload: CreateServerRequest): Promise<Server> {
  const { data } = await apiClient.post<Server>('/servers', payload)
  return data
}

/** `POST /servers/{id}/start`. */
export async function startServer(serverId: string): Promise<Server> {
  const { data } = await apiClient.post<Server>(`/servers/${serverId}/start`)
  return data
}

/** `POST /servers/{id}/stop` — `grace` en segundos (default 30). */
export async function stopServer(serverId: string, grace = 30): Promise<Server> {
  const { data } = await apiClient.post<Server>(`/servers/${serverId}/stop`, { grace })
  return data
}

/** `POST /servers/{id}/restart` — `grace` en segundos (default 30). */
export async function restartServer(serverId: string, grace = 30): Promise<Server> {
  const { data } = await apiClient.post<Server>(`/servers/${serverId}/restart`, { grace })
  return data
}
