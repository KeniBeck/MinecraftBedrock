import { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'

import { Loader2 } from 'lucide-react'

import { getApiMessage } from '@/lib/api/client'
import { useRestartServer, useServer, useStartServer, useStopServer } from '@/features/servers/hooks'
import { ServerCard } from '@/features/servers/components/ServerCard'
import { StatCards } from '@/features/servers/components/StatCards'

type BusyAction = 'start' | 'stop' | 'restart' | null

export function ServerDetailPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const { data: server, isLoading, isError, error } = useServer(serverId)
  const [busy, setBusy] = useState<BusyAction>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const startMutation = useStartServer()
  const stopMutation = useStopServer()
  const restartMutation = useRestartServer()

  const run = useCallback(
    async (action: Exclude<BusyAction, null>, fn: () => Promise<unknown>) => {
      if (!serverId) return
      setActionError(null)
      setBusy(action)
      try {
        await fn()
      } catch (err) {
        setActionError(getApiMessage(err, 'No se pudo completar la acción'))
      } finally {
        setBusy(null)
      }
    },
    [serverId],
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (isError || !server) {
    const message = getApiMessage(error, 'No se pudo cargar el servidor')
    return (
      <div
        role="alert"
        className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-6 text-sm text-red-300"
      >
        {message}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {actionError && (
        <div
          role="alert"
          className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300"
        >
          {actionError}
        </div>
      )}
      <ServerCard
        server={server}
        busy={busy}
        onStart={() => run('start', () => startMutation.mutateAsync({ serverId: server.id }))}
        onStop={() => run('stop', () => stopMutation.mutateAsync({ serverId: server.id }))}
        onRestart={() =>
          run('restart', () => restartMutation.mutateAsync({ serverId: server.id }))
        }
      />
      <StatCards server={server} />
    </div>
  )
}
