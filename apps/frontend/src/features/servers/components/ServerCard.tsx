import { useEffect, useState } from 'react'

import { Loader2, Play, RotateCw, Square } from 'lucide-react'

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

function CeilTag({ label, value }: { label: string; value: string }) {
  return (
    <span className="pixel-tag max-w-[18rem]">
      <span className="pixel-tag-label">{label}</span>
      <span className="pixel-tag-value min-w-0 truncate" title={value}>
        {value}
      </span>
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
    return <span className="pixel-tag-value text-slate-400">—</span>
  }
  const elapsed = Math.max(0, now - new Date(server.updated_at).getTime())
  const hours = Math.floor(elapsed / 3_600_000)
  const minutes = Math.floor((elapsed % 3_600_000) / 60_000)
  const text = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
  return <span className="pixel-tag-value text-slate-200">{text}</span>
}

/**
 * Card principal del servidor (mockup §9.1) como bloque con bisel. Layout en dos
 * columnas: a la izquierda el "mundo" (la imagen de fondo del panel, renderizada
 * pixelada), al centro el título + badge y una cuadrícula de datos, y a la
 * derecha la columna vertical de acciones (Iniciar/Reiniciar/Detener/Backup).
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
        'grid gap-6 p-6 md:grid-cols-[auto_1fr_auto]',
      )}
    >
      {/* Col 1 — el mundo: imagen de fondo pixelada (reemplaza al avatar). */}
      <div
        className="relative aspect-[4/3] w-40 shrink-0 overflow-hidden rounded-xl border border-black/60 bg-black/40"
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

      {/* Col 2 — título + badge + cuadrícula de datos. */}
      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h2 className="pixel-title truncate text-base text-white sm:text-lg">{server.name}</h2>
          <StatusBadge state={server.state} />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <CeilTag label="Versión" value={server.version} />
          <CeilTag label="Mundo" value={server.name} />
          <CeilTag label="Dirección" value={server.connection.address} />
          <div className="pixel-tag max-w-[18rem]">
            <span className="pixel-tag-label">Tiempo activo</span>
            <UptimeLabel server={server} />
          </div>
        </div>
      </div>

      {/* Col 3 — botones de acción apilados a la derecha. */}
      <div className="flex flex-col gap-3">
        {actionButtons.map((a) => (
          <Button
            key={a.key}
            variant={a.variant}
            size="lg"
            disabled={a.disabled || busy !== null}
            onClick={a.onClick}
            data-testid={`${a.key}-button`}
            className="w-full h-12 text-base"
          >
            {busy === a.key ? <Loader2 className="animate-spin" /> : a.icon}
            {a.label}
          </Button>
        ))}
        <Button
          variant="backup"
          size="lg"
          disabled
          data-testid="backup-button"
          title="Disponible en una fase posterior"
          className="w-full h-12 text-base"
        >
          Crear backup
        </Button>
      </div>
    </section>
  )
}