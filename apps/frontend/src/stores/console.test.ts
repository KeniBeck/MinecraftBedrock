import { beforeEach, describe, expect, it } from 'vitest'

import { useConsoleStore, type ConsoleLine } from '@/stores/console'

function line(seq: number): ConsoleLine {
  return { seq, line: `line-${seq}`, timestamp: '2026-01-01T00:00:00Z' }
}

describe('useConsoleStore', () => {
  beforeEach(() => {
    useConsoleStore.setState({ lines: {}, lastSeq: {} })
  })

  it('añade líneas por servidor y registra el último seq', () => {
    useConsoleStore.getState().addLine('srv-1', line(0))
    useConsoleStore.getState().addLine('srv-1', line(1))
    useConsoleStore.getState().addLine('srv-2', line(0))

    const state = useConsoleStore.getState()
    expect(state.lines['srv-1']?.map((l) => l.seq)).toEqual([0, 1])
    expect(state.lines['srv-2']?.map((l) => l.seq)).toEqual([0])
    expect(state.lastSeq['srv-1']).toBe(1)
    expect(state.lastSeq['srv-2']).toBe(0)
  })

  it('mantiene los buffers por servidor independientes', () => {
    useConsoleStore.getState().addLine('srv-1', line(0))
    useConsoleStore.getState().addLine('srv-2', line(7))
    expect(useConsoleStore.getState().lines['srv-1']).toHaveLength(1)
    expect(useConsoleStore.getState().lines['srv-2']).toHaveLength(1)
  })

  it('limita el buffer a 1000 líneas (anillo, descarta la más antigua)', () => {
    const state = useConsoleStore.getState()
    for (let i = 0; i < 1005; i += 1) state.addLine('srv-1', line(i))

    const lines = useConsoleStore.getState().lines['srv-1']!
    expect(lines).toHaveLength(1000)
    expect(lines[0]?.seq).toBe(5)
    expect(lines[999]?.seq).toBe(1004)
    expect(useConsoleStore.getState().lastSeq['srv-1']).toBe(1004)
  })

  it('addLines inserta un lote en una sola escritura respetando el anillo', () => {
    useConsoleStore.getState().addLines('srv-1', [line(0), line(1), line(2)])

    const state = useConsoleStore.getState()
    expect(state.lines['srv-1']?.map((l) => l.seq)).toEqual([0, 1, 2])
    expect(state.lastSeq['srv-1']).toBe(2)

    // Lote mayor al anillo: conserva las 1000 últimas.
    const big = Array.from({ length: 1100 }, (_, i) => line(i + 10))
    useConsoleStore.getState().addLines('srv-1', big)
    const lines = useConsoleStore.getState().lines['srv-1']!
    expect(lines).toHaveLength(1000)
    expect(lines[0]?.seq).toBe(110)
    expect(lines[999]?.seq).toBe(1109)
    expect(useConsoleStore.getState().lastSeq['srv-1']).toBe(1109)
  })

  it('addLines ignora lotes vacíos', () => {
    useConsoleStore.getState().addLines('srv-1', [line(0)])
    const before = useConsoleStore.getState().lines['srv-1']!
    useConsoleStore.getState().addLines('srv-1', [])
    expect(useConsoleStore.getState().lines['srv-1']).toBe(before)
  })

  it('clear elimina líneas y lastSeq de un servidor', () => {
    useConsoleStore.getState().addLine('srv-1', line(0))
    useConsoleStore.getState().addLine('srv-2', line(0))
    useConsoleStore.getState().clear('srv-1')

    const state = useConsoleStore.getState()
    expect(state.lines['srv-1']).toBeUndefined()
    expect(state.lastSeq['srv-1']).toBeUndefined()
    expect(state.lines['srv-2']).toHaveLength(1)
  })
})
