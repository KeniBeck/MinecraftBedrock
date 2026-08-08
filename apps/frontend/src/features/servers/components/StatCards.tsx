import { Cpu, Globe, HardDrive, Signal, Wifi, Zap } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { STATE_LABEL } from '@/lib/serverState'
import type { Server } from '@/lib/api/servers'
import { cn } from '@/lib/utils'

interface StatItem {
  label: string
  value: string
  icon: typeof Cpu
}

function StatCard({ item, accent }: { item: StatItem; accent: string }) {
  const Icon = item.icon
  return (
    <Card className="rounded-2xl border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <div className={cn('shrink-0 rounded-lg p-2', accent)}>
          <Icon className="size-5" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{item.label}</p>
          <p
            title={item.value}
            className="truncate text-lg font-semibold leading-tight"
          >
            {item.value}
          </p>
        </div>
      </div>
    </Card>
  )
}

/**
 * Fila de stat cards con datos reales disponibles del `ServerResponse`.
 * CPU/RAM/Jugadores requieren Monitoring/Players (fases posteriores); aquí solo
 * se muestran datos que el endpoint ya devuelve — no se inventan métricas.
 */
export function StatCards({ server }: { server: Server }) {
  const items: StatItem[] = [
    { label: 'Estado', value: STATE_LABEL[server.state], icon: Signal },
    { label: 'Versión', value: server.version, icon: Zap },
    { label: 'Dirección', value: server.connection.address, icon: Globe },
    { label: 'Puerto', value: String(server.connection.port), icon: Wifi },
    {
      label: 'RCON',
      value: server.connection.rcon_port ? String(server.connection.rcon_port) : '—',
      icon: Cpu,
    },
    { label: 'Imagen', value: server.image_ref, icon: HardDrive },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {items.map((item) => (
        <StatCard
          key={item.label}
          item={item}
          accent="bg-indigo-500/15 text-indigo-300"
        />
      ))}
    </div>
  )
}
