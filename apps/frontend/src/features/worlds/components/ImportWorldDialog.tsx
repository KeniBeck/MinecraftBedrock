import { useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getApiMessage } from '@/lib/api/client'

import { useImportWorld } from '../hooks'

interface ImportWorldDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
}

export function ImportWorldDialog({ open, onOpenChange, serverId }: ImportWorldDialogProps) {
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const importWorld = useImportWorld(serverId)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return
    setError(null)
    try {
      await importWorld.mutateAsync({ name, file })
      onOpenChange(false)
      setName('')
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setError(getApiMessage(err, 'Error al importar el mundo'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Importar mundo</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="import-name">Nombre del mundo</Label>
            <Input
              id="import-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Mi mundo importado"
              required
              maxLength={64}
            />
          </div>
          <div>
            <Label htmlFor="import-file">Archivo .mcworld</Label>
            <Input
              id="import-file"
              type="file"
              accept=".mcworld,.zip"
              ref={fileInputRef}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" variant="create" pixel disabled={importWorld.isPending || !file}>
              {importWorld.isPending ? 'Importando…' : 'Importar'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
