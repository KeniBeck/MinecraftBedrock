import { Link } from 'react-router-dom'
import { ArrowUpRight, Globe, Layers } from 'lucide-react'

import type { Server } from '@/lib/api/servers'
import { STATE_BADGE, STATE_LABEL } from '@/lib/serverState'
import { cn } from '@/lib/utils'

/**
 * Tabla compacta de todos los servidores (solo lectura) para el dashboard.
 * Muestra los campos disponibles en `GET /servers` (nombre, estado, versión,
 * dirección); los jugadores online no vienen en `ServerResponse` y no se abre
 * un WS de monitoreo por servidor desde aquí, así que no se muestran.
 * La fila navega al detalle, donde sí viven las acciones y los datos en vivo.
 */
export function ServerTable({ servers }: { servers: Server[] }) {
  if (servers.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        Sin servidores visibles. Crea uno desde el detalle o el selector del header.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-white/10">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-white/10 bg-white/5 text-xs uppercase tracking-wider text-slate-400">
            <th className="px-4 py-3 font-medium">Servidor</th>
            <th className="px-4 py-3 font-medium">Estado</th>
            <th className="hidden px-4 py-3 font-medium sm:table-cell">Versión</th>
            <th className="hidden px-4 py-3 font-medium md:table-cell">Dirección</th>
            <th className="px-4 py-3 text-right font-medium">Ir</th>
          </tr>
        </thead>
        <tbody>
          {servers.map((server) => (
            <tr
              key={server.id}
              className="border-b border-white/5 last:border-b-0 transition-colors hover:bg-white/5"
            >
              <td className="px-4 py-3">
                <Link
                  to={`/servers/${server.id}`}
                  className="font-medium text-slate-100 hover:text-emerald-300"
                  data-testid={`dashboard-server-${server.name}`}
                >
                  {server.name}
                </Link>
              </td>
              <td className="px-4 py-3">
                <span
                  className={cn(
                    'inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium',
                    STATE_BADGE[server.state],
                  )}
                >
                  {STATE_LABEL[server.state]}
                </span>
              </td>
              <td className="hidden px-4 py-3 text-slate-300 sm:table-cell">
                <span className="inline-flex items-center gap-1.5">
                  <Layers className="size-3.5 text-slate-400" />
                  {server.version || '—'}
                </span>
              </td>
              <td className="hidden px-4 py-3 text-slate-300 md:table-cell">
                <span className="inline-flex items-center gap-1.5">
                  <Globe className="size-3.5 text-slate-400" />
                  {server.connection.address}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  to={`/servers/${server.id}`}
                  aria-label={`Ir al servidor ${server.name}`}
                  className="inline-flex items-center justify-center rounded-md border border-white/10 bg-white/5 p-1.5 text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
                  data-testid={`dashboard-open-${server.name}`}
                >
                  <ArrowUpRight className="size-4" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
