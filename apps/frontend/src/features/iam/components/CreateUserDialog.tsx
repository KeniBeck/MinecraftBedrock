import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { getApiMessage } from '@/lib/api/client'
import type { CreateUserRequest } from '@/lib/api/iam'
import { useCreateUser, useRoles } from '../hooks'
import { ROLE_OPTIONS, type RoleName } from '../types'

interface CreateUserDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated?: (username: string) => void
}

/**
 * Alta de usuario del panel: `POST /users` y, si se elige un rol global
 * distinto de `viewer`, `POST /users/{id}/roles` (dos endpoints reales, ya que
 * el alta no acepta roles). La asignación de miembros por servidor se hace por
 * separado y no se expone aquí (sin listado de usuarios en el backend).
 */
export function CreateUserDialog({ open, onOpenChange, onCreated }: CreateUserDialogProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<RoleName>('viewer')
  const [error, setError] = useState<string | null>(null)

  const createUser = useCreateUser()
  const { data: roles = [] } = useRoles()

  const roleOptions = roles.length > 0
    ? roles.map((role) => ({
        value: role.name as RoleName,
        label: ROLE_OPTIONS.find((option) => option.value === role.name)?.label ?? role.name,
      }))
    : ROLE_OPTIONS

  const handleSubmit = async () => {
    setError(null)
    const payload: CreateUserRequest & { role: RoleName } = {
      username: username.trim(),
      password,
      display_name: displayName.trim(),
      role,
    }
    try {
      await createUser.mutateAsync(payload)
      onCreated?.(username.trim())
      onOpenChange(false)
      setUsername('')
      setPassword('')
      setDisplayName('')
      setRole('viewer')
    } catch (err) {
      setError(getApiMessage(err, 'Error al crear el usuario'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setUsername('')
          setPassword('')
          setDisplayName('')
          setError(null)
        }
        onOpenChange(next)
      }}
      title="Crear usuario"
      description="Crea una cuenta del panel y asigna su rol global."
      onSubmit={handleSubmit}
      busy={createUser.isPending}
      error={error}
      submitLabel="Crear"
      submittingLabel="Creando…"
      submitVariant="create"
      submitDisabled={!username.trim() || password.length < 8}
      submitTestId="create-user-submit"
    >
      <FormField label="Nombre de usuario" htmlFor="user-username" hint="Mínimo 3 caracteres.">
        <Input id="user-username" value={username} onChange={(e) => setUsername(e.target.value)} />
      </FormField>
      <FormField label="Contraseña" htmlFor="user-password" hint="Mínimo 8 caracteres.">
        <Input
          id="user-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </FormField>
      <FormField
        label="Nombre visible"
        htmlFor="user-display"
        hint="Opcional. Se muestra en lugar del nombre de usuario."
      >
        <Input id="user-display" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
      </FormField>
      <FormField
        label="Rol global"
        htmlFor="user-role"
        hint="Si no es 'viewer', se asigna vía POST /users/{id}/roles."
      >
        <Select id="user-role" value={role} onChange={(e) => setRole(e.target.value as RoleName)}>
          {roleOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </FormField>
    </FormDialog>
  )
}