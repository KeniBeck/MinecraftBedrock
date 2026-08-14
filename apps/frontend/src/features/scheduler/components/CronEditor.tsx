import { useState } from 'react'

import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import {
  buildCronFromParts,
  CRON_PART_LABELS,
  CRON_PRESETS,
  describeCron,
  isValidCron,
  parseCronToParts,
  type CronParts,
} from '../cron'

interface CronEditorProps {
  value: string
  onChange: (cron: string) => void
}

const PART_WIDTHS: ReadonlyArray<string> = ['w-14', 'w-14', 'w-14', 'w-14', 'w-16']

/**
 * Editor de programación cron amigable y compacto: presets, cinco selectores
 * desglosados en línea con wrap, lector del cron generado con su descripción
 * y un toggle "Avanzado" para edición manual. Se remonta con `key` desde el
 * diálogo padre para refrescar la carga (evita `setState` en `useEffect`).
 */
export function CronEditor({ value, onChange }: CronEditorProps) {
  const [manual, setManual] = useState(!isValidCron(value))
  const [parts, setParts] = useState<CronParts>(parseCronToParts(value))
  const [manualText, setManualText] = useState(value)

  const generated = buildCronFromParts(parts)
  const cronValue = manual ? manualText : generated
  const description = describeCron(cronValue)

  function applyParts(next: CronParts) {
    setParts(next)
    onChange(buildCronFromParts(next))
  }

  function handlePartChange(index: number, partValue: string) {
    const next: CronParts = [...parts]
    next[index] = partValue
    applyParts(next)
  }

  function enableSelectors() {
    const parsed = parseCronToParts(manualText)
    if (!isValidCron(buildCronFromParts(parsed))) return
    setParts(parsed)
    setManual(false)
    onChange(buildCronFromParts(parsed))
  }

  function enableManual() {
    setManualText(generated)
    setManual(true)
  }

  return (
    <div className="space-y-2">
      {/* Presets: botones compactos en línea con wrap. */}
      <div className="flex flex-wrap gap-1.5">
        {CRON_PRESETS.map((preset) => (
          <Button
            key={preset.cron}
            type="button"
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => applyParts(parseCronToParts(preset.cron))}
          >
            {preset.label}
          </Button>
        ))}
      </div>

      {manual ? (
        <Input
          value={manualText}
          onChange={(e) => {
            setManualText(e.target.value)
            onChange(e.target.value)
          }}
          placeholder="* * * * *"
          className="font-mono text-sm"
          aria-label="Expresión cron"
        />
      ) : (
        // Selectores desglosados: en línea con wrap y etiquetas cortas.
        <div className="flex flex-wrap items-end gap-2">
          {CRON_PART_LABELS.map((part, i) => (
            <div key={part.label} className="flex flex-col items-center gap-1">
              <label
                htmlFor={`cron-part-${i}`}
                className="text-[10px] uppercase tracking-wide text-muted-foreground"
              >
                {part.label}
              </label>
              <Select
                id={`cron-part-${i}`}
                value={parts[i]}
                onChange={(e) => handlePartChange(i, e.target.value)}
                className={`h-8 ${PART_WIDTHS[i]} px-1 text-xs`}
              >
                <option value="*">*</option>
                {Array.from({ length: part.max - part.min + 1 }, (_, j) => part.min + j).map(
                  (n) => (
                    <option key={n} value={String(n)}>
                      {n}
                    </option>
                  ),
                )}
              </Select>
            </div>
          ))}
        </div>
      )}

      {/* Lector + descripción + toggle avanzado en una línea. */}
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-white/10 bg-black/30 px-3 py-1.5">
        <code className="flex-1 font-mono text-xs text-emerald-300">{cronValue}</code>
        <span className="text-xs text-muted-foreground">
          {description ?? 'Expresión avanzada'}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="ml-auto h-6 px-2 text-[11px]"
          onClick={manual ? enableSelectors : enableManual}
        >
          {manual ? 'Usar selectores' : 'Avanzado'}
        </Button>
      </div>
    </div>
  )
}