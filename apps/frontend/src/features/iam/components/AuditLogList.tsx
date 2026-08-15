import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import type { AuditFilters } from '@/lib/api/iam'
import { useAuditLogs } from '../hooks'

const PAGE_SIZE = 20

/**
 * Listado del audit log tamper-evident (`GET /iam/audit`) con filtros por
 * actor, acción parcial y rango de fechas, más paginación.
 */
export function AuditLogList() {
  const [actorId, setActorId] = useState('')
  const [action, setAction] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [offset, setOffset] = useState(0)

  const filters: AuditFilters = {
    actor_id: actorId.trim() || undefined,
    action: action.trim() || undefined,
    from: from || undefined,
    to: to || undefined,
    limit: PAGE_SIZE,
    offset,
  }

  const { data, isLoading, isFetching, isError, error } = useAuditLogs(filters)

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const page = offset / PAGE_SIZE + 1
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const applyFilters = (nextOffset = 0) => {
    setOffset(nextOffset)
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Input
          placeholder="Actor (id)"
          value={actorId}
          onChange={(e) => setActorId(e.target.value)}
          aria-label="Filtrar por actor"
        />
        <Input
          placeholder="Acción (parcial)"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          aria-label="Filtrar por acción"
        />
        <Input
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          aria-label="Desde"
        />
        <Input
          type="date"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          aria-label="Hasta"
        />
      </div>
      <div className="flex justify-end">
        <Button variant="outline" pixel size="sm" onClick={() => applyFilters(0)}>
          Aplicar filtros
        </Button>
      </div>

      {isError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300"
        >
          {getApiMessage(error, 'No se pudieron cargar los registros de auditoría')}
        </div>
      )}

      {!isError && (
        <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-white/10 bg-white/5 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2">Fecha</th>
                <th className="px-4 py-2">Actor</th>
                <th className="px-4 py-2">Acción</th>
                <th className="px-4 py-2">Recurso</th>
                <th className="px-4 py-2">Resultado</th>
                <th className="px-4 py-2">IP</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    Cargando auditoría…
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No hay registros para los filtros indicados.
                  </td>
                </tr>
              ) : (
                items.map((log) => (
                  <tr key={log.id} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-2 text-xs text-muted-foreground">
                      {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-2 text-xs">{log.actor_id ?? '—'}</td>
                    <td className="px-4 py-2 font-medium">{log.action}</td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">
                      {log.resource_type ? `${log.resource_type}:${log.resource_id ?? ''}` : '—'}
                    </td>
                    <td className="px-4 py-2">
                      <Badge
                        variant={log.result === 'success' ? 'outline' : 'destructive'}
                        className="text-[10px]"
                      >
                        {log.result}
                      </Badge>
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">{log.ip ?? '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          Página {page} de {pages} · {total} registros
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            pixel
            size="sm"
            disabled={offset <= 0 || isFetching}
            onClick={() => applyFilters(offset - PAGE_SIZE)}
          >
            Anterior
          </Button>
          <Button
            variant="outline"
            pixel
            size="sm"
            disabled={offset + PAGE_SIZE >= total || isFetching}
            onClick={() => applyFilters(offset + PAGE_SIZE)}
          >
            Siguiente
          </Button>
        </div>
      </div>
    </div>
  )
}