import { useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { Background } from '@/components/Background'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { useActiveServer } from '@/stores/servers'
import { useServers } from '@/features/servers/hooks'
import { useServerMonitoring } from '@/hooks/useServerMonitoring'

/**
 * Layout raíz de las rutas protegidas (Fase 2): fondo dinámico detrás,
 * sidebar colapsable, header con selector de servidor, y el panel central.
 */
export function AppLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.innerWidth < 768)
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const setActiveServer = useActiveServer((state) => state.setActiveServer)
  const { data: servers = [] } = useServers()

  // WS de monitoreo del servidor activo a nivel de layout: el badge de
  // jugadores del header vive aquí y necesita datos en vivo en cualquier página.
  useServerMonitoring(activeServerId ?? undefined)

  // Si no hay servidor activo y existen servidores, seleccionar el primero
  // (para que el selector del header y el sidebar tengan contexto). NO se
  // navega automáticamente: la raíz `/` es el dashboard global y `/servers`
  // redirige al detalle del primer servidor.
  useEffect(() => {
    if (servers.length === 0 || activeServerId) return
    const first = servers[0]
    if (!first) return
    setActiveServer(first.id)
    if (pathname !== '/') navigate(`/servers/${first.id}`, { replace: true })
  }, [servers, activeServerId, setActiveServer, navigate, pathname])

  return (
    <div className="min-h-screen text-foreground">
      <Background />
      <div className="flex">
<Sidebar
            collapsed={sidebarCollapsed}
            onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
          />
          <div className="flex min-w-0 flex-1 flex-col">
            <Header />
          <main className="flex-1 p-4 sm:p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
