import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createTask,
  deleteTask,
  listTasks,
  runTask,
  taskKeys,
  updateTask,
  type CreateTaskRequest,
  type ScheduleTask,
  type UpdateTaskRequest,
} from '@/lib/api/scheduler'

export { taskKeys }

/** `GET /servers/{id}/schedule/tasks` — lista de tareas del servidor. */
export function useTasks(serverId: string | undefined) {
  return useQuery({
    queryKey: taskKeys.list(serverId ?? ''),
    queryFn: () => listTasks(serverId!),
    enabled: Boolean(serverId),
    refetchOnWindowFocus: false,
  })
}

/** `POST /servers/{id}/schedule/tasks` — crear una tarea programada. */
export function useCreateTask(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateTaskRequest) => createTask(serverId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.all(serverId) })
    },
  })
}

/** `PATCH /servers/{id}/schedule/tasks/{task_id}` — editar una tarea. */
export function useUpdateTask(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: string; payload: UpdateTaskRequest }) =>
      updateTask(serverId, taskId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.all(serverId) })
    },
  })
}

/** `DELETE /servers/{id}/schedule/tasks/{task_id}` (204). */
export function useDeleteTask(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (taskId: string) => deleteTask(serverId, taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.all(serverId) })
    },
  })
}

/** `POST /servers/{id}/schedule/tasks/{task_id}/run` — ejecutar ahora. */
export function useRunTask(serverId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (taskId: string) => runTask(serverId, taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: taskKeys.all(serverId) })
    },
  })
}

/** Aplica los valores de un formulario a un `CreateTaskRequest` del backend. */
export function buildCreatePayload(values: {
  name: string
  type: string
  cron: string
  worldName: string
  commands: string
}): CreateTaskRequest {
  const payload: Record<string, unknown> = {}
  if (values.type === 'backup') payload.world_name = values.worldName
  if (values.type === 'command') {
    payload.commands = values.commands
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
  }
  return {
    name: values.name,
    type: values.type,
    cron: values.cron,
    payload,
    max_retries: 3,
    backoff_seconds: 60,
  }
}

/** Aplica los valores de un formulario a un `UpdateTaskRequest` del backend. */
export function buildUpdatePayload(
  task: ScheduleTask,
  values: {
    name: string
    type: string
    cron: string
    worldName: string
    commands: string
  },
): UpdateTaskRequest {
  const payload: Record<string, unknown> = {}
  if (values.type === 'backup') payload.world_name = values.worldName
  if (values.type === 'command') {
    payload.commands = values.commands
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
  }
  return {
    name: values.name,
    cron: values.cron,
    payload,
    max_retries: task.max_retries,
    backoff_seconds: task.backoff_seconds,
  }
}