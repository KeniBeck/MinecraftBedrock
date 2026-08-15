import { useState } from 'react'
import { Copy, KeyRound, RefreshCw, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { getApiMessage } from '@/lib/api/client'
import type { ApiKey } from '@/lib/api/iam'
import { useApiKeys, useRegenerateApiKey, useRevokeApiKey } from '../hooks'
import { CreateApiKeyDialog } from './CreateApiKeyDialog'

function MaterialNotice({ label, material }: { label: string; material: string }) {
  return (
    <div
      role="status"
      className="rounded-none border-2 border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
    >
      <p className="mb-1 font-medium">{label} — cópialo ahora. No se volverá a mostrar.</p>
      <div className="flex items-center gap-2">
        <code className="break-all font-mono text-xs">{material}</code>
        <Button
          variant="ghost"
          size="sm"
          pixel
          onClick={() => navigator.clipboard?.writeText(material)}
          aria-label="Copiar"
        >
          <Copy className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}

export function ApiKeyList() {
  const { data: keys = [], isLoading, isError, error } = useApiKeys()
  const revokeKey = useRevokeApiKey()
  const regenerateKey = useRegenerateApiKey()

  const [createOpen, setCreateOpen] = useState(false)
  const [revealed, setRevealed] = useState<{ label: string; material: string } | null>(null)
  const [deletingKey, setDeletingKey] = useState<ApiKey | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const handleRevoke = () => {
    if (!deletingKey) return
    const key = deletingKey
    setDeletingKey(null)
    setActionError(null)
    revokeKey.mutate(key.id, {
      onError: (err) => setActionError(getApiMessage(err, 'No se pudo revocar la API key')),
    })
  }

  const handleRegenerate = (key: ApiKey) => {
    setActionError(null)
    regenerateKey.mutate(key.id, {
      onSuccess: (created) => setRevealed({ label: `Nuevo material de "${key.name}"`, material: created.material }),
      onError: (err) => setActionError(getApiMessage(err, 'No se pudo rotar la API key')),
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          API keys del usuario autenticado (el backend solo lista las propias).
        </p>
        <Button variant="create" pixel size="sm" onClick={() => setCreateOpen(true)}>
          <KeyRound className="mr-1 h-4 w-4" />
          Crear API key
        </Button>
      </div>

      {revealed && <MaterialNotice label={revealed.label} material={revealed.material} />}
      {actionError && (
        <div
          role="alert"
          className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
        >
          {actionError}
        </div>
      )}

      {isLoading && <div className="p-8 text-muted-foreground">Cargando API keys…</div>}
      {isError && (
        <div role="alert" className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300">
          {getApiMessage(error, 'No se pudieron cargar las API keys')}
        </div>
      )}

      {!isLoading && !isError && keys.length === 0 && (
        <div className="py-8 text-center text-muted-foreground">
          No hay API keys. Crea una desde "Crear API key".
        </div>
      )}

      {!isLoading && !isError && keys.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-white/10 bg-slate-900/60 backdrop-blur-xl">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-white/10 bg-white/5 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2">Nombre</th>
                <th className="px-4 py-2">Scopes</th>
                <th className="px-4 py-2">Último uso</th>
                <th className="px-4 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} className="border-b border-white/5 last:border-0">
                  <td className="px-4 py-2 font-medium">{key.name}</td>
                  <td className="px-4 py-2">
                    <div className="flex flex-wrap gap-1">
                      {key.scopes.length === 0 && (
                        <span className="text-xs text-muted-foreground">sin scopes</span>
                      )}
                      {key.scopes.map((scope) => (
                        <Badge key={scope} variant="outline" className="text-[10px]">
                          {scope}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : 'nunca'}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      pixel
                      onClick={() => handleRegenerate(key)}
                      disabled={regenerateKey.isPending}
                      title="Rotar clave"
                      aria-label={`Rotar ${key.name}`}
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      pixel
                      onClick={() => setDeletingKey(key)}
                      disabled={revokeKey.isPending}
                      title="Revocar"
                      aria-label={`Revocar ${key.name}`}
                    >
                      <Trash2 className="h-4 w-4 text-red-400" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreateApiKeyDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(material, name) => setRevealed({ label: `Nueva API key "${name}"`, material })}
      />

      <ConfirmDialog
        open={deletingKey !== null}
        onOpenChange={(next) => {
          if (!next) setDeletingKey(null)
        }}
        title="Revocar API key"
        description={
          deletingKey
            ? `¿Revocar "${deletingKey.name}"? Las integraciones que la usen perderán acceso.`
            : undefined
        }
        confirmLabel="Revocar"
        destructive
        busy={revokeKey.isPending}
        onConfirm={handleRevoke}
      />
    </div>
  )
}