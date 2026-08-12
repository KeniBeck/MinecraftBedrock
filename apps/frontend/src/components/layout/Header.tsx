import { useLocation, useMatch, useNavigate } from 'react-router-dom'
import {
  Check,
  ChevronDown,
  ChevronsUpDown,
  LogOut,
  Settings,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { CreateServerDialog } from '@/features/servers/components/CreateServerDialog'
import { NotificationsBell } from '@/components/layout/NotificationsBell'
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
import { useMonitoringStore, currentSnapshot } from '@/stores/monitoring'
import { useAuthStore } from '@/stores/auth'
import { cn } from '@/lib/utils'

/**
 * Header del mockup (§9.1) como bloques flotantes de Minecraft con bisel de dos
 * tonos (claro arriba-izq / oscuro abajo-der) sobre el fondo dinámico — NO una
 * barra sólida. Cada bloque usa las mismas clases Tailwind (glassmorphism +
 * bisel) sin CSS adicional:
 *   1. Centro-izq: selector de servidor real (dropdown) con espada y estado.
 *   2. Centro-der: contador de jugadores (icono + "X / 10 jugadores").
 *   3. Der: campana con badge, engranaje y menú de perfil con chevron.
 * (El logo y el control de colapso viven en el Sidebar; el header no los repite.)
 */
export function Header() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const identity = useAuthStore((state) => state.identity)
  const clear = useAuthStore((state) => state.clear)
  const activeServerId = useActiveServer((state) => state.activeServerId)
  const setActiveServer = useActiveServer((state) => state.setActiveServer)

  // "Crear servidor" solo en el detalle exacto `/servers/:id` (no en consola,
  // mundos, etc.). `useMatch` no matchea rutas con segmentos extra.
  const isServerDetail = useMatch('/servers/:serverId')

  const { data: servers = [] } = useServers()
  const activeServer = servers.find((server) => server.id === activeServerId)

  // Jugadores en vivo del WS de monitoreo del servidor activo — la misma fuente
  // que el StatCard "Jugadores" (useMonitoringStore, no REST ni query aparte).
  const snapshots = useMonitoringStore((state) => state.snapshots)
  const snap = currentSnapshot(snapshots, activeServerId)
  const onlinePlayers = snap.players || 0
  const playersMax = Math.max(snap.players_max, 10)

  const isOnline = activeServer?.state === 'running' || activeServer?.state === 'starting'

  /** Subpágina actual dentro de `/servers/:id/...` (o `null` si no la hay). */
  const currentSub = (() => {
    const match = pathname.match(/^\/servers\/[^/]+\/([^/]+)/)
    return match?.[1] ?? null
  })()

  function selectServer(serverId: string) {
    setActiveServer(serverId)
    // Conservar la subpágina actual: si estamos en `/servers/:id/monitoring`,
    // cambiar solo el id → `/servers/:nuevoId/monitoring` (los datos del nuevo
    // servidor cargan en la misma página). En el detalle exacto o fuera de una
    // ruta de servidor, ir al detalle.
    navigate(currentSub ? `/servers/${serverId}/${currentSub}` : `/servers/${serverId}`)
  }

  function handleLogout() {
    clear()
    navigate('/login', { replace: true })
  }

  // Clase base de cada "bloque": glassmorphism + bisel de Minecraft (§9.1/§9.2).
  // Bisel claro arriba-izq y oscuro abajo-der = bloque saliente (como un slot).
  const block = cn(
    'relative rounded-xl bg-slate-900/60 bg-gradient-to-br from-white/[0.04] to-transparent',
    'backdrop-blur-xl border border-white/10',
    'shadow-[inset_1px_1px_0_rgba(255,255,255,0.16),inset_-1px_-1px_0_rgba(0,0,0,0.64)]',
    'flex items-center shrink-0 px-4 py-2.5',
  )

  return (
    <header className="sticky top-0 z-20 flex items-center gap-2 bg-transparent px-4 py-3">
      {/* Bloque 1 — Selector de servidor real (dropdown, mockup §9.1). */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className={cn(block, 'gap-2.5 text-slate-200 transition-colors hover:bg-slate-800/70')}
            data-testid="server-selector"
          >
            <img
              src="/icons/Diamond_Sword_JE3_BE3.webp"
              alt="Espada de diamante"
              className="w-8 h-8 object-contain shrink-0"
            />
            <span className="text-sm">Servidor: {activeServer?.name ?? '—'}</span>
            <span
              className={cn('size-2 rounded-full', isOnline ? 'bg-emerald-400' : 'bg-slate-500')}
            />
            <span className="text-xs text-slate-400">
              {activeServer ? (isOnline ? 'En línea' : STATE_LABEL[activeServer.state]) : '—'}
            </span>
            <ChevronsUpDown className="size-4 text-slate-400" />
          </button>
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

      {/* Bloque 2 — Contador de jugadores (mockup §9.1). */}
      <div className={cn(block, 'gap-2.5')}>
        <img
          src="/icons/dressing_room_skins.png"
          alt="Jugadores"
          className="w-6 h-6 object-contain shrink-0"
        />
        <span className="whitespace-nowrap text-sm text-slate-200">
          {onlinePlayers} / {playersMax} jugadores
        </span>
      </div>

      {/* Separador elástico: empuja el bloque 3 a la derecha. */}
      <div className="flex-1" />

      {/* Acción de creación: solo en la página de detalle del servidor (y si la
          identidad tiene server.create — el dialog se oculta él mismo). */}
      {isServerDetail && <CreateServerDialog/>}

      {/* Bloque 3 — Campana (badge real de notificaciones), engranaje y perfil (mockup §9.1). */}
      <div className={cn(block, 'gap-0.5')}>
        <NotificationsBell />

        <button
          type="button"
          aria-label="Ajustes del panel"
          title="Ajustes"
          className="rounded-lg p-1.5 text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
        >
          <Settings className="size-5" />
        </button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex items-center gap-2 rounded-lg px-1.5 py-1 text-slate-200 transition-colors hover:bg-white/10"
              data-testid="profile-menu"
            >
              <img
                src="/avatar/skinmc-avatar.png"
                alt="Avatar"
                className="w-9 h-9 object-contain shrink-0 rounded-md"
              />
              <span className="hidden max-w-28 truncate text-sm sm:inline">
                {identity?.username}
              </span>
              <ChevronDown className="size-4 text-slate-400" />
            </button>
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