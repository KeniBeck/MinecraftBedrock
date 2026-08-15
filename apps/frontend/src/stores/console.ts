import { create } from 'zustand'

/** Línea de consola (envelope `CONSOLE.OUTPUT` del WS de consola). */
export interface ConsoleLine {
  seq: number
  line: string
  timestamp: string
}

/**
 * Buffer de consola por servidor (límite 1000 líneas, igual que el anillo del
 * backend `ConsoleLog.max_lines`). Además de las líneas se guarda el último
 * `seq` visto por servidor para reanudar el WS de consola con `after_seq` sin
 * duplicar líneas al reconectar o al volver a la página.
 */
interface ConsoleState {
  lines: Record<string, ConsoleLine[]>
  lastSeq: Record<string, number>
  addLine: (serverId: string, line: ConsoleLine) => void
  addLines: (serverId: string, lines: ConsoleLine[]) => void
  clear: (serverId: string) => void
}

const MAX_LINES = 1000

export const useConsoleStore = create<ConsoleState>((set) => ({
  lines: {},
  lastSeq: {},
  addLines: (serverId, lines) =>
    set((state) => {
      if (lines.length === 0) return state
      const current = state.lines[serverId] ?? []
      const next = [...current, ...lines]
      const trimmed = next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next
      const last = lines[lines.length - 1]!
      return {
        lines: { ...state.lines, [serverId]: trimmed },
        lastSeq: { ...state.lastSeq, [serverId]: last.seq },
      }
    }),
  addLine: (serverId, line) =>
    set((state) => {
      const current = state.lines[serverId] ?? []
      const next =
        current.length >= MAX_LINES
          ? [...current.slice(1), line]
          : [...current, line]
      return {
        lines: { ...state.lines, [serverId]: next },
        lastSeq: { ...state.lastSeq, [serverId]: line.seq },
      }
    }),
  clear: (serverId) =>
    set((state) => {
      const lines = { ...state.lines }
      const lastSeq = { ...state.lastSeq }
      delete lines[serverId]
      delete lastSeq[serverId]
      return { lines, lastSeq }
    }),
}))
