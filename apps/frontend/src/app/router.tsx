import { createBrowserRouter, Navigate } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { LoginPage } from '@/features/auth/LoginPage'
import { ServerDetailPage } from '@/features/servers/ServerDetailPage'
import { ConsolePage } from '@/features/console/ConsolePage'
import { WorldsPage } from '@/features/worlds/WorldsPage'
import { TemplatesPage } from '@/features/templates/TemplatesPage'
import { PlayersPage } from '@/features/players/PlayersPage'
import { BackupsPage } from '@/features/backups/BackupsPage'
import { MonitoringPage } from '@/features/monitoring/MonitoringPage'
import { SchedulerPage } from '@/features/scheduler/SchedulerPage'
import { PermissionPage } from '@/features/permission/PermissionPage'
import { IAMPage } from '@/features/iam/IAMPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { ProfilePage } from '@/features/iam/ProfilePage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { RequireAuth, RequireGuest } from '@/lib/auth/guards'
import { ServerRedirect } from '@/features/servers/ServerRedirect'

export const router = createBrowserRouter([
  {
    element: <RequireGuest />,
    children: [{ path: '/login', element: <LoginPage /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />,
        children: [
          // La raíz muestra el dashboard global; `/servers` delega en el
          // selector que navega al detalle del primer servidor activo.
          { index: true, element: <DashboardPage /> },
          { path: '/servers', element: <ServerRedirect /> },
          { path: '/servers/:serverId', element: <ServerDetailPage /> },
          { path: '/servers/:serverId/console', element: <ConsolePage /> },
          { path: '/servers/:serverId/worlds', element: <WorldsPage /> },
          { path: '/servers/:serverId/templates', element: <TemplatesPage /> },
          { path: '/servers/:serverId/players', element: <PlayersPage /> },
          { path: '/servers/:serverId/backups', element: <BackupsPage /> },
          { path: '/servers/:serverId/scheduler', element: <SchedulerPage /> },
          { path: '/servers/:serverId/permissions', element: <PermissionPage /> },
          { path: '/servers/:serverId/monitoring', element: <MonitoringPage /> },
          { path: '/admin/iam', element: <IAMPage /> },
          { path: '/admin/settings', element: <SettingsPage /> },
          { path: '/profile', element: <ProfilePage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
