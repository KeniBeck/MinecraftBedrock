import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { WebSocketClient } from '@/lib/ws/WebSocketClient'

type Listener = ((event: MessageEvent) => void) | ((event: Event) => void)

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  readyState = 0
  sent: string[] = []
  listeners: Record<string, Listener[]> = {}

  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  addEventListener(type: string, listener: Listener) {
    this.listeners[type] = [...(this.listeners[type] ?? []), listener]
  }

  removeEventListener(type: string, listener: Listener) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((l) => l !== listener)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED
  }

  // Helpers de test (el cliente real usa `onopen`/`onclose`/`onmessage`).
  emitOpen() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }

  emitMessage(payload: unknown) {
    const event = { data: JSON.stringify(payload) } as MessageEvent
    this.onmessage?.(event)
  }

  emitClose() {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.()
  }
}

describe('WebSocketClient', () => {
  const originalHref = window.location.href

  function socketAt(index: number): FakeWebSocket {
    const socket = FakeWebSocket.instances[index]
    if (!socket) throw new Error(`FakeWebSocket[${index}] no existe`)
    return socket
  }

  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    Object.defineProperty(window, 'location', {
      value: { protocol: 'http:', host: 'localhost:5173', href: originalHref },
      writable: true,
    })
  })

  afterEach(() => {
    Object.defineProperty(window, 'location', { value: { href: originalHref }, writable: true })
    vi.unstubAllGlobals()
  })

  it('conecta con el token en el query param y suscribe', () => {
    const client = new WebSocketClient()
    client.connect('token-abc')
    const socket = socketAt(0)
    expect(socket.url).toContain('/api/v1/ws?token=token-abc')
    socket.emitOpen()
    client.subscribe('global')
    expect(socket.sent).toContain(JSON.stringify({ action: 'subscribe', channels: ['global'] }))
  })

  it('emite envelopes al listener de eventos', () => {
    const client = new WebSocketClient()
    const received: unknown[] = []
    client.onEvent((envelope) => received.push(envelope))
    client.connect('token')
    const socket = socketAt(0)
    socket.emitOpen()

    socket.emitMessage({
      event: 'SERVER.STARTED',
      server_id: 'srv-1',
      scope: 'server',
      payload: {},
      ts: '2026-01-01T00:00:00Z',
      seq: 5,
    })

    expect(received).toHaveLength(1)
    const envelope = received[0] as { event: string; seq: number }
    expect(envelope.event).toBe('SERVER.STARTED')
    expect(envelope.seq).toBe(5)
  })

  it('guarda el último seq por canal y hace resume tras reconexión', () => {
    const client = new WebSocketClient()
    client.connect('token')
    const first = socketAt(0)
    first.emitOpen()
    client.subscribe('global')

    first.emitMessage({
      event: 'HEALTH.OK',
      server_id: null,
      scope: 'global',
      payload: {},
      ts: '2026-01-01T00:00:00Z',
      seq: 10,
    })

    // Desconexión y reconexión (el timer se dispara con 0ms de delay real; en
    // el test forzamos abriendo de nuevo tras close).
    first.emitClose()
    client['reconnectAttempt'] = 0
    client['open']()
    const second = socketAt(1)
    second.emitOpen()

    expect(second.sent).toContain(
      JSON.stringify({ action: 'resume', last_seq: 10, channels: ['global'] }),
    )
  })

  it('ante RESUME_TOO_LARGE descarta el historial y re-suscribe sin last_seq', () => {
    const client = new WebSocketClient()
    client.connect('token')
    const socket = socketAt(0)
    socket.emitOpen()
    client.subscribe('global')
    client['lastSeqByChannel'].set('global', 50)

    socket.emitMessage({ type: 'error', code: 'NOTI.RESUME_TOO_LARGE', last_seq: 50 })

    expect(client['lastSeqByChannel'].has('global')).toBe(false)
    expect(socket.sent.at(-1)).toBe(
      JSON.stringify({ action: 'subscribe', channels: ['global'] }),
    )
  })

  it('al cerrar un socket en CONNECTING difiere el cierre hasta que abra', () => {
    const client = new WebSocketClient()
    client.connect('token')
    const socket = socketAt(0)
    expect(socket.readyState).toBe(FakeWebSocket.CONNECTING)

    client.close(1000, 'unmount')

    // No cierra en CONNECTING (evita "WebSocket is closed before the
    // connection is established"); el cierre se difiere al onopen.
    expect(socket.readyState).toBe(FakeWebSocket.CONNECTING)
    socket.emitOpen()
    expect(socket.readyState).toBe(FakeWebSocket.CLOSED)
  })
})
