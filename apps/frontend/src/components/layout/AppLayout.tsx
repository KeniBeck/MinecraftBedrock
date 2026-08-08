import { useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'

import { Background } from '@/components/Background'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { useActiveServer } from '@/stores/servers'
import { useServers } from '@/features/servers/hooks'

/**
 * Layout raíz de las rutas protegidas (Fase 2): fondo dinámico detrás,
 * sidebar colapsable, header con selector de servidor, y el panel central.
 */
export function AppLayout() {
  const navigate = useNavigate()
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const setActiveServer = useActiveServer((state) => state.setActiveServer)
  const { data: servers = [] } = useServers()

  // Si no hay servidor activo y existen servidores, seleccionar el primero y
  // navegar a su detalle (comportamiento del selector del mockup).
  useEffect(() => {
    if (servers.length === 0 || activeServerId) return
    const first = servers[0]
    if (!first) return
    setActiveServer(first.id)
    navigate(`/servers/${first.id}`, { replace: true })
  }, [servers, activeServerId, setActiveServer, navigate])

  return (
    <div className="min-h-screen text-foreground">
      <Background />
      <div className="flex">
        <Sidebar />
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
