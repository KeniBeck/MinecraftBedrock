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

/**
 * Últimos snapshots de monitoreo por servidor. Cada servidor con un WS de
 * monitoreo activo escribe aquí; los componentes leen en vivo sin abrir sus
 * propios sockets (frontend-standards §4 — un solo cliente WS por recurso).
 */
interface MonitoringState {
  snapshots: Record<string, MonitoringSnapshot>
  setSnapshot: (serverId: string, snapshot: MonitoringSnapshot) => void
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

export const useMonitoringStore = create<MonitoringState>((set) => ({
  snapshots: {},
  setSnapshot: (serverId, snapshot) =>
    set((state) => ({ snapshots: { ...state.snapshots, [serverId]: snapshot } })),
  clear: (serverId) =>
    set((state) => {
      const snapshots = { ...state.snapshots }
      delete snapshots[serverId]
      return { snapshots }
    }),
}))

/** Lee el snapshot de un servidor (o EMPTY si aún no llega ninguno). */
export function currentSnapshot(
  snapshots: Record<string, MonitoringSnapshot>,
  serverId: string,
): MonitoringSnapshot {
  return snapshots[serverId] ?? EMPTY
}