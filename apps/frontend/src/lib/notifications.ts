import type { NotificationItem } from '@/stores/notifications'

/** Etiqueta legible por tipo de evento global (compartida campana + dashboard). */
export const EVENT_LABEL: Record<string, string> = {
  'SERVER.STARTED': 'Servidor en línea',
  'SERVER.STOPPED': 'Servidor detenido',
  'SERVER.CRASHED': 'Servidor caído',
  'PLAYER.JOINED': 'Jugador conectado',
  'PLAYER.LEFT': 'Jugador desconectado',
  'BACKUP.COMPLETED': 'Backup completado',
  'BACKUP.FAILED': 'Backup fallido',
  'TASK.FAILED': 'Tarea fallida',
}

/** Tiempo relativo corto ("hace 2 m") a partir de `ts` ISO. */
export function relativeTime(ts: string): string {
  const then = new Date(ts).getTime()
  const diffMs = Math.max(0, Date.now() - then)
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) return 'ahora'
  if (minutes < 60) return `hace ${minutes} m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `hace ${hours} h`
  return `hace ${Math.floor(hours / 24)} d`
}

/** Texto del evento incluyendo el nombre del objeto si el payload lo trae. */
export function labelFor(item: Pick<NotificationItem, 'event' | 'payload'>): string {
  const base = EVENT_LABEL[item.event] ?? item.event
  const name = typeof item.payload.name === 'string' ? item.payload.name : undefined
  return name ? `${base}: ${name}` : base
}

/** ¿Es un evento de error/fallo (para el punto de color rojo)? */
export function isErrorEvent(event: string): boolean {
  return event.endsWith('.FAILED') || event.endsWith('CRASHED')
}
