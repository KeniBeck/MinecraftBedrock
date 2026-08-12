import { useDeferredValue, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Input } from '@/components/ui/input'
import { getApiCode, getApiMessage } from '@/lib/api/client'
import { useCan } from '@/lib/auth/useCan'
import type { GlobalBanResponse, ServerBanResponse } from '@/lib/api/players'
import { toBanRows } from './banRows'
import { BanPlayerDialog } from './components/BanPlayerDialog'
import { BanListSection } from './components/BanListSection'
import { GlobalBanDialog } from './components/GlobalBanDialog'
import { OnlinePlayerRow } from './components/OnlinePlayerRow'
import {
  useBanPlayerOnServer,
  useGlobalBans,
  useKickPlayer,
  useOnlinePlayers,
  useSearchPlayer,
  useServerBans,
  useUnbanPlayerGlobally,
  useUnbanPlayerOnServer,
} from './hooks'
import { Search, ShieldX } from 'lucide-react'

interface UnbanTarget {
  scope: 'global' | 'server'
  playerId: string
  banId: string
  gamertag: string
}

/** Devuelve el ban activo que coincide con un resultado de búsqueda. */
function matchBan(result: { name: string; xuid: string }, bans: (GlobalBanResponse | ServerBanResponse)[]) {
  const key = result.name.toLowerCase()
  return bans.find(
    (ban) =>
      (ban.xuid !== null && ban.xuid === result.xuid) ||
      (ban.xuid === null && ban.gamertag.toLowerCase() === key),
  )
}

export function PlayersPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const canManage = useCan('player.manage')
  const canWrite = useCan('permission.write')
  const canGlobal = useCan('player.ban.global')

  const [query, setQuery] = useState('')
  const deferred = useDeferredValue(query)
  const search = useSearchPlayer(serverId, deferred)

  const [globalBanOpen, setGlobalBanOpen] = useState(false)
  const [banTarget, setBanTarget] = useState<string | null>(null)
  const [kickTarget, setKickTarget] = useState<string | null>(null)
  const [unbanTarget, setUnbanTarget] = useState<UnbanTarget | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const online = useOnlinePlayers(serverId)
  const globalBans = useGlobalBans(canGlobal)
  const serverBans = useServerBans(serverId)
  const kick = useKickPlayer(serverId ?? '')
  const ban = useBanPlayerOnServer(serverId ?? '')
  const unbanGlobal = useUnbanPlayerGlobally()
  const unbanServer = useUnbanPlayerOnServer(serverId ?? '')

  const banRows = useMemo(
    () => toBanRows(globalBans.data ?? [], serverBans.data ?? []),
    [globalBans.data, serverBans.data],
  )

  if (!serverId) return null

  const searchResults = search.data ?? []

  const handleKick = () => {
    if (!kickTarget) return
    const xuid = kickTarget
    setKickTarget(null)
    kick.mutate(xuid, { onError: (err) => setActionError(getApiMessage(err)) })
  }

  const handleUnban = () => {
    if (!unbanTarget) return
    const target = unbanTarget
    setUnbanTarget(null)
    const run =
      target.scope === 'global'
        ? () => unbanGlobal.mutateAsync(target.playerId)
        : () => unbanServer.mutateAsync(target.playerId)
    run().catch((err) => setActionError(getApiMessage(err)))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Jugadores</h1>
        {canGlobal && (
          <Button variant="destructive" pixel onClick={() => setGlobalBanOpen(true)}>
            <ShieldX className="mr-1 h-4 w-4" />
            Ban global
          </Button>
        )}
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
        >
          {actionError}
        </div>
      )}

      {/* Buscador de jugadores por gamertag (coincidencia parcial). */}
      <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl">
        <label htmlFor="player-search" className="mb-1 block text-sm font-medium">
          Buscar jugador por gamertag
        </label>
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="player-search"
              className="pl-9"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Gamertag de Xbox (ej. Cra)"
            />
          </div>
        </div>

        {query.trim() && search.isLoading && (
          <p className="mt-2 text-xs text-muted-foreground">Buscando…</p>
        )}
        {query.trim() && !search.isLoading && search.isError && (
          <p className="mt-2 text-xs text-red-300">
            {getApiCode(search.error) === 'PLAYER.NOT_FOUND'
              ? `No se encontró "${query.trim()}" en la caché del panel.`
              : getApiMessage(search.error, 'Error al buscar el jugador')}
          </p>
        )}
        {query.trim() && !search.isLoading && !search.isError && searchResults.length === 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            Sin coincidencias para "{query.trim()}".
          </p>
        )}
        {searchResults.length > 0 && (
          <div className="mt-3 space-y-2">
            {searchResults.map((result) => {
              const globalBan = matchBan(result, globalBans.data ?? [])
              const serverBan = matchBan(result, serverBans.data ?? [])
              const banned = globalBan !== undefined || serverBan !== undefined
              return (
                <div
                  key={result.xuid}
                  className={`flex items-center justify-between rounded-none border px-3 py-2 ${
                    banned
                      ? 'border-red-500/30 bg-red-500/10'
                      : 'border-emerald-500/30 bg-emerald-500/10'
                  }`}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{result.name}</p>
                    <p className="text-xs text-muted-foreground">XUID: {result.xuid}</p>
                  </div>
                  {banned ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      pixel
                      disabled={unbanGlobal.isPending || unbanServer.isPending}
                      onClick={() =>
                        setUnbanTarget({
                          scope: serverBan !== undefined ? 'server' : 'global',
                          playerId:
                            serverBan !== undefined
                              ? (serverBan.xuid ?? result.xuid)
                              : (globalBan?.id ?? ''),
                          banId: (serverBan ?? globalBan)?.id ?? '',
                          gamertag: result.name,
                        })
                      }
                    >
                      Desbanear
                    </Button>
                  ) : (
                    (canManage || canWrite) && (
                      <div className="flex gap-2">
                        {canManage && (
                          <Button
                            variant="secondary"
                            size="sm"
                            pixel
                            onClick={() => setKickTarget(result.xuid)}
                          >
                            Kick
                          </Button>
                        )}
                        {canWrite && (
                          <Button
                            variant="destructive"
                            size="sm"
                            pixel
                            onClick={() => setBanTarget(result.xuid)}
                          >
                            Ban
                          </Button>
                        )}
                      </div>
                    )
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Jugadores baneados (globales + este servidor) — visibles "a la mano". */}
      {(canWrite || canGlobal) && (
        <BanListSection
          bans={banRows}
          unbanningId={unbanTarget?.banId ?? null}
          onUnban={(scope, playerId, banId, gamertag) =>
            setUnbanTarget({ scope, playerId, banId, gamertag })
          }
        />
      )}

      {/* Jugadores con sesión abierta. */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Jugadores en línea</h2>
        {online.isLoading && <p className="text-sm text-muted-foreground">Cargando…</p>}
        {online.isError && (
          <p className="text-sm text-red-300">
            {getApiMessage(online.error, 'No se pudo cargar la lista de jugadores')}
          </p>
        )}
        {online.data && online.data.length === 0 && (
          <p className="py-8 text-center text-muted-foreground">No hay jugadores conectados.</p>
        )}
        <div className="space-y-3">
          {online.data?.map((session) => (
            <OnlinePlayerRow
              key={session.id}
              session={session}
              onKick={(xuid) => setKickTarget(xuid)}
              onBan={(xuid) => setBanTarget(xuid)}
              isKicking={kick.isPending}
              isBanning={ban.isPending}
            />
          ))}
        </div>
      </div>

      <ConfirmDialog
        open={kickTarget !== null}
        onOpenChange={(next) => {
          if (!next) setKickTarget(null)
        }}
        title="Expulsar jugador"
        description={`¿Expulsar al jugador con XUID ${kickTarget ?? ''}? Puede volver a entrar.`}
        confirmLabel="Expulsar"
        busy={kick.isPending}
        onConfirm={handleKick}
      />

      <ConfirmDialog
        open={unbanTarget !== null}
        onOpenChange={(next) => {
          if (!next) setUnbanTarget(null)
        }}
        title="Desbanear jugador"
        description={`¿Quitar el ban a ${unbanTarget?.gamertag || 'este jugador'}? Podrá volver a entrar.`}
        confirmLabel="Desbanear"
        busy={unbanGlobal.isPending || unbanServer.isPending}
        onConfirm={handleUnban}
      />

      <BanPlayerDialog
        open={banTarget !== null}
        onOpenChange={(next) => {
          if (!next) setBanTarget(null)
        }}
        serverId={serverId}
        xuid={banTarget ?? ''}
      />

      <GlobalBanDialog open={globalBanOpen} onOpenChange={setGlobalBanOpen} />
    </div>
  )
}
