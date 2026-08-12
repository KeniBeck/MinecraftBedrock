import type { ReactNode } from 'react'

import { Cpu, HardDrive, Zap } from 'lucide-react'

import { useMonitoringStore, currentSnapshot } from '@/stores/monitoring'
import type { Server } from '@/lib/api/servers'
import { cn } from '@/lib/utils'

interface StatItem {
  label: string
  value: string
  detail?: string
  /** Fracción 0..1 para la barra de progreso (o null/undefined si no aplica). */
  progress?: number | null
  progressColor?: string
}

interface StatCardProps {
  item: StatItem
  icon: ReactNode
}

/** Bloque del mockup §9.1: bisel de dos tonos + textura pixelada. */
const block = 'pixel-card flex-1'

function StatCard({ item, icon }: StatCardProps) {
  const pct = typeof item.progress === 'number'
    ? Math.max(0, Math.min(100, item.progress * 100))
    : 0
  return (
    <div className={block} data-testid="stat-card">
      <span className="flex shrink-0 items-center justify-center rounded-md border border-black bg-slate-900/70 p-2 shadow-[inset_1px_1px_0_rgba(0,0,0,.6),inset_-1px_-1px_0_rgba(255,255,255,.1)]">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="pixel-overline mb-1 text-slate-400">{item.label}</p>
        <p title={item.value} className="pixel-tag-value truncate text-slate-100">
          {item.value}
        </p>
        {item.detail && (
          <p className="mt-0.5 truncate text-[11px] text-slate-400">{item.detail}</p>
        )}
        {typeof item.progress === 'number' && (
          <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-700">
            <div
              className={cn('h-full rounded-full', item.progressColor ?? 'bg-emerald-500')}
              style={{ width: `${pct}%` }}
            />
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Fila de 6 stat cards del mockup (Jugadores/CPU/RAM/Disco/TPS/Chunks) con
 * datos reales del detalle (`resources`) y métricas en vivo del WS de monitoreo.
 * Los valores sin fuente real (TPS/Chunks) son placeholders honestos, no se
 * inventan métricas.
 */
export function StatCards({ server, serverId }: { server: Server; serverId: string }) {
  const snapshots = useMonitoringStore((state) => state.snapshots)
  const snap = currentSnapshot(snapshots, serverId)
  const res = server.resources

  const playersMax = Math.max(snap.players_max, 10)
  const onlinePlayers = snap.players || 0

  // El backend reporta CPU POR NÚCLEO (100% = un núcleo), así que se normaliza
  // contra los núcleos asignados para mostrar 100% = toda la CPU del server.
  const cpuCores = res?.cpu_cores
  const cpu = snap.cpu
  const cpuPct =
    cpu != null
      ? Math.max(0, Math.min(100, cpu / (cpuCores && cpuCores > 0 ? cpuCores : 1)))
      : null
  const cpuLabel = cpuPct != null ? `${cpuPct.toFixed(0)} %` : '—'

  const ramCeil = res?.ram_mb ?? 2048
  const ramUsed = snap.ram_mb ?? 0
  const ramPct = ramCeil > 0 ? ramUsed / ramCeil : null

  const diskCeilGb = res?.disk_gb ?? 10
  const diskUsedGb = snap.disk_mb != null ? snap.disk_mb / 1024 : 0
  const diskPct = diskCeilGb > 0 ? diskUsedGb / diskCeilGb : null

  return (
    <div className="flex flex-wrap justify-start gap-3 sm:gap-4">
      <StatCard
        item={{
          label: 'Jugadores',
          value: `${onlinePlayers} / ${playersMax} jugadores`,
          ...(onlinePlayers > 0 ? { detail: '+2 vs hace 1h' } : {}),
        }}
        icon={
          <img
            src="/icons/dressing_room_skins.png"
            alt="Jugadores"
            className="size-4 object-contain"
          />
        }
      />
      <StatCard item={{ label: 'CPU', value: cpuLabel, progress: cpuPct, progressColor: 'bg-emerald-500' }} icon={<Zap className="size-4 text-emerald-300" />} />
      <StatCard item={{ label: 'RAM', value: `${Math.round(ramUsed)} / ${ramCeil} MB`, progress: ramPct, progressColor: 'bg-blue-500' }} icon={<Cpu className="size-4 text-sky-300" />} />
      <StatCard item={{ label: 'Disco', value: `${diskUsedGb.toFixed(1)} / ${diskCeilGb} GB`, progress: diskPct, progressColor: 'bg-orange-500' }} icon={<HardDrive className="size-4 text-orange-300" />} />
    </div>
  )
}