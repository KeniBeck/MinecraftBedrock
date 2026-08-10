import { apiClient } from '@/lib/api/client'

/**
 * Tipos del módulo Console — verificados contra
 * `apps/backend/src/app/modules/console/api/schemas.py`:
 * - `SendCommandRequest = {command: str(1..512), priority?: normal|low|high|critical}`.
 * - `CommandAckResponse` (202) = `{server_id, command, priority, seq, at}`.
 */

export type ConsolePriority = 'critical' | 'high' | 'normal' | 'low'

/** Cuerpo de `POST /servers/{server_id}/console/commands`. */
export interface SendConsoleCommandRequest {
  command: string
  priority?: ConsolePriority
}

/** `CommandAckResponse` — acuse del comando encolado al stdin. */
export interface ConsoleCommandAck {
  server_id: string
  command: string
  priority: string
  seq: number
  at: string
}

/**
 * `POST /servers/{server_id}/console/commands` — requiere `server.console.write`.
 * Responde **202 Accepted** con el acuse (priority se deja en `normal`).
 */
export async function sendConsoleCommand(
  serverId: string,
  command: string,
): Promise<ConsoleCommandAck> {
  const { data } = await apiClient.post<ConsoleCommandAck>(
    `/servers/${serverId}/console/commands`,
    { command } satisfies SendConsoleCommandRequest,
  )
  return data
}
