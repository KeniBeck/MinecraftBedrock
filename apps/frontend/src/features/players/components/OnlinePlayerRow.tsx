import { Button } from '@/components/ui/button'
import { useCan } from '@/lib/auth/useCan'
import { formatDuration } from '@/lib/format'
import type { PlaySessionResponse } from '@/lib/api/players'

interface OnlinePlayerRowProps {
  session: PlaySessionResponse
  onKick: (xuid: string) => void
  onBan: (xuid: string) => void
  isKicking?: boolean
  isBanning?: boolean
}

/**
 * Fila de un jugador con sesión abierta: XUID + hora de conexión + duración.
 * El backend NO devuelve el gamertag en `online` (PlaySessionResponse solo
 * trae `xuid`), así que el nombre se resuelve aparte (buscador de jugadores)
 * y las acciones kick/ban se lanzan sobre el XUID.
 */
export function OnlinePlayerRow({
  session,
  onKick,
  onBan,
  isKicking = false,
  isBanning = false,
}: OnlinePlayerRowProps) {
  const canManage = useCan('player.manage')
  const canWrite = useCan('permission.write')

  return (
    <div className="flex items-center justify-between rounded-xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-3">
          <span className="truncate font-mono text-sm">{session.xuid}</span>
          <span className="rounded-none border border-emerald-500/30 bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-300">
            En línea
          </span>
        </div>
        <div className="mt-1 flex gap-4 text-xs text-muted-foreground">
          <span>Desde {new Date(session.joined_at).toLocaleTimeString()}</span>
          {session.playtime_seconds > 0 && (
            <span>{formatDuration(session.playtime_seconds)} en esta sesión</span>
          )}
        </div>
      </div>
      {(canManage || canWrite) && (
        <div className="flex items-center gap-2">
          {canManage && (
            <Button
              variant="secondary"
              size="sm"
              pixel
              disabled={isKicking}
              onClick={() => onKick(session.xuid)}
            >
              Kick
            </Button>
          )}
          {canWrite && (
            <Button
              variant="destructive"
              size="sm"
              pixel
              disabled={isBanning}
              onClick={() => onBan(session.xuid)}
            >
              Ban
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
