import { useRef, useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
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

  const handleSubmit = async () => {
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
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Importar mundo"
      onSubmit={handleSubmit}
      busy={importWorld.isPending}
      error={error}
      submitLabel="Importar"
      submittingLabel="Importando…"
      submitDisabled={!file}
    >
      <FormField label="Nombre del mundo" htmlFor="import-name">
        <Input
          id="import-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Mi mundo importado"
          required
          maxLength={64}
        />
      </FormField>
      <FormField label="Archivo .mcworld" htmlFor="import-file">
        <Input
          id="import-file"
          type="file"
          accept=".mcworld,.zip"
          ref={fileInputRef}
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          required
        />
      </FormField>
    </FormDialog>
  )
}
