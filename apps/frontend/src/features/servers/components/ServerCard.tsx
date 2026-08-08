import { Loader2, Play, RotateCw, Square } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { serverActions, STATE_BADGE, STATE_LABEL } from '@/lib/serverState'
import type { Server } from '@/lib/api/servers'
import { cn } from '@/lib/utils'

interface ServerCardProps {
  server: Server
  onStart: () => void
  onStop: () => void
  onRestart: () => void
  busy: 'start' | 'stop' | 'restart' | null
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold text-foreground">{value}</span>
    </div>
  )
}

/**
 * Card grande del servidor (mockup §9.1): miniatura, nombre, badge de estado,
 * metadata en pastillas y los 4 botones de acción con color semántico.
 */
export function ServerCard({ server, onStart, onStop, onRestart, busy }: ServerCardProps) {
  const actions = serverActions(server.state)
  const isRunning = server.state === 'running' || server.state === 'starting'

  return (
    <Card className="overflow-hidden rounded-2xl border-white/10 bg-slate-900/60 backdrop-blur-xl">
      {/* Miniatura decorativa (sin mundo todavía — Fase 4). */}
      <div className="h-36 bg-gradient-to-br from-indigo-900/60 via-slate-900/40 to-emerald-900/30" />
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="min-w-0">
          <CardTitle className="text-2xl">{server.name}</CardTitle>
          <CardDescription
            title={server.image_ref}
            className="max-w-[26rem] truncate"
          >
            {server.image_ref}
          </CardDescription>
        </div>
        <Badge className={cn('mt-1', STATE_BADGE[server.state])}>
          <span
            className={cn(
              'size-1.5 rounded-full',
              isRunning ? 'bg-emerald-400' : server.state === 'crashed' ? 'bg-red-400' : 'bg-slate-400',
            )}
          />
          {STATE_LABEL[server.state]}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <StatPill label="Versión" value={server.version} />
          <StatPill label="Dirección" value={server.connection.address} />
          <StatPill label="Puerto" value={String(server.connection.port)} />
          <StatPill label="RCON" value={server.connection.rcon_port ? String(server.connection.rcon_port) : '—'} />
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Button
            variant="start"
            disabled={!actions.canStart || busy !== null}
            onClick={onStart}
            data-testid="start-button"
          >
            {busy === 'start' ? <Loader2 className="animate-spin" /> : <Play />}
            Iniciar
          </Button>
          <Button
            variant="restart"
            disabled={!actions.canRestart || busy !== null}
            onClick={onRestart}
            data-testid="restart-button"
          >
            {busy === 'restart' ? <Loader2 className="animate-spin" /> : <RotateCw />}
            Reiniciar
          </Button>
          <Button
            variant="stop"
            disabled={!actions.canStop || busy !== null}
            onClick={onStop}
            data-testid="stop-button"
          >
            {busy === 'stop' ? <Loader2 className="animate-spin" /> : <Square />}
            Detener
          </Button>
          <Button
            variant="backup"
            disabled
            data-testid="backup-button"
            title="Disponible en una fase posterior"
          >
            Crear backup
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
