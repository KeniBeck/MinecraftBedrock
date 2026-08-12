import { useMonitoringStore, type MetricSample } from '@/stores/monitoring'

/** Rangos temporales del selector (en milisegundos). */
export const TIME_RANGES = [
  { id: '15m', label: '15m', ms: 15 * 60 * 1000 },
  { id: '1h', label: '1h', ms: 60 * 60 * 1000 },
  { id: '6h', label: '6h', ms: 6 * 60 * 60 * 1000 },
  { id: '24h', label: '24h', ms: 24 * 60 * 60 * 1000 },
  { id: '7d', label: '7d', ms: 7 * 24 * 60 * 60 * 1000 },
] as const

export type TimeRangeId = (typeof TIME_RANGES)[number]['id']

/** Duración de un rango en ms (por id). */
export function rangeDurationMs(id: TimeRangeId): number {
  return TIME_RANGES.find((r) => r.id === id)?.ms ?? TIME_RANGES[0].ms
}

/** Filtra las muestras dentro de la ventana temporal (por `ts`). */
export function filterByRange(samples: MetricSample[], rangeMs: number, now = Date.now()): MetricSample[] {
  const cutoff = now - rangeMs
  return samples.filter((s) => {
    const t = new Date(s.ts).getTime()
    return Number.isFinite(t) && t >= cutoff
  })
}

/**
 * Normaliza el % de CPU del backend a 0..100. El backend reporta CPU POR
 * NÚCLEO (fórmula Docker × `online_cpus`: 100% = un núcleo), así que en un
 * host multicore un proceso puede dar N×100%. Dividir por `cpuCores` (núcleos
 * asignados al servidor) devuelve 100% = toda la CPU asignada.
 */
export function normalizeCpu(
  cpu: number | null | undefined,
  cpuCores: number | undefined,
): number | null {
  if (cpu == null) return null
  if (cpuCores && cpuCores > 0) return Math.max(0, Math.min(100, cpu / cpuCores))
  return Math.max(0, Math.min(100, cpu))
}

/**
 * Histórico de muestras de monitoreo de un servidor desde `useMonitoringStore`
 * (los gráficos leen de aquí, no abren sockets propios). Devuelve `undefined`
 * si el servidor aún no tiene muestras (referencia estable — zustand compara
 * con `Object.is`, no devolver un `[]` nuevo cada render o hay bucle). El WS
 * acumula hasta `MAX_SNAPSHOTS` por servidor; el rango más largo muestra solo
 * lo disponible.
 */
export function useMonitoringHistory(serverId: string | undefined): MetricSample[] | undefined {
  return useMonitoringStore((state) => state.history[serverId ?? ''])
}
