export type { ScheduleTask, CreateTaskRequest, UpdateTaskRequest } from '@/lib/api/scheduler'

/** Tipo de tarea programada (coincide con `ScheduleTaskType` del backend). */
export type TaskType = 'backup' | 'restart' | 'command'

/** Estado de la tarea (coincide con `ScheduleTaskState` del backend). */
export type TaskState = 'active' | 'paused' | 'running' | 'disabled'

/** Vista de la tarea en el formulario de creación/edición. */
export interface TaskFormValues {
  name: string
  type: TaskType
  cron: string
  /** Solo para `backup`: nombre del mundo a guardar. */
  worldName: string
  /** Solo para `command`: comandos de consola a ejecutar. */
  commands: string
}