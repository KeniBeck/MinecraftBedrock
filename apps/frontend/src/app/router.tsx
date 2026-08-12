import { createBrowserRouter, Navigate } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { LoginPage } from '@/features/auth/LoginPage'
import { ServerDetailPage } from '@/features/servers/ServerDetailPage'
import { ConsolePage } from '@/features/console/ConsolePage'
import { WorldsPage } from '@/features/worlds/WorldsPage'
import { TemplatesPage } from '@/features/templates/TemplatesPage'
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
          // La raíz y /servers delegan en AppLayout (que selecciona el primer
          // servidor y navega a su detalle).
          { index: true, element: <ServerRedirect /> },
          { path: '/servers', element: <ServerRedirect /> },
          { path: '/servers/:serverId', element: <ServerDetailPage /> },
          { path: '/servers/:serverId/console', element: <ConsolePage /> },
          { path: '/servers/:serverId/worlds', element: <WorldsPage /> },
          { path: '/servers/:serverId/templates', element: <TemplatesPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
