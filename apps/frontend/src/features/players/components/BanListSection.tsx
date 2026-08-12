import { Ban } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/format'
import type { BanRow } from '../banRows'

interface BanListSectionProps {
  bans: BanRow[]
  onUnban: (scope: 'global' | 'server', playerId: string, banId: string, gamertag: string) => void
  unbanningId: string | null
  title?: string
}

/**
 * Lista de jugadores baneados (globales y por servidor) con acción de
 * desbaneo. El usuario pidió tener "a la mano" los baneados en vez de tener
 * que buscarlos uno por uno.
 */
export function BanListSection({
  bans,
  onUnban,
  unbanningId,
  title = 'Jugadores baneados',
}: BanListSectionProps) {
  if (bans.length === 0) return null

  return (
    <div>
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <div className="space-y-3">
        {bans.map((ban) => (
          <div
            key={ban.banId}
            className="flex items-center justify-between rounded-xl border border-red-500/20 bg-red-500/5 p-4"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3">
                <span className="truncate text-sm font-medium">{ban.gamertag}</span>
                <span className="rounded-none border border-red-500/30 bg-red-500/20 px-2 py-0.5 text-xs text-red-300">
                  {ban.scope === 'global' ? 'Global' : 'Este servidor'}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
                {ban.reason && <span>Motivo: {ban.reason}</span>}
                <span>Desde {formatDateTime(ban.created_at)}</span>
                {ban.expires_at && <span>Hasta {formatDateTime(ban.expires_at)}</span>}
              </div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              pixel
              disabled={unbanningId === ban.banId}
              onClick={() => onUnban(ban.scope, ban.playerId, ban.banId, ban.gamertag)}
            >
              <Ban className="mr-1 h-4 w-4" />
              {unbanningId === ban.banId ? 'Quitando…' : 'Desbanear'}
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}
