import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { Activity, Cpu, HardDrive, Users, Zap } from 'lucide-react'

import { useServerMonitoring } from '@/hooks/useServerMonitoring'
import { useServer } from '@/features/servers/hooks'
import { currentSnapshot, useMonitoringStore } from '@/stores/monitoring'
import { MetricsChart } from './components/MetricsChart'
import { TimeRangeSelector } from './components/TimeRangeSelector'
import { filterByRange, normalizeCpu, rangeDurationMs, useMonitoringHistory, type TimeRangeId } from './hooks'

/** Stat card resumida (icono + label + valor) sobre el snapshot en vivo. */
function SummaryCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="pixel-card flex-1">
      <span className="flex shrink-0 items-center justify-center rounded-md border border-black bg-slate-900/70 p-2 shadow-[inset_1px_1px_0_rgba(0,0,0,.6),inset_-1px_-1px_0_rgba(255,255,255,.1)]">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="pixel-overline mb-1 text-slate-400">{label}</p>
        <p className="pixel-tag-value truncate text-slate-100">{value}</p>
      </div>
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

  // Límites configurados del servidor (resources del detalle) para normalizar
  // RAM/Disco/CPU a % en el gráfico y las cards.
  const { data: server } = useServer(serverId)
  const cpuCores = server?.resources?.cpu_cores
  const cpuPct = normalizeCpu(snap.cpu, cpuCores)

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
        <SummaryCard
          icon={<Activity className="size-4 text-emerald-300" />}
          label="Estado"
          value={snap.status}
        />
        <SummaryCard
          icon={<Users className="size-4 text-emerald-300" />}
          label="Jugadores"
          value={`${snap.players} / ${snap.players_max}`}
        />
        <SummaryCard
          icon={<Zap className="size-4 text-emerald-300" />}
          label="CPU"
          value={cpuPct != null ? `${cpuPct.toFixed(1)} %` : '—'}
        />
        <SummaryCard
          icon={<Cpu className="size-4 text-sky-300" />}
          label="RAM"
          value={snap.ram_mb != null ? `${Math.round(snap.ram_mb)} MB` : '—'}
        />
        <SummaryCard
          icon={<HardDrive className="size-4 text-orange-300" />}
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
          <MetricsChart
            data={filtered}
            ramLimitMb={server?.resources?.ram_mb}
            diskLimitGb={server?.resources?.disk_gb}
            cpuCores={cpuCores}
          />
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
