import type { ServerState } from '@/lib/api/servers'

/** Etiqueta legible del estado del servidor (badge del mockup). */
export const STATE_LABEL: Record<ServerState, string> = {
  created: 'Creado',
  starting: 'Iniciando',
  running: 'En línea',
  stopping: 'Deteniendo',
  stopped: 'Detenido',
  crashed: 'Caído',
  removed: 'Eliminado',
}

/**
 * Clases de color del badge según estado (frontend-standards §9.3: verde para
 * online/activo, ámbar para transiciones, rojo para caído, gris para detenido).
 */
export const STATE_BADGE: Record<ServerState, string> = {
  created: 'bg-slate-500/20 text-slate-300 border-slate-400/30',
  starting: 'bg-amber-500/20 text-amber-300 border-amber-400/40',
  running: 'bg-emerald-500/20 text-emerald-300 border-emerald-400/40',
  stopping: 'bg-amber-500/20 text-amber-300 border-amber-400/40',
  stopped: 'bg-slate-500/20 text-slate-300 border-slate-400/30',
  crashed: 'bg-red-500/20 text-red-300 border-red-400/40',
  removed: 'bg-slate-700/30 text-slate-400 border-slate-600/30',
}

export interface ServerActions {
  canStart: boolean
  canStop: boolean
  canRestart: boolean
}

/**
 * Qué acciones son válidas según el estado (misma lógica que el backend:
 * start desde created/stopped/crashed, stop/restart desde running/starting).
 */
export function serverActions(state: ServerState): ServerActions {
  switch (state) {
    case 'created':
    case 'stopped':
    case 'crashed':
      return { canStart: true, canStop: false, canRestart: false }
    case 'running':
    case 'starting':
      return { canStart: false, canStop: true, canRestart: true }
    case 'stopping':
    case 'removed':
      return { canStart: false, canStop: false, canRestart: false }
  }
}
