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
  const inputRef = useRef<HTMLInputElement>(null)
  const focusOnEnable = useRef(false)

  const isRunning = serverState === 'running'

  useEffect(() => {
    const el = scrollRef.current
    if (el && autoScroll) el.scrollTop = el.scrollHeight
  }, [lines, autoScroll])

  useEffect(() => {
    // Enfoca solo tras el commit en que el input ya no está `disabled` y el
    // comando se vació. Los dos commits (isPending→false y command→'') pueden
    // llegar en cualquier orden, así que el effect se re-evalúa ante cualquiera.
    if (command === '' && !sendCommand.isPending && focusOnEnable.current) {
      focusOnEnable.current = false
      inputRef.current?.focus()
    }
  }, [command, sendCommand.isPending])

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
      // El input está `disabled` durante el envío; enfocar ahora no tendría efecto
      // porque React aún no ha re-renderizado. Se enfoca tras el commit (ver abajo).
      focusOnEnable.current = true
    } catch (err) {
      // 409 CONSOLE.SERVER_OFFLINE y demás: `detail.message` del backend tal cual.
      setError(getApiMessage(err, 'No se pudo enviar el comando'))
    }
  }


return (
  <section className="console-terminal flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[#080a08] text-green-400 shadow-[0_0_0_1px_rgba(0,0,0,.4),0_12px_40px_rgba(0,0,0,.25)]">

    {/* Header */}
    <div className="flex shrink-0 items-center justify-between border-b border-white/10 bg-[#0d100d] px-4 py-2.5">
      <div className="flex items-center gap-2">
        <Terminal className="size-4 text-emerald-400" />

        <span className="pixel-overline text-slate-300">
          Consola en vivo
        </span>
      </div>

      <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider">
        <span
          className={cn(
            'size-1.5 rounded-full',
            isRunning
              ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,.8)]'
              : 'bg-amber-400',
          )}
        />

        <span className="text-slate-500">
          {isRunning ? 'Online' : 'Offline'}
        </span>
      </div>
    </div>

    {/* Terminal */}
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      data-testid="console-scroll"
      className={cn(
        'console-scroll min-h-0 flex-1 overflow-y-auto',
        'bg-[#050705]',
        'px-4 py-3',
        'font-mono text-[13px] leading-6',
        'selection:bg-emerald-500/20 selection:text-emerald-200',
      )}
    >
      {/* Terminal content */}
      {lines.length === 0 ? (
        <div
          data-testid="console-empty"
          className="flex h-full items-center justify-center text-xs text-slate-600"
        >
          <span className="animate-pulse">
            Esperando líneas de consola…
          </span>
        </div>
      ) : (
        <div className="space-y-0.5">
          {lines.map((line) => (
            <div
              key={line.seq}
              className="group flex min-w-0 rounded-sm px-1 transition-colors hover:bg-white/[0.025]"
            >
              {/* Timestamp */}
              <span className="mr-3 shrink-0 select-none text-[11px] text-slate-600">
                {new Date(line.timestamp).toLocaleTimeString()}
              </span>

              {/* Prompt */}
              <span className="mr-2 select-none text-emerald-700">
                ›
              </span>

              {/* Output */}
              <span className="min-w-0 whitespace-pre-wrap break-all text-green-400/90">
                {line.line}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>

    {/* Offline banner */}
    {!isRunning && (
      <div
        data-testid="console-banner"
        className="shrink-0 border-t border-amber-500/20 bg-amber-500/[0.06] px-4 py-2 text-xs text-amber-300"
      >
        <span className="mr-2">⚠</span>
        El servidor no está en línea: no se pueden enviar comandos.
      </div>
    )}

    {/* Command input */}
    {canWrite && (
      <form
        onSubmit={handleSend}
        className="shrink-0 border-t border-white/10 bg-[#0a0d0a] p-3"
      >
        {error && (
          <div
            role="alert"
            className="mb-2 border border-red-500/30 bg-red-500/[0.06] px-3 py-2 font-mono text-xs text-red-300"
          >
            <span className="mr-2 text-red-400">✕</span>
            {error}
          </div>
        )}

        <div className="flex items-center gap-2">
          {/* Prompt */}
          <span className="select-none font-mono text-sm font-bold text-emerald-500">
            &gt;
          </span>

          <Input
            ref={inputRef}
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder={
              isRunning
                ? 'Escribe un comando…'
                : 'Servidor no disponible'
            }
            disabled={!isRunning || sendCommand.isPending}
            data-testid="console-input"
            className={cn(
              'h-10 flex-1 rounded-md border-white/10',
              'bg-[#050705]',
              'font-mono text-sm text-green-400',
              'placeholder:text-slate-600',
              'focus-visible:border-emerald-500/40',
              'focus-visible:ring-1 focus-visible:ring-emerald-500/20',
            )}
            maxLength={512}
          />

          <Button
            type="submit"
            variant="default"
            pixel
            disabled={!isRunning || sendCommand.isPending || !command.trim()}
            data-testid="console-send"
            className="h-10 min-w-20"
          >
            {sendCommand.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              'Enviar'
            )}
          </Button>
        </div>
      </form>
    )}
  </section>
)
}
