import { CircleUserRound } from 'lucide-react'

import { useAuthStore } from '@/stores/auth'
import { ProfileSettings } from './components/ProfileSettings'

/**
 * Perfil del usuario autenticado (`/profile`): información de sesión de solo
 * lectura + quórum de 2FA y apariencia. El backend no expone `GET/PUT
 * /users/me` ni cambio de contraseña, por lo que no se muestran formularios
 * para editar nombre/email ni contraseña (ver change-log Fase 7).
 */
export function ProfilePage() {
  const identity = useAuthStore((state) => state.identity)

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-3">
        <CircleUserRound className="h-9 w-9 text-slate-300" />
        <div>
          <h1 className="text-xl font-bold">{identity?.username ?? 'Perfil'}</h1>
          <p className="text-sm text-muted-foreground">
            Roles:{' '}
            {identity?.roles.length ? identity.roles.join(', ') : 'sin roles'}
          </p>
        </div>
      </header>

      <ProfileSettings />
    </div>
  )
}