import { useState } from 'react'

import { FormDialog } from '@/components/ui/form-dialog'
import { FormField } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { getApiMessage } from '@/lib/api/client'

import { useCreateWorld } from '../hooks'
import type { CreateWorldRequest } from '@/lib/api/worlds'

interface CreateWorldDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
}

const GAMEMODES = ['survival', 'creative', 'adventure'] as const
const DIFFICULTIES = ['peaceful', 'easy', 'normal', 'hard'] as const

export function CreateWorldDialog({ open, onOpenChange, serverId }: CreateWorldDialogProps) {
  const [name, setName] = useState('')
  const [seed, setSeed] = useState('')
  const [gamemode, setGamemode] = useState<string>('')
  const [difficulty, setDifficulty] = useState<string>('')
  const [viewDistance, setViewDistance] = useState('')
  const [error, setError] = useState<string | null>(null)
  const create = useCreateWorld(serverId)

  const handleSubmit = async () => {
    setError(null)
    const payload: CreateWorldRequest = { name }
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
    try {
      await create.mutateAsync(payload)
      onOpenChange(false)
      setName('')
      setSeed('')
      setGamemode('')
      setDifficulty('')
      setViewDistance('')
    } catch (err) {
      setError(getApiMessage(err, 'Error al crear el mundo'))
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Crear mundo"
      onSubmit={handleSubmit}
      busy={create.isPending}
      error={error}
      submitLabel="Crear"
      submittingLabel="Creando…"
    >
      <FormField label="Nombre del mundo" htmlFor="world-name">
        <Input
          id="world-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Mi mundo"
          required
          maxLength={64}
        />
      </FormField>
      <FormField
        label="Semilla (opcional)"
        htmlFor="world-seed"
        hint="Se usa al generar el mundo por primera vez."
      >
        <Input
          id="world-seed"
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          placeholder="Deja vacío para una semilla aleatoria"
          maxLength={64}
        />
      </FormField>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Modo de juego" htmlFor="world-gamemode">
          <Select
            id="world-gamemode"
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
        <FormField label="Dificultad" htmlFor="world-difficulty">
          <Select
            id="world-difficulty"
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
      <FormField label="Distancia de chunks (2–64)" htmlFor="world-view-distance">
        <Input
          id="world-view-distance"
          type="number"
          min={2}
          max={64}
          value={viewDistance}
          onChange={(e) => setViewDistance(e.target.value)}
          placeholder="Por defecto"
        />
      </FormField>
    </FormDialog>
  )
}