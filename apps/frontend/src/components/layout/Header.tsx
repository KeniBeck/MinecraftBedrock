import { useNavigate } from 'react-router-dom'
import { Bell, Check, ChevronsUpDown, LogOut, Moon, Settings, Sun } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useServers } from '@/features/servers/hooks'
import { STATE_LABEL } from '@/lib/serverState'
import { useActiveServer } from '@/stores/servers'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { cn } from '@/lib/utils'

/**
 * Header del mockup (§9.1): a la izquierda la pastilla de servidor — selector
 * real con dropdown que cambia el servidor activo — y a la derecha campana,
 * ajustes y el menú de perfil con logout.
 */
export function Header() {
  const navigate = useNavigate()
  const identity = useAuthStore((state) => state.identity)
  const clear = useAuthStore((state) => state.clear)
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const setActiveServer = useActiveServer((state) => state.setActiveServer)
  const theme = useThemeStore((state) => state.theme)
  const toggleTheme = useThemeStore((state) => state.toggleTheme)

  const { data: servers = [] } = useServers()
  const activeServer = servers.find((server) => server.id === activeServerId)

  function selectServer(serverId: string) {
    setActiveServer(serverId)
    navigate(`/servers/${serverId}`)
  }

  function handleLogout() {
    clear()
    navigate('/login', { replace: true })
  }

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-white/10 bg-slate-900/50 px-4 py-3 backdrop-blur-xl">
      {/* Selector de servidor real (mockup §9.1 — no una etiqueta). */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="gap-2 border-white/10 bg-white/5 text-sm"
            data-testid="server-selector"
          >
            <span className="size-2 rounded-full bg-emerald-400" />
            <span>Servidor: {activeServer?.name ?? '—'}</span>
            <ChevronsUpDown className="size-4 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" data-testid="server-selector-menu">
          <DropdownMenuLabel>Servidores</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {servers.length === 0 && (
            <DropdownMenuItem disabled>Sin servidores visibles</DropdownMenuItem>
          )}
          {servers.map((server) => (
            <DropdownMenuItem
              key={server.id}
              onSelect={() => selectServer(server.id)}
              data-testid={`server-option-${server.id}`}
            >
              <span
                className={cn(
                  'size-2 rounded-full',
                  server.state === 'running' || server.state === 'starting'
                    ? 'bg-emerald-400'
                    : 'bg-slate-400',
                )}
              />
              <span className="flex-1">{server.name}</span>
              <Badge className="bg-white/5 text-xs">{STATE_LABEL[server.state]}</Badge>
              {server.id === activeServerId && <Check className="size-4 text-emerald-400" />}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Derecha: campana, ajustes, perfil. */}
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" aria-label="Notificaciones" disabled>
          <Bell className="size-5" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Ajustes del panel" disabled>
          <Settings className="size-5" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Cambiar tema" onClick={toggleTheme}>
          {theme === 'dark' ? <Sun className="size-5" /> : <Moon className="size-5" />}
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2 px-2" data-testid="profile-menu">
              <span className="flex size-7 items-center justify-center rounded-full bg-emerald-500 text-xs font-bold text-white">
                {identity?.username.slice(0, 1).toUpperCase() ?? '?'}
              </span>
              <span className="hidden text-sm sm:inline">{identity?.username}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{identity?.username}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={handleLogout} data-testid="logout-item">
              <LogOut className="size-4" />
              Cerrar sesión
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
