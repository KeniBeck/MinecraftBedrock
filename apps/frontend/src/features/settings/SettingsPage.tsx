import { useMemo, useState } from 'react'
import { RotateCcw, Save, Settings2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { PixelCard } from '@/components/ui/pixel-card'
import { cn } from '@/lib/utils'
import { useCan } from '@/lib/auth/useCan'
import { usePatchSettings, useResetSetting, useSettings } from './hooks'
import { CATEGORY_LABELS, SETTING_CATEGORIES, groupByCategory } from './types'
import type { PanelSetting } from './types'

function formatValue(setting: PanelSetting): string {
  const value = setting.value
  if (typeof value === 'boolean') return String(value)
  if (value === null || value === undefined) return ''
  return String(value)
}

function coerce(setting: PanelSetting, raw: string): unknown {
  if (raw === '') return setting.default
  switch (setting.type) {
    case 'int':
      return Number.parseInt(raw, 10)
    case 'float':
      return Number.parseFloat(raw)
    case 'bool':
      return raw === 'true'
    default:
      return raw
  }
}

/**
 * Fila editable de un ajuste: input según el tipo del catálogo (bool → checkbox,
 * int/float → number, str/path → texto) + botón reset (solo con `settings.update`).
 */
function SettingRow({
  setting,
  value,
  onChange,
  disabled,
  onReset,
  resetting,
}: {
  setting: PanelSetting
  value: string
  onChange: (raw: string) => void
  disabled: boolean
  onReset: () => void
  resetting: boolean
}) {
  const isBool = setting.type === 'bool'
  const isNumber = setting.type === 'int' || setting.type === 'float'
  const checked = value === 'true'

  return (
    <div className="flex items-center gap-3 py-2">
      <div className="min-w-0 flex-1">
        <p className="font-mono text-xs text-slate-200">{setting.key}</p>
        {setting.description && (
          <p className="mt-0.5 text-xs text-slate-400">{setting.description}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {isBool ? (
          <input
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={(event) => onChange(String(event.target.checked))}
            aria-label={setting.key}
            className="size-4 accent-emerald-500 disabled:opacity-50"
          />
        ) : (
          <input
            type={isNumber ? 'number' : 'text'}
            value={value}
            disabled={disabled}
            onChange={(event) => onChange(event.target.value)}
            aria-label={setting.key}
            className={cn(
              'w-40 rounded-md border border-white/10 bg-slate-900/70 px-2 py-1 text-sm text-slate-100',
              'disabled:cursor-not-allowed disabled:opacity-50 focus:border-emerald-400 focus:outline-none',
            )}
          />
        )}

        <Button
          variant="outline"
          size="sm"
          pixel
          disabled={disabled || resetting}
          onClick={onReset}
          aria-label={`Resetear ${setting.key}`}
          title="Resetear al valor por defecto"
        >
          <RotateCcw className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}

/**
 * Ajustes globales del panel (`/admin/settings`), desde los endpoints reales
 * del backend `settings` (`GET /settings`, `PATCH /settings`,
 * `DELETE /settings/{key}`). Lectura con `settings.view` (viewer+); la
 * edición/reset requiere `settings.update` (solo admin/super_admin). Agrupados
 * por categoría del catálogo (storage, limits, defaults, system).
 */
export function SettingsPage() {
  const canView = useCan('settings.view')
  const canUpdate = useCan('settings.update')
  const { data } = useSettings()
  const patch = usePatchSettings()
  const reset = useResetSetting()

  // Estado local de edición por clave (coercido a string para los inputs).
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [feedback, setFeedback] = useState<string | null>(null)

  const settings = useMemo(() => data?.settings ?? [], [data])
  const byCategory = useMemo(() => groupByCategory(settings), [settings])

  if (!canView) {
    return (
      <div
        role="alert"
        className="rounded-none border-2 border-red-500/40 bg-red-500/10 px-4 py-6 text-sm text-red-300 shadow-[inset_2px_2px_0_rgba(0,0,0,.3)]"
      >
        No tienes permisos para ver la configuración del panel.
      </div>
    )
  }

  if (settings.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        Cargando ajustes del panel…
      </div>
    )
  }

  const dirtyKeys = (catSettings: PanelSetting[]) =>
    catSettings.filter((setting) => drafts[setting.key] !== formatValue(setting))

  async function saveCategory(cat: string) {
    const catSettings = byCategory[cat] ?? []
    const dirty = dirtyKeys(catSettings)
    if (dirty.length === 0) return
    const values: Record<string, unknown> = {}
    for (const setting of dirty) {
      values[setting.key] = coerce(setting, drafts[setting.key] ?? formatValue(setting))
    }
    try {
      await patch.mutateAsync(values)
      setDrafts((current) => {
        const next = { ...current }
        for (const setting of dirty) {
          if (setting.key in next) delete next[setting.key]
        }
        return next
      })
      setFeedback(`Ajustes de "${CATEGORY_LABELS[cat as keyof typeof CATEGORY_LABELS] ?? cat}" guardados.`)
    } catch {
      setFeedback('No se pudo guardar. Revisa permisos o inténtalo de nuevo.')
    }
  }

  async function handleReset(setting: PanelSetting) {
    try {
      await reset.mutateAsync(setting.key)
      setDrafts((current) => {
        const next = { ...current }
        delete next[setting.key]
        return next
      })
    } catch {
      setFeedback(`No se pudo resetear "${setting.key}".`)
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="flex items-center gap-2 text-xl font-bold">
          <Settings2 className="h-5 w-5 text-slate-300" />
          Configuración del panel
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Ajustes globales del panel (almacenamiento, límites, valores por defecto y sistema).
        </p>
      </header>

      {feedback && (
        <div
          role="status"
          className="rounded-none border-2 border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300"
        >
          {feedback}
        </div>
      )}

      {SETTING_CATEGORIES.map((cat) => {
        const catSettings = byCategory[cat] ?? []
        if (catSettings.length === 0) return null
        const dirty = dirtyKeys(catSettings)
        return (
          <PixelCard noHover key={cat} className="flex-col items-stretch p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-100">
                {CATEGORY_LABELS[cat]}
              </h2>
              {canUpdate && (
                <Button
                  variant="create"
                  size="sm"
                  pixel
                  disabled={dirty.length === 0 || patch.isPending}
                  onClick={() => void saveCategory(cat)}
                  data-testid={`save-${cat}`}
                >
                  <Save className="size-3.5" />
                  Guardar{dirty.length > 0 ? ` (${dirty.length})` : ''}
                </Button>
              )}
            </div>
            <div className="divide-y divide-white/5">
              {catSettings.map((setting) => (
                <SettingRow
                  key={setting.key}
                  setting={setting}
                  value={drafts[setting.key] ?? formatValue(setting)}
                  onChange={(raw) =>
                    setDrafts((current) => ({ ...current, [setting.key]: raw }))
                  }
                  disabled={!canUpdate}
                  onReset={() => void handleReset(setting)}
                  resetting={reset.isPending}
                />
              ))}
            </div>
          </PixelCard>
        )
      })}
    </div>
  )
}
