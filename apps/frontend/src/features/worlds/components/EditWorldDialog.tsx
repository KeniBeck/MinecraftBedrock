import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getApiMessage } from '@/lib/api/client'
import { cn } from '@/lib/utils'
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

const selectClass = cn(
  'h-10 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm transition-colors',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
  'disabled:cursor-not-allowed disabled:opacity-50',
  '[&>option]:bg-slate-900 [&>option]:text-slate-100',
)

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="edit-world-name">Nombre del mundo</Label>
        <Input
          id="edit-world-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={64}
        />
      </div>
      <div>
        <Label htmlFor="edit-world-seed">Semilla (opcional)</Label>
        <Input
          id="edit-world-seed"
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          maxLength={64}
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Solo se aplica al generar un mundo nuevo; no regenera uno existente.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="edit-world-gamemode">Modo de juego</Label>
          <select
            id="edit-world-gamemode"
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
          <Label htmlFor="edit-world-difficulty">Dificultad</Label>
          <select
            id="edit-world-difficulty"
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
        <Label htmlFor="edit-world-view-distance">Distancia de chunks (2–64)</Label>
        <Input
          id="edit-world-view-distance"
          type="number"
          min={2}
          max={64}
          value={viewDistance}
          onChange={(e) => setViewDistance(e.target.value)}
        />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" variant="create" pixel disabled={update.isPending}>
          {update.isPending ? 'Guardando…' : 'Guardar'}
        </Button>
      </div>
    </form>
  )
}

export function EditWorldDialog({ open, onOpenChange, serverId, world }: EditWorldDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ajustar mundo</DialogTitle>
        </DialogHeader>
        {world && (
          <EditWorldForm
            key={world.id}
            serverId={serverId}
            world={world}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
