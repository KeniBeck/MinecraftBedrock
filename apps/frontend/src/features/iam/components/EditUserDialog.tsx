import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { getApiMessage } from '@/lib/api/client'
import type { RoleName, UpdateUserRequest, User } from '@/lib/api/iam'
import { useRoles, useUpdateUser } from '../hooks'
import { ROLE_OPTIONS } from '../types'

interface EditUserDialogProps {
  user: User
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved?: (user: User) => void
}

/**
 * Edición de un usuario (`PUT /users/{id}`, iam.manage): display_name, email,
 * estado y roles globales. El selector de roles usa `GET /roles` con fallback
 * al catálogo estático mientras carga.
 */
export function EditUserDialog({ user, open, onOpenChange, onSaved }: EditUserDialogProps) {
  const { data: roles = [] } = useRoles()
  const updateUser = useUpdateUser()

  const [displayName, setDisplayName] = useState(user.display_name)
  const [email, setEmail] = useState(user.email ?? '')
  const [status, setStatus] = useState<'active' | 'suspended'>(
    user.status === 'suspended' ? 'suspended' : 'active',
  )
  const [selectedRoles, setSelectedRoles] = useState<RoleName[]>(
    user.roles.filter((role): role is RoleName =>
      ROLE_OPTIONS.some((option) => option.value === role),
    ),
  )
  const [error, setError] = useState<string | null>(null)

  const roleOptions = roles.length > 0
    ? roles.map((role) => ({
        value: role.name as RoleName,
        label: ROLE_OPTIONS.find((option) => option.value === role.name)?.label ?? role.name,
      }))
    : ROLE_OPTIONS

  const toggleRole = (role: RoleName) => {
    setSelectedRoles((current) =>
      current.includes(role) ? current.filter((r) => r !== role) : [...current, role],
    )
  }

  const handleSubmit = async () => {
    setError(null)
    const trimmedEmail = email?.trim()
    const payload: UpdateUserRequest = {
      display_name: displayName.trim(),
      status,
      ...(trimmedEmail ? { email: trimmedEmail } : {}),
      ...(selectedRoles.length > 0 ? { roles: selectedRoles } : {}),
    }
    try {
      const updated = await updateUser.mutateAsync({ id: user.id, data: payload })
      onSaved?.(updated)
      onOpenChange(false)
    } catch (err) {
      setError(getApiMessage(err, 'No se pudo actualizar el usuario'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setError(null)
        }
        onOpenChange(next)
      }}
      title={`Editar usuario — ${user.username}`}
      description="Actualiza nombre visible, email, estado y roles globales."
      onSubmit={handleSubmit}
      busy={updateUser.isPending}
      error={error}
      submitLabel="Guardar"
      submittingLabel="Guardando…"
      submitVariant="create"
    >
      <FormField label="Nombre visible" htmlFor="edit-display">
        <Input
          id="edit-display"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
      </FormField>
      <FormField label="Email" htmlFor="edit-email">
        <Input
          id="edit-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </FormField>
      <FormField label="Estado" htmlFor="edit-status">
        <Select
          id="edit-status"
          value={status}
          onChange={(e) => setStatus(e.target.value as 'active' | 'suspended')}
        >
          <option value="active">Activo</option>
          <option value="suspended">Suspendido</option>
        </Select>
      </FormField>
      <FormField
        label="Roles globales"
        htmlFor="edit-roles"
        hint="Reemplaza el conjunto de roles actual (solo admin/super_admin)."
      >
        <div id="edit-roles" className="space-y-1.5">
          {roleOptions.map((role) => (
            <label
              key={role.value}
              className="flex cursor-pointer items-center gap-2 text-sm"
            >
              <input
                type="checkbox"
                checked={selectedRoles.includes(role.value)}
                onChange={() => toggleRole(role.value)}
              />
              <span>{role.label}</span>
            </label>
          ))}
        </div>
      </FormField>
    </FormDialog>
  )
}