import { useAuthStore } from '@/stores/auth'
import { ProfileSettings } from './components/ProfileSettings'
import { ProfileAvatar } from './components/ProfileAvatar'

/**
 * Perfil del usuario autenticado (`/profile`): avatar (subible), información de
 * sesión de solo lectura + quórum de 2FA y apariencia. El backend no expone
 * `GET/PUT /users/me` con edición de nombre/email ni cambio de contraseña, por
 * lo que no se muestran formularios para editar esos campos (ver change-log).
 */
export function ProfilePage() {
  const identity = useAuthStore((state) => state.identity)

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-4">
        <ProfileAvatar />
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