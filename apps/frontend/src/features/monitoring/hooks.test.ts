import { describe, expect, it } from 'vitest'

import { filterByRange, rangeDurationMs, TIME_RANGES, type TimeRangeId } from './hooks'
import type { MetricSample } from '@/stores/monitoring'

function sample(ts: string): MetricSample {
  return {
    ts,
    state: 'running',
    status: 'online',
    latency_ms: 1,
    players: 1,
    players_max: 10,
    cpu: 5,
    ram_mb: 512,
    disk_mb: 2048,
  }
}

describe('rangeDurationMs', () => {
  it('expone los 5 rangos del plan', () => {
    expect(TIME_RANGES.map((r) => r.id)).toEqual(['15m', '1h', '6h', '24h', '7d'])
  })

  it('devuelve la duración en ms de cada rango', () => {
    expect(rangeDurationMs('15m')).toBe(15 * 60 * 1000)
    expect(rangeDurationMs('1h')).toBe(60 * 60 * 1000)
    expect(rangeDurationMs('7d')).toBe(7 * 24 * 60 * 60 * 1000)
  })

  it('cae al primer rango si el id es desconocido', () => {
    expect(rangeDurationMs('bogus' as TimeRangeId)).toBe(15 * 60 * 1000)
  })
})

describe('filterByRange', () => {
  const now = new Date('2026-08-12T12:00:00Z').getTime()
  const samples = [
    sample('2026-08-12T10:00:00Z'), // hace 2h (fuera de 1h)
    sample('2026-08-12T11:30:00Z'), // hace 30m
    sample('2026-08-12T11:59:00Z'), // hace 1m
    sample('2026-08-12T12:00:00Z'), // ahora
  ]

  it('mantiene las muestras dentro de la ventana', () => {
    const within1h = filterByRange(samples, 60 * 60 * 1000, now)
    expect(within1h.length).toBe(3)
  })

  it('filtra según el rango elegido', () => {
    const within15m = filterByRange(samples, 15 * 60 * 1000, now)
    expect(within15m.length).toBe(2)
  })

  it('ignora timestamps inválidos', () => {
    const bad = [sample('no-es-fecha'), ...samples]
    expect(filterByRange(bad, 60 * 60 * 1000, now).length).toBe(3)
  })

  it('preserva el orden cronológico', () => {
    const out = filterByRange(samples, 60 * 60 * 1000, now)
    expect(out.map((s) => s.ts)).toEqual([
      '2026-08-12T11:30:00Z',
      '2026-08-12T11:59:00Z',
      '2026-08-12T12:00:00Z',
    ])
  })
})
