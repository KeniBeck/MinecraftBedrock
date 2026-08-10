import { useEffect, useState, type ReactNode } from 'react'

import { Box, Globe, Layers, Timer, Loader2, Play, RotateCw, Square } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { serverActions, STATE_LABEL } from '@/lib/serverState'
import { currentBackground, useThemeStore } from '@/stores/theme'
import type { Server } from '@/lib/api/servers'
import { cn } from '@/lib/utils'

interface ServerCardProps {
  server: Server
  onStart: () => void
  onStop: () => void
  onRestart: () => void
  busy: 'start' | 'stop' | 'restart' | null
}

function textColor(state: Server['state']): string {
  if (state === 'running' || state === 'starting') return 'text-emerald-300'
  if (state === 'crashed') return 'text-red-300'
  return 'text-slate-300'
}

function StatusBadge({ state }: { state: Server['state'] }) {
  const isRunning = state === 'running' || state === 'starting'
  const dot = isRunning
    ? 'bg-emerald-400 shadow-[0_0_0_3px_rgba(16,185,129,.18)]'
    : state === 'crashed'
      ? 'bg-red-400 shadow-[0_0_0_3px_rgba(248,113,113,.18)]'
      : 'bg-slate-400 shadow-[0_0_0_3px_rgba(148,163,184,.15)]'
  return (
    <span className="inline-flex items-center gap-2 border border-black bg-slate-900/70 px-2.5 py-1 shadow-[inset_1px_1px_0_rgba(255,255,255,.15),inset_-1px_-1px_0_rgba(0,0,0,.4)]">
      <span className={cn('size-2 rounded-none', dot)} />
      <span className={cn('font-pixel text-[9px] tracking-wider', textColor(state))}>
        {STATE_LABEL[state]}
      </span>
    </span>
  )
}

/** Píldora glass con ícono para un dato de la metadata central. */
function Pill({ icon, children, title }: { icon: ReactNode, children: ReactNode, title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-2 rounded-full bg-slate-900/60 px-3 py-1.5 text-xs font-medium text-white backdrop-blur-xl border border-white/10"
    >
      {icon}
      <span className="truncate">{children}</span>
    </span>
  )
}

/** Tiempo activo aproximado desde `updated_at` cuando el server está en línea. */
function UptimeLabel({ server }: { server: Server }) {
  const isRunning = server.state === 'running' || server.state === 'starting'
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!isRunning) return
    const timer = setInterval(() => setNow(Date.now()), 60_000)
    return () => clearInterval(timer)
  }, [isRunning])

  if (!isRunning) {
    return <span className="text-slate-400">—</span>
  }
  const elapsed = Math.max(0, now - new Date(server.updated_at).getTime())
  const hours = Math.floor(elapsed / 3_600_000)
  const minutes = Math.floor((elapsed % 3_600_000) / 60_000)
  return <span className="text-slate-200">{hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`}</span>
}

/**
 * Card principal del servidor (mockup §9.1): cristal redondeado, 3 columnas —
 * imagen del mundo (pixelada, estirada a la altura), metadata en píldoras glass
 * y columna de botones pixelados. Layout con grid y alineación central.
 */
export function ServerCard({ server, onStart, onStop, onRestart, busy }: ServerCardProps) {
  const actions = serverActions(server.state)
  const backgroundId = useThemeStore((state) => state.backgroundId)
  const background = currentBackground({ backgroundId })
  const running = server.state === 'running' || server.state === 'starting'

  const actionButtons = [
    { key: 'start' as const, variant: 'start' as const, label: 'Iniciar', icon: <Play />, disabled: !actions.canStart, onClick: onStart },
    { key: 'restart' as const, variant: 'restart' as const, label: 'Reiniciar', icon: <RotateCw />, disabled: !actions.canRestart, onClick: onRestart },
    { key: 'stop' as const, variant: 'stop' as const, label: 'Detener', icon: <Square />, disabled: !actions.canStop, onClick: onStop },
  ]

  return (
    <section
      className={cn(
        'relative w-full rounded-xl bg-slate-900/60 backdrop-blur-xl border border-white/10',
        'flex flex-col gap-8 p-6 md:flex-row md:items-stretch',
      )}
    >
      {/* Col 1 — el mundo: imagen pixelada estirada a la altura de los botones. */}
      <div
        className="relative shrink-0 self-stretch overflow-hidden rounded-xl border border-black/60 bg-black/40 md:flex-1 md:min-h-0"
        style={{ imageRendering: 'pixelated' }}
        aria-hidden
      >
        <div
          className="absolute inset-0"
          style={{
            background: background.css,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        />
        {running && (
          <span className="absolute right-1.5 top-1.5 flex size-2.5 rounded-none bg-emerald-400 shadow-[0_0_0_3px_rgba(16,185,129,.25)]" />
        )}
      </div>

      {/* Col 2 — título + badge + píldoras de metadata. */}
      <div className="flex min-w-0 flex-1 flex-col items-start justify-center gap-5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h2 className="pixel-title truncate text-base text-white sm:text-lg">{server.name}</h2>
          <StatusBadge state={server.state} />
        </div>

        <div className="flex max-w-full flex-wrap gap-2">
          <Pill icon={<Layers className="h-3 w-3 text-slate-300" />} title={server.version}>{server.version}</Pill>
          <Pill icon={<Box className="h-3 w-3 text-slate-300" />} title={server.name}>{server.name}</Pill>
          <Pill icon={<Globe className="h-3 w-3 text-slate-300" />} title={server.connection.address}>{server.connection.address}</Pill>
          <Pill icon={<Timer className="h-3 w-3 text-slate-300" />}>
            <UptimeLabel server={server} />
          </Pill>
        </div>
      </div>

      {/* Col 3 — botones pixelados apilados a la derecha. */}
      <div className="flex flex-col gap-2 md:w-48 md:items-stretch">
        {actionButtons.map((a) => (
          <Button
            key={a.key}
            variant={a.variant}
            size="default"
            disabled={a.disabled || busy !== null}
            onClick={a.onClick}
            data-testid={`${a.key}-button`}
            className="pixel-btn rounded-none w-full h-10 text-sm"
          >
            {busy === a.key ? <Loader2 className="animate-spin" /> : a.icon}
            {a.label}
          </Button>
        ))}
        <Button
          variant="backup"
          size="default"
          disabled
          data-testid="backup-button"
          title="Disponible en una fase posterior"
          className="pixel-btn rounded-none w-full h-10 text-sm"
        >
          Crear backup
        </Button>
      </div>
    </section>
  )
}