import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { useServerMonitoring } from '@/hooks/useServerMonitoring'
import { currentSnapshot, useMonitoringStore } from '@/stores/monitoring'
import { MetricsChart } from './components/MetricsChart'
import { TimeRangeSelector } from './components/TimeRangeSelector'
import { filterByRange, rangeDurationMs, useMonitoringHistory, type TimeRangeId } from './hooks'

/** Stat card resumida (valor actual + unidades) sobre el snapshot en vivo. */
function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="pixel-card flex-1">
      <p className="pixel-overline mb-1 text-slate-400">{label}</p>
      <p className="pixel-tag-value truncate text-slate-100">{value}</p>
    </div>
  )
}

export function MonitoringPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const [range, setRange] = useState<TimeRangeId>('1h')

  // Idempotente (refcount): no abre un segundo socket si AppLayout ya lo tiene.
  useServerMonitoring(serverId)

  const history = useMonitoringHistory(serverId)
  const snapshots = useMonitoringStore((state) => state.snapshots)
  const snap = currentSnapshot(snapshots, serverId)

  const filtered = useMemo(() => {
    const rangeMs = rangeDurationMs(range)
    // Recalcular con cada render (now = Date.now()) mantiene el corte vivo.
    return filterByRange(history ?? [], rangeMs)
  }, [history, range])

  const historyLen = history?.length ?? 0

  const last = filtered.length > 0 ? filtered[filtered.length - 1] : null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Monitoreo</h1>
        <TimeRangeSelector value={range} onChange={setRange} />
      </div>

      <div className="flex flex-wrap justify-start gap-3 sm:gap-4">
        <SummaryCard label="Estado" value={snap.status} />
        <SummaryCard label="Jugadores" value={`${snap.players} / ${snap.players_max}`} />
        <SummaryCard
          label="CPU"
          value={snap.cpu != null ? `${snap.cpu.toFixed(1)} %` : '—'}
        />
        <SummaryCard
          label="RAM"
          value={snap.ram_mb != null ? `${Math.round(snap.ram_mb)} MB` : '—'}
        />
        <SummaryCard
          label="Disco"
          value={snap.disk_mb != null ? `${Math.round(snap.disk_mb)} MB` : '—'}
        />
      </div>

      {filtered.length === 0 && historyLen === 0 && (
        <div className="rounded-xl border border-white/10 bg-slate-900/60 p-8 text-center text-sm text-muted-foreground backdrop-blur-xl">
          Conectando al monitoreo del servidor… Los datos aparecen en unos segundos.
        </div>
      )}

      {filtered.length === 0 && historyLen > 0 && (
        <div className="rounded-xl border border-white/10 bg-slate-900/60 p-8 text-center text-sm text-muted-foreground backdrop-blur-xl">
          No hay datos dentro de este rango todavía. El servidor acumula muestras
          cada ~5 s mientras esté conectado.
        </div>
      )}

      {filtered.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl">
          <MetricsChart data={filtered} />
        </div>
      )}

      {last && (
        <p className="text-xs text-muted-foreground">
          {filtered.length} muestras · última a las {new Date(last.ts).toLocaleTimeString()}
        </p>
      )}
    </div>
  )
}
