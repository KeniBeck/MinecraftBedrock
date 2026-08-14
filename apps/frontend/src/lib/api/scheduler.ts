import { apiClient } from './client'

/**
 * Claves de cache de TanStack Query para el módulo Scheduler: `all(serverId)`
 * es la base `['scheduler', serverId]`; `list` recoge el listado de tareas y
 * `detail` deja sitio para una tarea concreta.
 */
export const taskKeys = {
  all: (serverId: string) => ['scheduler', serverId] as const,
  list: (serverId: string) => [...taskKeys.all(serverId), 'list'] as const,
  detail: (serverId: string, taskId: string) =>
    [...taskKeys.all(serverId), taskId] as const,
}

/**
 * Tipos del módulo Scheduler — verificados contra
 * `apps/backend/src/app/modules/scheduler/api/schemas.py` y el router real:
 * - `GET /servers/{id}/schedule/tasks` → `list[ScheduleTaskResponse]`
 * - `POST /servers/{id}/schedule/tasks` → `ScheduleTaskResponse` (201)
 * - `PATCH /servers/{id}/schedule/tasks/{task_id}` → `ScheduleTaskResponse`
 * - `POST /servers/{id}/schedule/tasks/{task_id}/run` → `ScheduleTaskResponse`
 * - `DELETE /servers/{id}/schedule/tasks/{task_id}` → 204
 */

/** `ScheduleTaskResponse` — registro de una tarea programada del servidor. */
export interface ScheduleTask {
  id: string
  server_id: string
  name: string
  type: string
  cron: string
  payload: Record<string, unknown>
  state: string
  next_run_at: string | null
  last_run_at: string | null
  last_result: string | null
  failures: number
  max_retries: number
  backoff_seconds: number
  created_at: string | null
  updated_at: string | null
}

/** `CreateTaskRequest` — cuerpo de `POST .../schedule/tasks`. */
export interface CreateTaskRequest {
  name: string
  type: string
  cron: string
  payload: Record<string, unknown>
  max_retries?: number
  backoff_seconds?: number
}

/** `UpdateTaskRequest` — cuerpo de `PATCH .../schedule/tasks/{task_id}`. */
export interface UpdateTaskRequest {
  name?: string
  cron?: string
  payload?: Record<string, unknown>
  max_retries?: number
  backoff_seconds?: number
  state?: string
}

/** `GET /servers/{id}/schedule/tasks` — lista de tareas del servidor. */
export async function listTasks(serverId: string): Promise<ScheduleTask[]> {
  const { data } = await apiClient.get<ScheduleTask[]>(
    `/servers/${serverId}/schedule/tasks`,
  )
  return data
}

/** `POST /servers/{id}/schedule/tasks` (201) — crear una tarea. */
export async function createTask(
  serverId: string,
  data: CreateTaskRequest,
): Promise<ScheduleTask> {
  const res = await apiClient.post<ScheduleTask>(`/servers/${serverId}/schedule/tasks`, data)
  return res.data
}

/** `PATCH /servers/{id}/schedule/tasks/{task_id}` — editar una tarea. */
export async function updateTask(
  serverId: string,
  taskId: string,
  data: UpdateTaskRequest,
): Promise<ScheduleTask> {
  const res = await apiClient.patch<ScheduleTask>(
    `/servers/${serverId}/schedule/tasks/${encodeURIComponent(taskId)}`,
    data,
  )
  return res.data
}

/** `POST /servers/{id}/schedule/tasks/{task_id}/run` — ejecutar ahora. */
export async function runTask(
  serverId: string,
  taskId: string,
): Promise<ScheduleTask> {
  const res = await apiClient.post<ScheduleTask>(
    `/servers/${serverId}/schedule/tasks/${encodeURIComponent(taskId)}/run`,
  )
  return res.data
}

/** `DELETE /servers/{id}/schedule/tasks/{task_id}` (204). */
export async function deleteTask(serverId: string, taskId: string): Promise<void> {
  await apiClient.delete(`/servers/${serverId}/schedule/tasks/${encodeURIComponent(taskId)}`)
}