import { useParams } from 'react-router-dom'

import { Loader2 } from 'lucide-react'

import { getApiMessage } from '@/lib/api/client'
import { useServer } from '@/features/servers/hooks'
import { useConsole } from '@/features/console/hooks'
import { ConsoleTerminal } from '@/features/console/components/ConsoleTerminal'

/**
 * Página de consola en vivo (`/servers/:serverId/console`). Reutiliza
 * `useServer` (carga + sync de estado por WS) para saber si el servidor está en
 * línea y `useConsole` para conectar el WS de consola del servidor.
 */
export function ConsolePage() {
  const { serverId } = useParams<{ serverId: string }>()
  const { data: server, isLoading, isError, error } = useServer(serverId)
  useConsole(serverId)

  if (isLoading) {
    return (
      <div data-testid="console-loading" className="flex items-center justify-center py-24">
        <Loader2 className="size-6 animate-spin text-emerald-300" />
      </div>
    )
  }

  if (isError || !server) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        {getApiMessage(error, 'No se pudo cargar el servidor')}
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-9rem)]">
      <ConsoleTerminal serverId={server.id} serverState={server.state} />
    </div>
  )
}
