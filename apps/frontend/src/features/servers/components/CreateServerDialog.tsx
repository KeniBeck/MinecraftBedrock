import { useState } from 'react'

import { Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getApiCode, getApiMessage } from '@/lib/api/client'
import { useCreateServer } from '@/features/servers/hooks'
import { useCan } from '@/lib/auth/useCan'

/**
 * "Crear servidor" (§cambio): modal pixelado sobre el schema real
 * `CreateServerRequest` = `{ name (1..128), version?, template_id? }` — el
 * puerto lo asigna el pool del backend, no va en el form. Reutiliza el patrón
 * de LoginPage: estado local + `getApiMessage`/`getApiCode` (no react-hook-form,
 * ver change-log). `server.create` es PANEL_ACTION → solo admin/super_admin, y
 * el botón se oculta en el Header vía `useCan`.
 */
export function CreateServerDialog() {
  const canCreate = useCan('server.create')
  const createServer = useCreateServer()

  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [version, setVersion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)

  if (!canCreate) return null

  function reset() {
    setName('')
    setVersion('')
    setError(null)
    setFieldError(null)
  }

  async function handleSubmit() {
    setError(null)
    setFieldError(null)
    try {
      await createServer.mutateAsync({ name, version: version || null, template_id: null })
      setOpen(false)
      reset()
    } catch (err) {
      // Nombre duplicado: el backend responde SERVER.ALREADY_EXISTS → resaltar el campo name.
      if (getApiCode(err) === 'SERVER.ALREADY_EXISTS') {
        setFieldError(getApiMessage(err, 'Ya existe un servidor con ese nombre'))
      } else {
        setError(getApiMessage(err, 'No se pudo crear el servidor'))
      }
    }
  }

  return (
    <>
      <Button
        variant="create"
        pixel
        onClick={() => setOpen(true)}
        data-testid="create-server-button"
        className="h-10 px-4 text-sm"
      >
        <Plus className="size-4" />
        <span className="hidden sm:inline">Crear servidor</span>
      </Button>
      <FormDialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next)
          if (!next) reset()
        }}
        title="Crear servidor"
        description="El puerto lo asigna el sistema automáticamente."
        onSubmit={handleSubmit}
        busy={createServer.isPending}
        error={error}
        submitLabel="Crear"
        submittingLabel="Creando…"
        submitTestId="create-server-submit"
      >
        <FormField label="Nombre" htmlFor="server-name" error={fieldError ?? undefined}>
          <Input
            id="server-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={128}
            required
            aria-invalid={Boolean(fieldError)}
          />
        </FormField>
        <FormField label="Versión (opcional)" htmlFor="server-version">
          <Input
            id="server-version"
            placeholder="Ej. 1.21.1"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
          />
        </FormField>
      </FormDialog>
    </>
  )
}
