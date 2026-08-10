import { useState, type FormEvent } from 'react'

import { Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  const [busy, setBusy] = useState(false)

  if (!canCreate) return null

  function reset() {
    setName('')
    setVersion('')
    setError(null)
    setFieldError(null)
    setBusy(false)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
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
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) reset() }}>
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
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Crear servidor</DialogTitle>
          <DialogDescription>
            El puerto lo asigna el sistema automáticamente.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div
              role="alert"
              className="rounded-none border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300"
            >
              {error}
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="server-name">Nombre</Label>
            <Input
              id="server-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={128}
              required
              aria-invalid={Boolean(fieldError)}
            />
            {fieldError && <p className="text-xs text-red-300">{fieldError}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="server-version">Versión (opcional)</Label>
            <Input
              id="server-version"
              placeholder="Ej. 1.21.1"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={busy}>
              Cancelar
            </Button>
            <Button type="submit" variant="create" pixel disabled={busy} data-testid="create-server-submit">
              {busy ? 'Creando…' : 'Crear'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}