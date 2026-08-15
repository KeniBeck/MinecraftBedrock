import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiMessage } from '@/lib/api/client'
import { useCreateApiKey } from '../hooks'
import { SCOPE_OPTIONS } from '../types'

interface CreateApiKeyDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Recibe el material (una sola vez) para mostrarlo tras crear. */
  onCreated?: (material: string, name: string) => void
}

/**
 * Crear una API key: `POST /iam/api-keys` con nombre + scopes. El material se
 * devuelve una sola vez y se muestra en el estado de creada.
 */
export function CreateApiKeyDialog({ open, onOpenChange, onCreated }: CreateApiKeyDialogProps) {
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  const createApiKey = useCreateApiKey()

  const toggleScope = (scope: string) => {
    setScopes((prev) => (prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]))
  }

  const handleSubmit = async () => {
    setError(null)
    try {
      const created = await createApiKey.mutateAsync({ name: name.trim(), scopes })
      onCreated?.(created.material, created.name)
      onOpenChange(false)
      setName('')
      setScopes([])
    } catch (err) {
      setError(getApiMessage(err, 'Error al crear la API key'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setName('')
          setScopes([])
          setError(null)
        }
        onOpenChange(next)
      }}
      title="Crear API key"
      description="El material solo se muestra una vez; cópialo antes de cerrar."
      onSubmit={handleSubmit}
      busy={createApiKey.isPending}
      error={error}
      submitLabel="Crear"
      submittingLabel="Creando…"
      submitVariant="create"
      submitDisabled={!name.trim()}
      submitTestId="create-apikey-submit"
    >
      <FormField label="Nombre" htmlFor="apikey-name" hint="Identificador interno de la key.">
        <Input id="apikey-name" value={name} onChange={(e) => setName(e.target.value)} />
      </FormField>
      <FormField label="Permisos (scopes)" hint="Selecciona los permisos que otorga la key.">
        <div className="grid gap-2">
          {SCOPE_OPTIONS.map((option) => (
            <label
              key={option.value}
              className="flex cursor-pointer items-center gap-2 rounded-none border border-white/10 bg-white/5 px-3 py-2 text-sm"
            >
              <input
                type="checkbox"
                className="size-4"
                checked={scopes.includes(option.value)}
                onChange={() => toggleScope(option.value)}
              />
              <span>{option.label}</span>
              <code className="ml-auto text-xs text-muted-foreground">{option.value}</code>
            </label>
          ))}
        </div>
      </FormField>
    </FormDialog>
  )
}