import { Activity, Gamepad2 } from 'lucide-react'

import { useDashboardServers, useDashboardStats } from './hooks'
import { StatsCards } from './components/StatsCards'
import { ServerTable } from './components/ServerTable'
import { RecentEvents } from './components/RecentEvents'
import { QuickActions } from './components/QuickActions'

/**
 * Dashboard (vista global de todos los servidores) para la ruta `/`. Resume en
 * cards el estado agregado, lista los servidores en una tabla de solo lectura
 * y muestra el feed de eventos globales — todo a partir de la cache de
 * `useServers` y del `useNotificationsStore`, sin abrir sockets de monitoreo
 * adicionales. Las acciones por servidor viven en su detalle.
 */
export function DashboardPage() {
  const stats = useDashboardStats()
  const servers = useDashboardServers()

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <Gamepad2 className="h-9 w-9 text-emerald-300" />
        <div>
          <h1 className="text-xl font-bold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Visión global de tus servidores y eventos recientes.
          </p>
        </div>
      </header>

      <StatsCards stats={stats} />

      <QuickActions />

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <Gamepad2 className="size-4 text-slate-300" />
          Servidores ({servers.length})
        </h2>
        <ServerTable servers={servers} />
      </section>

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-base font-semibold">
          <Activity className="size-4 text-slate-300" />
          Eventos recientes
        </h2>
        <div className="rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
          <RecentEvents />
        </div>
      </section>
    </div>
  )
}