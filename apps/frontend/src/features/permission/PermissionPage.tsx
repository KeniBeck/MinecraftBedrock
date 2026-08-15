import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { getApiMessage } from '@/lib/api/client'
import { useCan } from '@/lib/auth/useCan'
import type { AllowlistEntry, OperatorEntry } from '@/lib/api/permissions'
import {
  useAllowlist,
  useOperators,
  useRemoveAllowlistEntry,
  useRemoveOperator,
  useToggleAllowlistEnabled,
} from './hooks'
import { AddAllowlistDialog } from './components/AddAllowlistDialog'
import { AddOperatorDialog } from './components/AddOperatorDialog'
import { Plus, ShieldCheck, Trash2, UserCheck, Users } from 'lucide-react'

export function PermissionPage() {
  const { serverId } = useParams<{ serverId: string }>()
  const canRead = useCan('permission.read')
  const canWrite = useCan('permission.write')

  const [addAllowlistOpen, setAddAllowlistOpen] = useState(false)
  const [addOperatorOpen, setAddOperatorOpen] = useState(false)
  const [deletingAllowlist, setDeletingAllowlist] = useState<AllowlistEntry | null>(null)
  const [deletingOperator, setDeletingOperator] = useState<OperatorEntry | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [allowlistEnabled, setAllowlistEnabled] = useState(false)

  const { data: allowlist, isLoading, isError, error } = useAllowlist(serverId)
  const {
    data: operatorsData,
    isLoading: operatorsLoading,
    isError: operatorsError,
    error: operatorsErrorDetail,
  } = useOperators(serverId)
  const operators = operatorsData ?? []
  const removeAllowlistEntry = useRemoveAllowlistEntry(serverId ?? '')
  const removeOperator = useRemoveOperator(serverId ?? '')
  const toggleEnabled = useToggleAllowlistEnabled(serverId ?? '')

  if (!serverId) return null

  if (!canRead) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        No tienes permisos para ver la gestión de permisos del servidor.
      </div>
    )
  }

  const handleToggleAllowlist = () => {
    const next = !allowlistEnabled
    setActionError(null)
    setAllowlistEnabled(next)
    toggleEnabled.mutate(next, {
      onError: (err) => {
        setAllowlistEnabled((prev) => !prev)
        setActionError(getApiMessage(err, 'No se pudo cambiar la allowlist'))
      },
    })
  }

  const handleDeleteAllowlist = () => {
    if (!deletingAllowlist) return
    const entry = deletingAllowlist
    setDeletingAllowlist(null)
    removeAllowlistEntry.mutate(entry.xuid, {
      onError: (err) => setActionError(getApiMessage(err)),
    })
  }

  const handleDeleteOperator = () => {
    if (!deletingOperator) return
    const entry = deletingOperator
    setDeletingOperator(null)
    removeOperator.mutate(entry.xuid, {
      onError: (err) => setActionError(getApiMessage(err)),
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Permisos</h1>
        {canWrite && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">Allowlist activada</span>
            <Button
              variant={allowlistEnabled ? 'start' : 'outline'}
              size="sm"
              pixel
              onClick={handleToggleAllowlist}
              disabled={toggleEnabled.isPending}
              title="El backend no expone lectura del estado; se mantiene en esta sesión."
            >
              {allowlistEnabled ? 'Activada' : 'Desactivada'}
            </Button>
          </div>
        )}
      </div>

      {actionError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
        >
          {actionError}
        </div>
      )}

      {isLoading && <div className="p-8 text-muted-foreground">Cargando allowlist…</div>}

      {isError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
        >
          {getApiMessage(error, 'No se pudo cargar la allowlist')}
        </div>
      )}

      {/* Allowlist */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <ShieldCheck className="h-5 w-5 text-emerald-300" />
            Allowlist
          </h2>
          {canWrite && (
            <Button variant="create" pixel size="sm" onClick={() => setAddAllowlistOpen(true)}>
              <Plus className="mr-1 h-4 w-4" />
              Añadir
            </Button>
          )}
        </div>

        {!isLoading && !isError && (allowlist?.length ?? 0) === 0 && (
          <div className="py-8 text-center text-muted-foreground">
            La allowlist está vacía. Añade jugadores desde el botón "Añadir".
          </div>
        )}

        {!isLoading && !isError && (allowlist?.length ?? 0) > 0 && (
          <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 bg-white/5 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2">Gamertag</th>
                  <th className="px-4 py-2">XUID</th>
                  <th className="px-4 py-2 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {(allowlist ?? []).map((entry) => (
                  <tr key={entry.xuid} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-2 font-medium">{entry.name}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                      {entry.xuid}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {canWrite && (
                        <Button
                          variant="ghost"
                          size="sm"
                          pixel
                          onClick={() => setDeletingAllowlist(entry)}
                          disabled={removeAllowlistEntry.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-red-400" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Operadores */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Users className="h-5 w-5 text-amber-300" />
            Operadores
          </h2>
          {canWrite && (
            <Button variant="create" pixel size="sm" onClick={() => setAddOperatorOpen(true)}>
              <UserCheck className="mr-1 h-4 w-4" />
              Añadir operador
            </Button>
          )}
        </div>

        {operatorsLoading && (
          <div className="p-8 text-muted-foreground">Cargando operadores…</div>
        )}

        {operatorsError && (
          <div
            role="alert"
            className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
          >
            {getApiMessage(operatorsErrorDetail, 'No se pudo cargar los operadores')}
          </div>
        )}

        {!operatorsLoading && !operatorsError && (operators?.length ?? 0) === 0 && (
          <div className="py-8 text-center text-muted-foreground">
            No hay operadores registrados. Añade uno desde el botón "Añadir operador".
          </div>
        )}

        {!operatorsLoading && !operatorsError && (operators?.length ?? 0) > 0 && (
          <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-white/10 bg-white/5 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-2">XUID</th>
                  <th className="px-4 py-2">Nivel</th>
                  <th className="px-4 py-2 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {operators.map((entry) => (
                  <tr key={entry.xuid} className="border-b border-white/5 last:border-0">
                    <td className="px-4 py-2 font-mono text-xs">{entry.xuid}</td>
                    <td className="px-4 py-2">
                      <span className="rounded-none border border-amber-500/30 bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-300">
                        {entry.level}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {canWrite && (
                        <Button
                          variant="ghost"
                          size="sm"
                          pixel
                          onClick={() => setDeletingOperator(entry)}
                          disabled={removeOperator.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-red-400" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <AddAllowlistDialog
        open={addAllowlistOpen}
        onOpenChange={setAddAllowlistOpen}
        serverId={serverId}
      />

      <AddOperatorDialog
        open={addOperatorOpen}
        onOpenChange={setAddOperatorOpen}
        serverId={serverId}
      />

      <ConfirmDialog
        open={deletingAllowlist !== null}
        onOpenChange={(next) => {
          if (!next) setDeletingAllowlist(null)
        }}
        title="Quitar de la allowlist"
        description={
          deletingAllowlist
            ? `¿Quitar a "${deletingAllowlist.name}" (${deletingAllowlist.xuid}) de la allowlist?`
            : undefined
        }
        confirmLabel="Quitar"
        destructive
        busy={removeAllowlistEntry.isPending}
        onConfirm={handleDeleteAllowlist}
      />

      <ConfirmDialog
        open={deletingOperator !== null}
        onOpenChange={(next) => {
          if (!next) setDeletingOperator(null)
        }}
        title="Quitar operador"
        description={
          deletingOperator
            ? `¿Quitar los privilegios de operador al jugador ${deletingOperator.xuid}?`
            : undefined
        }
        confirmLabel="Quitar"
        destructive
        busy={removeOperator.isPending}
        onConfirm={handleDeleteOperator}
      />
    </div>
  )
}