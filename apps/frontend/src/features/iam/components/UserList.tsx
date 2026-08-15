import { useState } from 'react'
import { Pencil, ShieldCheck, ShieldX } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { getApiMessage } from '@/lib/api/client'
import type { User } from '@/lib/api/iam'
import { useDeleteUser, useUpdateUser, useUsers } from '../hooks'
import { roleLabel } from '../types'
import { EditUserDialog } from './EditUserDialog'

interface UserListProps {
  canManage: boolean
}

/**
 * Tabla de usuarios del panel (`GET /users`). La edición, suspensión y
 * reactivación exigen `iam.manage`; con solo `iam.view` la tabla es de lectura.
 */
export function UserList({ canManage }: UserListProps) {
  const { data: users = [], isLoading, isError, error } = useUsers()
  const updateUser = useUpdateUser()
  const deleteUser = useDeleteUser()

  const [editing, setEditing] = useState<User | null>(null)
  const [suspending, setSuspending] = useState<User | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const handleActivate = (user: User) => {
    setActionError(null)
    updateUser.mutate(
      { id: user.id, data: { status: 'active' } },
      { onError: (err) => setActionError(getApiMessage(err, 'No se pudo reactivar el usuario')) },
    )
  }

  const handleSuspend = () => {
    if (!suspending) return
    const user = suspending
    setSuspending(null)
    setActionError(null)
    deleteUser.mutate(user.id, {
      onError: (err) => setActionError(getApiMessage(err, 'No se pudo suspender el usuario')),
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Todos los usuarios del panel. Edición y suspensión requieren permisos administrador.
        </p>
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
        >
          {actionError}
        </div>
      )}

      {isLoading && <div className="p-8 text-muted-foreground">Cargando usuarios…</div>}
      {isError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300"
        >
          {getApiMessage(error, 'No se pudieron cargar los usuarios')}
        </div>
      )}

      {!isLoading && !isError && users.length === 0 && (
        <div className="py-8 text-center text-muted-foreground">No hay usuarios.</div>
      )}

      {!isLoading && !isError && users.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-white/10 bg-white/5 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2">Usuario</th>
                <th className="px-4 py-2">Email</th>
                <th className="px-4 py-2">Estado</th>
                <th className="px-4 py-2">Roles</th>
                <th className="px-4 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const suspended = user.status === 'suspended'
                return (
                  <tr key={user.id} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-2">
                      <div className="font-medium">{user.display_name || user.username}</div>
                      <div className="text-xs text-muted-foreground">@{user.username}</div>
                    </td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">
                      {user.email || '—'}
                    </td>
                    <td className="px-4 py-2">
                      <Badge
                        variant={suspended ? 'destructive' : 'outline'}
                        className="text-[10px]"
                      >
                        {suspended ? 'suspendido' : 'activo'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {user.roles.length === 0 && (
                          <span className="text-xs text-muted-foreground">sin roles</span>
                        )}
                        {user.roles.map((role) => (
                          <Badge key={role} variant="outline" className="text-[10px]">
                            {roleLabel(role)}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {canManage ? (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            pixel
                            onClick={() => setEditing(user)}
                            disabled={updateUser.isPending || deleteUser.isPending}
                            title="Editar"
                            aria-label={`Editar ${user.username}`}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          {suspended ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              pixel
                              onClick={() => handleActivate(user)}
                              disabled={updateUser.isPending || deleteUser.isPending}
                              title="Reactivar"
                              aria-label={`Reactivar ${user.username}`}
                            >
                              <ShieldCheck className="h-4 w-4 text-emerald-400" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              pixel
                              onClick={() => setSuspending(user)}
                              disabled={updateUser.isPending || deleteUser.isPending}
                              title="Suspender"
                              aria-label={`Suspender ${user.username}`}
                            >
                              <ShieldX className="h-4 w-4 text-red-400" />
                            </Button>
                          )}
                        </>
                      ) : null}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <EditUserDialog
          user={editing}
          open
          onOpenChange={(next) => {
            if (!next) setEditing(null)
          }}
        />
      )}

      <ConfirmDialog
        open={suspending !== null}
        onOpenChange={(next) => {
          if (!next) setSuspending(null)
        }}
        title="Suspender usuario"
        description={
          suspending
            ? `¿Suspender a "${suspending.username}"? No podrá iniciar sesión hasta reactivarlo.`
            : undefined
        }
        confirmLabel="Suspender"
        destructive
        busy={deleteUser.isPending}
        onConfirm={handleSuspend}
      />
    </div>
  )
}