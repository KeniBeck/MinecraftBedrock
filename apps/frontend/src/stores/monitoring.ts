import { create } from 'zustand'

/** Snapshot de monitoreo (payload de `SERVER.STATE` scope=monitoring). */
export interface MonitoringSnapshot {
  state: string
  status: string
  latency_ms: number | null
  players: number
  players_max: number
  cpu: number | null
  ram_mb: number | null
  disk_mb: number | null
}

/** Muestra con timestamp para los gráficos (una entrada por snapshot WS). */
export interface MetricSample extends MonitoringSnapshot {
  /** ISO timestamp del envelope (campo `ts` del WS). */
  ts: string
}

/**
 * Tope del histórico en memoria por servidor. El WS emite cada ~5 s; con 2000
 * muestras se cubren ~2.7 h completas y un buen rango de gráfico. El selector
 * de rango filtra sobre esto y muestra solo lo disponible (no hay REST).
 */
export const MAX_SNAPSHOTS = 2000

/**
 * Últimos snapshots de monitoreo por servidor. Cada servidor con un WS de
 * monitoreo activo escribe aquí; los componentes leen en vivo sin abrir sus
 * propios sockets (frontend-standards §4 — un solo cliente WS por recurso).
 */
interface MonitoringState {
  /** Último snapshot por servidor (StatCards/Header). */
  snapshots: Record<string, MonitoringSnapshot>
  /** Histórico de muestras por servidor (gráficos de MonitoringPage). */
  history: Record<string, MetricSample[]>
  setSnapshot: (serverId: string, snapshot: MonitoringSnapshot, ts?: string) => void
  clear: (serverId: string) => void
}

const EMPTY: MonitoringSnapshot = {
  state: 'unknown',
  status: 'unknown',
  latency_ms: null,
  players: 0,
  players_max: 0,
  cpu: null,
  ram_mb: null,
  disk_mb: null,
}

function appendSample(
  history: MetricSample[] | undefined,
  sample: MetricSample,
): MetricSample[] {
  const next = [...(history ?? []), sample]
  return next.length > MAX_SNAPSHOTS ? next.slice(next.length - MAX_SNAPSHOTS) : next
}

export const useMonitoringStore = create<MonitoringState>((set) => ({
  snapshots: {},
  history: {},
  setSnapshot: (serverId, snapshot, ts) =>
    set((state) => {
      const sample: MetricSample = { ...snapshot, ts: ts ?? new Date().toISOString() }
      return {
        snapshots: { ...state.snapshots, [serverId]: snapshot },
        history: {
          ...state.history,
          [serverId]: appendSample(state.history[serverId], sample),
        },
      }
    }),
  clear: (serverId) =>
    set((state) => {
      const snapshots = { ...state.snapshots }
      delete snapshots[serverId]
      const history = { ...state.history }
      delete history[serverId]
      return { snapshots, history }
    }),
}))

/** Lee el snapshot de un servidor (o EMPTY si aún no llega ninguno). */
export function currentSnapshot(
  snapshots: Record<string, MonitoringSnapshot>,
  serverId: string | null | undefined,
): MonitoringSnapshot {
  return snapshots[serverId ?? ''] ?? EMPTY
}
