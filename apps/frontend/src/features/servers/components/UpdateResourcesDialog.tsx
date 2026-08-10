import { useState, type FormEvent } from 'react'

import { Gauge } from 'lucide-react'

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
import { getApiMessage } from '@/lib/api/client'
import { useUpdateResources } from '@/features/servers/hooks'
import { useCan } from '@/lib/auth/useCan'
import type { Server, UpdateServerResourcesRequest } from '@/lib/api/servers'

interface UpdateResourcesDialogProps {
  server: Server
  /** Deshabilitar el botón mientras hay otra acción (start/stop/restart) en vuelo. */
  disabled?: boolean
}

/**
 * "Actualizar recursos" (CPU/RAM) — `PUT /servers/{id}/resources` (contracto
 * verificado en `apps/backend/src/app/modules/server/api/schemas.py`). Ambos
 * campos son opcionales y se envían solo los que cambiaron; si el servidor está
 * corriendo, el backend recrea el contenedor (se reinicia). `server.update` es
 * WRITE_ACTION → lo tienen operator/admin/super_admin (useCan).
 *
 * Manejo de errores igual que CreateServerDialog: estado local + getApiMessage.
 * `SERVER.BUSY` (409) muestra `detail.message` del backend tal cual.
 */
export function UpdateResourcesDialog({ server, disabled = false }: UpdateResourcesDialogProps) {
  const canUpdate = useCan('server.update')
  const updateResources = useUpdateResources()

  const [open, setOpen] = useState(false)
  const [cpuCores, setCpuCores] = useState('')
  const [ramMb, setRamMb] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!canUpdate) return null

  const running = server.state === 'running' || server.state === 'starting'

  function openDialog() {
    // Precarga los valores configurados actuales desde el detalle (`resources`).
    setCpuCores(server.resources ? String(server.resources.cpu_cores) : '')
    setRamMb(server.resources ? String(server.resources.ram_mb) : '')
    setError(null)
    setFieldError(null)
    setOpen(true)
  }

  function closeDialog() {
    setOpen(false)
    setError(null)
    setFieldError(null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setFieldError(null)

    const cpuRaw = cpuCores.trim()
    const ramRaw = ramMb.trim()
    const payload: UpdateServerResourcesRequest = {}

    if (cpuRaw) {
      const cpu = Number(cpuRaw)
      if (!Number.isFinite(cpu) || cpu < 1 || cpu > 64) {
        setFieldError('CPU debe estar entre 1 y 64 núcleos')
        return
      }
      payload.cpu_cores = cpu
    }
    if (ramRaw) {
      const ram = Number(ramRaw)
      if (!/^\d+$/.test(ramRaw) || ram < 512 || ram > 65536) {
        setFieldError('RAM debe estar entre 512 MB y 65536 MB (64 GB)')
        return
      }
      payload.ram_mb = ram
    }
    if (Object.keys(payload).length === 0) {
      setFieldError('Introduce al menos un valor para cambiar')
      return
    }

    setBusy(true)
    try {
      await updateResources.mutateAsync({ serverId: server.id, payload })
      closeDialog()
    } catch (err) {
      // SERVER.BUSY (409) y demás: el mensaje legible del backend tal cual.
      setError(getApiMessage(err, 'No se pudieron actualizar los recursos'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) closeDialog() }}>
      <Button
        variant="secondary"
        size="default"
        pixel
        disabled={disabled}
        onClick={openDialog}
        data-testid="update-resources-button"
        title="Cambiar CPU y RAM asignadas"
        className="w-full h-10 text-sm"
      >
        <Gauge className="size-4" />
        Actualizar recursos
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Actualizar recursos</DialogTitle>
          <DialogDescription>
            Cambia la CPU y la RAM asignadas al servidor. Si está corriendo, se reiniciará
            para aplicar el cambio.
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
          {fieldError && (
            <p role="alert" className="text-xs text-red-300">{fieldError}</p>
          )}
          <div className="space-y-2">
            <Label htmlFor="update-resources-cpu">CPU (núcleos)</Label>
            <Input
              id="update-resources-cpu"
              inputMode="decimal"
              placeholder="1 – 64"
              value={cpuCores}
              onChange={(e) => setCpuCores(e.target.value)}
              data-testid="update-resources-cpu"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="update-resources-ram">RAM (MB)</Label>
            <Input
              id="update-resources-ram"
              inputMode="numeric"
              placeholder="512 – 65536"
              value={ramMb}
              onChange={(e) => setRamMb(e.target.value)}
              data-testid="update-resources-ram"
            />
          </div>
          {running && (
            <div
              data-testid="recreate-warning"
              className="rounded-none border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-300"
            >
              El servidor está en línea: se detendrá, se recreará el contenedor con los nuevos
              recursos y se volverá a arrancar.
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={closeDialog} disabled={busy}>
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="secondary"
              pixel
              disabled={busy}
              data-testid="update-resources-submit"
            >
              {busy ? 'Guardando…' : 'Aplicar cambios'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
