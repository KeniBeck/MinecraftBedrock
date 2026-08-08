import { API_BASE } from '@/lib/api/client'
import type { WsClientMessage, WsControlMessage, WsEnvelope } from '@/lib/ws/types'

/**
 * Cliente WebSocket compartido del gateway único `/api/v1/ws?token=`.
 *
 * Un solo socket a nivel de app (no uno por componente — frontend-standards
 * §4). Gestiona:
 * - Autenticación por query param `?token=` (los browsers no soportan headers
 *   en WebSocket de forma portable).
 * - `subscribe`/`unsubscribe` por canales.
 * - `resume` tras reconexión: guarda el último `seq` visto POR CANAL y lo manda
 *   en el `resume` antes de operar normal.
 * - Reconexión con backoff exponencial.
 * - Heartbeat `pong` ante mensajes que lo pidan (el router responde a un ping
 *   con la acción esperada; aquí se responde por si el server lo solicita).
 */

type WsEventListener = (envelope: WsEnvelope) => void
type WsControlListener = (message: WsControlMessage) => void
type WsStatusListener = (status: WsConnectionStatus) => void

export type WsConnectionStatus = 'connecting' | 'open' | 'closed'

const BACKOFF_BASE_MS = 1000
const BACKOFF_MAX_MS = 15_000

function wsUrl(token: string): string {
  // Reutiliza el origen actual; el proxy de Vite reenvía /api (HTTP + WS).
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${API_BASE}/ws?token=${encodeURIComponent(token)}`
}

export class WebSocketClient {
  private socket: WebSocket | null = null
  private token: string | null = null
  private subscriptions: Set<string> = new Set()
  /** Último `seq` visto por canal (para resume tras reconexión). */
  private lastSeqByChannel: Map<string, number> = new Map()
  private eventListeners = new Set<WsEventListener>()
  private controlListeners = new Set<WsControlListener>()
  private statusListeners = new Set<WsStatusListener>()
  private reconnectAttempt = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private manuallyClosed = false
  private status: WsConnectionStatus = 'closed'

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('offline', () => this.close(1001, 'offline'))
      window.addEventListener('online', () => {
        if (this.token && !this.manuallyClosed) this.connect(this.token)
      })
    }
  }

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN
  }

  get connectionStatus(): WsConnectionStatus {
    return this.status
  }

  connect(token: string): void {
    this.token = token
    this.manuallyClosed = false
    this.reconnectAttempt = 0
    this.open()
  }

  /** Cierre manual (logout, página que ya no necesita WS). No reconecta. */
  close(code = 1000, reason?: string): void {
    this.manuallyClosed = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.socket?.close(code, reason)
    this.socket = null
    this.setStatus('closed')
  }

  onEvent(listener: WsEventListener): () => void {
    this.eventListeners.add(listener)
    return () => this.eventListeners.delete(listener)
  }

  onControl(listener: WsControlListener): () => void {
    this.controlListeners.add(listener)
    return () => this.controlListeners.delete(listener)
  }

  onStatus(listener: WsStatusListener): () => void {
    this.statusListeners.add(listener)
    return () => this.statusListeners.delete(listener)
  }

  subscribe(...channels: string[]): void {
    for (const channel of channels) {
      this.subscriptions.add(channel)
    }
    this.send({ action: 'subscribe', channels })
  }

  unsubscribe(...channels: string[]): void {
    for (const channel of channels) {
      this.subscriptions.delete(channel)
    }
    this.send({ action: 'unsubscribe', channels })
  }

  /** Limpia el `seq` guardado de un canal (cuando el backlog se descarta). */
  forgetSeq(channel: string): void {
    this.lastSeqByChannel.delete(channel)
  }

  private open(): void {
    if (!this.token) return
    this.setStatus('connecting')
    const socket = new WebSocket(wsUrl(this.token))
    this.socket = socket

    socket.onopen = () => {
      this.reconnectAttempt = 0
      this.setStatus('open')
      // Al reconectar: resume por canal (guardando el último seq) antes de
      // re-suscribir. Si el server responde RESUME_TOO_LARGE, se re-suscribe
      // sin last_seq (perder historial es aceptable — frontend-standards §4).
      this.resumeOrSubscribe()
    }

    socket.onmessage = (event) => {
      let message: WsControlMessage
      try {
        message = JSON.parse(String(event.data)) as WsControlMessage
      } catch {
        // Frame no-JSON: lo ignora el cliente (el server cierra con 4408 solo
        // en mensajes salientes malformados, no entrantes).
        return
      }
      this.handleServerMessage(message)
    }

    socket.onclose = () => {
      this.socket = null
      this.setStatus('closed')
      if (!this.manuallyClosed) this.scheduleReconnect()
    }

    socket.onerror = () => {
      // onclose siempre sigue a onerror; no hacer nada aquí para no duplicar.
    }
  }

  private handleServerMessage(message: WsControlMessage): void {
    const envelope = this.toEnvelope(message)
    if (envelope) {
      this.recordSeq(envelope)
      this.eventListeners.forEach((listener) => listener(envelope))
      return
    }

    // Respuesta `resume`: reenvía los envelopes del backlog ordenados por seq.
    if (message.type === 'resume' && Array.isArray(message.events)) {
      for (const event of message.events) {
        this.recordSeq(event)
        this.eventListeners.forEach((listener) => listener(event))
      }
    }

    // Resume demasiado grande: perder historial y re-suscribirse sin last_seq.
    if (message.code === 'NOTI.RESUME_TOO_LARGE') {
      this.lastSeqByChannel.clear()
      this.send({ action: 'subscribe', channels: [...this.subscriptions] })
    }

    this.controlListeners.forEach((listener) => listener(message))
  }

  private toEnvelope(message: WsControlMessage): WsEnvelope | null {
    // Los envelopes traen `event` (serialize_envelope) y NO `type`; los
    // mensajes de control traen `type` (subscribed/resume/error…). Detectar
    // por `event`, no por ausencia de `type`.
    const event = message.event
    if (typeof event !== 'string' || event.length === 0) return null
    const seq = typeof message.seq === 'number' ? message.seq : 0
    const scopeRaw = message.scope ?? 'global'
    const scope = scopeRaw === 'user' || scopeRaw === 'server' ? scopeRaw : 'global'
    return {
      event,
      server_id: typeof message.server_id === 'string' ? message.server_id : null,
      scope,
      payload: (message.payload ?? {}) as Record<string, unknown>,
      ts: message.ts ?? new Date().toISOString(),
      seq,
    }
  }

  private recordSeq(envelope: WsEnvelope): void {
    if (envelope.seq > 0) {
      const channel = this.channelFor(envelope)
      const previous = this.lastSeqByChannel.get(channel) ?? 0
      if (envelope.seq > previous) {
        this.lastSeqByChannel.set(channel, envelope.seq)
      }
    }
  }

  private channelFor(envelope: WsEnvelope): string {
    if (envelope.scope === 'server' && envelope.server_id) return `server:${envelope.server_id}`
    if (envelope.scope === 'user') return 'user'
    return 'global'
  }

  private resumeOrSubscribe(): void {
    const channels = [...this.subscriptions]
    if (channels.length === 0) return
    const resumeChannels = channels.filter((c) => (this.lastSeqByChannel.get(c) ?? 0) > 0)
    if (resumeChannels.length > 0) {
      const lastSeq = Math.max(
        ...resumeChannels.map((c) => this.lastSeqByChannel.get(c) ?? 0),
      )
      this.send({ action: 'resume', last_seq: lastSeq, channels: resumeChannels })
      // El resto de canales sin seq se re-suscriben normal.
      const plain = channels.filter((c) => (this.lastSeqByChannel.get(c) ?? 0) === 0)
      if (plain.length > 0) this.send({ action: 'subscribe', channels: plain })
    } else {
      this.send({ action: 'subscribe', channels })
    }
  }

  private send(message: WsClientMessage): void {
    if (this.isConnected) {
      this.socket?.send(JSON.stringify(message))
    }
  }

  private scheduleReconnect(): void {
    if (this.manuallyClosed || this.reconnectTimer) return
    const delay = Math.min(BACKOFF_BASE_MS * 2 ** this.reconnectAttempt, BACKOFF_MAX_MS)
    this.reconnectAttempt += 1
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (!this.manuallyClosed) this.open()
    }, delay)
  }

  private setStatus(status: WsConnectionStatus): void {
    if (this.status === status) return
    this.status = status
    this.statusListeners.forEach((listener) => listener(status))
  }
}
