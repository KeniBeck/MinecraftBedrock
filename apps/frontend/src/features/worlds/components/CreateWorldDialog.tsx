import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getApiMessage } from '@/lib/api/client'
import { cn } from '@/lib/utils'

import { useCreateWorld } from '../hooks'
import type { CreateWorldRequest } from '@/lib/api/worlds'

interface CreateWorldDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  serverId: string
}

const GAMEMODES = ['survival', 'creative', 'adventure'] as const
const DIFFICULTIES = ['peaceful', 'easy', 'normal', 'hard'] as const

const selectClass = cn(
  'h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
  'disabled:cursor-not-allowed disabled:opacity-50',
  '[&>option]:bg-slate-900 [&>option]:text-slate-100',
)

export function CreateWorldDialog({ open, onOpenChange, serverId }: CreateWorldDialogProps) {
  const [name, setName] = useState('')
  const [seed, setSeed] = useState('')
  const [gamemode, setGamemode] = useState<string>('')
  const [difficulty, setDifficulty] = useState<string>('')
  const [viewDistance, setViewDistance] = useState('')
  const [error, setError] = useState<string | null>(null)
  const create = useCreateWorld(serverId)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Crear mundo</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="world-name">Nombre del mundo</Label>
            <Input
              id="world-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Mi mundo"
              required
              maxLength={64}
            />
          </div>
          <div>
            <Label htmlFor="world-seed">Semilla (opcional)</Label>
            <Input
              id="world-seed"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              placeholder="Deja vacío para una semilla aleatoria"
              maxLength={64}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="world-gamemode">Modo de juego</Label>
              <select
                id="world-gamemode"
                value={gamemode}
                onChange={(e) => setGamemode(e.target.value)}
                className={selectClass}
              >
                <option value="">Por defecto</option>
                {GAMEMODES.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="world-difficulty">Dificultad</Label>
              <select
                id="world-difficulty"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                className={selectClass}
              >
                <option value="">Por defecto</option>
                {DIFFICULTIES.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <Label htmlFor="world-view-distance">Distancia de chunks (2–64)</Label>
            <Input
              id="world-view-distance"
              type="number"
              min={2}
              max={64}
              value={viewDistance}
              onChange={(e) => setViewDistance(e.target.value)}
              placeholder="Por defecto"
            />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" variant="create" pixel disabled={create.isPending}>
              {create.isPending ? 'Creando…' : 'Crear'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
