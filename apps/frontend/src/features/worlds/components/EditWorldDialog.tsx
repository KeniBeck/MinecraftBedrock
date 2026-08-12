import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { getApiMessage } from '@/lib/api/client'
import type { UpdateWorldRequest, World } from '@/lib/api/worlds'

import { useUpdateWorld } from '../hooks'

interface EditWorldDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
  world: World | null
}

const GAMEMODES = ['survival', 'creative', 'adventure'] as const
const DIFFICULTIES = ['peaceful', 'easy', 'normal', 'hard'] as const

interface EditWorldFormProps {
  serverId: string
  world: World
  onDone: () => void
}

function EditWorldForm({ serverId, world, onDone }: EditWorldFormProps) {
  const [name, setName] = useState(world.name)
  const [seed, setSeed] = useState(world.seed ?? '')
  const [gamemode, setGamemode] = useState(world.gamemode ?? '')
  const [difficulty, setDifficulty] = useState(world.difficulty ?? '')
  const [viewDistance, setViewDistance] = useState(
    world.view_distance != null ? String(world.view_distance) : '',
  )
  const [error, setError] = useState<string | null>(null)
  const update = useUpdateWorld(serverId)

  const handleSubmit = async () => {
    setError(null)
    const payload: UpdateWorldRequest = {}
    if (name.trim() && name.trim() !== world.name) payload.name = name.trim()
    if (seed.trim()) payload.seed = seed.trim()
    if (gamemode) payload.gamemode = gamemode as 'survival' | 'creative' | 'adventure'
    if (difficulty) payload.difficulty = difficulty as 'peaceful' | 'easy' | 'normal' | 'hard'
    if (viewDistance.trim()) {
      const parsed = Number(viewDistance)
      if (Number.isInteger(parsed) && parsed >= 2 && parsed <= 64) {
        payload.view_distance = parsed
      } else {
        setError('La distancia de chunks debe ser un número entre 2 y 64')
        return
      }
    }
    if (Object.keys(payload).length === 0) {
      onDone()
      return
    }
    try {
      await update.mutateAsync({ name: world.name, payload })
      onDone()
    } catch (err) {
      setError(getApiMessage(err, 'Error al actualizar el mundo'))
    }
  }

  return (
    <FormDialog
      open
      onOpenChange={(next) => {
        if (!next) onDone()
      }}
      title="Ajustar mundo"
      onSubmit={handleSubmit}
      busy={update.isPending}
      error={error}
      submitLabel="Guardar"
      submittingLabel="Guardando…"
    >
      <FormField label="Nombre del mundo" htmlFor="edit-world-name">
        <Input
          id="edit-world-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={64}
        />
      </FormField>
      <FormField
        label="Semilla (opcional)"
        htmlFor="edit-world-seed"
        hint="Solo se aplica al generar un mundo nuevo; no regenera uno existente."
      >
        <Input
          id="edit-world-seed"
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          maxLength={64}
        />
      </FormField>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Modo de juego" htmlFor="edit-world-gamemode">
          <Select
            id="edit-world-gamemode"
            value={gamemode}
            onChange={(e) => setGamemode(e.target.value)}
          >
            <option value="">Por defecto</option>
            {GAMEMODES.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Dificultad" htmlFor="edit-world-difficulty">
          <Select
            id="edit-world-difficulty"
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
          >
            <option value="">Por defecto</option>
            {DIFFICULTIES.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </Select>
        </FormField>
      </div>
      <FormField label="Distancia de chunks (2–64)" htmlFor="edit-world-view-distance">
        <Input
          id="edit-world-view-distance"
          type="number"
          min={2}
          max={64}
          value={viewDistance}
          onChange={(e) => setViewDistance(e.target.value)}
        />
      </FormField>
    </FormDialog>
  )
}

export function EditWorldDialog({ open, onOpenChange, serverId, world }: EditWorldDialogProps) {
  if (!open || !world) return null
  return (
    <EditWorldForm
      key={world.id}
      serverId={serverId}
      world={world}
      onDone={() => onOpenChange(false)}
    />
  )
}
