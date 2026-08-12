import { cn } from '@/lib/utils'
import { TIME_RANGES, type TimeRangeId } from '../hooks'

interface TimeRangeSelectorProps {
  value: TimeRangeId
  onChange: (range: TimeRangeId) => void
}

/** Selector de rango temporal: botones pixelados 15m/1h/6h/24h/7d. */
export function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label="Rango temporal">
      {TIME_RANGES.map((range) => (
        <button
          key={range.id}
          type="button"
          onClick={() => onChange(range.id)}
          aria-pressed={value === range.id}
          className={cn(
            'rounded-none border border-black px-3 py-1.5 text-sm font-semibold transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            value === range.id
              ? 'bg-emerald-600 text-white shadow-[inset_1px_1px_0_rgba(255,255,255,.2),inset_-1px_-1px_0_rgba(0,0,0,.4)]'
              : 'bg-slate-800/80 text-slate-300 hover:bg-white/10 hover:text-white',
          )}
        >
          {range.label}
        </button>
      ))}
    </div>
  )
}
