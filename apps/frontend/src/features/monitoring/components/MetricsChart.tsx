import { useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { cn } from '@/lib/utils'
import type { MetricSample } from '@/stores/monitoring'

type SeriesKey = 'cpu' | 'ram_mb' | 'players' | 'disk_mb'

interface SeriesDef {
  key: SeriesKey
  label: string
  color: string
  /** Formatea el valor del tooltip/eje. */
  format: (value: number) => string
}

const SERIES: SeriesDef[] = [
  { key: 'cpu', label: 'CPU', color: '#22d3ee', format: (v) => `${v.toFixed(1)} %` },
  { key: 'ram_mb', label: 'RAM', color: '#a78bfa', format: (v) => `${v.toFixed(0)} MB` },
  { key: 'players', label: 'Jugadores', color: '#34d399', format: (v) => `${v.toFixed(0)}` },
  { key: 'disk_mb', label: 'Disco', color: '#fb923c', format: (v) => `${v.toFixed(0)} MB` },
]

const DEFAULT_VISIBLE: SeriesKey[] = ['cpu', 'ram_mb', 'players']

/** Ticks del eje X cada ~6 muestras (evita saturar la etiqueta). */
function tickEvery(dataLength: number): number {
  if (dataLength <= 20) return 1
  return Math.ceil(dataLength / 8)
}

interface MetricsChartProps {
  data: MetricSample[]
  height?: number
}

/**
 * Gráfico de área con Recharts (tema oscuro, gradiente) de las métricas en
 * vivo del WS de monitoreo. Cada serie se puede ocultar/mostrar con un toggle;
 * solo se dibujan las visibles. Los valores nulos (servidor apagado) se filtran
 * para que el área no se rompa.
 */
export function MetricsChart({ data, height = 320 }: MetricsChartProps) {
  const [visible, setVisible] = useState<SeriesKey[]>(DEFAULT_VISIBLE)

  const toggle = (key: SeriesKey) => {
    setVisible((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  if (data.length === 0) {
    return (
      <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">
        Esperando datos del servidor…
      </div>
    )
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-2">
        {SERIES.map((s) => {
          const on = visible.includes(s.key)
          return (
            <button
              key={s.key}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(s.key)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-none border px-2.5 py-1 text-xs font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                on
                  ? 'border-white/20 bg-white/10 text-slate-100'
                  : 'border-white/10 bg-transparent text-slate-500',
              )}
            >
              <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: s.color }} />
              {s.label}
            </button>
          )
        })}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 8, left: 0, bottom: 0 }}>
          <defs>
            {SERIES.map((s) => (
              <linearGradient key={s.key} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.4} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke="#ffffff14" strokeDasharray="3 3" />
          <XAxis
            dataKey="ts"
            tickFormatter={(ts: string) => new Date(ts).toLocaleTimeString()}
            tick={{ fill: '#64748b', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            minTickGap={40}
            interval={tickEvery(data.length)}
          />
          <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} width={44} />
          <Tooltip
            labelFormatter={(ts) => (typeof ts === 'string' ? new Date(ts).toLocaleString() : String(ts))}
            contentStyle={{
              backgroundColor: '#0f172a',
              border: '1px solid #ffffff22',
              borderRadius: 0,
              fontSize: 12,
            }}
            labelStyle={{ color: '#cbd5e1' }}
          />
          {visible.includes('cpu') && (
            <Area
              type="monotone"
              dataKey="cpu"
              name="CPU"
              stroke="#22d3ee"
              strokeWidth={2}
              fill="url(#grad-cpu)"
              connectNulls={false}
            />
          )}
          {visible.includes('ram_mb') && (
            <Area
              type="monotone"
              dataKey="ram_mb"
              name="RAM"
              stroke="#a78bfa"
              strokeWidth={2}
              fill="url(#grad-ram_mb)"
              connectNulls={false}
            />
          )}
          {visible.includes('players') && (
            <Area
              type="monotone"
              dataKey="players"
              name="Jugadores"
              stroke="#34d399"
              strokeWidth={2}
              fill="url(#grad-players)"
              connectNulls={false}
            />
          )}
          {visible.includes('disk_mb') && (
            <Area
              type="monotone"
              dataKey="disk_mb"
              name="Disco"
              stroke="#fb923c"
              strokeWidth={2}
              fill="url(#grad-disk_mb)"
              connectNulls={false}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
