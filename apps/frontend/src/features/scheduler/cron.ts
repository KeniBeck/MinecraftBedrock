import type { TaskType } from './types'

/** Presets de programación rápida: etiqueta → expresión cron. */
export const CRON_PRESETS: ReadonlyArray<{ label: string; cron: string }> = [
  { label: 'Cada minuto', cron: '* * * * *' },
  { label: 'Cada hora', cron: '0 * * * *' },
  { label: 'Diario a las 00:00', cron: '0 0 * * *' },
  { label: 'Diario a las 03:00', cron: '0 3 * * *' },
  { label: 'Semanal (lunes 00:00)', cron: '0 0 * * 1' },
  { label: 'Mensual (día 1 a las 00:00)', cron: '0 0 1 * *' },
]

export type CronParts = [string, string, string, string, string]

export const CRON_PART_LABELS: ReadonlyArray<{ label: string; min: number; max: number }> = [
  { label: 'Minuto', min: 0, max: 59 },
  { label: 'Hora', min: 0, max: 23 },
  { label: 'Día del mes', min: 1, max: 31 },
  { label: 'Mes', min: 1, max: 12 },
  { label: 'Día de la semana', min: 0, max: 6 },
]

/** Valores válidos de una parte: `*` o un entero en `[min, max]`. */
function isValidPart(part: string, min: number, max: number): boolean {
  if (part === '*') return true
  if (!/^\d+$/.test(part)) return false
  const n = Number(part)
  return Number.isInteger(n) && n >= min && n <= max
}

/** Divide la expresión cron en 5 partes (rellena con `*` si faltan). */
export function parseCronToParts(cron: string): CronParts {
  const parts = cron.trim().split(/\s+/).slice(0, 5)
  while (parts.length < 5) parts.push('*')
  return parts as CronParts
}

/** Une las 5 partes en una expresión cron separada por espacios. */
export function buildCronFromParts(parts: CronParts): string {
  return parts.map((p) => p.trim() || '*').join(' ')
}

/** Valida una expresión cron de 5 campos (solo `*` o números en rango). */
export function isValidCron(cron: string): boolean {
  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) return false
  return parts.every((p, i) => {
    const { min, max } = CRON_PART_LABELS[i]
    return isValidPart(p, min, max)
  })
}

/** Traduce las 5 partes a una descripción legible, o `null` si no puede. */
export function describeCronParts(parts: CronParts): string | null {
  return describeCron(buildCronFromParts(parts))
}

/**
 * Traduce una expresión cron de 5 campos al español para mostrarla como
 * "disfraz": el usuario escribe/revisa la expresión y ve su significado
 * (`0 3 * * *` → "todos los días a las 03:00"). Devuelve `null` si no puede
 * interpretarla para que la UI muestre un aviso en vez de un texto erróneo.
 */
const WEEKDAYS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']
const MONTHS = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

/** Parseo de pasos (`*`/`n`, rangos `/n` en un campo numérico). */
function parseSteps(part: string): { range: string | null; step: number } | null {
  if (part === '*') return { range: null, step: 1 }
  if (part.startsWith('*/')) {
    const step = Number(part.slice(2))
    return Number.isInteger(step) && step > 0 ? { range: null, step } : null
  }
  if (part.includes('/')) {
    const [range, stepStr] = part.split('/')
    const step = Number(stepStr)
    return Number.isInteger(step) && step > 0 ? { range, step } : null
  }
  return null
}

/** Intervalo de minutos del campo: cada-N minutos, o null si es hora en punto. */
function minuteDescription(part: string): { every: number | null; isZero: boolean } | null {
  const steps = parseSteps(part)
  if (steps) {
    if (steps.range === null) return { every: steps.step, isZero: false }
    return null
  }
  if (/^\d+$/.test(part)) return { every: null, isZero: Number(part) === 0 }
  return null
}

/** Describe el campo hora+minuto. Devuelve el texto del "a las HH:MM" o null. */
function timeDescription(minutePart: string, hourPart: string): string | null {
  const m = minuteDescription(minutePart)
  if (!m) return null

  if (m.every !== null) {
    if (hourPart === '*') return `cada ${m.every} ${m.every === 1 ? 'minuto' : 'minutos'}`
    const hSteps = parseSteps(hourPart)
    if (hSteps && hSteps.range === null) {
      return `cada ${m.every} ${m.every === 1 ? 'minuto' : 'minutos'}`
    }
  }

  if (m.isZero) {
    if (/^\d+$/.test(hourPart)) return `las ${pad2(Number(hourPart))}:00`
  } else if (/^\d+$/.test(hourPart) && /^\d+$/.test(minutePart)) {
    return `las ${pad2(Number(hourPart))}:${pad2(Number(minutePart))}`
  }

  return null
}

/**
 * Devuelve una descripción con el día y la hora: `"todos los días a las 03:00"`,
 * `"los lunes y viernes a las 12:30"`, `"último día de cada mes a las 00:05"`.
 * Si el cron no es de los casos interpretables vuelve null.
 */
export function describeCron(cron: string): string | null {
  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) return null

  const [minute, hour, dom, month, dow] = parts

  const time = timeDescription(minute, hour)
  if (!time) return null

  // Recurrencias de intervalo (cada 5 minutos / cada hora) no dependen del día.
  if (time.startsWith('cada')) return time

  if (month !== '*') {
    if (/^\d+$/.test(month)) {
      const idx = Number(month) - 1
      if (idx >= 0 && idx < 12) return `en ${MONTHS[idx]} a ${time}`
    }
    return null
  }

  if (dow !== '*' && dom === '*') {
    const dows = dow
      .split(',')
      .map((p) => p.trim())
      .filter((p) => /^[0-6]$/.test(p))
      .map((p) => Number(p))
    if (dows.length > 0 && dows.every((n) => n >= 0 && n <= 6)) {
      const days = dows.map((n) => WEEKDAYS[n]).join(' y ')
      return `los ${days} a ${time}`
    }
    return null
  }

  if (dom !== '*') {
    if (/^\d+$/.test(dom)) return `el día ${Number(dom)} de cada mes a ${time}`
    if (dom.toLowerCase() === 'l') return `el último día de cada mes a ${time}`
    return null
  }

  return `todos los días a ${time}`
}

/** Muestra el tipo de tarea de manera legible. */
export function taskTypeLabel(type: TaskType): string {
  switch (type) {
    case 'backup':
      return 'Backup'
    case 'restart':
      return 'Reinicio'
    case 'command':
      return 'Comando'
  }
}