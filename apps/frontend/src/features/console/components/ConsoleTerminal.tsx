import { useEffect, useRef, useState, type FormEvent } from 'react'

import { Loader2, Terminal } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import { useConsoleStore, type ConsoleLine } from '@/stores/console'
import { useCan } from '@/lib/auth/useCan'
import { useSendCommand } from '@/features/console/hooks'
import type { ServerState } from '@/lib/api/servers'
import { cn } from '@/lib/utils'

interface ConsoleTerminalProps {
  serverId: string
  serverState?: ServerState
}

/** Referencia estable para el selector (evita re-render infinito de zustand v5). */
const EMPTY_LINES: ConsoleLine[] = []

/**
 * Terminal de consola en vivo (Fase 3): líneas `CONSOLE.OUTPUT` desde
 * `useConsoleStore` con auto-scroll al final (se pausa si el usuario sube),
 * e input de comandos contra `POST .../console/commands`.
 *
 * `server.console.write` es WRITE_ACTION (operator+) → sin permiso se oculta el
 * input (el backend además responde 403). Si el servidor no está en línea no se
 * pueden enviar comandos (`CONSOLE.SERVER_OFFLINE`). Errores en línea, con
 * `getApiMessage` (sin toasts — sonner no está instalado).
 */
export function ConsoleTerminal({ serverId, serverState }: ConsoleTerminalProps) {
  const lines = useConsoleStore((state) => state.lines[serverId] ?? EMPTY_LINES)
  const canWrite = useCan('server.console.write')
  const sendCommand = useSendCommand(serverId)

  const [command, setCommand] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  const isRunning = serverState === 'running'

  useEffect(() => {
    const el = scrollRef.current
    if (el && autoScroll) el.scrollTop = el.scrollHeight
  }, [lines, autoScroll])

  function handleScroll() {
    const el = scrollRef.current
    if (!el) return
    setAutoScroll(el.scrollHeight - el.scrollTop <= el.clientHeight + 8)
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault()
    const trimmed = command.trim()
    if (!trimmed || !isRunning || !canWrite || sendCommand.isPending) return
    setError(null)
    try {
      await sendCommand.mutateAsync(trimmed)
      setCommand('')
    } catch (err) {
      // 409 CONSOLE.SERVER_OFFLINE y demás: `detail.message` del backend tal cual.
      setError(getApiMessage(err, 'No se pudo enviar el comando'))
    }
  }

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
      <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2.5">
        <Terminal className="size-4 text-emerald-300" />
        <span className="pixel-overline text-slate-300">Consola en vivo</span>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        data-testid="console-scroll"
        className="flex-1 min-h-0 overflow-y-auto p-4 font-mono text-xs leading-relaxed"
      >
        {lines.length === 0 && (
          <p data-testid="console-empty" className="text-slate-500">
            Esperando líneas de consola…
          </p>
        )}
        {lines.map((line) => (
          <div key={line.seq} className="whitespace-pre-wrap break-all">
            <span className="text-slate-500">{new Date(line.timestamp).toLocaleTimeString()} </span>
            <span className="text-slate-200">{line.line}</span>
          </div>
        ))}
      </div>

      {!isRunning && (
        <div
          data-testid="console-banner"
          className="border-t border-amber-500/40 bg-amber-500/10 px-4 py-2 text-xs text-amber-300"
        >
          El servidor no está en línea: no se pueden enviar comandos.
        </div>
      )}

      {canWrite && (
        <form onSubmit={handleSend} className="border-t border-white/10 p-3">
          {error && (
            <div
              role="alert"
              className="mb-2 rounded-none border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300"
            >
              {error}
            </div>
          )}
          <div className="flex gap-2">
            <Input
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder={isRunning ? 'Escribe un comando…' : 'Servidor no disponible'}
              disabled={!isRunning || sendCommand.isPending}
              data-testid="console-input"
              className={cn('flex-1 font-mono')}
              maxLength={512}
            />
            <Button
              type="submit"
              variant="default"
              pixel
              disabled={!isRunning || sendCommand.isPending || !command.trim()}
              data-testid="console-send"
              className="h-10"
            >
              {sendCommand.isPending ? <Loader2 className="animate-spin" /> : 'Enviar'}
            </Button>
          </div>
        </form>
      )}
    </section>
  )
}
