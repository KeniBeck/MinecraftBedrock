import type { ReactNode } from 'react'
import { Archive, Gamepad2, Server, Users } from 'lucide-react'

import type { DashboardStats } from '../types'

interface CardProps {
  label: string
  value: string
  hint?: string
  icon: ReactNode
  accent?: 'emerald' | 'sky' | 'amber' | 'violet'
}

const ACCENTS: Record<NonNullable<CardProps['accent']>, string> = {
  emerald: 'text-emerald-300',
  sky: 'text-sky-300',
  amber: 'text-amber-300',
  violet: 'text-violet-300',
}

/** Tarjeta de resumen reutilizando el estilo `pixel-card` del mockup. */
function StatCard({ label, value, hint, icon, accent = 'emerald' }: CardProps) {
  return (
    <div className="pixel-card flex-1">
      <span
        className={`flex shrink-0 items-center justify-center rounded-md border border-black bg-slate-900/70 p-2 shadow-[inset_1px_1px_0_rgba(0,0,0,.6),inset_-1px_-1px_0_rgba(255,255,255,.1)] ${ACCENTS[accent]}`}
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="pixel-overline mb-1 text-slate-400">{label}</p>
        <p title={value} className="pixel-tag-value truncate text-slate-100">
          {value}
        </p>
        {hint && <p className="mt-0.5 truncate text-[11px] text-slate-400">{hint}</p>}
      </div>
    </div>
  )
}

/**
 * Cards de resumen del dashboard: total de servidores, en línea/offline,
 * jugadores online (siempre "—" en el MVP: `ServerResponse` no expone
 * `players` y no se abre un WS de monitoreo por servidor) y backups recientes
 * (contados desde el feed de eventos).
 */
export function StatsCards({ stats }: { stats: DashboardStats }) {
  return (
    <div className="flex flex-wrap justify-start gap-3 sm:gap-4">
      <StatCard
        label="Servidores"
        value={String(stats.total)}
        icon={<Server className="size-4" />}
        accent="emerald"
      />
      <StatCard
        label="En línea"
        value={`${stats.online} / ${stats.total}`}
        hint={`${stats.offline} detenidos`}
        icon={<Gamepad2 className="size-4" />}
        accent="sky"
      />
      <StatCard
        label="Jugadores"
        value={stats.players === null ? '—' : String(stats.players)}
        hint="No expuesto por GET /servers"
        icon={<Users className="size-4" />}
        accent="violet"
      />
      <StatCard
        label="Backups recientes"
        value={String(stats.recentBackups)}
        hint="Desde el feed de eventos"
        icon={<Archive className="size-4" />}
        accent="amber"
      />
    </div>
  )
}
